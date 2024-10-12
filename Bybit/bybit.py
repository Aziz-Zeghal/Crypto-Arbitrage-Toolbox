from pybit.unified_trading import HTTP
from datetime import datetime
import sys
import os

# We add the path to the sys.path
# sys.path is contains a list of directories that the interpreter will search in for the required module. 
sys.path.append(os.path.dirname(os.path.abspath("keys.py")))

import keys

class Bybit:
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
            dict: 
                markets: Future markets and their info
        """

        # Sadly, I do not think there is a better way to do this
        # But the contracts themself are not always queried
        pairs = self.session.get_instruments_info(category="linear")
        markets = []
        for p in pairs['result']['list']:
            # Looks like BTC-01NOV24
            if p["symbol"].startswith(coin + "-"):
                markets.append(p)

        return markets
    
    def get_gap(self, futureContract1, futureContract2):
        """
        Get the gap between two future contracts 
        CAREFUL: We suppose the contract1 is closer to delivery than contract2
        This means that the price of contract1 should be lower than contract2

        Args:
            futureContract (str): The future contract to get the gap for
        Return:
            dict:
                gap: The gap between the two contracts
                coeff: The coefficient of the gap
                apr: The annual percentage rate
                daysLeft: The number of days left before the delivery of the first contract
        """
        # Index price is in spot price
        futureTickers1 = self.session.get_tickers(symbol=futureContract1, category="linear")['result']['list'][0]
        futureTickers2 = self.session.get_tickers(symbol=futureContract2, category="linear")['result']['list'][0]

        # | Price of the future contract
        longPrice = float(futureTickers1["lastPrice"])
        shortPrice = float(futureTickers2["lastPrice"])
        # - Calculate the gap
        gap = shortPrice - longPrice

        # - Calculate the coefficient
        coeff = round((shortPrice / longPrice - 1) * 100, 3)

        # | Time to delivery for the long contract, epoch in milliseconds (convert to seconds)
        longDelivery = int(futureTickers1["deliveryTime"]) / 1000
        todayDate = datetime.now().timestamp()
        # - Time to delivery
        # Transform to int to round floor (no need for Math.floor)
        daysLeft = (longDelivery - todayDate) / 86400

        apr = coeff * 365 / daysLeft / 2
        return {"gap": gap, "coeff": coeff, "apr": apr, "daysLeft": daysLeft}

if __name__ == "__main__":
    bybit = Bybit()
    print(bybit.get_gap("BTC-29NOV24", "BTC-27JUN25"))