import asyncio
import datetime

from bybit.client import UlysseSpotFut
from bybit.greek_master import GreekMaster
from bybit.utils import ColorFormatter


def init() -> GreekMaster:
    """Make the GreekMaster with specified client."""
    # Configure logging
    ColorFormatter.configure_logging(verbose=1, run_name="actual_run.log")

    # Create a Bybit client
    now = datetime.datetime.now(tz=datetime.UTC)
    Master = GreekMaster(client=UlysseSpotFut(demo=True))
    then = datetime.datetime.now(tz=datetime.UTC)
    print(f"Time taken to create the client: {then - now}")
    return Master


async def main() -> None:
    """Make Main loop for the application."""
    # Very important, else we will get recursion errors in the long run
    Master = init()

    # TODO: Env variable for this to have a clean exit
    while True:
        try:
            await Master.stable_collateral(selector=Master.quickest_gap, quantityUSDC=3000)
        except Exception:
            print("Something happened, exiting")
            raise


if __name__ == "__main__":
    asyncio.run(main())
