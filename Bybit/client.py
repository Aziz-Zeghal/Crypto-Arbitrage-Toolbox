import asyncio
import sys
import logging
from beartype import beartype
from typing import Callable

# Custom imports
from apiFetcher import bybitFetcher
from analyser import bybitAnalyser


class BybitClient:
    __slots__ = ["fetcher", "longContractmsg", "shortContractmsg", "logger", "active"]

    @beartype
    def __init__(self, demo=False):
        """
        Logic for a pair of products.
        It contains all the strategies for a pair of products.
        This will run as a systemd process (a daemon in the background).

        2 types of methods:
            - Strategies: Called by the executor
            - Executors: Setup application, then call the strategy

        Defines:
            - fetcher (bybitFetcher): Fetcher for the Bybit API
            - longContract (str): last long contract message
            - shortContract (str): last short contract message
            - logger (logging.Logger): Logger for the client

        """
        self.fetcher = bybitFetcher(demo=demo)

        self.longContractmsg: str = None
        self.shortContractmsg: str = None
        self.active = False

        self.logger = logging.getLogger("greekMaster.client")

    def check_arbitrage(self, minimumGap: float | int):
        """
        Callback function for both products' channels

        Checks if conditions are met for the arbitrage.

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

    async def _setup_contracts(
        self,
        longContract: str,
        shortContract: str,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = 0.12,
    ):
        """
        Setup the contracts for the client

        Args:
            longContract (str): The long contract's name
            shortContract (str): The short contract's name
        Returns:
            longContract, shortContract (str, str): The contracts (renamed if needed)
        """

        if strategy.__name__ not in dir(self):
            self.logger.error("Strategy not implemented")
            raise NotImplementedError

        # Define handlers
        def short_handler(message):
            if self.active:
                self.shortContractmsg = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring short websocket...")

        def long_handler(message):
            if self.active:
                self.longContractmsg = message
                strategy(minimumGap=minimumGap)
            else:
                self.logger.warning("Not active anymore. Ignoring long websocket...")

        # Determine if the long contract is spot
        is_spot = longContract.endswith("(Spot)")

        self.fetcher.start_linear_ws()  # Always start linear ws (for futures)
        await self.fetcher.set_leverage(shortContract, leverage)

        if is_spot:
            longContract = longContract.replace(" (Spot)", "")
            self.fetcher.start_spot_ws()  # Only start spot ws if it's a spot contract
        else:
            await self.fetcher.set_leverage(longContract, leverage)

        # Sleep to give websockets time to initialize
        await asyncio.sleep(5)

        # Stream tickers for both contracts using the same handler
        self.fetcher.ws.ticker_stream(symbol=shortContract, callback=short_handler)

        if is_spot:
            self.fetcher.ws_spot.ticker_stream(symbol=longContract, callback=long_handler)
        else:
            self.fetcher.ws.ticker_stream(symbol=longContract, callback=long_handler)

        self.active = True
        self.logger.info("Listening to the tickers")

        return longContract, shortContract

    @beartype
    async def Ulysse_spot(
        self,
        longContract: str,
        shortContract: str,
        quantityUSDC: float | int,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = 0.12,
    ):
        """
        The main executor, Ulysse (for spot and future contracts)
        Main character to spawn the strategy

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

        # Setup the contracts
        longContract, shortContract = await self._setup_contracts(
            longContract, shortContract, strategy, leverage, minimumGap
        )

        # TODO: Find a way to call entry in callbacks to avoid busy waiting
        while self.active:
            await asyncio.sleep(0.1)

        try:
            # We do not need the long info, because we can take how much we want
            shortTickers = self.shortContractmsg["data"]

            # Calculate the position
            shortPosition = bybitAnalyser.position_calculator(shortTickers, "Sell", quantityUSDC)

            # Open the positions
            resp = await self.fetcher.enter_spot_linear(
                longContract, shortContract, round(shortPosition["value"], 2), shortPosition["quantityContracts"]
            )
        except Exception as e:
            self.logger.error(f"Error when entering: {e}")
            self.logger.error("Exiting")
            self.fetcher.close_websockets()
            raise e

        # Not active anymore, close the Websockets
        self.fetcher.close_websockets()

        # Return the response
        return {
            "long": resp[0],
            "short": resp[1],
        }

    # TODO: In the long run, this will be the strategy selector too
    # TODO: If connection ends too fast, program takes time to end
    # Could make threaded websocket call_backs, and when we are done SIGINT them
    @beartype
    async def Ulysse(
        self,
        longContract: str,
        shortContract: str,
        quantityUSDC: float | int,
        strategy: Callable,
        leverage: str = "1",
        minimumGap: float | int = 0.12,
    ):
        """
        The main executor, Ulysse
        Main character to spawn the strategy

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

        # Setup the contracts
        longContract, shortContract = await self._setup_contracts(
            longContract, shortContract, strategy, leverage, minimumGap
        )

        # TODO: Find a way to call entry in callbacks to avoid busy waiting
        while self.active:
            await asyncio.sleep(0.1)

        try:
            longTickers = self.longContractmsg["data"]
            shortTickers = self.shortContractmsg["data"]

            # Calculate the position
            longPosition = bybitAnalyser.position_calculator(longTickers, "Buy", quantityUSDC)
            shortPosition = bybitAnalyser.position_calculator(shortTickers, "Sell", quantityUSDC)
            # Open the positions
            resp = await self.fetcher.enter_double_linear(
                longContract, shortContract, longPosition["quantityContracts"], shortPosition["quantityContracts"]
            )

        except Exception as e:
            self.logger.error(f"Error: {e}")
            self.logger.error("Exiting")
            self.fetcher.ws.exit()
            raise e

        # Not active anymore, close the Websockets
        self.fetcher.close_websockets()

        logging.info(self.longContractmsg)
        # Return the response
        return {
            "long": longPosition,
            "short": shortPosition,
        }
