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
        "fetcher",
        "logger",
        "longContractSymbol",
        "longContractmsg",
        "shortContractSymbol",
        "shortContractmsg",
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

        Defines:
            - fetcher (Fetcher): Fetcher for the Bybit API
            - longContract (str): last long contract message
            - shortContract (str): last short contract message
            - logger (logging.Logger): Logger for the client

        """
        self.fetcher = Fetcher(demo=demo)

        self.longContractmsg: str = None
        self.shortContractmsg: str = None
        self.active = False

        self.logger = logging.getLogger("greekMaster.client")

    def new_round(self) -> None:
        """Routine called by the Master to reset the client's state."""
        self.longContractSymbol = None
        self.shortContractSymbol = None

        self.longContractmsg = None
        self.shortContractmsg = None

        # For next execution
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
        if self.longContractmsg is None or self.shortContractmsg is None:
            return
        longTickers = self.longContractmsg["data"]
        shortTickers = self.shortContractmsg["data"]

        # | Price of the future contract
        longPrice = float(longTickers["lastPrice"])
        shortPrice = float(shortTickers["lastPrice"])
        # - Calculate the gap
        coeff = (shortPrice / longPrice - 1) * 100

        # TODO: Add logging ?

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
                self.shortContractmsg = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring short websocket...")

        def long_handler(message: str) -> None:
            if self.active:
                self.longContractmsg = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring long websocket...")

        # Logic to activate websockets, and subscribe to the tickers (extra setup before: leverage, spot handling...)
        self._activate_websockets(short_handler, long_handler)

        # Stream tickers for both contracts using the same handler
        self.active = True

        self.logger.info("Listening to the tickers")

    @abstractmethod
    def base_executor(self):  # noqa: ANN201
        """Implement the main executor for the client.

        Should be implemented in the child class, depending on the used products.
        """


class UlysseSpotPerp(BybitClient):
    """The base_executor client has executors for spot and perpetual contracts."""

    def _activate_websockets(self, short_handler: Callable, long_handler: Callable) -> None:
        # TODO: This cannot be definitive
        self.longContractSymbol = self.longContractSymbol.replace(" (Spot)", "")

        # Start the websockets
        self.fetcher.start_linear_ws()
        self.fetcher.start_spot_ws()

        # Sleep to give websockets time to initialize
        sleep(5)

        # Subscribe to the tickers
        self.fetcher.ws_spot.ticker_stream(symbol=self.longContractSymbol, callback=long_handler)
        self.fetcher.ws.ticker_stream(symbol=self.shortContractSymbol, callback=short_handler)

    async def base_executor(
        self,
        quantityUSDC: float,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = -0.2,
    ) -> dict:
        """Implement the main executor for Ulysse (for spot and future contracts).

        Actions:
            - Initialize the Bybit client
            - Listen to the tickers with the websocket
            - Associate to callback functions

        Callback functions for both channels will check for the conditions of the arbitrage.

        Args:
            longContract (str): The long contract's name
            shortContract (str): The short contract's name
            quantityUSDC (float | int): The quantity in USDC
            strategy (callable): The strategy to use (Needs to be implemented in client)
            leverage (str): The leverage to use, default is "1"
            minimumGap (float | int): The minimum gap to consider for the arbitrage
        Returns:
            dict: The response from the API

        """
        # Leverage only on the future product
        await self.fetcher.set_leverage(self.shortContractSymbol, leverage)

        # Setup the contracts
        await self._setup_contracts(strategy, minimumGap)

        # TODO: Find a way to call entry in callbacks to avoid busy waiting
        while self.active:
            await asyncio.sleep(0.1)

        try:
            # We do not need the long info, because we can take how much we want
            shortTickers = self.shortContractmsg["data"]

            # Calculate the position
            shortPosition = Analyser.position_calculator(shortTickers, "Sell", quantityUSDC)

            # Open the positions
            await self.fetcher.enter_spot_linear(
                self.longContractSymbol,
                self.shortContractSymbol,
                round(shortPosition["value"], 8),
                shortPosition["quantityContracts"],
            )
        except Exception:
            self.logger.exception("Error when entering arbitrage position")
            self.logger.exception("Exiting", stack_info=False)
            self.fetcher.close_websockets()
            raise

        # Not active anymore, close the Websockets
        self.fetcher.close_websockets()

        # Return the response
        return {
            "longContract": {
                "symbol": self.longContractSymbol,
                "qty": round(self.fetcher.get_wallet()["BTC"]["Available"] - 0.000001, 6),
            },
            "shortContract": {"symbol": self.shortContractSymbol, "qty": shortPosition["quantityContracts"]},
        }
