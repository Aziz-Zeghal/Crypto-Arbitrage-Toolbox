import pandas as pd
import sys
import os

# Custom imports
from utils import format_volume
from apiFetcher import bybitFetcher
from analyser import bybitAnalyser


class BybitClient:
    __slots__ = ["fetcher", "analyser"]

    def __init__(self):
        """
        Initialize the Bybit fetcher
        """
        self.fetcher = bybitFetcher()

        # Just to reference the methods for the analyser
        self.analyser = bybitAnalyser

    def all_gaps(self, pretty=True):
        """
        Get all the gaps for all the future contracts

        Args:
            pretty (bool): If True, will format the elements in a more readable way
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """

        btcFutureContracts = self.fetcher.get_futures("BTC")
        btcTickers = []
        # First, get the tickers of every future contract
        for future in btcFutureContracts:
            btcTickers.append(self.fetcher.session.get_tickers(symbol=future, category="linear")["result"]["list"][0])

        # Now, we can calculate the gaps
        rows = []
        for longTicker in btcTickers:
            # Take all futures after it
            for shortTicker in btcTickers[btcTickers.index(longTicker) + 1 :]:
                gap = bybitAnalyser.get_gap(longTicker, shortTicker)
                vol = int(gap["cumVolume"])
                if pretty:
                    rows.append(
                        {
                            "Buy": longTicker["symbol"],
                            "Sell": shortTicker["symbol"],
                            "Gap": f"$ {gap['gap']:.2f}",
                            "Coeff": f"{gap['coeff']:.2f} %",
                            "APR": f"{gap['apr']:.2f} %",
                            "DaysLeft": int(gap["daysLeft"]),
                            "CumVolume": format_volume(vol),
                        }
                    )
                else:
                    rows.append(
                        {
                            "Buy": longTicker["symbol"],
                            "Sell": shortTicker["symbol"],
                            "Gap": gap["gap"],
                            "Coeff": gap["coeff"],
                            "APR": gap["apr"],
                            "DaysLeft": gap["daysLeft"],
                            "CumVolume": gap["cumVolume"],
                        }
                    )

        gaps = pd.DataFrame(rows)
        return gaps

    def all_gaps_pd(self, pretty=True, inverse=False, perpetual=False):
        """
        Get all the gaps for all the future contracts

        Args:
            pretty (bool): will format the elements in a more readable way
            inverse (bool): will get the inverse contracts
            perpetual (bool): will get the perpetual contracts
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """

        btcFutureContracts = self.fetcher.get_futures("BTC", inverse=inverse, perpetual=perpetual)

        # First, get the tickers of every future contract in a dataframe
        btcTickers = pd.DataFrame(
            [
                self.fetcher.session.get_tickers(symbol=future, category="linear")["result"]["list"][0]
                for future in btcFutureContracts
            ]
        )

        # Create an empty dataframe to store the result
        df_gaps = pd.DataFrame(columns=["Buy", "Sell", "Gap", "Coeff", "APR", "DaysLeft", "CumVolume"])

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
