import asyncio
import websockets
import json

# IMPORTANT
# XXX_XXX is for spot
# XXX-PERPETUAL is for perpetual

# Here are the current methods !
# connect
# logout
# get_currencies
# get_instruments
# ticker
# buy_market
# buy_limit
# sell_market
# pending_orders

# DEPRECATED
# get_index_price_stream btc_usdt (does not stop) 
# get_index_price btc_usdt (last tick)

class myClient:
    def __init__(self, client_id, client_secret):
        self.websocket = None
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.refresh_token = None
    
    async def connect(self):
        """
        Authenticate, and fills the access_token and refresh_token
        Args:
            msg (string)
        Returns:
            info (json)
        """
        msg = \
            {
            "jsonrpc": "2.0",
            "id": 9929,
            "method": "public/auth",
            "params": {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            }
        }
        self.websocket = await websockets.connect('wss://www.deribit.com/ws/api/v2')
        await self.websocket.send(json.dumps(msg))
        while self.websocket.open:
            response = await self.websocket.recv()
            info = json.loads(response)
            if 'error' in info.keys():
                return info
            self.access_token = info.get("result", {}).get("access_token")
            self.refresh_token = info.get("result", {}).get("refresh_token")
            return info
        
    async def get_currencies(self):
        """
        Retrieves all the currencies
        Args:
            None
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 7538,
          "method" : "public/get_currencies",
          "params" : {

          }
        }
        await self.websocket.send(json.dumps(msg))
        while self.websocket.open:
            response = await self.websocket.recv()
            info = json.loads(response)
            return info
        
    async def get_instruments(self, coin="BTC", k="spot"):
        """
        Retrieves all the instruments of a kind
        Args:
            coin (string) [BTC, ETH, USDC, USDT, EURR]
            k (string) [future, option, spot, future_combo, option_combo]
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 1,
          "method" : "public/get_instruments",
          "params" : {
              "currency" : coin,
              "kind" : k
          }
        }
        await self.websocket.send(json.dumps(msg))
        while self.websocket.open:
            response = await self.websocket.recv()
            info = json.loads(response)
            return info
        
    async def get_index_price_stream(self, coinPair):
        """
        Streams the ticks of a coinPair
        Args:
            coinPair (string)
        Returns:
            info (json)
        """
        msg = \
            {"jsonrpc": "2.0",
         "method": "public/get_index_price",
         "id": 42,
         "params": {
            "index_name": coinPair}
        }
        await self.websocket.send(json.dumps(msg))
        while self.websocket.open:
            # Receive, then send again, by doing this, we get an infinite loop
            response = await self.websocket.recv()
            info = json.loads(response)
            print(info['result'])
            await self.websocket.send(json.dumps(msg))
    
    async def get_index_price(self, coinPair):
        """
        Takes the last tick of a coinpair
        Args:
            coinPair (string)
        Returns:
            info (json)
        """
        msg = \
            {"jsonrpc": "2.0",
         "method": "public/get_index_price",
         "id": 42,
         "params": {
            "index_name": coinPair}
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        return info
    
    async def ticker(self, coinPair):
        """
        Takes the last tick of a coinpair
        Args:
            coinPair (string)
        Returns:
            info (json)
        """
        msg = \
            {"jsonrpc": "2.0",
         "method": "public/ticker",
         "id": 8106,
         "params": {
            "instrument_name": coinPair}
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        return info

    async def buy_market(self, coinPair, amount):
        """
        Market order on the coinPair
        Perpetual: XXX-PERPETUAL format
        Spot: XXX_XXX format
        Args:
            coinPair (string)
            amount (float)
            orderType (float)
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 5275,
          "method" : "private/buy",
          "params" : {
            "instrument_name" : coinPair,
            "amount" : amount,
            "type" : "market"
          }
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        print(info)
        return info
    
    async def sell_market(self, coinPair, amount):
        """
        Market order on the coinPair
        Perpetual: XXX-PERPETUAL format
        Spot: XXX_XXX format
        Args:
            coinPair (string)
            amount (float)
            orderType (float)
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 2148,
          "method" : "private/sell",
          "params" : {
            "instrument_name" : coinPair,
            "amount" : amount,
            "type" : "market"
          }
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)

        return info

    async def buy_limit(self, coinPair, amount, aimed):
        """
        Limit order on the coinPair
        Perpetual: XXX-PERPETUAL format
        Spot: XXX_XXX format
        Args:
            coinPair (string)
            amount (float)
            orderType (float)
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 5275,
          "method" : "private/buy",
          "params" : {
            "instrument_name" : coinPair,
            "amount" : amount,
            "type" : "limit",
            "price" : aimed
          }
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        print(info)
        return info
    
    async def sell_limit(self, coinPair, amount, aimed):
        """
        limit order on the coinPair
        Perpetual: XXX-PERPETUAL format
        Spot: XXX_XXX format
        Args:
            coinPair (string)
            amount (float)
            orderType (float)
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 2148,
          "method" : "private/sell",
          "params" : {
            "instrument_name" : coinPair,
            "amount" : amount,
            "type" : "market",
            "price" : aimed
          }
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        print(info)
        return info
    
    async def pending_orders(self, coinPair):
        """
        Gets all current orders
        Perpetual: XXX-PERPETUAL format
        Spot: XXX_XXX format
        Args:
            coinPair (string)
            amount (float)
            orderType (float)
        Returns:
            info (json)
        """
        msg = \
        {
          "jsonrpc" : "2.0",
          "id" : 8442,
          "method" : "private/get_open_orders_by_instrument",
          "params" : {
            "instrument_name" : coinPair
          }
        }
        await self.websocket.send(json.dumps(msg))
        response = await self.websocket.recv()
        info = json.loads(response)
        return info
    
    async def logout(self):
        """
        Simple logout
        Args:
            None
        Returns:
            info (json)
        """
        if not self.access_token:
            print("Not logged in.")
            return
        logout_msg = \
                   {
            "jsonrpc": "2.0",
            "method": "private/logout",
            "id": 42,
            "params": {
                "access_token": self.access_token,
                "invalidate_token": True
            }
        }
        try:
            await self.websocket.send(json.dumps(logout_msg))
            while self.websocket.open:
                response = await self.websocket.recv()
                info = json.loads(response)
                return info
        except:
              print("Gracefully closed connection ! (I guess ?)")


