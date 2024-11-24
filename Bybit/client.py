import pandas as pd
import sys
import os

# Custom imports
from utils import format_volume
from apiFetcher import bybitFetcher
from analyser import bybitAnalyser


class BybitClient:
    __slots__ = ["fetcher", "analyser"]

    def __init__(self, demo=False):
        """
        Initialize the Bybit fetcher
        """
        self.fetcher = bybitFetcher(demo=demo)

        # Just to reference the methods for the analyser
        self.analyser = bybitAnalyser

    def all_gaps_pd(self, pretty=True, inverse=False, perpetual=False, spot=False):
        """
        Get all the gaps for all the future contracts

        Careful: All flags should not be activated at the same time
        Args:
            pretty (bool): will format the elements in a more readable way
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
                gap = bybitAnalyser.get_gap(longTicker, shortTicker)
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

    def position_calculator(self, contract, side, quantityUSDC, leverage=1):
        """
        Checks information about a position before entering it
        User submits a USDC quantity, and we calculate the amount of contracts to buy/sell
        The calculations are based on the Bybit documentation, but they will never be 100% accurate

        Args:
            contract (str): The future contract to get the history from
            side (str): The side of the position (buy/sell)
            quantityUSDC (float): The quantity in USDC
            leverage (int): The leverage to use
        Returns:
            dict: The position information
        """
        # Get the tickers
        ticker = self.fetcher.session.get_tickers(symbol=contract, category="linear")["result"]["list"][0]
        return bybitAnalyser.position_calculator(ticker, side, quantityUSDC, leverage)

    async def perp_future_arbitrage(self, longContract, shortContract, quantityUSDC):
        """
        Given two contracts, calculate the quantity of contracts to buy/sell and enter.
        Finally, enter an arbitrage position. The leverage is already set.

        We suppose that the conditions are met for the arbitrage.


        This function is dedicated to contracts, but it could also be spot

        Args:
            longContract (str): The long contract
            shortContract (str): The short contract
            quantityUSDC (float): The quantity in USDC
            leverage (int): The leverage to use
        Returns:
            dict: The response from the API
        """

        return True
