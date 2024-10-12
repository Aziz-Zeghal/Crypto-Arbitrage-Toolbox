# Crypto-Arbitrage-Toolbox
This repository is a sandbox for many arbitrage strategies using crypto platforms (maybe DeFy one day).

Still modifying architecture


---
### Process
Any strategy implemented has to respect these steps:

- Implement a pipeline to retrieve data consistently and store it
- Simulate market
- Make calls
- Profit

### Strategies
- Funding rate arbitrage Spot & Perpetual
- Funding rate arbitrage Perpetual & Perpetual
- Spot and Perpetual spread arbitrage (no funding rate profit)
- Future - Future arbitrage
- Future - Spot arbitrage
- Cash and Carry Arbitrage or Basis Trading


---
### Environnement and tools

#### Conda
I use a conda env:
```
conda create -n <env_name> python=3.10.6
conda activate <env_name>
conda create --name <env> --file req.txt
```

Run the code with Python3.10.

#### VSCode
If you want to use VSCode, you can select the conda env like this:
- Ctrl+Shift+P to open the command palette
- Python: Select Interpreter
- Select the conda env you want
And you have color syntax and auto-completion !

#### Kestra
In order to launch code, I use Kestra (pipeline orchestrator) to extract data on a scheduler
You can pull a docker image of Kestra like this:
```
docker run --pull=always --rm -it -p 8080:8080 --user=root \
 -v /var/run/docker.sock:/var/run/docker.sock \
 -v /tmp:/tmp kestra/kestra:latest server local
```

We want to scrape info on the market to create simulations and this is nice to have code run 24/7 on a VPS.


---
### Research

Looking into cash & carry arbitrage with leverage, flash loans.

Looked into Put/Call parity, Triangular arbitrage, and Spot/Perpetual arbitrage (without funding rate).

Made my Deribit Client with websockets, the code is nice

## Funding Rate Arbitrage

### Concept

- Retrieve the best funding rate on the CEX
- Take position when Spot & Perpetual converge
- Profit from funding rates, check every 8 hours for positivity

### How to use

2 strategies can be applied:

Take positions and only exit them when the funding rate is negative

Make the minimum to break even from fees and look for a better pair (if the funding rates make an APY < 50 % for example)


- Install the requirements
- Put the API key and secret key of Bybit in a file called keys
- Get a crypto pair available in both perpetual and spot
- Insert it in enterArbitrage(coin)
- Now wait for convergence of perpetual and spot
- ???
- Profit from the position with funding rate :)

### Does it make money ?

Code is functionnal, but upgrades are missing.

I noticed that a little luck is involved in this arbitrage strategy. We can enter a position that has a good funding rate, but at the next refresh it turns negative.
One way to counter act this, would be to enter positions that have a really good APY and need the least amount of funding rates to be in profit.

EXAMPLE: HNTUSDT had a funding rate of 0.2111%. On 100$, the total of fees (SpotEntry and SpotExit, PerpEntry and PerpExit) is around 0.685$

Now, the required turnover to break even is 0.275% (sum of the fees). We need 2 funding rates to be in profit (if it stayed the same)

Predicting the exact value of the next funding rate for a cryptocurrency is challenging, as it depends on various factors and market dynamics.
Market sentiment, position imbalance, leverage and history of funding rates all have an impact on its value.

For now, this code is linked to luck, and should not be considered reliable or optimized.

### Upgrades

- **Autonomous position taker:**  sometimes, orders are not completed. Timeout system for positions, and better decision making (through trial and error no other ways). System that checks current positions, exits them if the funding rate is negative, takes current wallet size and fractions accordingly...
- **Liquidation survey:**  if liquidation in short position is near, exit arbitrage position
- **Position escaper:**  if the funding rate is negative, exit arbitrage position, and start looking for a new host
- **Notifier:**  if positions are active, message the new funding rate of coins, the current realised PNL, the new potential APY, and other info
- **Heuristic system:**  calculate best coin based on multiple factors (liquidity, funding rate, history of funding rate). A coin is valuable if we know it will have a positive funding rate for a long period, to avoid fees
- **Leverage:**  simply include leverage and calculate correctly
- **Error handler:**  queries through the API can fail in rare cases. Find all possible results and handle them properly
- **Better functions:**  some functions are just lame (O(n^2) complexity instead of O(nlog(n)) and many requests for nothing). Use websockets for live information, and make functions more adaptive and easy to use
