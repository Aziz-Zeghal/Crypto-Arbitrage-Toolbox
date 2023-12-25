# bybit-spot-perp-arbitrage
Small Python script implements a basic delta-neutral arbitrage strategy between a spot market and a perpetual futures contract. The strategy aims to capitalize on funding rate differentials between the two markets.

Still building

## Concept

- Retrieve the best funding rate on the CEX
- Take position when Spot & Perpetual converge
- Profit from funding rates, check every 8 hours for positivity

## Upgrades

- **Autonomous position taker**: sometimes, orders are not completed. Timeout system for positions, and better decision making (through trial and error no other ways)
- **Position escaper**: if the funding rate is negative, exit position, and start looking for a new host
- **Notifier**: message every action (start position, end position, new found token, new funding rate, etc…)
- **Heuristic system**: calculate best coin based on multiple factors (liquidity, funding rate, history of funding rate). A coin is valuable if we know it will have a positive funding rate for a long period, to avoid fees
