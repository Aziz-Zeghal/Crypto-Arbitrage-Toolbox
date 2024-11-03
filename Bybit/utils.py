import json
import pandas as pd
import plotly.graph_objects as go
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


def plot_candles(file: str, dateLimit=None) -> dict:
    """
    Takes a file, transforms it to a pandas DataFrame, and plots it as a candlestick chart.
    The file contains a list of candles in the format:
        [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

    Special thanks to this ressource: https://github.com/SteWolk/kuegiBot/blob/4bf335fbdebeca89b49c4fd7843d70f79235f3fe/kuegi_bot/utils/helper.py#L132
    Args:
        file (str): The file containing the candles data
        dateLimit (str): The date to filter the data (format: YYYY-MM-DD HH:MM)
    Returns:
        dict: {"figure": fig, "dataframe": df}
    """
    df = load_klines_parquet(file, pretty=True)

    # Filter according to the date
    if dateLimit:
        # This syntax looks like numpy
        df = df[df["startTime"] >= dateLimit]

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

    return fig, df


# TODO: The difference plot is not in the caption I don't know why
def plot_compare(longfile: str, shortfile: str, dateLimit=None) -> go.Figure:
    """
    Takes two files, transforms them to pandas DataFrames, and plots them as a candlestick chart.
    We suppose that the first dataset is the Long position, second is the Short position.
    Also, they are the same candle size.

    Args:
        longfile (str): The file containing the long candles data
        shortfile (str): The file containing the short candles data
        dateLimit (str): The date to filter the data (format: YYYY-MM-DD HH:MM)
    Returns:
        go.Figure: The figure containing both datasets
    """
    figLong, dfLong = plot_candles(longfile, dateLimit=dateLimit)
    figShort, dfShort = plot_candles(shortfile, dateLimit=dateLimit)

    # Merge both DataFrames on the 'startTime' column to align their data
    merged_df = pd.merge(dfShort, dfLong, suffixes=("_long", "_short"), how="inner", on="startTime")

    # Calculate the difference only for aligned data
    # We do this to stop calculating difference when one of the datasets ends
    diffCalc = 100 - merged_df["closePrice_long"] * 100 / merged_df["closePrice_short"]

    # Create the figure
    fig = go.Figure(data=figLong.data + figShort.data)

    # Display the difference
    diff_graph = go.Scatter(
        x=merged_df["startTime"],
        y=(merged_df["closePrice_short"] + merged_df["closePrice_long"]) / 2,
        mode="lines",
        name="Difference",
        textfont=dict(color="black", size=10),
        text=[f"{diff:.2f}%" for diff in diffCalc],
        showlegend=False,
    )

    # Add the difference trace to the figure
    fig.add_trace(diff_graph)

    # Change the name of traces to distinguish between the two datasets
    fig.data[0].name = longfile
    fig.data[1].name = shortfile

    # Change color to have 1 whole color
    fig.data[0].decreasing.fillcolor = "green"
    fig.data[0].decreasing.line.color = "green"

    fig.data[1].increasing.fillcolor = "red"
    fig.data[1].increasing.line.color = "red"

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
