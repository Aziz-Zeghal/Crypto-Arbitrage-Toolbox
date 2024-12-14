import logging
import pandas as pd
import asyncio
import schedule as sch
from beartype import beartype
from typing import Callable

from client import BybitClient
from analyser import bybitAnalyser
from utils import format_volume


class GreekMaster:
    __slots__ = ["client", "fetcher", "logger", "position_info"]

    @beartype
    def __init__(self, demo=False):
        """
        Logic for all products.
        Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry.
        Talks to Bybit through the client.
        Can send notifications and logs arbitrage events.

        GreekMaster is supposed to live forever. Context will be stopped here, not in main.

        3 types of methods:
            - Selectors: The method to choose the best pair of contracts
            - Strategies: Called by the executor
            - Executors: Setup application, then call the strategy, monitor then repeat
        Defines:
            - client (BybitClient): Client for the Bybit API
            - fetcher (bybitFetcher): Fetcher for the Bybit API
            - contracts (list): List of all the current contracts
            - logger (logging.Logger): Logger for the client
            - position_info: Dictionnary with live updates

        """
        self.client = BybitClient(demo=demo)

        # Just for easy reference
        self.fetcher = self.client.fetcher

        self.position_info = {}

        self.logger = logging.getLogger("greekMaster")

        self.logger.info("GreekMaster initialized")

    # TODO: Does not fetch in parallel. Should be done in parallel
    @beartype
    async def save_klines(self, dest: str):
        """
        Save the klines of all the future contracts in parquet format
        Checks if a parquet file exists to update it, else creates a new one

        Args:
            dest (str): The destination folder
        """
        allContracts = self.client.fetcher.get_futureNames()

        async def fetch_history(contract, interval, category="linear"):
            await self.client.fetcher.get_history_pd(
                contract, interval=interval, dest=dest, dateLimit="2024-01-01 00:00", category=category
            )

        tasks = []

        for contract in allContracts:
            tasks.extend([fetch_history(contract, "15"), fetch_history(contract, "5"), fetch_history(contract, "1")])

        # spot
        tasks.extend(
            [
                fetch_history("BTCUSDT", "15", category="spot"),
                fetch_history("BTCUSDT", "5", category="spot"),
                fetch_history("BTCUSDT", "1", category="spot"),
            ]
        )

        # Perpetual contracts
        tasks.extend(
            [
                fetch_history("BTCUSDT", "15"),
                fetch_history("BTCUSDT", "5"),
                fetch_history("BTCUSDT", "1"),
                fetch_history("BTCPERP", "15"),
                fetch_history("BTCPERP", "5"),
                fetch_history("BTCPERP", "1"),
            ]
        )

        await asyncio.gather(*tasks)

    def monitor(self):
        """
        Monitor the accounts, check the positions, the liquidation risk, etc.

        Writes inside position_info

        """
        self.logger.info("Monitoring the account")

    # TODO: boolean for future, and upgrade function
    @beartype
    def all_gaps_pd(
        self,
        pretty=True,
        applyFees=False,
        inverse=False,
        perpetual=False,
        spot=False,
        quoteCoins: list[str] = ["USDC", "USDT", "USD"],
    ):
        """
        Get all the gaps for multiple products in a DataFrame

        Careful: All flags should not be activated at the same time
        Args:
            pretty (bool): will format the elements in a more readable way
            applyFees (bool): will apply the fees (4 takers, 0.22%)
            inverse (bool): will get the inverse contracts
            perpetual (bool): will get the perpetual contracts
            spot (bool): will get the spot contracts
            quoteCoins (list[str]): The quote coins to consider. Can be ["USDC", "USDT"]
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """

        # WARNING: No perpetual with USDT, so remove it here
        btcFutureContracts = self.fetcher.get_futureNames(
            "BTC", inverse=inverse, perpetual=perpetual, quoteCoins=quoteCoins
        )

        # First, get the tickers of every future contract in a dataframe
        btcTickers = pd.DataFrame(
            [
                self.fetcher.session.get_tickers(symbol=future, category="linear")["result"]["list"][0]
                for future in btcFutureContracts
            ]
        )

        # Then the spot contracts (Take only USDT)
        if spot:
            if "USDT" in quoteCoins:
                response = self.fetcher.session.get_tickers(symbol="BTCUSDT", category="spot")["result"]["list"][0]
                # Put deliveryTime to 0
                response["deliveryTime"] = 0
                response["symbol"] = "BTCUSDT (Spot)"
                btcTickers = pd.concat([pd.DataFrame([response]), btcTickers], ignore_index=True)

            if "USDC" in quoteCoins:
                response = self.fetcher.session.get_tickers(symbol="BTCUSDC", category="spot")["result"]["list"][0]
                # Put deliveryTime to 0
                response["deliveryTime"] = 0
                response["symbol"] = "BTCUSDC (Spot)"
                btcTickers = pd.concat([pd.DataFrame([response]), btcTickers], ignore_index=True)

        # Define an empty DataFrame with specified columns and data types
        column_types = {
            "Buy": "string",
            "Sell": "string",
            "Gap": "float" if not pretty else "string",
            "Coeff": "float" if not pretty else "string",
            "APR": "float" if not pretty else "string",
            "DaysLeft": "int",
            "CumVolume": "int" if not pretty else "string",
        }

        # Create an empty DataFrame with the specified columns
        df_gaps = pd.DataFrame(columns=column_types.keys()).astype(column_types)

        # Now, we can calculate the gaps
        for i, longTicker in btcTickers.iterrows():
            # Take all futures after the current one
            for j, shortTicker in btcTickers.iloc[i + 1 :].iterrows():
                gap = bybitAnalyser.get_gap(longTicker, shortTicker, applyFees)
                vol = int(gap["cumVolume"])

                # Prepare the row data
                row = {
                    "Buy": longTicker["symbol"],
                    "Sell": shortTicker["symbol"],
                    "Gap": f"$ {gap['gap']:.2f}" if pretty else gap["gap"],
                    "Coeff": f"{gap['coeff']:.2f} %" if pretty else gap["coeff"],
                    "APR": f"{gap['apr']:.2f} %" if pretty else gap["apr"],
                    "DaysLeft": int(gap["daysLeft"]),
                    "CumVolume": format_volume(vol) if pretty else gap["cumVolume"],
                }

                df_gaps = pd.concat([df_gaps, pd.DataFrame([row])], ignore_index=True)

        df_gaps = df_gaps.astype(column_types)
        return df_gaps

    def CT_best_gap(self, perpetual=True, spot=False, maxDays: int = 25, quoteCoins: list[str] = ["USDC"]):
        """
        Find the best gap for a pair of contracts

        Args:
            perpetual (bool): will get the perpetual contracts
            spot (bool): will get the spot contracts
            maxDays (int): The maximum number of days left before delivery
            quoteCoins (list[str]): The quote coins to consider
        Returns:
            dict: The best gap
        """
        gaps = self.all_gaps_pd(
            inverse=False, perpetual=perpetual, pretty=False, applyFees=True, spot=spot, quoteCoins=quoteCoins
        )

        # TODO: This filtering should be in all_gaps_pd
        if spot:
            # Keep only the spot contracts
            gaps = gaps.loc[gaps["Buy"].str.contains("Spot")]

        # Buy should have USDC or PERP inside it
        # TODO will remove this as soon as all_gaps_pd is updated
        gaps = gaps.loc[gaps["Buy"].str.contains("USDT|USDC|PERP")]
        # Keep the positive coeffs
        gaps = gaps.loc[gaps["Coeff"] > 0]

        # Take the best proportion (short time, good gap)
        gaps = gaps.loc[gaps["DaysLeft"] < maxDays]
        bestGap = gaps.loc[gaps["Coeff"].idxmax()]

        self.logger.info(f"Best gap\n{bestGap}")

        return bestGap

    # TODO: callables should be a pydantic object to reference the existing strategies
    @beartype
    async def one_shot_PF(self, strategy: Callable, quantityUSDC: float | int, leverage: str = "1"):
        """
        One shot strategy with perpetual and future contracts

        Steps:
            - Finds the best pair of contracts for the strategy
            - Calls the client to enter the position
            - Writes the position in our books
            - Wait for gap on other side
            - Cashout
            - Repeat.

        Args:
            strategy (callable): The strategy to use
            quantityUSDC (float): The quantity in USDC
            leverage (str): The leverage to use, default is "1"
        """

        # Get best gap
        bestGap = self.CT_best_gap(perpetual=True, spot=False)

        self.logger.info(f"Starting {strategy.__name__} with {quantityUSDC} USDC and {leverage}x leverage")
        # Invoke strategy
        try:
            resp = await self.client.Ulysse(
                longContract=bestGap["Buy"],
                shortContract=bestGap["Sell"],
                strategy=strategy,
                quantityUSDC=quantityUSDC,
                leverage=leverage,
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise e

        self.logger.info(f"\nLong: {resp['long']}\nShort: {resp['short']}")

    @beartype
    async def stay_alive_SF(self, collateral: str = "USDC", quantityUSDC: float | int = 1000):
        """
        The classic strategy !
        Buy the spot, short the future.

        Client will be executed once.
        Will set a schedule a monitoring loop every day
        This will check the gap, liquidation risk etc.

        Once scheduler reaches the delivery day, it will cashout the position and start again

        Steps:
            - Find the best pair of contracts
            - Calls the client to enter the position
            - Writes the position in our books
            - Wait for the delivery day
            - Cashout
            - Repeat.

        Args:
            quantityUSDC (float): The quantity in USDC
            collateral (str): The collateral to use, either "USDC" or "USDT
        """

        # Clear the schedule
        sch.clear()

        # Get best gap
        bestGap = self.CT_best_gap(perpetual=False, spot=True, quoteCoins=[collateral])

        # Invoke strategy
        try:
            resp = await self.client.Ulysse_spot(
                longContract=bestGap["Buy"],
                shortContract=bestGap["Sell"],
                strategy=self.client.check_arbitrage,
                quantityUSDC=quantityUSDC,
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise e

        self.logger.info(f"\nLong: {resp['long']}\nShort: {resp['short']}")

        self.logger.info("Now we wait...")

        # Monitor the position (write perceived position, compare with real position, log)

        # Schedule the monitoring loop (every day, check delta, liquidation risk, etc.)
        sch.every().day.at("12:00").do(self.monitor)

        # Schedule the delivery day (cashout, write the position in the books, etc.)
        sch.every().day.at("21:00").do(lambda: self.client.fetcher.exit_double_linear(resp["long"], resp["short"]))
        # Repeat by calling this function
