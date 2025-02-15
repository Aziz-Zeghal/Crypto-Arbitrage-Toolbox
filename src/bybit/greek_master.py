import asyncio
import datetime
import logging
from collections.abc import Callable

import schedule
from beartype import beartype

from bybit.client import BybitClient
from bybit.utils import get_date


class GreekMaster:
    __slots__ = ["client", "fetcher", "logger", "sch", "watching"]

    @beartype
    def __init__(self, client: BybitClient) -> None:
        """Logic for all products.

        Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry.
        Talks to Bybit through the client.
        Can send notifications and logs arbitrage events.

        GreekMaster is an interface for its child classes.

        2 types of methods:
            - Selectors: The method to choose the best pair of contracts
            - Executors: Setup application, call the strategy, monitor, then exit.
        Defines:
            - client (BybitClient): Client for the Bybit API
            - fetcher (Fetcher): Fetcher for the Bybit API
            - contracts (list): List of all the current contracts
            - logger (logging.Logger): Logger for the client
            - watching: Boolean to know if GreekMaster has control

        Implements:
            - _new_round: Cleanup for next arbitrage round
            - _monitor: Monitor the accounts, check the positions, the liquidation risk, etc.
            - _exit_on_delivery: Handler called every second to check if delivery arrived or not (uses _select_order)
            - _friday_job: Handler for the delivery day
            - _handle_on_delivery: Handler to exit on delivery day (uses _exit_amount)

        """
        self.client: BybitClient = client

        self.fetcher = self.client.fetcher

        self.logger = logging.getLogger("greekMaster")

        self.logger.info("GreekMaster initialized")

        self.sch = schedule.Scheduler()
        self.watching = False

    def _new_round(self) -> None:
        """Cleanup for next arbitrage round."""
        self.sch.clear()

        self.client.new_round()

        self.watching = False

    async def _monitor(self) -> None:
        """Monitor the accounts, check the positions, the liquidation risk, etc.

        Writes inside position_info

        """
        self.logger.info("Monitoring the account...")

        ret = self.fetcher.get_wallet()
        if ret:
            logging.info(
                f"""--------------------
                {ret}
                --------------------""",
            )

        ret = await self.fetcher.get_greeks("BTC")
        if ret:
            logging.info(
                f"""--------------------
                {ret}
                --------------------""",
            )

    async def _exit_on_delivery(self):  # noqa: ANN202
        """Call handler every second to check if delivery arrived or not.

        Uses _select_order to exit the position when delivery arrives.
        """
        shortContract = self.client.shortContract

        res = await self.fetcher.get_position(symbol=shortContract["symbol"])

        # If the position is 0, delivery arrived, sell spot.
        if res["qty"] == "0" or res["positionValue"] == "":
            # Exit position (can also be a rollover)
            await self.client.exit_amount()

            (setattr(self, "watching", False),)
            self.logger.info("Delivery arrived, exited arbitrage !")

            # Here, you would want to return self.sch.CancelJob.
            # But, we are in an async function, so we cannot return it easily.

    # TODO: Use aioschedule + run_until_complete
    def _friday_job(self, epochTime: int) -> None:
        """Job for the delivery day.

        Calls _exit_on_delivery every second until the delivery arrives.
        """
        self.logger.info(f"{epochTime - datetime.datetime.now(datetime.UTC).timestamp() * 1000}")
        # If we are 30 minutes before the delivery time
        if (epochTime - datetime.datetime.now(datetime.UTC).timestamp() * 1000) < 1200 * 1000:
            self.logger.info("Delivery day ! Setting up surveillance...")

            # When the position is 0, delivery arrived, sell spot.
            self.sch.every().second.do(lambda: asyncio.ensure_future(self._exit_on_delivery()))

            # Job is no longer useful, so remove it
            return schedule.CancelJob
        return None

        # Else, we are friday but not yet the delivery day

    async def _handle_on_delivery(self) -> None:
        """Call handler after entering arbitrage.

        Short contract is always supposed to be a future contract (perpetual/linear/inverse)
        """
        epochTime = int(
            self.fetcher.session.get_tickers(symbol=self.client.shortContract["symbol"], category="linear")["result"][
                "list"
            ][0]["deliveryTime"],
        )

        self.logger.info(f"Delivery date at 8:00AM UTC for: {get_date(epochTime)}")

        # SCHEDULING PART
        self.sch.every().minute.do(lambda: asyncio.ensure_future(self._monitor()))
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

    def best_gap(
        self,
        maxDays: int = 25,
        quoteCoins: list[str] = ["USDC"],
    ):
        """Find the best gap for spot and future contracts.

        Args:
            maxDays (int): The maximum number of days left before delivery
            quoteCoins (list[str]): The quote coins to consider
        Returns:
            dict: The best gap

        """
        gaps = self.fetcher.all_gaps_pd(
            inverse=False,
            perpetual=False,
            applyFees=True,
            spot=True,
            quoteCoins=quoteCoins,
        )

        # Keep the positive coeffs
        gaps = gaps.loc[gaps["Coeff"] > 0]

        # Take the best proportion (short time, good gap)
        gaps = gaps.loc[gaps["DaysLeft"] < maxDays]
        bestGap = gaps.loc[gaps["Coeff"].idxmax()]

        self.logger.info(f"Best gap\n{bestGap}")

        return bestGap

    def quickest_gap(self) -> dict:
        """Find the quickest gap for spot and future contracts."""
        gaps = self.fetcher.all_gaps_pd(
            inverse=False,
            perpetual=False,
            applyFees=True,
            spot=True,
            quoteCoins=["USDC"],
        )

        # Take the gap that finishes the soonest
        bestGap = gaps.loc[gaps["DaysLeft"].idxmin()]

        self.logger.info(f"Best gap\n{bestGap}")

        return bestGap

    # TODO: Callable should also take kwargs if selectors have parameters
    @beartype
    async def stable_collateral(
        self, selector: Callable[["GreekMaster"], dict] = quickest_gap, quantityUSDC: float | int = 0
    ) -> None:
        """Buy the spot, short the future. The classic strategy.

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
            quantityUSDC (float): The quantity in USDC. If 0, will take the max of the wallet
            selector (callable of greek_master): The selector for the contracts (should be implemented in GreekMaster)

        """
        # Clear the schedule
        self._new_round()

        # If no quantity was indicated, get the max of the wallet
        if quantityUSDC == 0:
            quantityUSDC = self.fetcher.get_wallet()["USDC"]

        self.client.balance = quantityUSDC
        # Get the Pandas series (Buy, Sell)
        contractPair = selector()

        # Set current information
        self.client.longContract["symbol"] = contractPair["Buy"]
        self.client.shortContract["symbol"] = contractPair["Sell"]

        # Invoke strategy
        try:
            await self.client.base_executor(
                strategy=self.client.most_basic_arb,
            )
        except Exception:
            self.logger.exception("Error")
            raise

        self.logger.info(
            f"""
            {self.client.longContract["symbol"]}: {self.client.longContract["qty"]}
            {self.client.shortContract["symbol"]}: {self.client.shortContract["qty"]}
            """,
        )

        self.logger.info("Now we wait...")
        # Monitor the position (write perceived position, compare with real position, log)

        self.watching = True

        # Schedule the monitoring loop (every day, check delta, liquidation risk, etc.)
        await self._handle_on_delivery()

        asyncio.sleep(5)
