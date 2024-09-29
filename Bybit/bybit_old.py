import math
from pybit.unified_trading import HTTP
import time
import sys
# The keys file is in the parent directory
sys.path.append("../")

import keys
test = False

# Bybit testnet is really bad, BTC/USDT is at 38k and in Perp it is at 5k :)
if not test:
    session = HTTP(api_key = keys.bybitPKey, api_secret = keys.bybitSKey)
else:
    session = HTTP(testnet = True, api_key = keys.testbybitPKey, api_secret = keys.testbybitSKey)

# All requests will return a dictionnary containing retCode, retMsg, result, retExtInfo, time
# In our case, inside result we have the category, and the list of pairs
# TODO: All functions make requests with API, handle all possible errors while executing code

# ETH/USDC, BTC/USDC, ETH/BTC
def TriangularPNL(pair1, pair2, pair3, amount=100):
    whatItShouldBe = pair1 / pair2
    if (whatItShouldBe < pair3):
        # Buy ETH with USDC
        ethBalance = amount / pair1
        # Buy BTC with ETH
        btcBalance = ethBalance * pair3
        # Sell BTC for USDC
        amount = btcBalance * pair2
        print("With ETH")
    elif (whatItShouldBe > pair3):
        # Buy BTC with USDC
        btcBalance = amount / pair2
        # Buy ETH with BTC
        ethBalance = btcBalance / pair3
        # Sell ETH for USDC
        amount = ethBalance * pair1
        print("With BTC")
    else:
        print("Perfect equilibrium")
    return amount

def getSymbols(verbose=True, cat="linear"):
    """
    Prints the symbol and APY with funding rate for each pair in Perpetual market.

    Args:
        verbose (bool)
        cat (string)
    Returns:
        pairs (list of dict)
    """
    pairs = session.get_tickers(category=cat)
    for p in pairs['result']['list']:
        if p['fundingRate'] != '':
            apy = round(float(p['fundingRate']) * 365 * 3 * 100, 2)
        else:
            apy = 0
        if (verbose):
            print(p['symbol'] +" with an APY of " + str(apy) + "%")
    return pairs['result']['list']

#BTCPERP not BTC-PERP
def getCoin(coin, cat="linear"):
    """
    Returns the selected symbol info in the given category (coin is in all caps)

    Args:
        coin (string)
        cat (string)
    Returns:
        coin (dict)
    """
    pairs = session.get_tickers(category=cat)
    for p in pairs['result']['list']:
        if p['symbol'] == coin:
            return p
    return None

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
        usdvalue, amount (int, int)
    """
    coinsum = session.get_wallet_balance(accountType="UNIFIED", coin=coin)['result']['list'][0]['coin'][0]
    availableToWithdraw = coinsum['availableToWithdraw']
    amount = coinsum['usdValue']
    print("Total value of " + coin + " is: " + availableToWithdraw + "💲")
    print("Usd value is: " + amount)
    return float(availableToWithdraw), float(amount)

# This function is kinda useless now
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
        print(coin + " has a funding rate of " + str(value))
        print("This coin brings an APY of " + str(apy) + "%!")
    except:
        print("Coin does not exist in this mode!")

def avgFundingRate(coin, history=4, verbose=True, negative=True):
    """
    Prints the average funding rate for a given coin based on its history
    
    Args:
        coin (str)
        history (int)
        verbose (bool)
        negative (bool)
    Returns:
        avg (float)
    
    """
    rates = session.get_funding_rate_history(category="linear", symbol=coin, limit=history + 40)['result']['list']
    sumrates = 0
    bad = 0
    reach = 0
    for rate in rates:
        val = float(rate['fundingRate'])
        if reach == history:
            break
        if not negative:
            if val < 0:
                bad += 1
            else:
                reach += 1
                sumrates += val
        else:
            if val < 0:
                bad += 1
            sumrates += val
            reach += 1


    avg = round((sumrates / history) * 100, 6)
    if (verbose):
        print("The average funding rate for " + str(history) + " is " + str(avg) + "%\n")
        print("Found " + str(bad) + " negatives!")
    return avg

def avgFundingRateList(coins, history=4, verbose=True, negative=True):
    """
    Prints the average of given list of coins, and makes the avg of the avg (yes)
    Can use bestList() and put it here
    
    Args:
        coin (list of dict)
        history (int)
        verbose (bool)
        negative (bool)
    Returns:
        avg, apy (float, float)
    """
    sumrates = 0
    for coin in coins:
        #print(coin['symbol'])
        sumrates += avgFundingRate(coin['symbol'], history, verbose, negative)
    avg = round((sumrates / len(coins)), 6)
    apy = avg * 3 * 365
    
    if (verbose):
        print("\nIn the end we have an average of " + str(avg) + "% for an APY of " + str(apy))
    return avg, apy


# TODO: If condition to check coin exists and in good format, for user's confort
# TODO: Holdtime can only be on coins that I own
# TODO: Fees calculation is WRONG, spot exit depends on the actual value of the amount
# EXAMPLE: 100 $ entry on spot, so 0.1 $ fee
# But when we exit: 116 $ on spot, so 0.116 $ fee
def holdTime(coin, amount=100):
    """
    Prints the total fees,
    the required percentage to break even, 
    the funding rate
    and how many funding rates have to be perceived to be in profit.
    Gets the fees from get_fee_rates(dynamic), and the funding rate from get_tickers.

    Args:
        coin (string)
        amount (int)
    Returns:
        totalFees - perpMaker (float)
        breakEven (float)
        APY (float)
    """
    spotcoin = session.get_fee_rates(category="spot", symbol=coin)['result']['list'][0]
    perpcoin = session.get_fee_rates(category="linear", symbol=coin)['result']['list'][0]
    
    spotMaker = float(spotcoin['makerFeeRate']) * amount
    perpMaker = float(perpcoin['makerFeeRate']) * amount
    
    totalFees = round(spotMaker * 2 + perpMaker * 2, 4)
    fundingRate = float(session.get_tickers(category="linear", symbol=coin)['result']['list'][0]['fundingRate']) * 100
    breakEven = round(totalFees * 100 / amount, 5)
    fundingRateTakes = math.ceil(breakEven / fundingRate)
    apy = round(fundingRate * 365 * 3, 4)

    print("P: " + str(perpMaker))
    print("S: " + str(spotMaker))
    print("Total fees: " + str(totalFees) + "$")
    print("Fees without the entry on perpetual: " + str(totalFees - perpMaker) + "$\n")
    
    print("Required to break even: " + str(breakEven) + "%")
    print(str(round(amount * fundingRate / 100, 4)) + "$ every pay")
    print("So an APY of " + str(apy) + "%\n")
    
    print("With funding rates of: " + str(fundingRate) + "%")
    print("How many funding rates have to be perceived: " + str(fundingRateTakes))
    return totalFees - perpMaker, breakEven, apy

def bestList(minapy=150):
    """
    Prints the best funding rates and APY of coins that exists in both Perpetual and Spot market.
    minapy default value is 150%, because the break even needs 2 funding rates
    a minimum of 265% needs only 1 funding rate
    
    Args:
        minapy (int)
    Returns:
        coins (list of dict)
    """
    perppairs = session.get_tickers(category="linear")
    spotpairs = session.get_tickers(category="spot")
    top = 0
    coins = []
    for p in perppairs['result']['list']:
        if p['fundingRate'] != '':
            apy = float(p['fundingRate']) * 365 * 3 * 100
            if apy > minapy and any(p['symbol'] == s['symbol'] for s in spotpairs['result']['list']):
                coins.append(p)
    
    print("Here are the winners!")
    for coin in coins:
        apy = float(coin['fundingRate']) * 365 * 3 * 100
        print(coin['symbol'] + " with an APY of " + str(apy) + "%!")
    return coins

# TODO: Not optimal at all, O(n^2) at worst
def bestCoin():
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

# TODO: Use threads to execute jobs simultanous
# TODO: Use sockets to retrieve live time information
# TODO: Add a small verification of the minOrderQty with get_instruments_info
# TODO: Add a after float maximum amount in the parameters
def enterArbitrage(coin, mingap, amount):
    """
    Gives the pourcentage gap between the perpetual and spot of a coin
    Will enter a position in spot and perpetual with the mingap
    Example: BTCUSDT has a 0.4 gap between spot and perpetual
    Enter in the position, then sell with convergence
    Args:
        coin (dict)
        mingap (float)
        amount (int)
        le (int)
    Returns:
        None
    """
    equity, available = getCoinBalance("USDT")
    if (amount * 2 >= available):
        print("You do not have enough!")
        return
    spot = session.get_tickers(category="spot", symbol=coin['symbol'])['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
    gap = float(perp['lastPrice']) * 100 / float(spot['lastPrice']) - 100
    try:
        session.set_leverage(category="linear", symbol=coin['symbol'], buyLeverage="1", sellLeverage="1")
    except:
        print("Already set to 1x")
    while gap < mingap:
        print("Gap in " + str(gap) + "%")
        time.sleep(0.1)
        spot = session.get_tickers(category="spot", symbol=coin['symbol'])['result']['list'][0]
        perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
        gap = float(perp['lastPrice']) * 100 / float(spot['lastPrice']) - 100
        
    # Take position
    quantity = str(int(amount / float(spot['lastPrice'])))
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
    
    # print("We take " + str(gap) + "% !")
    # print("spot " + spot['lastPrice'] + " and perp " + perp['lastPrice'])
    
    # exitArbitrageExtra(coin['symbol'], le)
    #print("Convergence!")

    return gap

def exitArbitrage(coin):
    """
    Exits an arbitrage position without any conditions
    Perpetual contract is bought, spot is sold
    
    Args:
        coin (string)
    Returns:
        None
    """
    le = coin.find("USDT")
    decimalp = 2
    spotamount = math.floor(getCoinBalance(coin[:le])[0] * 10**decimalp) / 10**decimalp
    perpvalue = session.get_positions(category="linear", symbol=coin)['result']['list'][0]['size']
    spot = session.get_tickers(category="spot", symbol=coin)['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
    while spot['lastPrice'] <= perp['lastPrice']:
        print("spot " + spot['lastPrice'] + " and perp " + perp['lastPrice'])
        time.sleep(0.1)
        spot = session.get_tickers(category="spot", symbol=coin)['result']['list'][0]
        perp = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
    session.place_order(
        category="spot",
        symbol=coin,
        side="Sell",
        orderType="Limit",
        qty=spotamount,
        price=spot['lastPrice'])
    session.place_order(
        category="linear",
        symbol=coin,
        side="Buy",
        orderType="Limit",
        qty=perpvalue,
        price=spot['lastPrice'],
        reduce_only=True)

# enterArbitrageUSDC(getCoin("BTCPERP"), 0.04, 100)
def enterArbitrageUSDC(coin, mingap, amount):
    """
    Similar to EnterArbitrage but for USDC (no fees)
    Gives the pourcentage gap between the perpetual and spot of a coin
    Will enter a position in spot and perpetual with the mingap
    Example: BTCUSDT has a 0.4 gap between spot and perpetual
    Enter in the position, then sell with convergence
    Args:
        coin (dict)
        mingap (float)
        amount (int)
        le (int)
    Returns:
        None
    """
    equity, available = getCoinBalance("USDC")
    if (amount * 2 >= available):
        print("You do not have enough!")
        return
    spotCoinName = coin['symbol'][:coin['symbol'].find("PERP")] + "USDC"
    spot = session.get_tickers(category="spot", symbol=spotCoinName)['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
    gap = float(perp['lastPrice']) * 100 / float(spot['lastPrice']) - 100
    try:
        session.set_leverage(category="linear", symbol=coin['symbol'], buyLeverage="1", sellLeverage="1")
    except:
        print("Already set to 1x")
    while gap < mingap:
        print("Gap in " + str(gap) + "%")
        time.sleep(0.1)
        spot = session.get_tickers(category="spot", symbol=spotCoinName)['result']['list'][0]
        perp = session.get_tickers(category="linear", symbol=coin['symbol'])['result']['list'][0]
        gap = float(perp['lastPrice']) * 100 / float(spot['lastPrice']) - 100
    
    # Take position
    quantity = str(int(amount / float(spot['lastPrice'])))
    session.place_order(
        category="spot",
        symbol=spotCoinName,
        side="Buy",
        orderType="Market",
        qty=quantity,
        price=spot['lastPrice'])
    session.place_order(
        category="linear",
        symbol=coin['symbol'],
        side="Sell",
        orderType="Limit",
        qty=quantity,
        price=spot['lastPrice'])
    return gap

# exitArbitrageUSDC("SOLPERP")
def exitArbitrageUSDC(coin):
    """
    Similar to exitArbitrage but for USDC (no fees)
    Exits an arbitrage position without any conditions
    Perpetual contract is bought, spot is sold
    
    Args:
        coin (string)
    Returns:
        None
    """
    le = coin.find("PERP")
    decimalp = 2
    spotamount = math.floor(getCoinBalance(coin[:le])[0] * 10**decimalp) / 10**decimalp
    spotCoinName = coin[:coin.find("PERP")] + "USDC"
    perpvalue = session.get_positions(category="linear", symbol=coin)['result']['list'][0]['size']
    spot = session.get_tickers(category="spot", symbol=spotCoinName)['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
    while spot['lastPrice'] <= perp['lastPrice']:
        print("spot " + spot['lastPrice'] + " and perp " + perp['lastPrice'])
        time.sleep(0.1)
        spot = session.get_tickers(category="spot", symbol=spotCoinName)['result']['list'][0]
        perp = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
    session.place_order(
        category="spot",
        symbol=spotCoinName,
        side="Sell",
        orderType="Market",
        qty=spotamount,
        price=spot['lastPrice'])
    session.place_order(
        category="linear",
        symbol=coin,
        side="Buy",
        orderType="Limit",
        qty=perpvalue,
        price=spot['lastPrice'],
        reduce_only=True)

# TODO: profitCheck()
# Checks if the current positions have a good PNL
# Query all positions, indicate the situation, how much is left to earn etc.
def quick(coin, le=3):
    decimalp = 2
    spotamount = math.floor(getCoinBalance(coin[:le])[0] * 10**decimalp) / 10**decimalp
    perpvalue = session.get_positions(category="linear", symbol=coin)['result']['list'][0]['size']
    spot = session.get_tickers(category="spot", symbol=coin)['result']['list'][0]
    perp = session.get_tickers(category="linear", symbol=coin)['result']['list'][0]
    session.place_order(
        category="spot",
        symbol=coin,
        side="Sell",
        orderType="Limit",
        qty=spotamount,
        price=spot['lastPrice'])
    session.place_order(
        category="linear",
        symbol=coin,
        side="Buy",
        orderType="Limit",
        qty=perpvalue,
        price=spot['lastPrice'],
        reduce_only=True)
# TODO: statEater()
# Takes all current positions' funding rate to do some stats :)
# I need to approximate the APY, knowing that the funding rates always change

# TODO: averageBestFundingRate()
# Taking in account the history of funding rates, evaluate the best symbol

# TODO: Takedecision()
# If fundingRate is negative, exit
# If APY < to a certain required amount (50% for example), exit (if fees are covered)
# Passes everything ? Keep it
# Always return the holdTime info with the right amount, and if it was removed

# TODO: cleanPositions()
# Will check all current position, use Takedecision()
# Take information of it to do stats (the position was exited/kept, APY, PNL is positive/negative)

# theUltimate
# Check if positions are open, use cleanPosition
# Checks available USDT and use while balance > 20
# Get the best pair use enterArbitrage(bestFundingRate)
# Enter the position 2 hours before the countdown of funding rate
# Every 8 hours, use cleanPosition()