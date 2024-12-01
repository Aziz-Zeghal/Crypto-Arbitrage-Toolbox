import json
import pandas as pd
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime


def save_klines_parquet(file: str, df: pd.DataFrame) -> None:
    """
    Saves a DataFrame to a parquet file.
    We do NOT format it because we want to keep the raw data.

    Args:
        file (str): File to save
        df (pd.DataFrame): DataFrame to save
    """

    df.to_parquet(file)


def load_klines_parquet(file: str, pretty=False) -> pd.DataFrame:
    """
    Loads a parquet file and returns a DataFrame.

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
    """
    Converts a date to a human-readable date.
    Takes a date in the format DD/MM/YYYY or YYYY-MM-DD HH:MM and converts it to epoch time.

    Args:
        date (str): Date to convert
    Returns:
        int: Epoch time
    """
    # Check the format of the date

    # We have DD/MM/YYYY
    if "/" in date:
        return int(datetime.datetime.strptime(date, "%d/%m/%Y").timestamp() * 1000)
    # We have YYYY-MM-DD HH:MM
    else:
        return int(datetime.datetime.strptime(date, "%Y-%m-%d %H:%M").timestamp() * 1000)


def get_date(epoch: int) -> str:
    """
    Converts an epoch to a human-readable date.

    Args:
        epoch (int): Epoch time
    Returns:
        str: Date
    """
    return datetime.datetime.fromtimestamp(epoch / 1000).strftime("%d/%m/%Y")


def format_volume(volume: int) -> str:
    """
    Converts volume into a human-readable format, like 656666 -> 656.66K.

    Args:
        volume (int): Volume to format
    Returns:
        str: Formatted volume
    """
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f}B"
    elif volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f}M"
    elif volume >= 1_000:
        return f"{volume / 1_000:.2f}K"
    else:
        return str(volume)


def plot_candles(file: str, lowerlimit="2024-01-01 00:00", upperlimit="2026-01-01 00:00") -> dict:
    """
    Takes a file, transforms it to a pandas DataFrame, and plots it as a candlestick chart.
    The file contains a list of candles in the format:
        [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

    Special thanks to this ressource: https://github.com/SteWolk/kuegiBot/blob/4bf335fbdebeca89b49c4fd7843d70f79235f3fe/kuegi_bot/utils/helper.py#L132
    Args:
        file (str): The file containing the candles data
        lowerlimit (str): The lower bound date to filter the data (format: YYYY-MM-DD HH:MM)
        upperlimit (str): The upper bound date to filter the data (format: YYYY-MM-DD HH:MM)
    Returns:
        dict: {"figure": fig, "dataframe": df}
    """
    df = load_klines_parquet(file, pretty=True)

    # Filter according to the date
    # This syntax looks like numpy
    df = df[(df["startTime"] >= lowerlimit) & (df["startTime"] <= upperlimit)]

    # Use plotly
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["startTime"],
                open=df["openPrice"],
                high=df["highPrice"],
                low=df["lowPrice"],
                close=df["closePrice"],
            )
        ]
    )
    # Determine min and max prices for more granular y-axis control
    min_price = df[["lowPrice"]].min().values[0]
    max_price = df[["highPrice"]].max().values[0]

    # Add a buffer for the y-axis to extend beyond the min/max prices
    y_min = min_price * 0.99  # 1% below the lowest price
    y_max = max_price * 1.01  # 1% above the highest price

    try:
        fig.update_layout(
            title="Candlestick Chart",
            xaxis_title="Time",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,
            # To avoid overlapping text on x-axis
            xaxis_tickangle=-45,
            # Show a subset of x-axis labels for clarity
            xaxis_tickvals=df["startTime"][:: len(df) // 5],
            # Y-axis extension and more granular tick intervals
            yaxis=dict(range=[y_min, y_max], tickmode="linear", dtick=(y_max - y_min) / 10),
        )
    except Exception as e:
        print("Are you sure the date limits are correct?")
        raise e
    return fig, df


def plot_compare(
    longfile: str, shortfile: str, lowerlimit="2024-01-01 00:00", upperlimit="2026-01-01 00:00"
) -> go.Figure:
    """
    Compares two datasets in a candlestick chart.
    The two datasets are merged on the 'startTime' column to align them.

    Args:
        longfile (str): File containing the long dataset
        shortfile (str): File containing the short dataset
        lowerlimit (str): The lower bound date to filter the data (format: YYYY-MM-DD HH:MM)
        upperlimit (str): The upper bound date to filter the data (format: YYYY-MM-DD HH:MM)

    Returns:
        go.Figure: The plotly figure
    """
    # Get DataFrames for Long and Short datasets
    try:
        _, dfLong = plot_candles(longfile, lowerlimit=lowerlimit, upperlimit=upperlimit)
        _, dfShort = plot_candles(shortfile, lowerlimit=lowerlimit, upperlimit=upperlimit)
    except Exception as e:
        print("One limit is incorrect.")
        raise e

    # Merge both DataFrames on 'startTime' to align their data
    merged_df = pd.merge(dfLong, dfShort, suffixes=("_long", "_short"), how="inner", on="startTime")

    # Initialize figure
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.02)

    # Add Long position candlestick with specific color
    fig.add_trace(
        go.Candlestick(
            x=merged_df["startTime"],
            open=merged_df["openPrice_long"],
            high=merged_df["highPrice_long"],
            low=merged_df["lowPrice_long"],
            close=merged_df["closePrice_long"],
            name=shortfile,
        ),
        row=1,
        col=1,
    )

    # Add Short position candlestick with specific color
    fig.add_trace(
        go.Candlestick(
            x=merged_df["startTime"],
            open=merged_df["openPrice_short"],
            high=merged_df["highPrice_short"],
            low=merged_df["lowPrice_short"],
            close=merged_df["closePrice_short"],
            name=longfile,
        ),
        row=1,
        col=1,
    )

    # Change the name of traces to distinguish between the two datasets
    fig.data[0].name = longfile
    fig.data[1].name = shortfile

    # Change color to have 1 whole color
    fig.data[0].decreasing.fillcolor = "green"
    fig.data[0].decreasing.line.color = "green"

    fig.data[1].increasing.fillcolor = "red"
    fig.data[1].increasing.line.color = "red"

    # Calculate and add the difference trace
    diffCalc = 100 - merged_df["closePrice_long"] * 100 / merged_df["closePrice_short"]
    diff_graph = go.Scatter(
        x=merged_df["startTime"], y=diffCalc, name="Coefficient of difference", marker=dict(color="blue")
    )
    fig.add_trace(diff_graph, row=2, col=1)

    # Trendline of difference trace
    trendline = go.Scatter(
        x=merged_df["startTime"],
        y=diffCalc.rolling(window=150).mean(),
        name="Trendline",
        marker=dict(color="black"),
    )
    fig.add_trace(trendline, row=2, col=1)

    # Final layout updates
    fig.update_layout(
        title="Candlestick Chart",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
        xaxis_tickangle=-45,
        newshape=dict(
            label=dict(
                texttemplate="Change: %{dy:.2f}",
            )
        ),
    )

    fig.update_layout(modebar_add=["drawline"])
    return fig


# Deprecated
def load_data(file: str) -> list:
    with open(file, "r") as f:
        return json.load(f)


def save_data(file: str, data: list) -> None:
    with open(file, "w") as f:
        json.dump(data, f)


def json_to_parquet(file: str) -> None:
    """
    Converts a JSON file to a parquet file.

    Args:
        file (str): File to convert
    """
    data = load_data(file)
    df = pd.DataFrame(
        data, columns=["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"]
    )
    save_klines_parquet(file.replace(".json", ".parquet"), df)


class ColorFormatter(logging.Formatter):
    """
    Custom formatter to colorize log level names based on their severity.
    """

    def format(self, record):
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
