import asyncio
import websockets
import json
from pybit.unified_trading import HTTP

# The keys file is in the parent directory
sys.path.append("../")
sys.path.append("../Bybit")

import keys
import deribitClient
import bybit

# Deribit
client = None
# Bybit
session = HTTP(api_key = keys.bybitPKey, api_secret = keys.bybitSKey)

async def checker(coin, g=0.3):
    """
    This function compares Perpetual and Spot of a coin with USDC
    Args:
        coin (string)
        g (float)
    Returns:
        None
    """
    # PERP: last_price or best_ask_price
    # SPOT: index_price
    perpIn = coin + "_USDC-PERPETUAL"
    spotIn = coin + "_USDC"
    while True:
        perpTick = await client.ticker(perpIn)
        spotTick = await client.ticker(spotIn)
        # print("spot is " + str(spotTick['result']['mark_price']) + " and perp is " + str(perpTick['result']['mark_price']))
        gap = float(perpTick['result']['mark_price']) * 100 / float(spotTick['result']['mark_price']) - 100
        print("Gap of: " + str(gap))


async def checkerBybit(coin):
    """
    This function compares Perpetual and Bybit spot of a coin in USDC
    Args:
        coin (string)
    Returns:
        None
    """
    # PERP: last_price or best_ask_price
    # SPOT: index_price
    perpIn = coin + "_USDC-PERPETUAL"
    spotIn = coin + "USDC"
    while True:
        perpTick = await client.ticker(perpIn)
        spotTick = session.get_tickers(category="spot", symbol=spotIn)['result']['list'][0]
        print("spot is " + str(spotTick['lastPrice']) + " and perp is " + str(perpTick['result']['mark_price']))
        gap = float(perpTick['result']['mark_price']) * 100 / float(spotTick['lastPrice']) - 100
        if (gap <= 0.0):
            return
        print("Gap of: " + str(gap))
        
async def checkTriangular(coin1, coin2, coin3):
    """
    This function is used to look at triangular arbitrage opportunities !
    Args:
        coin1, coin2, coin3 (string)
    Returns:
        None
    """
    while True:
        pair1 = await client.ticker(coin1)
        pair2 = await client.ticker(coin2)
        pair3 = await client.ticker(coin3)
        print(bybit.TriangularPNL(pair1['result']['index_price'], pair2['result']['index_price'], pair3['result']['index_price']))

# ETH/USDC, BTC/USDC, ETH/BTC
async def triangular(coin1, coin2, coin3, amount=10):
    """
    This function is used to take triangular arbitrage opportunities !
    Args:
        coin1, coin2, coin3 (string)
    Returns:
        None
    """
    pair1 = await client.ticker(coin1)
    pair2 = await client.ticker(coin2)
    pair3 = await client.ticker(coin3)
    whatItShouldBe = pair1['result']['mark_price'] / pair2['result']['mark_price']
    if (whatItShouldBe > pair3['result']['mark_price']):
        # Buy BTC with USDC
        quantity = round(amount / pair2['result']['mark_price'], 5)
        await client.buy_market(coin2, quantity)
        # Buy ETH with BTC
        await client.buy_market(coin3, quantity)
        quantity = round(quantity / pair3['result']['mark_price'], 4)
        # Sell ETH for USDC
        await client.sell_market(coin1, quantity)
    else:
        print("no")
    
# TODO: Check if we have enough
async def spot_perp_arbitrage(coin="ETH", amount=50, g=0.3):
    """
    This function takes an opportunity, and exits it
    Args:
        coin (string)
        amount (float)
        gap (float)
    Returns:
        None
    """
    # If this function stops, it means that we have what we want
    perpIn = coin + "_USDC-PERPETUAL"
    spotIn = coin + "_USDC"
    perpTick = await client.ticker(perpIn)
    spotTick = await client.ticker(spotIn)
    
    gap = float(perpTick['result']['mark_price']) * 100 / float(spotTick['result']['mark_price']) - 100
    while (g >= gap):
        print("Gap of: " + str(gap))
        perpTick = await client.ticker(perpIn)
        spotTick = await client.ticker(spotIn)
        # print("spot is " + str(spotTick['result']['mark_price']) + " and perp is " + str(perpTick['result']['mark_price']))
        gap = perpTick['result']['mark_price'] * 100 /spotTick['result']['mark_price'] - 100
    
    quantity = round(amount / spotTick['result']['mark_price'], 2)
    # Add 10 to make it like a market order hehe
    await client.buy_limit(perpIn, quantity, round(perpTick['result']['mark_price'] + 10, 1))
    await client.buy_market(spotIn, quantity)
    
    perpTick = await client.ticker(perpIn)
    spotTick = await client.ticker(spotIn)
    time.sleep(0.5)
    gap = perpTick['result']['mark_price'] * 100 /spotTick['result']['mark_price'] - 100
    while (gap >= g - 0.01):
        print("Second gap of: " + str(gap))
        perpTick = await client.ticker(perpIn)
        spotTick = await client.ticker(spotIn)
        gap = perpTick['result']['mark_price'] * 100 /spotTick['result']['mark_price'] - 100
    
    await client.sell_limit(perpIn, quantity, round(perpTick['result']['mark_price'] + 10, 1))
    await client.sell_market(spotIn, quantity)
async def main():
    global client
    # CHANGE KEYS HERE
    client = deribitClient.myClient(keys.deribitPKey, keys.deribitSKey)
    response = await client.connect()
    if 'error' in response.keys():
        print(f"Auth failed with error {response['error']}")
    else:
        print("Auth creds are good, it worked")
        # Where the magic happens, implement logic here!
        
        # await triangular("ETH_USDC", "BTC_USDC", "ETH_BTC", 50)
        #await checker("BTC")
        #r =await client.pending_orders("BTC_USDC-PERPETUAL")
        await spot_perp_arbitrage("ETH", 50, 0.04)
        #await checker("ETH")
        #await client.buy_market("ETH_USDC", 0.001)
        #await client.buy_market("USDC_USDT", 1)
        await client.logout()

def async_loop(api):
    # We make a loop, as of Python 3.11 will put an error otherwise
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(api)
    # Acts like a signal handler (not at all)
    except KeyboardInterrupt:
        print("Exiting...")
        return loop.run_until_complete(client.logout())

async_loop(main())