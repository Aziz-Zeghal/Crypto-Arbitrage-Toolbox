import asyncio
import sys
import logging
from beartype import beartype

# Custom imports
from apiFetcher import bybitFetcher
from analyser import bybitAnalyser


class BybitClient:
    __slots__ = ["fetcher", "longContract", "shortContract", "logger"]

    @beartype
    def __init__(self, demo=False):
        """
        Logic for a pair of products.
        It contains all the strategies for a pair of products.
        This will run as a systemd process (a daemon in the background).

        Makes:
            fetcher (bybitFetcher): Fetcher for the Bybit API
            longContract (str): last long contract message
            shortContract (str): last short contract message
            logger (logging.Logger): Logger for the client

        """
        self.fetcher = bybitFetcher(demo=demo)

        self.longContract: str = None
        self.shortContract: str = None

        self.logger = logging.getLogger("Bybit.greekMaster")

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
        if self.longContract is None or self.shortContract is None:
            return
        longTickers = self.longContract["data"]
        shortTickers = self.shortContract["data"]

        # | Price of the future contract
        longPrice = float(longTickers["lastPrice"])
        shortPrice = float(shortTickers["lastPrice"])
        # - Calculate the gap
        coeff = (shortPrice / longPrice - 1) * 100

        # Here, we put a check so that it will not process the log and use a buffer.
        if self.logger.level == logging.INFO:
            self.logger.info(f"Gap: {coeff:.4f} %")

        # Check if the gap is enough
        if coeff >= minimumGap:
            self.client.ws.exit()

    # TODO: In the long run, this will be the strategy selector too
    # TODO: If connection ends too fast, program takes time to end
    # Could make threaded websocket call_backs, and when we are done SIGINT them
    @beartype
    async def Ulysse(
        self,
        longContract: str,
        shortContract: str,
        quantityUSDC: float | int,
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
            leverage (str): The leverage to use, default is "1"
            minimumGap (float | int): The minimum gap to consider for the arbitrage
        Returns:
            dict: The response from the API
        """

        # Set the leverage
        await asyncio.gather(
            self.fetcher.set_leverage(longContract, leverage), self.fetcher.set_leverage(shortContract, leverage)
        )

        # Define handlers
        def short_handler(message):
            if not self.fetcher.ws.exited:
                self.shortContract = message

        # We position the arbitrage here, because more messages
        def long_handler(message):
            if not self.fetcher.ws.exited:
                self.longContract = message
                self.check_arbitrage(minimumGap=minimumGap)

        # Start socket
        self.fetcher.start_ws()

        # Listen to channels
        self.fetcher.ws.ticker_stream(symbol=shortContract, callback=short_handler)
        self.fetcher.ws.ticker_stream(symbol=longContract, callback=long_handler)

        self.logger.info("Listening to the tickers")
        # Now, hold the program
        while not self.fetcher.ws.exited:
            await asyncio.sleep(1)

        # Either arbitrage found or something bad happened
        # TODO: Need to be sure of arbitrage (boolean or better solution)

        longTickers = self.longContract["data"]
        shortTickers = self.shortContract["data"]

        # Calculate the position
        longPosition = bybitAnalyser.position_calculator(longTickers, "Buy", quantityUSDC)
        shortPosition = bybitAnalyser.position_calculator(shortTickers, "Sell", quantityUSDC)
        # Open the positions
        await self.fetcher.enter_both_position(
            longContract, shortContract, longPosition["quantityContracts"], shortPosition["quantityContracts"]
        )

        self.logger.info("For " + longContract + ":")
        self.logger.info(longPosition)
        self.logger.info("For " + shortContract + ":")
        self.logger.info(shortPosition)

        self.logger.info("Last messages:")
        self.logger.info(self.shortContract)
        self.logger.info(self.longContract)

        sys.exit(0)
