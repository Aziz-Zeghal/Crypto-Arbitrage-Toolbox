import sys
import asyncio
from datetime import datetime

sys.path.append("Bybit")

from Bybit.greekMaster import GreekMaster


async def main():
    # Create a Bybit client
    now = datetime.now()
    Master = GreekMaster(demo=True, verbose=1)
    then = datetime.now()
    print(f"Time taken to create the client: {then - now}")
    # BTCUSDT	BTC-29NOV24
    await Master.Eris("BTCUSDT", "BTC-20DEC24", quantityUSDC=400, minimumGap=-0.23)


if __name__ == "__main__":
    asyncio.run(main())
