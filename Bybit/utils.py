import json
import pandas as pd
import plotly.graph_objects as go

def load_data(file):
    with open(file, "r") as f:
        return json.load(f)
    
def save_data(file, data):
    with open(file, "w") as f:
        json.dump(data, f)

def list_to_pd(data):
    return pd.DataFrame(data, columns=["Timestamp", "Open", "High", "Low", "Close", "Volume", "Turnover"])

def pd_to_list(data):
    return data.to_dict(orient="records")

def format_volume(volume):
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
        
def plot_candles(file):
    """
    Takes a file, transforms it to a pandas DataFrame, and plots it as a candlestick chart.
    The file contains a list of candles in the format:
        [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

    Special thanks to this ressource: https://github.com/SteWolk/kuegiBot/blob/4bf335fbdebeca89b49c4fd7843d70f79235f3fe/kuegi_bot/utils/helper.py#L132
    Args:
        file (str): The file containing the candles data
    Returns:
        dict: {"figure": fig, "dataframe": df}
    """
    data = load_data(file)
    columns = ["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"]

    df = pd.DataFrame(data, columns=columns)

    # Convert timestamps to numeric to get rid of overflow errors
    df["startTime"] = pd.to_numeric(df["startTime"], errors='coerce')
    # Convert timestamps to datetime
    df["startTime"] = pd.to_datetime(df["startTime"], unit="ms", errors='coerce')
    df["startTime"] = df["startTime"].dt.strftime("%Y-%m-%d %H:%M")

    # Convert prices to numeric for proper plotting
    df["openPrice"] = pd.to_numeric(df["openPrice"], errors='coerce')
    df["highPrice"] = pd.to_numeric(df["highPrice"], errors='coerce')
    df["lowPrice"] = pd.to_numeric(df["lowPrice"], errors='coerce')
    df["closePrice"] = pd.to_numeric(df["closePrice"], errors='coerce')
    
    # Use plotly
    fig = go.Figure(data=[go.Candlestick(x=df["startTime"],
                                         open=df["openPrice"],
                                         high=df["highPrice"],
                                         low=df["lowPrice"],
                                         close=df["closePrice"])])
    # Determine min and max prices for more granular y-axis control
    min_price = df[["lowPrice"]].min().values[0]
    max_price = df[["highPrice"]].max().values[0]

    # Add a buffer for the y-axis to extend beyond the min/max prices
    y_min = min_price * 0.99  # 1% below the lowest price
    y_max = max_price * 1.01  # 1% above the highest price

    fig.update_layout(
        title='Candlestick Chart',
        xaxis_title='Time',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        # To avoid overlapping text on x-axis
        xaxis_tickangle=-45,
        # Show a subset of x-axis labels for clarity
        xaxis_tickvals=df["startTime"][::len(df)//5],
            # Y-axis extension and more granular tick intervals
        yaxis=dict(
            range=[y_min, y_max],
            tickmode='linear',
            dtick=(y_max - y_min) / 10
        )
    )

    return {"figure": fig, "dataframe": df}

# TODO: The difference plot is not in the caption I don't know why
def plot_compare(longfile, shortfile):
    """
    Takes two files, transforms them to pandas DataFrames, and plots them as a candlestick chart.
    We suppose that the first dataset is the Long position, second is the Short position.
    Also, they are the same candle size.

    The files contain a list of candles in the format:
        [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

    Args:
        longfile (str): The file containing the long position candles data
        shortfile (str): The file containing the short position candles data
    Returns:
        fig (plotly.graph_objects.Figure): The candlestick chart
    """

    figLong, dfLong = plot_candles(longfile).values()
    figShort, dfShort = plot_candles(shortfile).values()

    diffCalc = 100 - dfLong["closePrice"] * 100 / dfShort["closePrice"]

    fig = go.Figure(data = figLong.data + figShort.data)

    # Display difference
    diff_graph = go.Scatter(
        x=dfShort["startTime"],
        # Not the same number of candles, but it works
        y=(dfShort["closePrice"] + dfLong["closePrice"]) / 2,
        # Displaying text will be ugly as hell
        mode='lines',
        name="Difference",
        textfont=dict(
            color='black',
            size=10
        ),
        text=[f'{diff:.2f}%' for diff in diffCalc],
        showlegend=False
    )
    # Add in the caption
    fig.add_trace(diff_graph)

    # Can do this to display inside a candle's information
    # fig.data[1].text = [f'Difference: {diff:.2f}' for diff in diffCalc]

    # Change the name of traces to distinguish between the two datasets
    fig.data[0].name = longfile
    fig.data[1].name = shortfile

    # Change color to have 1 whole color
    fig.data[0].decreasing.fillcolor = 'green'
    fig.data[0].decreasing.line.color = 'green'

    fig.data[1].increasing.fillcolor = 'red'
    fig.data[1].increasing.line.color = 'red'

    # Last small params for the final plot
    fig.update_layout(
        title='Candlestick Chart',
        xaxis_title='Time',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        # To avoid overlapping text on x-axis
        xaxis_tickangle=-45,
        # Add the draw function
        newshape = dict(
            label=dict(
                texttemplate="Change: %{dy:.2f}",
            )
        )
    )

    fig.update_layout(modebar_add=['drawline'])

    return fig