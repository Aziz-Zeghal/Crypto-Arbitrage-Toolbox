from pybit.unified_trading import HTTP
from datetime import datetime
import pandas as pd

import sys
import os

# We add the path to the sys.path
# sys.path is contains a list of directories that the interpreter will search in for the required module. 
sys.path.append(os.path.dirname(os.path.abspath("keys.py")))

import keys

class BybitClient:
    def __init__(self):
        """
        Initialize the Bybit session
        """
        self.session = HTTP(api_key = keys.bybitPKey, api_secret = keys.bybitSKey)

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
        btcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="BTC")['result']['list'][0]
        usdcDict = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDC")['result']['list'][0]

        totalBalance = btcDict["totalEquity"]

        # Just to make the code more readable
        btcDict = btcDict["coin"][0]
        usdcDict = usdcDict["coin"][0]

        btcValue = {"Quantity": btcDict["equity"],
                    "Available": btcDict["availableToWithdraw"],
                    "usdValue": btcDict["usdValue"]}
        
        usdcValue = {"Quantity": usdcDict["equity"],
                     "Available": usdcDict["availableToWithdraw"],
                     "usdValue": usdcDict["usdValue"]}
        
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
        for p in pairs['result']['list']:
            # Looks like BTC-01NOV24
            if p["symbol"].startswith(coin + "-"):
                markets.append(p["symbol"])

        # Function to extract and convert the date part to a datetime object
        def extract_date(contract):
            date_str = contract.split('-')[-1]  # Extracts the date part, e.g., '01NOV24'
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
        daysLeft = (longDelivery - todayDate) / 86400

        apr = coeff * 365 / daysLeft / 2
        return {"gap": gap, "coeff": coeff, "apr": apr, "daysLeft": daysLeft, "cumVolume": cumVolume}
    
    def all_gaps(self, pretty=True):
        """
        Get all the gaps for all the future contracts

        Args:
            pretty (bool): If True, will format the elements in a more readable way
        Returns:
            list: List of all the gaps information
        """
        btcFutureContracts = self.get_futures("BTC")
        btcTickers = []
        # First, get the tickers of every future contract
        for future in btcFutureContracts:
            btcTickers.append(self.session.get_tickers(symbol=future, category="linear")['result']['list'][0])
        
        # Now, we can calculate the gaps
        rows = []
        for longTicker in btcTickers:
            # Take all futures after it
            for shortTicker in btcTickers[btcTickers.index(longTicker) + 1:]:
                gap = self.get_gap(longTicker, shortTicker)
                vol = int(gap["cumVolume"])
                if (pretty):
                    rows.append({
                        "Buy": longTicker["symbol"],
                        "Sell": shortTicker["symbol"],
                        "Gap": f"$ {gap['gap']:.2f}",
                        "Coeff": f"{gap['coeff']:.2f} %",
                        "APR": f"{gap['apr']:.2f} %",      
                        "DaysLeft": int(gap["daysLeft"]),
                        "CumVolume": self.format_volume(vol)
                    })
                else:
                    rows.append({
                        "Buy": longTicker["symbol"],
                        "Sell": shortTicker["symbol"],
                        "Gap": gap['gap'],
                        "Coeff": gap['coeff'],
                        "APR": gap['apr'],      
                        "DaysLeft": gap["daysLeft"],
                        "CumVolume": gap["cumVolume"]
                    })

        gaps = pd.DataFrame(rows)
        return gaps
    
    def format_volume(self, volume):
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

if __name__ == "__main__":
    bybit = BybitClient()
    print(bybit.all_gaps())