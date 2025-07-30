import os
from pathlib import Path

# Root directory
ROOT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
RESULTS_DIR = ROOT_DIR / "results"

# Ensure directories exist
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

# Data configuration
DATA_FILE = DATA_DIR / "gold_ohlcv.csv"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# MT5 configuration
MT5_ENABLED = True
MT5_LOGIN = 205568819  # Exness demo account ONLY
MT5_PASSWORD = "Mayank@96"
MT5_SERVER = "Exness-MT5Trial7"  # Exness server ONLY
MT5_SYMBOL = "XAUUSDm"  # Exness Gold symbol ONLY
MT5_INVESTOR_PASSWORD = "Q*3iWqEw"  # For read-only access

# Gold specification for risk calculation
# In MT5/Ava-Demo: 1 standard lot of GOLD = 100 Troy Oz
# $1 movement in gold price = $100 profit/loss per standard lot
GOLD_PER_LOT = 100  # Troy Oz per 1.0 lot

# Trading parameters
INITIAL_CAPITAL = 10000.0  # Starting capital in USD
RISK_PER_TRADE = 0.01  # Risk 1% of capital per trade
MAX_POSITIONS = 1  # Maximum number of open positions at a time

# Timeframes
SETUP_TIMEFRAME = "1H"  # For CRT range detection
EXECUTION_TIMEFRAME = "5min"  # For entry signals

# Strategy parameters
TRAIL_TO_BREAKEVEN_AT_TP1 = True  # Move SL to breakeven after hitting TP1
RR_MODE = "dynamic"  # Options: "fixed_2_1", "fixed_4_1", "dynamic"
SLIPPAGE = 0.1  # Slippage in pips for trade execution

# Visualization settings
PLOT_CHARTS = True
SAVE_CHARTS = True

# Logging configuration
LOG_FILE_PATH = LOGS_DIR / "trade_journal.csv"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"