import plotly.graph_objects as go
from plotly.subplots import make_subplots

from bybit.utils import load_klines_parquet


class Simulator:
    __slots__ = ["encyclopedia"]

    def __init__(self, contract: str | None = None) -> None:
        """Simulate for the contracts.

        Args:
            contract: The contract to simulate

        """
        if contract is None:
            self.encyclopedia = {}
        else:
            self.encyclopedia = {
                contract: load_klines_parquet(contract),
            }

    def plot_candles(
        self, contract: str, lowerlimit: str = "2024-01-01 00:00", upperlimit: str = "2026-01-01 00:00"
    ) -> dict:
        """Take a contract, transforms it to a pandas DataFrame, and plots it as a candlestick chart.

        The contract contains a list of candles in the format:
            [startTime, openPrice, highPrice, lowPrice, closePrice, volume, turnover]

        Special thanks to this ressource: https://github.com/SteWolk/kuegiBot/blob/4bf335fbdebeca89b49c4fd7843d70f79235f3fe/kuegi_bot/utils/helper.py#L132
        Args:
            contract (str): The contract containing the candles data
            lowerlimit (str): The lower bound date to filter the data (format: YYYY-MM-DD HH:MM)
            upperlimit (str): The upper bound date to filter the data (format: YYYY-MM-DD HH:MM)

        Returns:
            dict: {"figure": fig, "dataframe": df}

        """
        if contract not in self.encyclopedia:
            self.encyclopedia[contract] = load_klines_parquet(contract, pretty=True)

        df = self.encyclopedia[contract]

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
                ),
            ],
        )
        # Determine min and max prices for more granular y-axis control
        min_price = df[["lowPrice"]].min().to_numpy()[0]
        max_price = df[["highPrice"]].max().to_numpy()[0]

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
                yaxis={"range": [y_min, y_max], "tickmode": "linear", "dtick": (y_max - y_min) / 10},
            )
        except Exception as e:
            print("Are you sure the date limits are correct?")
            raise e
        return fig, df

    def plot_compare(
        self,
        longContract: str,
        shortContract: str,
        lowerlimit: str = "2024-01-01 00:00",
        upperlimit: str = "2026-01-01 00:00",
    ) -> go.Figure:
        """Compare two datasets in a candlestick chart.

        The two datasets are merged on the 'startTime' column to align them.

        Args:
            longContract (str): File containing the long dataset
            shortContract (str): File containing the short dataset
            lowerlimit (str): The lower bound date to filter the data (format: YYYY-MM-DD HH:MM)
            upperlimit (str): The upper bound date to filter the data (format: YYYY-MM-DD HH:MM)

        Returns:
            go.Figure: The plotly figure

        """
        # Get DataFrames for Long and Short datasets
        try:
            _, dfLong = self.plot_candles(longContract, lowerlimit=lowerlimit, upperlimit=upperlimit)
            _, dfShort = self.plot_candles(shortContract, lowerlimit=lowerlimit, upperlimit=upperlimit)
        except Exception:
            print("One limit is incorrect.")
            raise

        # Merge both DataFrames on 'startTime' to align their data
        merged_df = dfLong.merge(dfShort, suffixes=("_long", "_short"), how="inner", on="startTime")

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
                name=shortContract,
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
                name=longContract,
            ),
            row=1,
            col=1,
        )

        # Change the name of traces to distinguish between the two datasets
        fig.data[0].name = longContract
        fig.data[1].name = shortContract

        # Change color to have 1 whole color
        fig.data[0].decreasing.fillcolor = "green"
        fig.data[0].decreasing.line.color = "green"

        fig.data[1].increasing.fillcolor = "red"
        fig.data[1].increasing.line.color = "red"

        # Calculate and add the difference trace
        diffCalc = 100 - merged_df["closePrice_long"] * 100 / merged_df["closePrice_short"]
        diff_graph = go.Scatter(
            x=merged_df["startTime"],
            y=diffCalc,
            name="Coefficient of difference",
            marker={"color": "blue"},
        )
        fig.add_trace(diff_graph, row=2, col=1)

        # Trendline of difference trace
        trendline = go.Scatter(
            x=merged_df["startTime"],
            y=diffCalc.rolling(window=150).mean(),
            name="Trendline",
            marker={"color": "black"},
        )
        fig.add_trace(trendline, row=2, col=1)

        # Final layout updates
        fig.update_layout(
            title="Candlestick Chart",
            xaxis_title="Time",
            yaxis_title="Price",
            xaxis_rangeslider_visible=False,
            xaxis_tickangle=-45,
            newshape={
                "label": {
                    "texttemplate": "Change: %{dy:.2f}",
                },
            },
        )

        fig.update_layout(modebar_add=["drawline"])
        return fig
