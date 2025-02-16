import datetime
import logging
import sys

import pandas as pd


def save_klines_parquet(file: str, df: pd.DataFrame) -> None:
    """Save a DataFrame to a parquet file.

    We do NOT format it because we want to keep the raw data.

    Args:
        file (str): File to save
        df (pd.DataFrame): DataFrame to save

    """
    df.to_parquet(file)


def load_klines_parquet(file: str, pretty: bool = False) -> pd.DataFrame:
    """Load a parquet file and returns a DataFrame.

    Args:
        file (str): File to load
        pretty (bool): If True, will format the DataFrame

    """
    df = pd.read_parquet(file)

    if pretty:
        # Convert timestamps to numeric to get rid of overflow errors
        df["startTime"] = pd.to_numeric(df["startTime"], errors="coerce")
        # Convert timestamps to datetime
        df["startTime"] = pd.to_datetime(df["startTime"], unit="ms", errors="coerce")
        df["startTime"] = df["startTime"].dt.strftime("%Y-%m-%d %H:%M")

        # Convert prices to numeric for proper plotting
        df["openPrice"] = pd.to_numeric(df["openPrice"], errors="coerce")
        df["highPrice"] = pd.to_numeric(df["highPrice"], errors="coerce")
        df["lowPrice"] = pd.to_numeric(df["lowPrice"], errors="coerce")
        df["closePrice"] = pd.to_numeric(df["closePrice"], errors="coerce")

    return df


def get_epoch(date: str) -> int:
    """Convert a date to a human-readable date.

    Takes a date in the format DD/MM/YYYY or YYYY-MM-DD HH:MM and converts it to epoch time.

    Args:
        date (str): Date to convert
    Returns:
        int: Epoch time

    """
    # Check the format of the date

    # We have DD/MM/YYYY
    if "/" in date:
        return int(datetime.datetime.strptime(date, "%d/%m/%Y").replace(tzinfo=datetime.UTC).timestamp() * 1000)
    # We have YYYY-MM-DD HH:MM
    return int(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M").replace(tzinfo=datetime.UTC).timestamp() * 1000)


def get_date(epoch: int | str) -> str:
    """Convert an epoch to a human-readable date.

    WARNING: epoch must be in milliseconds.

    Args:
        epoch (int): Epoch time
    Returns:
        str: Date

    """
    if isinstance(epoch, str):
        epoch = int(epoch)
    return datetime.datetime.fromtimestamp(epoch / 1000, tz=datetime.UTC).strftime("%d/%m/%Y")


def format_volume(volume: int) -> str:
    """Convert volume into a human-readable format, like 656666 -> 656.66K.

    Args:
        volume (int): Volume to format
    Returns:
        str: Formatted volume

    """
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f}B"
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f}M"
    if volume >= 1_000:
        return f"{volume / 1_000:.2f}K"
    return str(volume)


class ColorFormatter(logging.Formatter):
    """Custom formatter to colorize log level names based on their severity."""

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record with colors based on the log level.

        Args:
            record (logging.LogRecord): The log record to format.

        Returns:
            str: The formatted log record as a string.

        """
        # Define color mappings for log levels
        level_colors = {
            "DEBUG": "\033[37m",  # White
            "INFO": "\033[32m",  # Green
            "WARNING": "\033[33m",  # Yellow
            "ERROR": "\033[31m",  # Red
            "CRITICAL": "\033[41m",  # Red background
        }
        reset = "\033[0m"

        # Apply color to levelname
        record.levelname = f"{level_colors.get(record.levelname, '')}{record.levelname}{reset}"
        return super().format(record)

    @staticmethod
    def configure_logging(run_name: str = "test.log", verbose: int = 0) -> None:
        """Configure logging for all loggers in the application.

        Args:
            verbose (int): Controls the verbosity level:
                0 - WARNING (default)
                1 - INFO
                2 or more - DEBUG
            run_name (str): Name of the logging file

        """
        # Default log level
        log_level = logging.WARNING
        if verbose == 1:
            log_level = logging.INFO
        elif verbose >= 2:
            log_level = logging.DEBUG

        # Formatter with colors
        formatter = ColorFormatter("\033[36m%(asctime)s\033[0m - %(name)s - %(levelname)s - %(message)s")

        # Stream handler for console output
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)

        # Stream handler for file output
        file_handler = logging.FileHandler(run_name)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

        # Apply the configuration to the root logger
        logging.basicConfig(
            level=log_level,
            handlers=[console_handler, file_handler],
        )

        # Test message to confirm configuration
        logging.getLogger().info("Global logging configuration applied with verbosity level %d", verbose)
