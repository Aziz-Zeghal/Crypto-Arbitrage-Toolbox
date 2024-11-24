from pybit.unified_trading import HTTP, WebSocket
from datetime import datetime
import sys
import os
import pandas as pd
import asyncio

# Custom imports
sys.path.append(os.path.dirname(os.path.abspath("keys.py")))
from utils import save_klines_parquet, get_epoch, load_klines_parquet, save_data, load_data
import keys


class bybitFetcher:
    __slots__ = ["session", "ws"]

    def __init__(self, demo=False):
        """
        Initialize the Bybit session
        """
        if demo:
            self.session = HTTP(api_key=keys.demobybitPKey, api_secret=keys.demobybitSKey, demo=True)
        else:
            self.session = HTTP(api_key=keys.bybitPKey, api_secret=keys.bybitSKey)

        self.ws = WebSocket(
            api_key=keys.demobybitPKey, api_secret=keys.demobybitSKey, testnet=False, channel_type="linear"
        )

    def get_USDC_BTC(self):
        """
        Gives some information on USDC and BTC

        Link: https://bybit-exchange.github.io/docs/v5/account/wallet-balance
        Returns:
            dict:
                Balance: Total balance in USD
                BTC: dict:
                    Quantity: Quantity of BTC
                    Available: Available to withdraw
                    usdValue: Value in USD
                USDC: dict:
                    Quantity: Quantity of USDC
                    Available: Available to withdraw
                    usdValue: Value in USD
        """
        btcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="BTC")["result"]["list"][0]
        usdcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDC")["result"]["list"][0]

        totalBalance = btcDict["totalEquity"]

        # Just to make the code more readable
        btcDict = btcDict["coin"][0]
        usdcDict = usdcDict["coin"][0]

        btcValue = {
            "Quantity": btcDict["equity"],
            "Available": btcDict["availableToWithdraw"],
            "usdValue": btcDict["usdValue"],
        }

        usdcValue = {
            "Quantity": usdcDict["equity"],
            "Available": usdcDict["availableToWithdraw"],
            "usdValue": usdcDict["usdValue"],
        }

        return {"Balance": totalBalance, "BTC": btcValue, "USDC": usdcValue}

    # TODO: Maybe add error handling for the case where the contract does not exist
    def get_spot(self, coin="BTC"):
        """
        Get spot for a given coin

        Args:
            coin (str): Either BTC or ETH
        Returns:
            list: List of all the products
        """
        markets = []
        pair = self.session.get_instruments_info(symbol=f"{coin}USDT", category="spot")["result"]["list"][0]
        markets.append(pair)
        pair = self.session.get_instruments_info(symbol=f"{coin}USDC", category="spot")["result"]["list"][0]
        markets.append(pair)

        return markets

    def get_futureNames(self, coin="BTC", inverse=False, perpetual=False):
        """
        Get all the future contracts for a given coin

        Link: https://bybit-exchange.github.io/docs/v5/market/instrument
        Args:
            coin (str): Either BTC or ETH
            inverse (bool): If True, will return inverse futures
            perpetual (bool): If True, will return perpetual
        Return:
            list: List of all the future contracts for the given coin sorted by expiry date
        """

        # Sadly, I do not think there is a better way to do this
        # But the contracts themself are not always queried
        pairs = self.session.get_instruments_info(category="linear", baseCoin=coin)
        markets = []
        for p in pairs["result"]["list"]:
            # Looks like BTC-01NOV24
            if p["contractType"] == "LinearFutures":
                markets.append(p["symbol"])
            elif perpetual and p["contractType"] == "LinearPerpetual":
                markets.append(p["symbol"])
            elif inverse and p["contractType"] == "InverseFutures":
                markets.append(p["symbol"])

        # Function to extract and convert the date part to a datetime object
        def extract_date(contract):
            # Extracts the date part, e.g., '01NOV24' or '0328' for inverse futures
            date_str = contract.split("-")[-1] if "-" in contract else contract[-4:]
            try:
                return datetime.strptime(date_str, "%d%b%y")
            except ValueError:
                # Maximum date for inverse futures and perpetuals
                return datetime.strptime("2000", "%Y")

        # Sort the markets by expiry date
        sorted_markets = sorted(markets, key=extract_date)
        return sorted_markets

    # TODO: No need to load the whole DataFrame, just the last part, then concat to the file (Parquet is not made for that though)
    # TODO: Add a verbose parameter
    def get_history_pd(self, product, interval="m", dateLimit="01/01/2021", category="linear", dest=None):
        """
        Get the history of a future product until dateLimit
        If we do not have any data, we start from the oldest data point, and fetch the data before it
        If we have some data, we start from the most recent data point, and fetch the data after it
        We do it this way, because we cannot know when the product started
        Also, when a product has no more klines, it will not throw an error

        Warning: the last candle will not be at dateLimit, but a little after it

        Link: https://bybit-exchange.github.io/docs/v5/market/kline
        Args:
            product (str): The future product to get the history from
            interval (str): The interval of the data
            dateLimit (str): The last date of fetched data
            category (str): The category of the product
        Returns:
            A DataFrame containing the accumulated data
        """

        file_name = f"{product}_{interval}"
        if category == "spot":
            file_name += "_spot.parquet"
        else:
            file_name += ".parquet"

        if dest:
            file_name = os.path.join(dest, file_name)

        dateLimit = get_epoch(dateLimit)

        # Initialize an empty DataFrame for accumulated data
        acc_data = pd.DataFrame(
            columns=["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"]
        )

        try:
            acc_data = load_klines_parquet(file_name)
            print(f"Loaded {len(acc_data)} existing data points.")
            timestamp_key = "start"
            timestamp = acc_data.iloc[0]["startTime"]

        except FileNotFoundError:
            print("No previous data found, starting fresh.")
            timestamp_key = "end"
            timestamp = None

        params = {
            "symbol": product,
            "category": category,
            "interval": interval,
            "limit": 1000,
        }

        while True:
            if timestamp:
                params[timestamp_key] = timestamp

            response = self.session.get_kline(**params)["result"]["list"]
            new_data = pd.DataFrame(
                response,
                columns=["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"],
            )

            print(f"Fetched {len(new_data)} new data points.")

            if timestamp_key == "start":
                acc_data = pd.concat([new_data, acc_data.iloc[1:]], ignore_index=True)
            else:
                acc_data = pd.concat([acc_data.iloc[:-1], new_data], ignore_index=True)

            numberCandles = len(new_data)
            if numberCandles > 0:
                timestamp = (
                    acc_data.iloc[0]["startTime"] if timestamp_key == "start" else acc_data.iloc[-1]["startTime"]
                )

            if numberCandles < 1000 or int(acc_data.iloc[-1]["startTime"]) < dateLimit:
                break

        if not acc_data.empty:
            save_klines_parquet(file_name, acc_data)
        return acc_data

    async def set_leverage(self, symbol: str, leverage: str):
        """
        Set the leverage for a given symbol

        Link: https://bybit-exchange.github.io/docs/inverse/#t-changeleverage
        Args:
            symbol (str): The symbol to change the leverage for
            leverage (str): The leverage to set
        Returns:
            dict: The response from the API
        """
        categories = ["linear", "inverse"]
        for category in categories:
            try:
                return self.session.set_leverage(
                    symbol=symbol, category=category, buyLeverage=leverage, sellLeverage=leverage
                )
            except Exception as e:
                print(f"Failed to set leverage for {symbol} in category '{category}': {e}")
        return None

    async def enter_both_position(self, longSymbol: str, shortSymbol: str, longQuantity: int, shortQuantity: int):
        """
        Enter a position in both contracts.

        CAREFUL: It will not be arbitrage. The quantities have to be calculated beforehand.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
            longQuantity (int): The quantity to long
            shortQuantity (int): The quantity to short
        Returns:
            dict: The response from the API
        """

        # We will use asyncio to make calls at the same time.

        async def enter_position(symbol, quantity):
            return self.session.place_order(
                symbol=symbol,
                category="linear",
                side="Buy" if symbol == longSymbol else "Sell",
                qty=quantity,
                orderType="Market",
            )

        # Make both API calls concurrently
        long_task = enter_position(longSymbol, longQuantity, "Buy")
        short_task = enter_position(shortSymbol, shortQuantity, "Sell")

        # Gather the results
        responses = await asyncio.gather(long_task, short_task)
        return responses

    async def exit_both_position(self, longSymbol: str, shortSymbol: str, longQuantity: int, shortQuantity: int):
        """
        Exit a position in both contracts.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
        Returns:
            dict: The response from the API
        """

        # We will use asyncio to make calls at the same time.

        async def close_position(symbol, quantity):
            return self.session.place_order(
                symbol=symbol,
                category="linear",
                side="Sell" if symbol == longSymbol else "Buy",
                qty=quantity,
                orderType="Market",
                reduceOnly=True,
            )

        # Make both API calls concurrently
        long_task = close_position(longSymbol, longQuantity)
        short_task = close_position(shortSymbol, shortQuantity)

        # Gather the results
        responses = await asyncio.gather(long_task, short_task)
        return responses
