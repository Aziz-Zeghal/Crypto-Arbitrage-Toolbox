# **Architecture**

The current architecture of the project includes the following components:

- **Utils**: Handles Parquet file management, primarily for Klines (spot, inverse, linear).
- **Analyser**: Calculates fees, balances quantities between contracts, and other analytics.
- **ApiFetcher**: Manages API/socket communication with exchanges.
- **Simulator**: A lab for visualizing data and simulating entry/exit scenarios.
- **Client**: Executes entry/exit arbitrage logic for specific product pairs.
- **GreekMaster**: Oversees all products, monitors accounts, and orchestrates ephemeral client processes.

The `GreekMaster` handles single rounds of arbitrage, while looping is managed by `main.py`.

![image](https://github.com/user-attachments/assets/2f15742a-193b-4251-b8ba-9a4a68108180)
