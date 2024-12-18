import schedule
import time
import threading
import asyncio


async def async_task():
    print("Async task is running")


def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


async def main():
    schedule.every(5).seconds.do(async_task)
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    while True:
        await asyncio.sleep(1)


asyncio.run(main())
