import threading
import time
import schedule
import signal
import sys


def run_continuously(interval=1):
    """Continuously run, while executing pending jobs at each elapsed time interval."""
    cease_continuous_run = threading.Event()

    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)

    continuous_thread = ScheduleThread()
    continuous_thread.start()
    return cease_continuous_run


def background_job():
    print("Hello from the background thread")


def handle_sigint(signum, frame):
    print("\nCtrl+C detected! Stopping all threads.")
    stop_run_continuously.set()  # Signal the scheduler thread to stop
    sys.exit(0)  # Exit the program


# Register the SIGINT handler
signal.signal(signal.SIGINT, handle_sigint)

# Schedule the background job
schedule.every().second.do(background_job)

# Start the background thread
stop_run_continuously = run_continuously()

try:
    # Keep the main thread alive
    while not stop_run_continuously.is_set():
        time.sleep(0.1)
except KeyboardInterrupt:
    # Handle unexpected manual interrupts gracefully
    handle_sigint(None, None)

print("Program terminated.")
