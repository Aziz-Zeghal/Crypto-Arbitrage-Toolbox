# **Strategies**

This document provides an overview of the arbitrage strategies implemented or researched in **KairosEdge**.

All the following strategies can be applied in long term (wait for expiry) or short term (pattern recognition) scenarios.
---

## **Table of Contents**

- [Cash and Carry Arbitrage (Spot x Future)](#cash-and-carry-arbitrage-spot-x-future)
- [Perpetual x Future](#perpetual-x-future-arbitrage)
- [Funding Rate Arbitrage (Spot x Perpetual)](#funding-rate-arbitrage-spot-x-perpetual)
- [Funding Rate Arbitrage (Perpetual x Perpetual)](#funding-rate-arbitrage-perpetual-x-perpetual)
- [Spot Spread Arbitrage (CEX/DEX)](#spot-spread-arbitrage-cex-dex)
- [Triangular Arbitrage](#triangular-arbitrage)

---
## **Cash and Carry Arbitrage**

### **Concept**
Takes advantage of mispricing between spot markets and futures contracts:
1. Buy the underlying asset in the spot market.
2. Sell a corresponding futures contract.
3. Hold until futures converge with spot price at expiry.

### **Variations**
- **USDC-Margined Futures**: Classic approach.
- **Coin-Margined Futures**: Collateralized with the asset itself, making it easier to track PNL.

### **Advantages**
- Predictable returns if executed correctly.
- Can be optimized using USDC or BTC collateralized futures for rolling positions.

### **Disadvantages**
- Requires significant capital for margin requirements.
- Returns are capped by the convergence of prices at expiry.

### **Profitability**
A safe and reliable strategy, especially when combined with leverage or low-fee exchanges like Deribit or Bybit.

---

## **Perpetual x Future Arbitrage**

### **Concept**
- Combines perpetual contracts and futures contracts.
- Depending on funding rates and holding periods:
  - Long perpetual, short future.
  - Or the reverse (less common).

### **Advantages**
- High leverage potential (up to 20x).
- Low fees when combining limit and market orders.
- Can capture both price gaps and funding rate profits.

### **Disadvantages**
- Returns are unpredictable due to market volatility.
- Sensitive to sharp price movements, which can impact ROI.

### **Profitability**
While theoretical profits exist, practical implementation depends on favorable funding rates and minimal divergence between contracts.

---

## **Funding Rate Arbitrage (Spot x Perpetual)**

### **Concept**
Leverages funding rates by taking positions in both spot and perpetual markets:
1. Buy in Spot Market.
2. Short in Perpetual Market.
3. Earn funding rate fees every 8 hours (or similar intervals).

### **How to Use**
1. Identify coins with high positive funding rates.
2. Enter positions when spot and perpetual prices converge.
3. Exit positions when funding rates turn negative or APY drops below a threshold.

### **Advantages**
- Profits from consistent funding payments.
- Minimal risk if positions are properly hedged.

### **Disadvantages**
- Requires active monitoring of funding rates.
- Luck can play a role in timing entries/exits effectively.

### **Profitability**
Profitable when funding rates remain positive for extended periods. However, upgrades like autonomous position management and error handling are recommended for optimization.

---

## **Funding Rate Arbitrage (Perpetual x Perpetual)**

### **Concept**
Exploits discrepancies in funding rates across two perpetual contract platforms:
1. Long position on the platform with lower funding rate.
2. Short position on the platform with higher funding rate.

### **Advantages**
- No need for asset transfers between platforms.
- Reduced fees compared to other arbitrage strategies.

### **Disadvantages**
- Requires careful monitoring of liquidity and price divergence between platforms.
- Profit margins can be slim after accounting for fees.

### **Profitability**
Highly dependent on platform-specific conditions, such as fee structures and liquidity levels.

---

## **Spot Spread Arbitrage (CEX/DEX)**

### **Concept**
Captures spreads between spot prices on centralized exchanges (CEX) and decentralized exchanges (DEX):
1. Identify pairs with significant price spreads.
2. Buy on the cheaper exchange, sell on the more expensive one.

### **Advantages**
- No need to wait for funding rates or expiry dates.
- Short-term positions with quick profits.

### **Disadvantages**
- Requires high precision due to potential delays in execution or blockchain transfers.
- Limited by API request limits or slippage during trades.

---

## **Triangular Arbitrage**

### **Concept**
Involves trading three related pairs on a single platform:
1. Identify a cross-rate discrepancy among three pairs (e.g., BTC/USDT, ETH/USDT, BTC/ETH).
2. Trade through all three pairs to capture profit from inefficiencies.

### **Advantages**
- No asset transfers required between platforms.
- Exploits pricing inefficiencies within a single exchange's order book.

### **Disadvantages**
- Requires fast execution to avoid losing opportunities due to price adjustments or slippage.
- Limited by exchange liquidity for certain pairs.

---

## Conclusion

Each strategy has its own strengths, weaknesses, and profitability potential. The choice of strategy depends on factors such as available capital, risk tolerance, market conditions, and technical capabilities. For optimal results, consider automating these strategies using bots or scripts tailored to specific platforms like Bybit, OKX, or Deribit.

For implementation details or code examples, refer to their respective modules in this repository!
