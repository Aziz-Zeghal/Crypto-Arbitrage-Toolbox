import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from time import sleep

from beartype import beartype

from bybit.analyser import Analyser

# Custom imports
from bybit.api_fetcher import Fetcher


class BybitClient(ABC):
    __slots__ = [
        "active",
        "balance",
        "fetcher",
        "logger",
        "longContract",
        "shortContract",
    ]

    @beartype
    def __init__(self, demo: bool = False) -> None:
        """Logic for a pair of products.

        It contains all the strategies for a pair of products.
        This will be run as a systemd process (a daemon in the background).

        Ulysse are instances of this class, and they will be the ones to call the strategies.

        2 types of methods:
            - Strategies (Common to all classes): Called by the executor
            If the strategy uses contract related information (like funding rate),
            the strategy will be in the child class.
            - Executors (Child class related): Setup application, then call the strategy

        longContract and shortContract are dictionnaries of this form:
        {
            "data": Last Kline data,
            "symbol": Contract symbol,
            "qty": Position quantity,
        }
        """
        self.fetcher = Fetcher(demo=demo)
        self.longContract: dict = {}
        self.shortContract: dict = {}
        self.balance = 0

        self.active = False

        self.logger = logging.getLogger("greekMaster.client")

    def new_round(self) -> None:
        """Routine called by the Master to reset the client's state."""
        self.longContract = {}
        self.shortContract = {}
        self.balance = 0

        self.active = True

    def most_basic_arb(self, minimumGap: float) -> None:
        """Check if conditions are met for the arbitrage.

        Callback function for both products' channels.

        Args:
            minimumGap (float | int): The minimum gap to consider for the arbitrage
        Returns:
            None

        """
        # Check if the data is complete
        if self.longContract.get("data") is None or self.shortContract.get("data") is None:
            return
        longTickers = self.longContract["data"]["data"]
        shortTickers = self.shortContract["data"]["data"]

        # | Price of the future contract
        longPrice = float(longTickers["lastPrice"])
        shortPrice = float(shortTickers["lastPrice"])
        # - Calculate the gap
        coeff = (shortPrice / longPrice - 1) * 100

        # Check if the gap is enough
        if coeff >= minimumGap:
            self.logger.info("Arbitrage found")
            self.active = False

    @abstractmethod
    def _activate_websockets(self, short_handler: Callable, long_handler: Callable) -> None:
        """Tells which websocket to activate, subscribes to the tickers, and more.

        Should be implemented in the child class, depending on the used products.

        WARNING: Do not forget to sleep between starting the websockets and subscribing to the tickers.
        """

    async def _setup_contracts(
        self,
        strategy: Callable,
        minimumGap: float = -0.2,
    ) -> None:
        """Set up the contracts for the client.

        Args:
            strategy: The strategy to use
            minimumGap: The minimum gap to consider for the arbitrage

        """
        if strategy.__name__ not in dir(self):
            self.logger.error("Strategy not implemented")
            raise NotImplementedError

        # Define handlers
        def short_handler(message: str) -> None:
            if self.active:
                self.shortContract["data"] = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring short websocket...")

        def long_handler(message: str) -> None:
            if self.active:
                self.longContract["data"] = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring long websocket...")

        # Logic to activate websockets, and subscribe to the tickers (extra setup before: leverage, spot handling...)
        self._activate_websockets(short_handler, long_handler)

        # Stream tickers for both contracts using the same handler
        self.active = True

        self.logger.info("Listening to the tickers")

    @abstractmethod
    async def _enter_amount() -> dict:  # noqa: ANN202
        """To use in base_executor.

        Selects the entry method for the client.
        """

    @abstractmethod
    async def exit_amount() -> dict:  # noqa: ANN202
        """To use in _exit_on_delivery.

        Selects the entity to sell (BTC, USDC, or not sell for rollover)
        """

    @abstractmethod
    async def base_executor(
        self,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = -0.2,
    ) -> None:
        """Implement the main executor for Ulysse, depending on the used products.

        Actions:
            - Initialize the Bybit client
            - Listen to the tickers with the websocket
            - Associate to callback functions

        Callback functions for both channels will check for the conditions of the arbitrage.

        Args:
            strategy (callable): The strategy to use (Needs to be implemented in client)
            leverage (str): The leverage to use, default is "1"
            minimumGap (float | int): The minimum gap to consider for the arbitrage

        """
        # TODO: Should be kwargs
        # Setup the contracts
        await self._setup_contracts(strategy, minimumGap)

        # TODO: Find a way to call entry in callbacks to avoid busy waiting
        while self.active:  # noqa: ASYNC110
            await asyncio.sleep(0.1)

        try:
            await self._enter_amount()

        except Exception:
            self.logger.exception("Error when entering arbitrage position")
            self.logger.exception("Exiting", stack_info=False)
            self.fetcher.close_websockets()
            raise

        # Not active anymore, close the Websockets
        self.fetcher.close_websockets()


class UlysseSpotFut(BybitClient):
    """The base_executor client has executors for spot and perpetual contracts."""

    async def _enter_amount(self) -> dict:
        """Places the entry order."""
        # We do not need the long info, because we can take how much we want
        shortTickers = self.shortContract["data"]["data"]

        # Calculate the position
        shortPosition = Analyser.position_calculator(shortTickers, "Sell", self.balance)

        # Open the positions
        await self.fetcher.enter_spot_linear(
            self.longContract["symbol"],
            self.shortContract["symbol"],
            round(shortPosition["value"], 8),
            shortPosition["quantityContracts"],
        )

        # Affect the qty to the dictionnaries
        self.longContract["qty"] = round(self.fetcher.get_wallet()["BTC"]["Available"] - 0.000001, 6)
        self.shortContract["qty"] = shortPosition["quantityContracts"]

    async def exit_amount(self) -> dict:
        """Places the exit order."""
        return await self.fetcher.place_order(
            symbol=self.longContract["symbol"],
            side="Sell",
            quantity=self.longContract["qty"],
            category="spot",
        )

    def _activate_websockets(self, short_handler: Callable, long_handler: Callable) -> None:
        # TODO: This cannot be definitive
        self.longContract["symbol"] = self.longContract["symbol"].replace(" (Spot)", "")

        # Start the websockets
        self.fetcher.start_linear_ws()
        self.fetcher.start_spot_ws()

        # Sleep to give websockets time to initialize
        sleep(5)

        # Subscribe to the tickers
        self.fetcher.ws_spot.ticker_stream(symbol=self.longContract["symbol"], callback=long_handler)
        self.fetcher.ws.ticker_stream(symbol=self.shortContract["symbol"], callback=short_handler)

    async def base_executor(
        self,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = -0.2,
    ) -> None:
        """Implement for spot and future contracts."""
        # Leverage only on the future product
        await self.fetcher.set_leverage(self.shortContract["symbol"], leverage)
        await super().base_executor(strategy, leverage, minimumGap)
