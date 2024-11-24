# Crypto-Arbitrage-Toolbox
This repository is a sandbox for many arbitrage strategies using crypto platforms (maybe DeFy one day).

Still modifying architecture

## Table of Contents


- [Process](#Process)
- [Strategies](#Strategies)
- [Architecture](#Architecture)
- [Environnement and tools](#Environnement-and-tools)
    - [Conda](#Conda)
    - [VSCode](#VSCode)
    - [Jupiter Notebook](#Jupiter-Notebook)
    - [Kestra](#Kestra)
- [Research](#Research)
  - [Spot x Future](#Spot-x-Future)
    - [Concept](#Concept)
    - [Variations](#Variations)
    - [Advantages](Advantages)
    - [Disadvantages](Disadvantages)
    - [Does it make money ?](#Does-it-make-money-?)
  - [Perpetual x Future](#Perpetual-x-Future)
    - [Concept](#Concept)
    - [Advantages](Advantages)
    - [Disadvantages](Disadvantages)
    - [Does it make money ?](#Does-it-make-money-?)
  - [Funding Rate - Spot x Perpetual](#Funding-Rate---Spot-x-Perpetual)
    - [Concept](#Concept-1)
    - [How to use](#How-to-use)
    - [Does it make money ?](#Does-it-make-money-?)
    - [Upgrades](#Upgrades)

---
### Process
Any strategy implemented has to respect these steps:

- Implement a pipeline to retrieve data consistently and store it
- Simulate market
- Make calls
- Profit

### Architecture
For now, the architecture looks like this:

![image](https://github.com/user-attachments/assets/d43148f0-880a-42e8-b005-beb766a03745)

- **Utils**: Management of Parquet files. Currently, it only handles Klines for everything (spot, inverse, linear).
- **Analyser**: Calculates fees, the amount of USDC required to balance quantities between two contracts, etc.
- **ApiFetcher**: Handles all communication with a socket or the API. Also tracks the Klines of previous contracts in a dictionary.
- **Simulation**: In the long term, it could simulate an entry + exit. For this, it relies on the Analyser for calculations.
- **Visualizer**: A laboratory for viewing data in different ways. It can display real data or simulated data (from Simulation).
- **Client**: Executes the entry + exit arbitrage logic. This will run as a systemd process (a daemon in the background).
- **GreekMaster**: Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry. If the delta is unfavorable (meaning the arbitrage is no longer profitable), it sends a notification.

### Strategies
- Funding rate arbitrage Spot & Perpetual
- Funding rate arbitrage Perpetual & Perpetual
- Spot and Perpetual spread arbitrage (no funding rate profit)
- Future - Future arbitrage
- Future - Spot arbitrage
- Cash and Carry Arbitrage or Basis Trading

---
### Environnement and tools
I code this project in a Github Codespace that I open with a Visual Studio Code window.

#### Conda
I use a conda env:
```
conda create --name <env_name> --file req.txt
conda activate <env_name>
```

You can dump an environment with:
```
conda list --export > req.txt
```

Run the code with Python3.10.6

#### VSCode
If you want to use VSCode, you can select the conda env like this:
- Ctrl+Shift+P to open the command palette
- Python: Select Interpreter
- Select the conda env you want


And you have color syntax and auto-completion !

#### Jupiter Notebook
Inside a Github Codespace from VSCode, you can open a Jupiter Notebook and run with a conda env:
- Install the Jupyter extension
- Open a new notebook
- Select a kernel (the conda env you want)

#### Kestra
In order to extract data on a scheduler, I will use Kestra (pipeline orchestrator) 
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

## Spot x Future
Future contracts are agreements between two parties to buy or sell an asset at a future date for a price agreed upon today. The price of the asset is determined by the market, and the contract is settled at the end of the contract period.

Future contracts are used by traders to hedge against price fluctuations in the underlying asset or to speculate on the future price of the asset.

But crypto futures are special, every platform has its own way to define a future contract.

### Concept
- Find a future contract
- Short the future, buy the spot token
- Wait for delivery of future
- Either roll over with another future or sell spot token

### Variations
Can be either:
- USDC-margined: Classic way
- Coin-margined: Even better, because the collateral of the future is the asset itself. Very easy to track PNL

### Advantages
- **Low fees**: Bybit USDC spot sometimes has 0% fees
- **Disadvantages can be paried**: With sharp movement, can join another arbitrage, because the spread will be huge
- **Very stable**: Hard to come out with a loss, even though there is risk

### Disadvantages
- **Non-delta**: Future contract is not as granular as spot (minimum unit is 0.01 contract)
- **No leverage**: Spot can be borrowed, but annoying

### Does it make money ?
YES. ROI is not reliable, but the strategy is.

The only thing that can break it is a huge divergence in both contracts but it is rare, and comes back to normal after a while.

## Perpetual x Future

### Concept
- Find a future contract and perpetual contract
- Depending on the funding rate and the holding period, either long perpetual and short future, or the opposite (mostly the first case)
- Wait for delivery of future
- Either roll over with another future or sell the perpetual contract

### Advantages
- **High leverage**: 20x easy, cause the margin cannot go really low
- **Low fees**: 2 legs with one in limit and the other following in market
- **Huge returns**: Has a pretty good resistance to short/long movement
- **Disadvantages can be paried**: With sharp movement, can join another arbitrage, because the spread will be huge

### Disadvantages
- **Unpredictable returns**: Cannot calculate how much I earn
- **Sensible to movement**: Huge spikes in long can break a resistance to ROI
- **Non-delta**: Again, future contracts are not as granular (minimum unit is 0.01 contract)

Example: 67k 30Mar2025 and 63k perpetual
1 short contract for 30Mar2025 is going to be more expensive.

### Does it make money ?
Still did not try it. But in theory if gap is higher than fees and funding rate is close to 0, can be controlled.

Best case is a funding rate either negative or close to zero. Because the strategy will capture the gap + the funding rate.

## Funding Rate - Spot x Perpetual

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
