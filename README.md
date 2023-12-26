# bybit-spot-perp-arbitrage
Small Python script implements a basic delta-neutral arbitrage strategy between a spot market and a perpetual futures contract. The strategy aims to capitalize on funding rate differentials between the two markets.

Still building, because I am still looking into other arbitrage techniques

BE CAREFUL: if you use this code, always check on the website the leverage of perpetual. API documentation does not refer to it, but the default value is 10x. Change it on the website for the wanted coin then use code.

## Concept

- Retrieve the best funding rate on the CEX
- Take position when Spot & Perpetual converge
- Profit from funding rates, check every 8 hours for positivity

## To-do list

Code is functionnal. Just implement upgrades and make better documentation

## Upgrades

- **Autonomous position taker:**  sometimes, orders are not completed. Timeout system for positions, and better decision making (through trial and error no other ways). System that checks current positions, exits them if the funding rate is negative, takes current wallet size and fractions accordingly...
- **Liquidation survey:**  if liquidation in short position is near, exit arbitrage position
- **Position escaper:**  if the funding rate is negative, exit arbitrage position, and start looking for a new host
- **Notifier:**  if positions are active, message the new funding rate of coins, the current realised PNL, the new potential APY, and other info
- **Heuristic system:**  calculate best coin based on multiple factors (liquidity, funding rate, history of funding rate). A coin is valuable if we know it will have a positive funding rate for a long period, to avoid fees
- **Leverage:**  simply include leverage and calculate correctly
- **Error handler:**  queries through the API can fail in rare cases. Find all possible results and handle them properly
- **Better functions:**  some functions are just lame (O(n^2) complexity instead of O(nlog(n)) and many requests for nothing). Use websockets for live information, and make functions more adaptive and easy to use
