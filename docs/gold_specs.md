## Gold Trading Specifications

The system is configured for trading Gold (XAU/USD) on the MetaTrader 5 platform. Here are the key specifications:

### Symbol Information
- **MT5 Symbol**: `GOLD` (Note: This may vary by broker; some use "XAUUSD" instead)
- **Contract Size**: 100 Troy Oz per 1.0 standard lot
- **Pricing**: Quoted in USD per Troy Oz

### Risk Calculation
- Each $1 movement in gold price equals $100 profit/loss per standard lot
- Example: If Gold moves from $2000 to $2001 with a 0.1 lot position, the P&L is $10 ($1 × 100 Troy Oz × 0.1 lot)

### Position Sizing
The system calculates appropriate position sizes based on:
1. Account risk per trade (default: 1% of account equity)
2. Stop loss distance in dollars
3. Gold's 100 Troy Oz per lot specification

### Trading Hours
Gold markets are typically most active during these sessions:
- London session: 08:00-16:00 GMT
- New York session: 13:00-21:00 GMT

### Testing
Run the Gold calculations test script to validate the risk management settings:
```
python test_gold_calculations.py
```
