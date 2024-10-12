from pybit.unified_trading import HTTP
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
        self.session = HTTP(demo = True, api_key = keys.demobybitPKey, api_secret = keys.demobybitSKey)

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
    

if __name__ == "__main__":
    bybit = Bybit()
    print(bybit.get_USDC_BTC())