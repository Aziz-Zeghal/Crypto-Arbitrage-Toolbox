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

def plot_candles(file):
    """
    Takes a file, transforms it to a pandas DataFrame, and plots it as a candlestick chart.
    The file contains a list of candles in the format:
        [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

    Special thanks to this ressource: https://github.com/SteWolk/kuegiBot/blob/4bf335fbdebeca89b49c4fd7843d70f79235f3fe/kuegi_bot/utils/helper.py#L132
    Args:
        file (str): The file containing the candles data
    Returns:
        fig (plotly.graph_objects.Figure): The candlestick chart
    """
    data = load_data(file)
    columns = ["startTime", "openPrice", "highPrice", "lowPrice", "closePrice", "volume", "turnover"]

    df = pd.DataFrame(data, columns=columns)

    # Convert timestamps to numeric to get rid of overflow errors
    df["startTime"] = pd.to_numeric(df["startTime"], errors='coerce')
    # Convert timestamps to datetime
    df["startTime"] = pd.to_datetime(df["startTime"], unit="ms", errors='coerce')
    df["startTime"] = df["startTime"].dt.strftime("%Y-%m-%d %H:%M")

    # Use plotly
    fig = go.Figure(data=[go.Candlestick(x=df["startTime"],
                                         open=df["openPrice"],
                                         high=df["highPrice"],
                                         low=df["lowPrice"],
                                         close=df["closePrice"])])
    
    fig.update_layout(
        title='Candlestick Chart',
        xaxis_title='Time',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        # To avoid overlapping text on x-axis
        xaxis_tickangle=-45,
        # Show a subset of x-axis labels for clarity
        xaxis_tickvals=df["startTime"][::len(df)//5]
    )
    return fig