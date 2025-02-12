# **Architecture**

The current architecture of the project includes the following components:

![image](https://github.com/user-attachments/assets/2f15742a-193b-4251-b8ba-9a4a68108180)

- **Utils**: Management of Parquet files. Currently, it only handles Klines for everything (spot, inverse, linear).
- **Analyser**: Calculates fees, the amount of USDC required to balance quantities between two contracts, etc.
- **ApiFetcher**: Handles all communication with a socket or the API.
- **Simulator**:  A laboratory for viewing data in different ways. It can display real data or simulated data. In the long term, it could simulate an entry + exit. For this, it relies on the Analyser for calculations.
- **Client**: Logic for a pair of products. Executes the entry + exit arbitrage logic. It contains all the strategies for a pair of products.
- **GreekMaster**: Logic for all products. Monitors the account and calls ephemeral client processes to orchestrate arbitrage entry. Can talk with Bybit through the client. If delta is unfavorable (meaning the arbitrage is no longer profitable), it sends a notification.


`GreekMaster` handles single rounds of arbitrage, looping managed by `main.py`.

## GreekMaster
Orchestrates the entire arbitrage process. Monitors accounts, initiates client processes, communicates with Bybit, sends notifications, and logs events.

### Key Responsibilities:
- **Selectors**: Logic for pair selection.
- **Executors**: Set up application, call strategy, monitor, and exit.

GreekMaster serves as an interface for child classes, depending on the manipulated products. It exposes groups of methods.


## Client
Manages a pair of products. Contains all the strategies for a pair of products.

### Key Responsibilities:
- **Strategies**: The entry and exit strategies for a pair of products.
- **Executors**: Initial setup before websocket subscription, and exit strategy.

The client can be long-term (wait for an expiry) or short term (scalping). Either way it ceises to exist after one cycle of arbitrage is completed.
