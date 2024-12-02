import sys
import asyncio
from datetime import datetime
import logging

sys.path.append("Bybit")

from Bybit.greekMaster import GreekMaster
from Bybit.utils import configure_logging


async def main():
    # Configure logging
    configure_logging(verbose=1)

    # Create a Bybit client
    now = datetime.now()
    Master = GreekMaster(demo=True)
    then = datetime.now()
    print(f"Time taken to create the client: {then - now}")
    # BTCUSDT	BTC-29NOV24
    try:
        await Master.one_shot_PF(strategy=Master.client.check_arbitrage, quantityUSDC=1000, leverage="1")
    except Exception:
        print("Something happened, exiting")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
