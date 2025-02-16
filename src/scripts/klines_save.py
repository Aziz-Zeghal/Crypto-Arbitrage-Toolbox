import asyncio  # noqa: INP001
import sys

import schedule

sys.path.append("..")

from bybit.api_fetcher import Fetcher
from bybit.utils import ColorFormatter


async def main() -> None:
    """Take the klines and saves them to a file."""
    schedule.every().friday.at("09:05", "Europe/Paris").do(
        lambda: asyncio.ensure_future(fetcher.save_klines(dest="../store"))
    )

    while True:
        schedule.run_pending()
        n = schedule.idle_seconds()
        await asyncio.sleep(n)


if __name__ == "__main__":
    ColorFormatter.configure_logging(verbose=1, run_name="save_klines.log")
    fetcher = Fetcher(demo=True)

    try:
        asyncio.run(main())
    except Exception:
        fetcher.logger.exception("Error")
        raise
