# Candle Range Theory (CRT) Trading System - Enhanced Version

This project implements an improved trading system based on the Candle Range Theory (CRT) strategy for trading GOLD (XAU/USD) in the Forex market. The system has been optimized for Exness broker and features sequential trading with up to 3 trades per day, closer take profit targets, and dynamic stop loss management. It includes comprehensive data handling, strategy logic, trade execution, risk management, and visualization components.

## Gold Trading Specifications

- **MT5 Symbol**: `GOLD` (in Ava-Demo 1-MT5)
- **Contract Size**: 100 Troy Oz per 1.0 standard lot
- **P&L Calculation**: Each $1 price movement = $100 profit/loss per standard lot
- **Example**: If Gold moves from $2000 to $2001 with a 0.1 lot position, the P&L is $10 

For more details on Gold trading specifications, see [Gold Specs](docs/gold_specs.md).

## Project Structure

```
crt_trading_system
├── data
│   └── gold_ohlcv.csv          # Historical OHLCV data for GOLD
├── src
│   ├── __init__.py             # Package initialization
│   ├── config.py               # Configuration settings
│   ├── data_handler.py         # Data loading and preprocessing
│   ├── strategy.py             # Candle Range Theory strategy implementation
│   ├── risk_manager.py         # Risk management functions
│   ├── trade_manager.py        # Trade execution and management
│   ├── visualization.py        # Plotting and visualization functions
│   ├── utils.py                # Utility functions
│   └── mt5_connector.py        # MetaTrader 5 connection and data retrieval
├── notebooks
│   └── strategy_analysis.ipynb # Jupyter notebook for strategy analysis
├── main.py                     # Main script for backtesting with historical data
├── live_trading.py             # Script for live trading with MT5
├── market_scanner.py           # Script to analyze current market conditions
├── test_mt5_connection.py      # Script to test MT5 connection
└── trading_dashboard.py        # Real-time dashboard for monitoring trades
├── logs
│   └── trade_journal.csv        # Trade journal logging entries and exits
├── main.py                      # Entry point for the trading system
├── requirements.txt             # Required Python dependencies
└── README.md                    # Project documentation
```

## Setup Instructions

1. **Clone the Repository**: 
   Clone this repository to your local machine using:
   ```
   git clone <repository-url>
   ```

2. **Install Dependencies**: 
   Navigate to the project directory and install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. **Configure MetaTrader 5**:
   - Install MetaTrader 5 if you don't have it already
   - Launch MT5 and log in to your trading account
   - Enable auto trading (Tools > Options > Expert Advisors > Allow automated trading)
   - Verify your MT5 connection using one of the provided scripts:
     ```
     python check_mt5_path.py
     ```
   - If you encounter connection issues, run the connection fixer:
     ```
     python fix_mt5_connection.py
     ```

4. **Test Gold Calculations**:
   Run the Gold calculations test to verify risk management settings:
   ```
   python test_gold_calculations.py
   ```

2. **Install Dependencies**: 
   Navigate to the project directory and install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. **Prepare Data**: 
   Ensure that the `gold_ohlcv.csv` file is located in the `data` directory. This file should contain historical OHLCV data for GOLD in the specified format.

4. **Run the Trading System**: 
   Execute the trading system by running the `main.py` file:
   ```
   python main.py
   ```

## Strategy Overview

The Candle Range Theory (CRT) strategy is based on analyzing the price action of candlesticks. The strategy identifies potential trading signals by observing price movements relative to a defined range from a daily candle. Key components of the strategy include:

- **Candle Range Definition**: The high and low of the daily candle define the CRT range.
- **Signal Detection**: On an hourly chart, the strategy looks for price to sweep above or below the CRT range and then close back inside it.
- **Trade Execution**: Trades are executed based on the direction of the sweep and confirmed by the last order block.
- **Sequential Trading**: The system takes up to 3 trades per day, but only after each previous trade has fully closed.
- **Advanced Take Profit**: Uses 2 positions with different take profit targets (0.65:1 and 1.3:1 risk-reward).

## Key Improvements

- **Closer Take Profit Targets**: Reduced from 1:1 and 2:1 to 0.65:1 and 1.3:1 risk-reward to increase win rate
- **Optimized Stop Loss Distance**: Using 1.2x ATR for dynamic volatility-based stops
- **Sequential Trading**: Ensuring only one trade at a time for better risk management
- **Automatic Breakeven**: Moves second position to breakeven when first position hits target
- **Premium/Discount Zone Filter**: Only takes trades in appropriate market zones based on trend

## Risk Management

The system incorporates robust risk management practices, including:

- Dynamic position sizing based on a fixed risk percentage of the account balance.
- Stop-loss and take-profit levels calculated based on the candle wick size and risk-reward ratios.

## Visualization

The project includes visualization tools to plot the CRT range, entry and exit points, and trade outcomes using libraries such as Matplotlib or Plotly.

## Forward Testing

The system simulates live bar-by-bar execution, allowing for realistic forward testing of the CRT strategy.

## Contributions

Contributions to enhance the functionality or performance of the trading system are welcome. Please submit a pull request or open an issue for discussion.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.

## MetaTrader 5 Integration

This system supports live trading through the MetaTrader 5 platform. To use the MT5 integration:

1. Install MetaTrader 5 on your computer
2. Configure your MT5 account credentials in `src/config.py`
3. Make sure the MetaTrader 5 terminal is running when you start the live trading script

### MT5 Setup

The system is pre-configured with the following demo account settings:

```python
MT5_ENABLED = True
MT5_LOGIN = 107032874  
MT5_PASSWORD = "Sx!0SpVs"
MT5_SERVER = "Ava-Demo 1-MT5"
MT5_SYMBOL = "GOLD"  # Symbol for gold in Ava-Demo 1-MT5
MT5_INVESTOR_PASSWORD = "Q*3iWqEw"  # For read-only access
```

### Using the Trading System

#### Easy Start with Run Script

Use the run_gold_trading.py script for an easy way to start the system:

```
python run_gold_trading.py --mode backtest  # Run backtesting
python run_gold_trading.py --mode live      # Run live trading (use with caution!)
python run_gold_trading.py --mode scan      # Scan market conditions
python run_gold_trading.py --check-only     # Only check environment and configuration
```

#### Scanning the Market

To analyze current Gold market conditions and identify potential trading opportunities:

```
python run_market_scanner.py --detailed     # Run with detailed analysis
python run_market_scanner.py --days 10      # Look back 10 days
```

#### Live Trading

To start live trading:

1. First, test the connection to MT5:

```
python test_mt5_connection.py
```
or
```
python check_mt5_path.py
```

2. Scan the market for current conditions:

```
python market_scanner.py
```
or
```
python run_market_scanner.py --detailed
```

3. Start live trading:

```
python live_trading.py
```

4. (Optional) Start the trading dashboard to monitor in real-time:

```
python trading_dashboard.py
```

## Backtesting with Historical Data

To run the forward test with historical data:

```
python main.py
```

To generate and use test data:

```
python main.py --test
```