import keys

from pybit.unified_trading import HTTP
import time

test = False

# Bybit testnet is really bad, BTC/USDT is at 38k and in Perp it is at 5k :)
if not test:
    session = HTTP(api_key = keys.bybitPKey, api_secret = keys.bybitSKey)
else:
    session = HTTP(testnet = True, api_key = keys.testbybitPKey, api_secret = keys.testbybitSKey)

# All requests will return a dictionnary containing retCode, retMsg, result, retExtInfo, time
# In our case, inside result we have the category, and the list of pairs
# TODO: All functions make requests with API, handle all possible errors while executing code

def getSymbols():
    """
    Prints the symbol and funding rate for each pair in Perpetual market.

    Args:
        None
    Returns:
        None
    """
    pairs = session.get_tickers(category="linear")
    for p in pairs['result']['list']:
        print(p['symbol'] + " with " + p['fundingRate'])
        
def getWallet():
    """
    Prints the total value of the wallet.
    To execute this function, need to upgrade_to_unified_trading_account()

    Args:
        None
    Returns:
        None
    """
    wallet = session.get_wallet_balance(accountType="UNIFIED")
    print("Total value of wallet is: " + wallet['result']['list'][0]['totalEquity'] + "💲")

def getCoinBalance(coin):
    """
    Prints the total value of a given coin in the wallet.
    To execute this function, need to upgrade_to_unified_trading_account()

    Args:
        coin (str)
    Returns:
        None
    """
    coinsum = session.get_wallet_balance(accountType="UNIFIED", coin=coin)
    print("Total value of this coin is: " + coinsum['result']['list'][0]['coin'][0]['usdValue'] + "💲")

def getFundingRate(coin):
    """
    Prints the funding rate and APY of a given coin.

    Args:
        coin (str)
    Returns:
        None
    """
    try:
        pair = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
        value = float(pair['fundingRate']) * 100
        apy = float(pair['fundingRate']) * 365 * 3 * 100
        print(coin + " has a funding rate of " + str(value))
        print("This coin brings an APY of " + str(apy) + "%!")
    except:
        print("Coin does not exist in this mode!")

# TODO: Not optimal at all, O(n^2) at worst
def bestFundingRate():
    """
    Prints the best funding rate and APY of a coin that exists in both Perpetual and Spot market.

    Args:
        None
    Returns:
        coin (dict)
    """
    perppairs = session.get_tickers(category="linear")
    spotpairs = session.get_tickers(category="spot")
    top = 0
    for p in perppairs['result']['list']:
        if p['fundingRate'] != '' and float(p['fundingRate']) > top and any(p['symbol'] == s['symbol'] for s in spotpairs['result']['list']):
            coin = p
            top = float(coin['fundingRate'])
    print("And the winner is, " + coin['symbol'] + " with " + str(float(coin['fundingRate']) * 100) + "!")
    apy = float(coin['fundingRate']) * 365 * 3 * 100
    print("This coin brings an APY of " + str(apy) + "%!")
    return coin

# TODO: This function takes ONLY coins that exist in spot and perpetual
# TODO: If condition to check coin exists and in good format, for user's confort
def holdTime(coin, amount=100):
    """
    Prints the total fees,
    the required percentage to break even, 
    the funding rate
    and how many funding rates have to be perceived to be in profit.
    Gets the fees from get_fee_rates(dynamic), and the funding rate from get_tickers.

    Args:
        coin (dict)
        amount (int)
    Returns:
        totalFees (float)
        breakEven (float)
    """
    spotcoin = session.get_fee_rates(category="spot", symbol=coin)['result']['list'][0]
    perpcoin = session.get_fee_rates(category="linear", symbol=coin)['result']['list'][0]
    
    spotMaker, spotTaker = float(spotcoin['makerFeeRate']) * amount, float(spotcoin['takerFeeRate']) * amount
    perpMaker, perpTaker = float(perpcoin['makerFeeRate']) * amount, float(perpcoin['takerFeeRate']) * amount
    
    totalFees = spotMaker + spotTaker + perpMaker + perpTaker
    fundingRate = float(session.get_tickers(category="linear", symbol=coin)['result']['list'][0]['fundingRate']) * 100
    breakEven = round(totalFees * 100 / amount, 5)
    fundingRateTakes = round(breakEven / fundingRate, 0)
    print("Perpetual enter: " + str(perpMaker) + " and exit: " + str(perpTaker))
    print("Spot enter: " + str(spotMaker) + " and exit: " + str(spotTaker))

    print("Total fees: " + str(totalFees) + "$")
    print("Required to break even: " + str(breakEven) + "%")
    print("With funding rates of: " + str(fundingRate) + "%")
    print("How many funding rates have to be perceived: " + str(fundingRateTakes))
    return totalFees, breakEven

# TODO: Use threads to execute jobs simultanous
# TODO: Use sockets to retrieve live time information
# TODO: Add a small verification of the minOrderQty with get_instruments_info
def enterArbitrage(coin, amount=20):
    """
    Enters an arbitrage position on a given coin.
    Uses the spot and perpetual market to enter both positions.
    IMPORTANT: the coin is a dictionnary, not a string.

    Args:
        coin (dict)
        amount (int)
    Returns:
        None
    """
    spot = session.get_tickers(category="spot", symbol=coin['symbol'])['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
    session.set_leverage(category="linear", symbol=coin['symbol'], buyLeverage="1", sellLeverage="1")
    while spot['lastPrice'] != perp['lastPrice']:
        print("spot " + spot['lastPrice'] + " and perp " + perp['lastPrice'])
        time.sleep(0.2)
        spot = session.get_tickers(category="spot", symbol=coin['symbol'])['result']['list'][0]
        perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
    quantity = str(round(amount / float(spot['lastPrice']), 1))
    session.place_order(
        category="spot",
        symbol=coin['symbol'],
        side="Buy",
        orderType="Limit",
        qty=quantity,
        price=spot['lastPrice'])
    session.place_order(
        category="linear",
        symbol=coin['symbol'],
        side="Sell",
        orderType="Limit",
        qty=quantity,
        price=spot['lastPrice'])

# TODO: exitArbitrage(coin), with a given coin, exit both positions
# Use holdTime to check if arbitrage is > to this value to see if we have a profit

