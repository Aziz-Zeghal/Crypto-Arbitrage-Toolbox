import sys
import asyncio
from datetime import datetime

sys.path.append("Bybit")

from Bybit.client import BybitClient
import Bybit.utils


async def main():
    # Create a Bybit client
    now = datetime.now()
    client = BybitClient(demo=True)
    then = datetime.now()
    print(f"Time taken to create the client: {then - now}")
    # BTCUSDT	BTC-29NOV24
    await client.Eris("BTCUSDT", "BTC-29NOV24", quantityUSDC=400, minimumGap=-0.23)


if __name__ == "__main__":
    asyncio.run(main())
