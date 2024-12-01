import logging
import sys
import pandas as pd
import asyncio
from beartype import beartype
from typing import Callable

from client import BybitClient
from analyser import bybitAnalyser
from utils import format_volume, ColorFormatter


class GreekMaster:
    __slots__ = ["client", "fetcher", "contracts", "logger"]

    @beartype
    def __init__(self, demo=False, verbose=0):
        """
        Logic for all products.
        Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry.
        Talks to Bybit through the client.
        Can send notifications and logs arbitrage events.

        GreekMaster is supposed to live forever. Context will be stopped here, not in main.

        3 types of methods:
            - Strategies: Called by the executor
            - Executors: Setup application, then call the strategy
            - Callables: Reference to the existing strategies
        Defines:
            - client (BybitClient): Client for the Bybit API
            - fetcher (bybitFetcher): Fetcher for the Bybit API
            - contracts (list): List of all the current contracts
            - logger (logging.Logger): Logger for the client

        """
        self.client = BybitClient(demo=demo, verbose=verbose)

        # Just for easy reference
        self.fetcher = self.client.fetcher

        self.contracts = {}

        # Set up logger here (not using basicConfig inside init)
        self.logger = logging.getLogger("greekMaster")

        # Default to WARNING level
        log_level = logging.WARNING

        # Configure verbosity levels
        if verbose == 1:
            log_level = logging.INFO
        elif verbose >= 2:
            log_level = logging.DEBUG

        self.logger.setLevel(log_level)

        # Create a StreamHandler for console output
        console_handler = logging.StreamHandler(sys.stdout)
        formatter = ColorFormatter("\033[36m%(asctime)s\033[0m - %(name)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)

        # Add handler to the logger
        self.logger.addHandler(console_handler)

        self.logger.info("GreekMaster initialized")

    @beartype
    def all_gaps_pd(self, pretty=True, applyFees=False, inverse=False, perpetual=False, spot=False):
        """
        Get all the gaps for all the future contracts

        Careful: All flags should not be activated at the same time
        Args:
            pretty (bool): will format the elements in a more readable way
            applyFees (bool): will apply the fees (4 takers, 0.22%)
            inverse (bool): will get the inverse contracts
            perpetual (bool): will get the perpetual contracts
            spot (bool): will get the spot contracts
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """

        btcFutureContracts = self.fetcher.get_futureNames("BTC", inverse=inverse, perpetual=perpetual)

        # First, get the tickers of every future contract in a dataframe
        btcTickers = pd.DataFrame(
            [
                self.fetcher.session.get_tickers(symbol=future, category="linear")["result"]["list"][0]
                for future in btcFutureContracts
            ]
        )

        # Then the spot contracts (Take only USDT)
        if spot:
            response = self.fetcher.session.get_tickers(symbol="BTCUSDT", category="spot")["result"]["list"][0]
            # Put deliveryTime to 0
            response["deliveryTime"] = 0
            response["symbol"] = "BTCUSDT (Spot)"
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
            tasks.append(fetch_history(contract, "15"))
            tasks.append(fetch_history(contract, "5"))
            tasks.append(fetch_history(contract, "1"))

        # spot
        tasks.append(fetch_history("BTCUSDT", "15", category="spot"))
        tasks.append(fetch_history("BTCUSDT", "5", category="spot"))
        tasks.append(fetch_history("BTCUSDT", "1", category="spot"))

        # Perpetual contracts
        tasks.append(fetch_history("BTCUSDT", "15"))
        tasks.append(fetch_history("BTCUSDT", "5"))
        tasks.append(fetch_history("BTCUSDT", "1"))

        await asyncio.gather(*tasks)

    def CT_best_gap(self, perpetual=True, spot=False, maxDays: int = 25):
        """
        Find the best gap for a pair of contracts

        Args:
            perpetual (bool): will get the perpetual contracts
            spot (bool): will get the spot contracts
            maxDays (int): The maximum number of days left before delivery
        Returns:
            dict: The best gap
        """
        gaps = self.all_gaps_pd(inverse=False, perpetual=perpetual, pretty=False, applyFees=True, spot=spot)

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
    async def stay_alive_SF(self, quantityUSDC: float | int):
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
        """
        # Get best gap
        bestGap = self.CT_best_gap(perpetual=False, spot=True)

        # Invoke strategy
        try:
            await self.client.Ulysse(
                longContract=bestGap["Buy"],
                shortContract=bestGap["Sell"],
                strategy=self.client.check_arbitrage,
                quantityUSDC=quantityUSDC,
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise e
