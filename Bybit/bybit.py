from pybit.unified_trading import HTTP
from datetime import datetime
import pandas as pd
import sys
import os

if __name__ == "__main__":
    from utils import load_data, save_data, format_volume

    # We add the path to the sys.path
    # sys.path is contains a list of directories that the interpreter will search in for the required module.
    sys.path.append(os.path.dirname(os.path.abspath("keys.py")))
else:
    # We are running this script as a module
    from .utils import load_data, save_data, format_volume

import keys


class BybitClient:
    def __init__(self):
        """
        Initialize the Bybit session
        """
        self.session = HTTP(api_key=keys.bybitPKey, api_secret=keys.bybitSKey)

    def get_USDC_BTC(self):
        """
        Gives some information on USDC and BTC

        Link: https://bybit-exchange.github.io/docs/v5/account/wallet-balance
        Returns:
            dict:
                Balance: Total balance in USD
                BTC: dict:
                    Quantity: Quantity of BTC
                    Available: Available to withdraw
                    usdValue: Value in USD
                USDC: dict:
                    Quantity: Quantity of USDC
                    Available: Available to withdraw
                    usdValue: Value in USD
        """
        btcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="BTC")["result"]["list"][0]
        usdcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDC")["result"]["list"][0]

        totalBalance = btcDict["totalEquity"]

        # Just to make the code more readable
        btcDict = btcDict["coin"][0]
        usdcDict = usdcDict["coin"][0]

        btcValue = {
            "Quantity": btcDict["equity"],
            "Available": btcDict["availableToWithdraw"],
            "usdValue": btcDict["usdValue"],
        }

        usdcValue = {
            "Quantity": usdcDict["equity"],
            "Available": usdcDict["availableToWithdraw"],
            "usdValue": usdcDict["usdValue"],
        }

        return {"Balance": totalBalance, "BTC": btcValue, "USDC": usdcValue}

    def get_futures(self, coin="BTC"):
        """
        Get all markets for a given coin

        Link: https://bybit-exchange.github.io/docs/v5/market/instrument
        Args:
            coin (str): Either BTC or ETH
        Return:
            list: List of all the future contracts for the given coin sorted by expiry date
        """

        # Sadly, I do not think there is a better way to do this
        # But the contracts themself are not always queried
        pairs = self.session.get_instruments_info(category="linear")
        markets = []
        for p in pairs["result"]["list"]:
            # Looks like BTC-01NOV24
            if p["symbol"].startswith(coin + "-"):
                markets.append(p["symbol"])

        # Function to extract and convert the date part to a datetime object
        def extract_date(contract):
            date_str = contract.split("-")[-1]  # Extracts the date part, e.g., '01NOV24'
            return datetime.strptime(date_str, "%d%b%y")

        # Sort the markets by expiry date
        sorted_markets = sorted(markets, key=extract_date)
        return sorted_markets

    def get_gap(self, longTickers, shortTickers):
        """
        Get the gap between two future contracts with their tickers
        CAREFUL: We suppose the longTickers is closer to delivery than shortTickers
        This means that the price of longTickers should be lower than shortTickers

        Args:
            longTickers (dict): Tickers of the first future contract
            shortTickers (dict): Tickers of the second future contract
        Return:
            dict:
                gap: The gap between the two contracts
                coeff: The coefficient of the gap
                apr: The annual percentage rate
                daysLeft: The number of days left before the delivery of the first contract
        """

        # | Volume of the future contract
        longVolume = float(longTickers["turnover24h"])
        shortVolume = float(shortTickers["turnover24h"])
        # - Cumulative volume
        cumVolume = longVolume + shortVolume

        # | Price of the future contract
        longPrice = float(longTickers["lastPrice"])
        shortPrice = float(shortTickers["lastPrice"])
        # - Calculate the gap
        gap = shortPrice - longPrice
        # - Calculate the coefficient
        coeff = round((shortPrice / longPrice - 1) * 100, 3)

        # | Time to delivery for the long contract, epoch in milliseconds (convert to seconds)
        longDelivery = int(longTickers["deliveryTime"]) / 1000
        todayDate = datetime.now().timestamp()
        # - Time to delivery
        # Transform to int to round floor (no need for Math.floor)
        daysLeft = (longDelivery - todayDate) / 86400 + 1

        apr = coeff * 365 / daysLeft / 2
        return {
            "gap": gap,
            "coeff": coeff,
            "apr": apr,
            "daysLeft": daysLeft,
            "cumVolume": cumVolume,
        }

    def all_gaps(self, pretty=True):
        """
        Get all the gaps for all the future contracts

        Args:
            pretty (bool): If True, will format the elements in a more readable way
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """
        btcFutureContracts = self.get_futures("BTC")
        btcTickers = []
        # First, get the tickers of every future contract
        for future in btcFutureContracts:
            btcTickers.append(self.session.get_tickers(symbol=future, category="linear")["result"]["list"][0])

        # Now, we can calculate the gaps
        rows = []
        for longTicker in btcTickers:
            # Take all futures after it
            for shortTicker in btcTickers[btcTickers.index(longTicker) + 1 :]:
                gap = self.get_gap(longTicker, shortTicker)
                vol = int(gap["cumVolume"])
                if pretty:
                    rows.append(
                        {
                            "Buy": longTicker["symbol"],
                            "Sell": shortTicker["symbol"],
                            "Gap": f"$ {gap['gap']:.2f}",
                            "Coeff": f"{gap['coeff']:.2f} %",
                            "APR": f"{gap['apr']:.2f} %",
                            "DaysLeft": int(gap["daysLeft"]),
                            "CumVolume": format_volume(vol),
                        }
                    )
                else:
                    rows.append(
                        {
                            "Buy": longTicker["symbol"],
                            "Sell": shortTicker["symbol"],
                            "Gap": gap["gap"],
                            "Coeff": gap["coeff"],
                            "APR": gap["apr"],
                            "DaysLeft": gap["daysLeft"],
                            "CumVolume": gap["cumVolume"],
                        }
                    )

        gaps = pd.DataFrame(rows)
        return gaps

    def all_gaps_pd(self, pretty=True):
        """
        Get all the gaps for all the future contracts

        Args:
            pretty (bool): If True, will format the elements in a more readable way
        Returns:
            pd.DataFrame: DataFrame containing all the gaps
        """

        btcFutureContracts = self.get_futures("BTC")

        # First, get the tickers of every future contract in a dataframe
        btcTickers = pd.DataFrame(
            [
                self.session.get_tickers(symbol=future, category="linear")["result"]["list"][0]
                for future in btcFutureContracts
            ]
        )

        # Create an empty dataframe to store the result
        df_gaps = pd.DataFrame(columns=["Buy", "Sell", "Gap", "Coeff", "APR", "DaysLeft", "CumVolume"])

        # Now, we can calculate the gaps
        for i, longTicker in btcTickers.iterrows():
            # Take all futures after the current one
            for j, shortTicker in btcTickers.iloc[i + 1 :].iterrows():
                gap = self.get_gap(longTicker, shortTicker)
                vol = int(gap["cumVolume"])

                # Prepare the row data
                row = {
                    "Buy": longTicker["symbol"],
                    "Sell": shortTicker["symbol"],
                    "Gap": f"$ {gap['gap']:.2f}" if pretty else gap["gap"],
                    "Coeff": f"{gap['coeff']:.2f} %" if pretty else gap["coeff"],
                    "APR": f"{gap['apr']:.2f} %" if pretty else gap["apr"],
                    "DaysLeft": int(gap["daysLeft"]),
                    "CumVolume": format_volume(vol) if pretty else gap["cumVolume"],
                }

                df_gaps = pd.concat([df_gaps, pd.DataFrame([row])], ignore_index=True)

        return df_gaps

    def get_history(self, contract, interval="m"):
        """
        Get the history of a future contract
        If we do not have any data, we start from the oldest data point, and fetch the data before it
        If we have some data, we start from the most recent data point, and fetch the data after it
        We do it this way, because we cannot know when the contract started
        Also, when a contract has no more klines, it will not throw an error

        Link: https://bybit-exchange.github.io/docs/v5/market/kline
        Args:
            contract (str): The future contract to get the history from
            interval (str): The interval of the data
        Returns:
            Nothing, but saves the data to a file
        """

        file_name = f"{contract}_{interval}.json"
        acc_data = []

        try:
            acc_data = load_data(file_name)
            print(f"Loaded {len(acc_data)} existing data points.")
            # Fetch newer data
            timestamp_key = "start"
            # Get the most recent timestamp
            timestamp = acc_data[0][0]
        except FileNotFoundError:
            print("No previous data found, starting fresh.")
            # Fetch older data
            timestamp_key = "end"
            # No timestamp available, start fresh
            timestamp = None

        # Fetch and append data
        while True:
            params = {
                "symbol": contract,
                "category": "linear",
                "interval": interval,
                "limit": 1000,
            }
            if timestamp:
                params[timestamp_key] = timestamp

            response = self.session.get_kline(**params)["result"]["list"]
            print(f"Fetched {len(response)} new data points.")

            # Depending on direction, either append or prepend the data
            if timestamp_key == "start":
                # Fetching forward, add new data at the start
                acc_data = response + acc_data[1:]
            else:
                # Fetching backward, add new data at the end
                acc_data = acc_data[:-1] + response

            numberCandles = len(response)
            # Update the timestamp for the next iteration
            if numberCandles > 0:
                timestamp = acc_data[0][0] if timestamp_key == "start" else acc_data[-1][0]

            # Break if fewer than 1000 data points were returned
            if numberCandles < 1000:
                break

        # Save to a file
        save_data(file_name, acc_data)

        return acc_data

    def position_calculator(self, contract, side, quantityUSDC, leverage=1):
        """
        Checks information about a position before entering it
        User submits a USDC quantity, and we calculate the amount of contracts to buy/sell
        The calculations are based on the Bybit documentation, but they will never be 100% accurate

        Link: https://bybit-exchange.github.io/docs/v5/order/create-order
        Source for calculations: https://www.bybit.com/en/help-center/article/Order-Cost-USDT-ContractUSDT_Perpetual_Contract
        Args:
            contract (str): The future contract to enter a position on
            side (str): Either "Buy" or "Sell"
            quantityUSDC (int): Price in USDC of contracts to buy/sell
            leverage (int): The leverage to use
        Returns:
            dict: The response from the API
        """
        # The user submits a USDC quantity, we calculate the amount of contracts to buy/sell
        # We could use the marketUnit parameter to "quoteCoin", but we want to control the quantity

        # We get the LAST ticker price
        ticker = self.session.get_tickers(symbol=contract, category="linear")["result"]["list"][0]

        # Retrieve last price
        orderPrice = float(ticker["lastPrice"])
        # Taker fees are 0.055%
        takerFees = 0.00055
        # Calculate the quantity of contracts to Buy/Sell and floor round to 3 decimals
        quantityContracts = int(quantityUSDC / orderPrice * 1000) / 1000

        # Initial Margin
        initialMargin = quantityContracts * orderPrice / leverage

        # Fee to Open Position
        feeToOpen = quantityContracts * orderPrice * takerFees

        # Bankruptcy Price for Position (short is + 1, long is - 1)
        bankruptcyPrice = orderPrice * (leverage - 1 if side == "Buy" else leverage + 1) / leverage

        # Fee to Close Position
        feeToClose = quantityContracts * bankruptcyPrice * takerFees

        # Finally the Order Cost
        orderCost = initialMargin + feeToOpen + feeToClose

        # TODO: Not sure about this, Buy/Sell do not have the same formula
        print(f"Used value: {quantityContracts * orderPrice} USDC")
        print(f"Order Cost: {orderCost} for {quantityContracts} contracts")
        return {
            "value": quantityContracts * orderPrice,
            "orderCost": orderCost,
            "quantityContracts": quantityContracts,
        }


if __name__ == "__main__":
    bybit = BybitClient()
    # print(bybit.all_gaps())
    # bybit.get_history("BTC-28MAR25", interval="720")
    # bybit.get_history("BTC-26SEP25", interval="W")
    print(bybit.position_calculator("BTC-28MAR25", side="Buy", quantityUSDC=100, leverage=3))
