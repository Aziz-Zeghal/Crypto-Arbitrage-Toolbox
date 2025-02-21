import datetime


class Analyser:
    # TODO: Still not perfect (take history)
    @staticmethod
    def get_gap(longTickers: dict, shortTickers: dict) -> dict:
        """Get the gap between two future contracts with their tickers.

        WARNING: We suppose the longTickers is closer to delivery than shortTickers.
        This means that the price of longTickers should be lower than shortTickers.
        WARNING: Results in decimal form. Not in percentage.

        Args:
            longTickers (dict): Tickers of the first future contract
            shortTickers (dict): Tickers of the second future contract

        Return:
            dict:
                gap: The gap between the two contracts
                coeff: The coefficient of the gap
                roi: The return on investment (coeff - 0.22%)
                apr: The annual percentage rate
                daysLeft: The number of days left before the delivery
                cumVolume: The cumulative volume of the two contracts
                funding: The cumulative funding rate until the delivery (0 if not perpetual)

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
        coeff = round((shortPrice / longPrice - 1), 3)
        # - Calculate the return on investment
        roi = coeff - 0.0022

        # | Time to delivery for the contracts, epoch in milliseconds (convert to seconds)
        longDelivery = int(longTickers["deliveryTime"]) / 1000
        shortDelivery = int(shortTickers["deliveryTime"]) / 1000
        todayDate = datetime.datetime.now(datetime.UTC).timestamp()
        # - Time to delivery
        # Sometimes, its a perpetual contract, so we need to check if the delivery time is 0
        maximumTime = longDelivery if longDelivery != 0 else shortDelivery
        daysLeft = (maximumTime - todayDate) / 86400 + 1

        # | Cumulate funding rate until the delivery
        funding = float(longTickers.get("fundingRate", 0)) * (int((maximumTime - todayDate) / (8 * 3600)) - 1)

        apr = roi * 365 / daysLeft if daysLeft != 0 else 0
        return {
            "gap": gap,
            "coeff": coeff,
            "roi": roi,
            "apr": apr,
            "cumFunding": funding,
            "cumVolume": cumVolume,
            "daysLeft": daysLeft,
        }

    @staticmethod
    def position_calculator(ticker: str, side: str, quantityUSDC: float, leverage: int = 1) -> dict:
        """Check information about a position before entering it.

        User submits a USDC quantity, and we calculate the amount of contracts to buy/sell.
        The calculations are based on the Bybit documentation, but they will never be 100% accurate.

        Link: https://bybit-exchange.github.io/docs/v5/order/create-order
        Source for calculations: https://www.bybit.com/en/help-center/article/Order-Cost-USDT-ContractUSDT_Perpetual_Contract

        Args:
            ticker (str): The future contract to enter a position on
            side (str): Either "Buy" or "Sell"
            quantityUSDC (float | int): Price in USDC of contracts to buy/sell
            leverage (int): The leverage to use

        Returns:
            dict: The response from the API

        """
        # The user submits a USDC quantity, we calculate the amount of contracts to buy/sell
        # We could use the marketUnit parameter to "quoteCoin", but we want to control the quantity

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
        return {
            "value": quantityContracts * orderPrice,
            "orderCost": orderCost,
            "quantityContracts": quantityContracts,
        }
