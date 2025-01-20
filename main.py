import sys
import asyncio
from datetime import datetime

sys.path.append("Bybit")

from Bybit.greekMaster import SpotFutStrategos
from Bybit.utils import ColorFormatter

# TODO: Here, include argparse


def init():
    # Configure logging
    ColorFormatter.configure_logging(verbose=1)

    # Create a Bybit client
    now = datetime.now()
    Master = SpotFutStrategos(demo=True)
    then = datetime.now()
    print(f"Time taken to create the client: {then - now}")
    return Master


async def run_forever(Master: SpotFutStrategos):
    try:
        # Master.CT_best_gap(perpetual=True, spot=False)
        # await Master.one_shot_PF(quantityUSDC=1000, leverage="1", strategy=Master.client.most_basic_arb)
        # await Master.save_klines(dest="store")
        await Master.stay_alive_SF(quantityUSDC=1000)
    except Exception as e:
        print("Something happened, exiting")
        raise e


async def main():
    # Very important, else we will get recursion errors in the long run
    # TODO: Env variable for this to have a clean exit
    Master = init()
    while True:
        await run_forever(Master)


if __name__ == "__main__":
    asyncio.run(main())
