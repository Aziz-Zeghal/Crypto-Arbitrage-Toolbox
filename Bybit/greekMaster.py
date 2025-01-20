from abc import ABC, abstractmethod
import datetime
import logging
import sys
import asyncio
import schedule
from beartype import beartype
from typing import Callable

from client import UlysseSpotPerp
from utils import get_date


class GreekMaster(ABC):
    __slots__ = ["client", "fetcher", "logger", "position_info", "watching", "sch"]

    @beartype
    def __init__(self, demo=False):
        """
        Logic for all products.
        Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry.
        Talks to Bybit through the client.
        Can send notifications and logs arbitrage events.

        GreekMaster is an interface for its child classes.

        3 types of methods:
            - Selectors: The method to choose the best pair of contracts
            - Strategies: Called by the executor
            - Executors: Setup application, call the strategy, monitor, then exit. (common to all children, with class customized utility methods)
        Defines:
            - client (BybitClient): Client for the Bybit API
            - fetcher (bybitFetcher): Fetcher for the Bybit API
            - contracts (list): List of all the current contracts
            - logger (logging.Logger): Logger for the client
            - position_info: Dictionnary with live updates
            - watching: Boolean to know if GreekMaster has control

        Implements:
            - _new_round: Cleanup for next arbitrage round
            - monitor: Monitor the accounts, check the positions, the liquidation risk, etc.
            - _exit_on_delivery: Handler called every second to check if delivery arrived or not (uses _select_order)
            - _friday_job: Handler for the delivery day
            - _handle_on_delivery: Handler to exit on delivery day (uses _select_amount)


        """

        # WARNING: This part will never be used because of the ABC.
        # But useful for syntax completion
        self.client = UlysseSpotPerp(demo=demo)

        self.fetcher = self.client.fetcher

        self.position_info = {}

        self.logger = logging.getLogger("greekMaster")

        self.logger.info("GreekMaster initialized")

        self.sch = schedule.Scheduler()
        self.watching = False

    def _new_round(self):
        """
        Cleanup for next arbitrage round
        """
        self.sch.clear()

        self.client._new_round()

        self.position_info = {}

        self.watching = False

    async def monitor(self):
        """
        Monitor the accounts, check the positions, the liquidation risk, etc.

        Writes inside position_info

        """
        self.logger.info("Monitoring the account...")

        ret = self.fetcher.get_USDC_BTC()
        if ret:
            logging.info(
                f"""--------------------
                {ret}
                --------------------"""
            )

        ret = await self.fetcher.get_greeks("BTC")
        if ret:
            logging.info(
                f"""--------------------
                {ret}
                --------------------"""
            )

    @abstractmethod
    async def _select_amount():
        """
        Used in _exit_on_delivery.
        Selects the entity to sell (BTC, USDC, or not sell for rollover)
        """
        pass

    async def _exit_on_delivery(self):
        """
        Handler called every second to check if delivery arrived or not.
        """
        shortContract = self.position_info["shortContract"]

        res = await self.fetcher.get_position(symbol=shortContract["symbol"])

        # If the position is 0, delivery arrived, sell spot.
        if res["qty"] == "0" or res["positionValue"] == "":

            # Exit position (can also be a rollover)
            await self._select_amount()

            setattr(self, "watching", False),
            self.logger.info("Delivery arrived, exited arbitrage !")

            # Here, you would want to return self.sch.CancelJob.
            # But, we are in an async function, so we cannot return it easily.

    def _friday_job(self, epochTime: int):
        self.logger.info(f"{epochTime - datetime.datetime.now().timestamp() * 1000}")
        # If we are 30 minutes before the delivery time
        if (epochTime - datetime.datetime.now().timestamp() * 1000) < 1200 * 1000:
            self.logger.info("Delivery day ! Setting up surveillance...")

            # When the position is 0, delivery arrived, sell spot.
            self.sch.every().second.do(lambda: asyncio.ensure_future(self._exit_on_delivery()))

            # Job is no longer useful, so remove it
            return schedule.CancelJob

        # Else, we are friday but not yet the delivery day

    async def _handle_on_delivery(self):
        """
        Handler to exit on delivery day (Spot/Perpetual)
        """
        epochTime = int(
            self.fetcher.session.get_tickers(symbol=self.position_info["shortContract"]["symbol"], category="linear")[
                "result"
            ]["list"][0]["deliveryTime"]
        )

        self.logger.info(f"Delivery date at 8:00AM UTC for: {get_date(epochTime)}")

        # SCHEDULING PART
        self.sch.every().minute.do(lambda: asyncio.ensure_future(self.monitor()))
        # Schedule the delivery day (cashout, write the position in the books, etc.)
        self.sch.every().friday.at("08:48", "Europe/Paris").do(self._friday_job, epochTime=epochTime)

        # WARNING: order of actions matters A LOT
        # If you run_pending at the end, function will get called even if the job is cancelled
        # Weirdest bug I have seen. Fixed it.
        while self.watching:
            self.sch.run_pending()
            n = self.sch.idle_seconds
            await asyncio.sleep(n)

        # Clear the schedule
        self._new_round()


class SpotFutStrategos(GreekMaster):
    """
    Implemented GreekMaster for Perpetual and Future contracts

    Carries scalper strategies + long term strategies
    """

    def __init__(self, demo=False):
        super().__init__(demo)
        self.client = UlysseSpotPerp(demo=demo)

    async def _select_amount(self):
        """ """
        longContract = self.position_info["longContract"]

        return await self.fetcher.place_order(
            symbol=longContract["symbol"],
            side="Sell",
            quantity=longContract["qty"],
            category="spot",
        )

    def CT_best_gap(self, perpetual=True, spot=False, maxDays: int = 25, quoteCoins: list[str] = ["USDC"]):
        """
        Find the best gap for spot and perpetual contracts

        Args:
            perpetual (bool): will get the perpetual contracts
            spot (bool): will get the spot contracts
            maxDays (int): The maximum number of days left before delivery
            quoteCoins (list[str]): The quote coins to consider
        Returns:
            dict: The best gap
        """
        gaps = self.fetcher.all_gaps_pd(
            inverse=False, perpetual=perpetual, pretty=False, applyFees=True, spot=spot, quoteCoins=quoteCoins
        )

        # TODO: This filtering should be in all_gaps_pd
        if spot:
            # Keep only the spot contracts
            gaps = gaps.loc[gaps["Buy"].str.contains("Spot")]

        # Buy should have USDC or PERP inside it
        # TODO will remove this as soon as all_gaps_pd is updated
        gaps = gaps.loc[gaps["Buy"].str.contains("USDT|USDC|PERP")]
        # Keep the positive coeffs
        gaps = gaps.loc[gaps["Coeff"] > 0]

        # Take the best proportion (short time, good gap)
        gaps = gaps.loc[gaps["DaysLeft"] < maxDays]
        bestGap = gaps.loc[gaps["Coeff"].idxmax()]

        self.logger.info(f"Best gap\n{bestGap}")

        return bestGap

    @beartype
    async def stay_alive_SF(self, collateral: str = "USDC", quantityUSDC: float | int = 1000):
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

        Args:
            quantityUSDC (float): The quantity in USDC
            collateral (str): The collateral to use, either "USDC" or "USDT"
        """

        # Clear the schedule
        self._new_round()
        # Get best gap
        bestGap = self.CT_best_gap(perpetual=False, spot=True, quoteCoins=[collateral])

        # Set current information
        self.client.longContractSymbol = bestGap["Buy"]
        self.client.shortContractSymbol = bestGap["Sell"]

        # Invoke strategy
        try:
            resp = await self.client.base_executor(
                strategy=self.client.most_basic_arb,
                quantityUSDC=quantityUSDC,
            )
        except Exception as e:
            self.logger.error(f"Error: {e}")
            raise e

        self.logger.info(
            f"\n{resp['longContract']['symbol']}: {resp['longContract']['qty']}\n{resp['shortContract']['symbol']}: {resp['shortContract']['qty']}"
        )
        self.position_info = resp

        self.logger.info("Now we wait...")
        # Monitor the position (write perceived position, compare with real position, log)

        self.watching = True

        # Schedule the monitoring loop (every day, check delta, liquidation risk, etc.)
        await self._handle_on_delivery()

        asyncio.sleep(5)
