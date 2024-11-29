import logging
import sys
import pandas as pd

from client import BybitClient
from analyser import bybitAnalyser
from utils import format_volume


class GreekMaster:
    __slots__ = ["client", "fetcher", "contracts", "logger"]

    def __init__(self, demo=False, verbose=0):
        """
        Logic for all products.
        Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry.
        Talks to Bybit through the client.
        Can send notifications and logs arbitrage events.

        GreekMaster is supposed to live forever. Context will be stopped here, not in main.

        client (BybitClient): Client for the Bybit API
        fetcher (bybitFetcher): Fetcher for the Bybit API
        contracts (list): List of all the current contracts
        logger (logging.Logger): Logger for the client

        """
        self.client = BybitClient(demo=demo)

        # Just for easy reference
        self.fetcher = self.client.fetcher

        self.contracts = {}

        # Set up logger here (not using basicConfig inside init)
        self.logger = logging.getLogger(__name__)

        if verbose:
            # Create a StreamHandler to output logs to console
            console_handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "\033[36m%(asctime)s\033[0m - %(name)s - \033[33m%(levelname)s\033[0m - %(message)s"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # Add the handler to the logger and set the level
            if verbose == 1:
                self.logger.setLevel(logging.INFO)
            else:
                self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.WARNING)  # Default to WARNING if not verbose

        self.logger.info("GreekMaster initialized")

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

    # TODO: callables should be a pydantic object to reference the existing strategies
    async def one_shot_PF(self, strategy: callable, quantityUSDC: float, leverage=1):
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
            leverage (int): The leverage to use
        """
        pass

    async def stay_alive_SF(self, quantityUSDC: float):
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
        """
        pass
