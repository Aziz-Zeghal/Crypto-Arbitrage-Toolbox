import asyncio
import datetime

from bybit.greek_master import SpotFutStrategos
from bybit.utils import ColorFormatter

# TODO: Here, include argparse


def init() -> SpotFutStrategos:
    # Configure logging
    ColorFormatter.configure_logging(verbose=1)

    # Create a Bybit client
    now = datetime.datetime.now(tz=datetime.UTC)
    Master = SpotFutStrategos(demo=True)
    then = datetime.datetime.now(tz=datetime.UTC)
    print(f"Time taken to create the client: {then - now}")
    return Master


async def run_forever(Master: SpotFutStrategos) -> None:
    try:
        # Master.CT_best_gap(perpetual=True, spot=False)
        # await Master.one_shot_PF(quantityUSDC=1000, leverage="1", strategy=Master.client.most_basic_arb)
        # await Master.save_klines(dest="store")
        await Master.stable_collateral(quantityUSDC=1000)
    except Exception:
        print("Something happened, exiting")
        raise


async def main() -> None:
    # Very important, else we will get recursion errors in the long run
    # TODO: Env variable for this to have a clean exit
    Master = init()
    while True:
        await run_forever(Master)


if __name__ == "__main__":
    asyncio.run(main())
