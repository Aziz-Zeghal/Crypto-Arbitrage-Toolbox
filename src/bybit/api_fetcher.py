import asyncio
import logging
import sys
from pathlib import Path

import pandas as pd
from beartype import beartype
from pybit.unified_trading import HTTP, WebSocket

# Custom imports
from bybit.analyser import Analyser
from bybit.utils import get_epoch, load_klines_parquet, save_klines_parquet

sys.path.append(str(Path("keys.py").resolve().parent))

try:
    import keys
except ImportError:
    print("No keys file found !")


class Fetcher:
    __slots__ = ["logger", "session", "ws", "ws_spot"]

    @beartype
    def __init__(self, demo: bool = False) -> None:
        """Initialize the Bybit session.

        Args:
            demo (bool): If True, will use the demo keys

        Defines:
            - session (HTTP): The HTTP session
            - logger (logging.Logger): Logger for the fetcher

        """
        if demo:
            self.session = HTTP(api_key=keys.demobybitPKey, api_secret=keys.demobybitSKey, demo=True)
        else:
            self.session = HTTP(api_key=keys.bybitPKey, api_secret=keys.bybitSKey)

        self.ws = None
        # TODO: In the future, have a dictionary of WebSocket sessions
        self.ws_spot = None

        self.logger = logging.getLogger("greekMaster.client.fetcher")

    def start_linear_ws(self) -> None:
        """Start the WebSocket session for linear contracts."""
        self.ws = WebSocket(
            api_key=keys.demobybitPKey,
            api_secret=keys.demobybitSKey,
            testnet=False,
            channel_type="linear",
            ping_interval=5,
            ping_timeout=4,
        )

    def start_spot_ws(self) -> None:
        """Start the WebSocket session for spot contracts."""
        self.ws_spot = WebSocket(
            api_key=keys.demobybitPKey,
            api_secret=keys.demobybitSKey,
            testnet=False,
            channel_type="spot",
            ping_interval=5,
            ping_timeout=4,
        )

    def close_websockets(self) -> None:
        """Close the WebSocket sessions."""
        for ws in [self.ws, self.ws_spot]:
            if ws:
                ws.exit()
                self.logger.info("WebSocket closed")

    def get_wallet(self) -> dict:
        """Give information on USDC and BTC.

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
        response = self.session.get_wallet_balance(accountType="UNIFIED")["result"]["list"][0]
        totalBalance = response["totalEquity"]

        btcDict = next((coin for coin in response["coin"] if coin["coin"] == "BTC"), None)
        usdcDict = next((coin for coin in response["coin"] if coin["coin"] == "USDC"), None)
        usdtDict = next((coin for coin in response["coin"] if coin["coin"] == "USDT"), None)

        def get_info(coin: dict) -> dict:
            return {
                "Quantity": float(coin["equity"]),
                "Available": float(coin["equity"]) - float(coin["totalPositionIM"]),
                "TotalPositionIM": float(coin["totalPositionIM"]),
                "usdValue": float(coin["usdValue"]),
            }

        return {
            "Balance": totalBalance,
            "BTC": get_info(btcDict),
            "USDC": get_info(usdcDict),
            "USDT": get_info(usdtDict),
        }

    # TODO: No need to load the whole DataFrame, just the last part,
    # then concat to the file (Parquet is not made for that though)
    # TODO: Add a verbose parameter
    @beartype
    async def get_history_pd(
        self,
        product: str,
        interval: str = "m",
        dateLimit: str = "01/01/2021",
        category: str = "linear",
        dest: str | None = None,
    ) -> pd.DataFrame:
        """Get the history of a future product until dateLimit.

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
            dest (str | None): The destination folder to save the data
        Returns:
            A DataFrame containing the accumulated data
        """
        file_name = f"{product}_{interval}"
        if category == "spot":
            file_name += "_spot.parquet"
        else:
            file_name += ".parquet"

        if dest:
            file_name = Path(dest) / file_name

        dateLimit = get_epoch(dateLimit)

        # Initialize an empty DataFrame for accumulated data
        acc_data = pd.DataFrame(
            columns=["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"],
        )
        ORANGE = "\033[38;5;214m"
        RESET = "\033[0m"
        self.logger.info(f"Fetching data for {ORANGE}{product}{RESET} in {ORANGE}{interval}{RESET} interval.")
        try:
            acc_data = load_klines_parquet(file_name)
            self.logger.info(f"Loaded {len(acc_data)} existing data points.")
            timestamp_key = "start"
            timestamp = acc_data.iloc[0]["startTime"]

        except FileNotFoundError:
            self.logger.info("No previous data found, starting fresh.")
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

            self.logger.info(f"Fetched {len(new_data)} new data points.")

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

    # TODO: Add inverse contracts file handling
    @beartype
    async def save_klines(
        self,
        coin: str = "BTC",
        datelimit: str = "01/01/2021",
        dest: str = "store",
        spot: bool = True,
        perpetual: bool = True,
        inverse: bool = True,
    ) -> None:
        """Save the klines of all the Perpetual/Future/Inverse contracts in parquet format.

        Checks if a parquet file exists to update it, else creates a new one

        Args:
            coin (str): The coin to consider (e.g., "BTC").
            datelimit (str): The last date of fetched data.
            dest (str): The destination folder to save the data.
            spot (bool): Include spot contracts.
            perpetual (bool): Include perpetual contracts.
            inverse (bool): Include inverse contracts.

        """
        allContracts = self.get_linearNames(inverse=inverse, perpetual=perpetual, coin=coin)

        # Combine perpetual and future contracts
        allContracts = allContracts["perpetual"] + allContracts["future"]

        async def _fetch_history(contract: str, interval: str, category: str = "linear") -> None:
            await self.get_history_pd(
                product=contract, dateLimit=datelimit, interval=interval, dest=dest, category=category
            )

        tasks = []

        for contract in allContracts:
            tasks.extend(
                [_fetch_history(contract, "15"), _fetch_history(contract, "5"), _fetch_history(contract, "1")],
            )

        # spot
        if spot:
            tasks.extend(
                [
                    _fetch_history(f"{coin}USDT", "15", category="spot"),
                    _fetch_history(f"{coin}USDT", "5", category="spot"),
                    _fetch_history(f"{coin}USDT", "1", category="spot"),
                ],
            )

        # TODO: This code will wait for other tasks, because we use I/O bound tasks
        await asyncio.gather(*tasks)

    # TODO: Maybe add error handling for the case where the contract does not exist
    @beartype
    def get_spot(self, coin: str = "BTC") -> list:
        """Get spot for a given coin.

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

    @beartype
    def get_linearNames(
        self,
        coin: str = "BTC",
        perpetual: bool = True,
        inverse: bool = False,
        quoteCoins: list[str] = ["USDT", "USDC", "USD"],
    ) -> dict:
        """Get all the future contracts for a given coin.

        Link: https://bybit-exchange.github.io/docs/v5/market/instrument
        Args:
            coin (str): Either BTC or ETH
            quoteCoins (list[str]): The quote coins to consider
        Return:
            dict: The future contracts. The keys are "perpetual" and "future"
        """
        # Sadly, I do not think there is a better way to do this
        # But the contracts themself are not always queried
        pairs = self.session.get_instruments_info(category="linear", baseCoin=coin)
        markets = {"perpetual": [], "future": []}
        for p in pairs["result"]["list"]:
            # Looks like BTC-01NOV24
            if p["quoteCoin"] in quoteCoins:
                if p["contractType"] == "LinearFutures":
                    markets["future"].append(p["symbol"])
                elif perpetual and p["contractType"] == "LinearPerpetual":
                    markets["perpetual"].append(p["symbol"])
                elif inverse and p["contractType"] == "InverseFutures":
                    markets["future"].append(p["symbol"])

        return markets

    # WARNING: There is no Future/Inverse with USD or USDT, so selecting these will return nothing.
    @beartype
    def all_gaps_pd(
        self,
        coin: str = "BTC",
        quoteCoins: list[str] = ["USDC", "USDT", "USD"],
        applyFees: bool = False,
        spot: bool = False,
        perpetual: bool = True,
        inverse: bool = False,
    ) -> pd.DataFrame:  # Function can return either DataFrame or Styler
        """Get all the gaps for multiple products in a DataFrame.

        Args:
            coin (str): The coin to consider (e.g., "BTC").
            quoteCoins (list[str]): Quote currencies to consider (e.g., ["USDC", "USDT"]).
            applyFees (bool): Apply trading fees (0.22% taker fee).
            spot (bool): Include spot contracts.
            perpetual (bool): Use perpetual contracts.
            inverse (bool): Use inverse contracts.

        Returns:
            pd.DataFrame | pd.io.formats.style.Styler: A DataFrame or a styled version.

        """
        # Get future and spot contracts
        market = self.get_linearNames(coin=coin, inverse=inverse, perpetual=perpetual, quoteCoins=quoteCoins)

        shortTickers = [
            self.session.get_tickers(symbol=future, category="linear")["result"] for future in market["future"]
        ]

        longTickers = [
            self.session.get_tickers(symbol=perpetual, category="linear")["result"] for perpetual in market["perpetual"]
        ]

        if spot:
            for stableCoin in ["USDT", "USDC"]:
                if stableCoin in quoteCoins:
                    response = self.session.get_tickers(symbol=f"{coin}{stableCoin}", category="spot")["result"]
                    response["list"][0]["deliveryTime"] = 0  # Spot contracts don't have a delivery time
                    response["list"][0]["symbol"] = f"{coin}{stableCoin} (Spot)"
                    longTickers.append(response)

        # Define the column types
        column_types = {
            "Buy": "string",
            "Sell": "string",
            "Gap": "float",
            "Coeff": "float",
            "APR": "float",
            "DaysLeft": "int",
            "CumVolume": "int",
        }

        df_gaps = pd.DataFrame(columns=column_types.keys()).astype(column_types)

        # Calculate gaps
        for _i, long in enumerate(longTickers):
            for short in shortTickers:
                # Cross only the products in different categories
                longInfo = long["list"][0]
                shortInfo = short["list"][0]
                gap = Analyser.get_gap(longInfo, shortInfo, applyFees)

                row = pd.DataFrame(
                    [
                        {
                            "Buy": longInfo["symbol"],
                            "Sell": shortInfo["symbol"],
                            "Gap": gap["gap"],
                            "Coeff": gap["coeff"],
                            "APR": gap["apr"],
                            "DaysLeft": max(0, int(gap["daysLeft"])),
                            "CumVolume": gap["cumVolume"],
                        },
                    ],
                )

                df_gaps = pd.concat([df_gaps, row], ignore_index=True)

        df_gaps = df_gaps.astype(column_types)

        # Sort by DaysLeft
        df_gaps = df_gaps.sort_values(by="DaysLeft")

        return df_gaps.reset_index(drop=True)

    async def get_greeks(self, baseCoin: str | None = None) -> dict:
        """Get the greeks for a given symbol.

        Link: https://bybit-exchange.github.io/docs/v5/account/coin-greeks
        Args:
            baseCoin (str): The baseCoin to get the greeks from
        Returns:
            dict: The response from the API
        """
        try:
            if baseCoin:
                return self.session.get_coin_greeks(baseCoin=baseCoin)["result"]["list"][0]
            return self.session.get_coin_greeks()["result"]["list"][0]
        except Exception as e:
            self.logger.warning(f"Error: {e}")
            return None

    async def get_position(self, symbol: str) -> dict:
        """Get the position of a linear/inverse contract.

        Link: https://bybit-exchange.github.io/docs/v5/position

        Args:
            symbol (str): The symbol to get the position from
        Returns:
            info (dict): The size and value of the position

        """
        position = self.session.get_positions(symbol=symbol, category="linear")["result"]["list"][0]
        return {"qty": position["size"], "positionValue": position["positionValue"]}

    @beartype
    async def set_leverage(self, symbol: str, leverage: str) -> dict | None:
        """Set the leverage for a given symbol.

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
                    symbol=symbol,
                    category=category,
                    buyLeverage=leverage,
                    sellLeverage=leverage,
                )
            except Exception as e:
                # Either wrong category, or leverage was set
                if not e.args[0].startswith(("Illegal category", "leverage not modified")):
                    raise

        return None

    async def place_order(
        self,
        symbol: str,
        quantity: float,
        side: str,
        category: str,
        reduce_only: bool = False,
    ) -> dict:
        """Place an order in the specified category.

        Args:
            symbol (str): The symbol to trade
            quantity (float | int): The quantity to trade
            side (str): The side of the trade, either "Buy" or "Sell"
            category (str): The category of the trade, either "spot" or "linear"
            reduce_only (bool): Whether the order is reduce-only
        Returns:
            dict: The response from the API

        """
        return self.session.place_order(
            symbol=symbol,
            category=category,
            side=side,
            qty=quantity,
            orderType="Market",
            reduceOnly=reduce_only,
        )

    @beartype
    async def enter_spot_linear(
        self,
        longSymbol: str,
        shortSymbol: str,
        longQuantity: float,
        shortQuantity: float,
    ) -> list:
        """Enter a long position in a spot contract and a short position in a linear contract.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
            longQuantity (float | int): The quantity to long
            shortQuantity (float | int): The quantity to short

        """
        # Make both API calls concurrently
        short_task = asyncio.create_task(self.place_order(shortSymbol, shortQuantity, "Sell", "linear"))
        long_task = asyncio.create_task(self.place_order(longSymbol, longQuantity, "Buy", "spot"))

        # Gather the results
        return await asyncio.gather(long_task, short_task)

    @beartype
    async def exit_spot_linear(
        self,
        longSymbol: str,
        shortSymbol: str,
        longQuantity: float,
        shortQuantity: float,
    ) -> list:
        """Exit a long position in a spot contract and a short position in a linear contract.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
            longQuantity (float | int): The quantity to long
            shortQuantity (float | int): The quantity to short

        """
        # Make both API calls concurrently
        long_task = asyncio.create_task(self.place_order(longSymbol, longQuantity, "Sell", "spot", reduce_only=True))
        short_task = asyncio.create_task(
            self.place_order(shortSymbol, shortQuantity, "Buy", "linear", reduce_only=True),
        )

        # Gather the results
        try:
            responses = await asyncio.gather(long_task, short_task)
        except Exception as e:
            self.logger.warning(f"Error: {e}")
        return responses

    @beartype
    async def enter_double_linear(
        self,
        longSymbol: str,
        shortSymbol: str,
        longQuantity: float,
        shortQuantity: float,
    ) -> list:
        """Enter a position in both contracts.

        CAREFUL: It will not be arbitrage. The quantities have to be calculated beforehand.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
            longQuantity (float | int): The quantity to long
            shortQuantity (float | int): The quantity to short
        Returns:
            dict: The response from the API

        """
        # Make both API calls concurrently
        short_task = asyncio.create_task(self.place_order(shortSymbol, shortQuantity, "Sell", "linear"))
        long_task = asyncio.create_task(self.place_order(longSymbol, longQuantity, "Buy", "linear"))

        # Gather the results
        return await asyncio.gather(long_task, short_task)

    async def exit_double_linear(
        self, longSymbol: str, shortSymbol: str, longQuantity: int, shortQuantity: int
    ) -> dict:
        """Exit a position in both contracts.

        Args:
            longSymbol (str): The symbol to long
            shortSymbol (str): The symbol to short
            longQuantity (float | int): The quantity to long
            shortQuantity (float | int): The quantity to short
        Returns:
            dict: The response from the API

        """
        # Make both API calls concurrently
        long_task = asyncio.create_task(self.place_order(longSymbol, longQuantity, "Sell", "linear", reduce_only=True))
        short_task = asyncio.create_task(
            self.place_order(shortSymbol, shortQuantity, "Buy", "linear", reduce_only=True),
        )

        # Gather the results
        return await asyncio.gather(long_task, short_task)
