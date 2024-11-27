import pandas as pd
import sys
import os

# Custom imports
from utils import format_volume
from apiFetcher import bybitFetcher
from analyser import bybitAnalyser


class BybitClient:
    __slots__ = ["fetcher", "analyser", "shared_data", "active"]

    def __init__(self, demo=False):
        """
        Initialize the Bybit fetcher

        fetcher (bybitFetcher): Fetcher for the Bybit API
        analyser (bybitAnalyser): Analyser for calculations
        shared_data (dict): Last message of the WebSocket (updated in real time)

        """
        self.fetcher = bybitFetcher(demo=demo)

        # Just to reference the methods for the analyser
        self.analyser = bybitAnalyser

        self.shared_data = {}

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

    def check_arbitrage(self, minimumGap):
        """
        Callback function for both products' channels

        Checks if conditions are met for the arbitrage.

        Args:
            quantityUSDC (float): The quantity in USDC
            minimumGap (float): The minimum gap to consider for the arbitrage
        Returns:
            None
        """

        # Check if the data is complete
        if "long" not in self.shared_data or "short" not in self.shared_data:
            return
        longTickers = self.shared_data["long"]["data"]
        shortTickers = self.shared_data["short"]["data"]

        # | Price of the future contract
        longPrice = float(longTickers["lastPrice"])
        shortPrice = float(shortTickers["lastPrice"])
        # - Calculate the gap
        coeff = (shortPrice / longPrice - 1) * 100
        print(f"Gap of: {coeff}%")
        # Check if the gap is enough
        if coeff >= minimumGap:
            print(f"Arbitrage opportunity found: {coeff}")

            self.client.ws.exit()

    # TODO: In the long run, this will be the strategy selector too
    async def Eris(self, longContract: str, shortContract: str, quantityUSDC: float, leverage=1, minimumGap=0.15):
        """
        The main executor, Eris

        Actions:
            - Initialize the Bybit client
            - Listen to the tickers with the websocket
            - Associate to callback functions

        Callback functions for both channels will check for the conditions of the arbitrage.

        Args:
            longContract (str): The long contract's name
            shortContract (str): The short contract's name
            quantityUSDC (float): The quantity in USDC
        Returns:
            dict: The response from the API
        """

        # Set the leverage
        await self.fetcher.set_leverage(longContract, leverage)
        await self.fetcher.set_leverage(shortContract, leverage)

        # Define handlers
        def short_handler(message):
            if not self.fetcher.ws.exited:
                self.shared_data["short"] = message

        # We position the arbitrage here, because more messages
        def long_handler(message):
            if not self.fetcher.ws.exited:
                self.shared_data["long"] = message
                self.check_arbitrage(minimumGap=minimumGap)

        # Listen to channels
        self.fetcher.ws.ticker_stream(symbol=shortContract, callback=short_handler)
        self.fetcher.ws.ticker_stream(symbol=longContract, callback=long_handler)

        # Now, hold the program
        while not self.fetcher.ws.exited:
            pass

        # Either arbitrage found or something bad happened
        # TODO: Need to be sure of arbitrage (boolean or better solution)

        longTickers = self.shared_data["long"]["data"]
        shortTickers = self.shared_data["short"]["data"]
        # Calculate the position
        longPosition = self.position_calculator(longTickers["symbol"], "Buy", quantityUSDC)
        shortPosition = self.position_calculator(shortTickers["symbol"], "Sell", quantityUSDC)
        # Open the positions
        await self.fetcher.enter_both_position(
            longContract, shortContract, longPosition["quantityContracts"], shortPosition["quantityContracts"]
        )

        print("For " + longContract + ":")
        print(longPosition)
        print("For " + shortContract + ":")
        print(shortPosition)

        print("Last messages:")
        print(self.shared_data)

        sys.exit(0)
