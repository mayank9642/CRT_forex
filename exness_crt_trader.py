import MetaTrader5 as mt5
import time
from datetime import datetime, timedelta, timezone
import pandas as pd
import os
import openpyxl
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from src.news_filter import is_news_blocking

# --- CONFIG ---
SYMBOL = 'XAUUSDm'
RISK_PER_TRADE = 0.01
# Set session hours to match Exness Market Watch time (UTC+0)
SESSION_HOURS = sorted(set([1, 5, 9, 13, 15, 18, 21] + list(range(7, 22))))  # Compare legacy and full London/NY sessions
USE_ORDER_BLOCK = True
USE_POWER_OF_THREE = False  # Set to False for flexible CRT mode
STRICT_CRT_MODE = False     # If True, use strict 3-candle power-of-three; if False, use flexible sweep/close-in-range
MIN_RR = 0.65  # Minimum R:R for a trade - adjusted to match our closer TP targets
TREND_LOOKBACK = 20  # Number of D1 candles for trend detection
TREND_MA_PERIOD = 10 # MA period for trend detection
SL_BUFFER = 20.0  # Buffer in price units ($20 for gold - reduced from 30)
MIN_SL_DISTANCE = 15.0  # Minimum stop-loss distance in price units (reduced from 20)
MAX_TRADES_PER_SIGNAL = 2   # Maximum trades per CRT signal (should be 2 for TP1 & TP2)
COOLDOWN_MINUTES = 240      # Minutes to wait after a trade before looking for new signals (increased for higher TF)
RANGE_TIMEFRAME = mt5.TIMEFRAME_D1  # Changed from H1 to D1 for proper range analysis
ENTRY_TIMEFRAME = mt5.TIMEFRAME_H1  # Changed from M5 to H1 for better entry timing

# --- Trading Lock to prevent duplicate entries ---
TRADE_LOCK = False  # Global lock for trading

# --- EXNESS TERMINAL PATH (set this to your Exness terminal64.exe) ---
EXNESS_MT5_PATH = r"C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"  # Update if needed

# --- MT5 Attach Only to Exness ---
print(f"Connecting to Exness MT5 terminal at {EXNESS_MT5_PATH} (attach only)...")
if not mt5.initialize(EXNESS_MT5_PATH, portable=True):
    print(f"MT5 initialize() failed: {mt5.last_error()}")
    quit()
account = mt5.account_info()
if account is None:
    print("Failed to get account info. Please ensure you are logged in manually.")
    mt5.shutdown()
    quit()
print(f"Connected: {account.name} | Balance: {account.balance}")

# --- Helper: Get last N candles as DataFrame ---
def get_rates(symbol, timeframe, count, shift=0):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, shift, count)
    if rates is None or len(rates) < count:
        return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

# --- Helper: Calculate Average True Range (ATR) for volatility-based stop loss ---
def calculate_atr(symbol, timeframe, period=14):
    """Calculate Average True Range (ATR) for volatility-based stop loss.
    Returns the ATR value or None if calculation fails."""
    # Get enough candles for proper ATR calculation
    df = get_rates(symbol, timeframe, period+10, 0)
    if df is None or len(df) < period+1:
        print(f"Failed to get enough data for ATR calculation")
        return None
    
    # Calculate true range
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift(1))
    df['low_close'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)
    
    # Calculate ATR
    df['atr'] = df['tr'].rolling(period).mean()
    
    # Return the latest ATR value
    latest_atr = df['atr'].iloc[-1]
    if pd.isna(latest_atr):
        return None
    
    return latest_atr

# --- Helper: Find order block (last opposite candle before move) ---
def find_order_block(df, direction):
    # For BUY: last bearish candle before up move; for SELL: last bullish before down move
    if direction == 'BUY':
        obs = df[(df['close'] < df['open'])]
    else:
        obs = df[(df['close'] > df['open'])]
    if obs.empty:
        return None
    return obs.iloc[-1]

# --- Helper: Get Market Watch (broker) time ---
def get_broker_time():
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(tick.time, timezone.utc)

# --- Helper: Get broker time ---

# --- Helper: Get detailed symbol info including stop levels ---
def get_symbol_details():
    """Get comprehensive symbol details including stop levels and point values.
    Returns a dictionary with symbol information or None if unavailable."""
    info = mt5.symbol_info(SYMBOL)
    if info is None:
        print(f"Failed to get symbol info for {SYMBOL}")
        return None
    
    # Convert named tuple to dictionary using _asdict()
    info_dict = info._asdict()
    
    # Create a detailed dictionary of symbol properties
    details = {
        "name": info_dict.get("name", SYMBOL),
        "point": info_dict.get("point", 0.001),
        "digits": info_dict.get("digits", 3),
        "trade_contract_size": info_dict.get("trade_contract_size", 100.0),
        "volume_min": info_dict.get("volume_min", 0.01),
        "volume_step": info_dict.get("volume_step", 0.01),
        "bid": info_dict.get("bid", 0.0),
        "ask": info_dict.get("ask", 0.0),
        "spread": info_dict.get("spread", 0),
        "stops_level": info_dict.get("trade_stops_level", 0)
    }
    
    # For XAUUSDm, use empirically determined stop distance
    if SYMBOL.startswith("XAU"):
        # Based on our testing, Exness allows stops as close as $0.50, 
        # but we'll use $1.00 for safety
        details["adjusted_min_stop"] = 1.0
        print(f"Gold {SYMBOL} details - Point: {details['point']}, Digits: {details['digits']}, Stops level: {details['stops_level']}")
        print(f"Using empirically tested minimum stop for Gold: $1.00")
    else:
        # For other symbols, calculate based on reported stops level
        min_stop_price = details["stops_level"] * details["point"]
        if min_stop_price < 0.0001:  # If essentially zero, use a safe default
            details["adjusted_min_stop"] = 0.0001
        else:
            details["adjusted_min_stop"] = min_stop_price
        
    return details

# --- Trade Limiting and R:R Filter ---
trades_today = 0  # Total trades count
last_trade_day = None

# --- Excel Journal Setup ---
JOURNAL_FILE = "trade_journal.xlsx"
JOURNAL_HEADERS = [
    "Ticket", "DateTime", "Symbol", "Direction", "EntryPrice", "SL", "TP", "LotSize", "RR1", "RR2", "Status", "ExitPrice", "Profit", "Comment"
]
if not os.path.exists(JOURNAL_FILE):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(JOURNAL_HEADERS)
    wb.save(JOURNAL_FILE)

# --- Helper: Log trade to Excel journal ---
def log_trade(ticket, dt, symbol, direction, entry, sl, tp, lot, rr1, rr2, status, exit_price, profit, comment):
    wb = openpyxl.load_workbook(JOURNAL_FILE)
    ws = wb.active
    ws.append([
        ticket, dt, symbol, direction, entry, sl, tp, lot, rr1, rr2, status, exit_price, profit, comment
    ])
    wb.save(JOURNAL_FILE)

# --- Helper: Move SL to breakeven ---
def move_sl_to_breakeven(ticket, breakeven_price):
    """Move stop loss to breakeven for a given position.
    Returns True if successful, False otherwise."""
    # First, check if the position exists and get its current TP
    positions = mt5.positions_get(ticket=ticket)
    if not positions or len(positions) == 0:
        print(f"Position {ticket} not found when trying to move SL to breakeven")
        return False
        
    position = positions[0]
    
    # Create request with the correct TP value (keep original TP)
    request = {
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "sl": breakeven_price,
        "tp": position.tp,  # Keep original TP
        "symbol": SYMBOL,
    }
    
    # Send the request
    result = mt5.order_send(request)
    
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Successfully moved SL to breakeven {breakeven_price} for position {ticket}")
        return True
    else:
        error_code = result.retcode if result else "Unknown"
        error_msg = result.comment if result else "No result"
        print(f"Failed to move SL to breakeven: Error {error_code} - {error_msg}")
        
        # If failure is due to invalid SL, try with a bit more buffer
        if result and result.retcode == 10016:
            symbol_details = get_symbol_details()
            point = symbol_details["point"] if symbol_details else 0.01
            
            # Add a bit more buffer in the direction away from the current price
            if position.type == mt5.POSITION_TYPE_BUY:  # If BUY position, move SL a bit lower
                adjusted_sl = breakeven_price - (10 * point)
            else:  # If SELL position, move SL a bit higher
                adjusted_sl = breakeven_price + (10 * point)
                
            print(f"Retrying with adjusted SL: {adjusted_sl}")
            
            request["sl"] = adjusted_sl
            retry_result = mt5.order_send(request)
            
            if retry_result and retry_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Successfully moved SL with adjusted value {adjusted_sl} for position {ticket}")
                return True
        
        return False

# --- Helper: Calculate position size for 1% risk ---
def calculate_lot_size(entry, sl, balance, risk_pct):
    risk_amount = balance * risk_pct
    pip_risk = abs(entry - sl)
    if pip_risk == 0:
        return 0.01  # fallback minimum
    # For gold, 1 lot = 100 oz, $1 move = $100 per lot
    lot_size = risk_amount / (pip_risk * 100)
    # Round down to nearest 0.01
    lot_size = max(0.01, round(lot_size, 2))
    return lot_size

# --- Helper: Determine trend direction (simple MA or price action) ---
def get_trend_direction():
    h1_df = get_rates(SYMBOL, RANGE_TIMEFRAME, TREND_LOOKBACK, 1)
    if h1_df is None or len(h1_df) < TREND_MA_PERIOD:
        return None
    ma = h1_df['close'].rolling(TREND_MA_PERIOD).mean()
    if h1_df['close'].iloc[-1] > ma.iloc[-1]:
        return 'UP'
    elif h1_df['close'].iloc[-1] < ma.iloc[-1]:
        return 'DOWN'
    else:
        return None

# --- Helper: Calculate premium/discount zone for CRT ---
def is_in_premium_discount_zone(candle, trend, h1_df):
    # Use the last N candles for the correction range
    correction_range = h1_df[-TREND_LOOKBACK:]
    high = correction_range['high'].max()
    low = correction_range['low'].min()
    mid = (high + low) / 2
    if trend == 'UP':
        # Only take CRT setups if the CRT range is in the lower half (discount)
        return candle['low'] < mid
    elif trend == 'DOWN':
        # Only take CRT setups if the CRT range is in the upper half (premium)
        return candle['high'] > mid
    return False

# --- Main CRT Strategy Loop ---
print("Starting advanced CRT strategy on live Exness demo...")
last_trade_time = None

# Initialize last trade day
last_trade_day = None
trades_today = 0

while True:
    broker_now = get_broker_time()
    broker_day = broker_now.date()
    symbol_details = get_symbol_details()
    min_stop = symbol_details["adjusted_min_stop"] if symbol_details else 3.0
    
    # Daily trade tracking
    if last_trade_day != broker_day:
        trades_today = 0
        last_trade_day = broker_day
        print(f"\n{broker_now} New trading day started. Trade count reset to 0/3.")
    
    # Clear display of current trading status
    print(f"\n{broker_now} === SEQUENTIAL TRADING STATUS ===")
    print(f"Trade lock active: {TRADE_LOCK}")
    print(f"Trades taken today: {trades_today}/3")
    print(f"Current positions: {len(mt5.positions_get(symbol=SYMBOL) or [])}")
    
    if trades_today >= 3:
        print(f"{broker_now} Max 3 trades reached for {broker_day}. Not taking any more trades today.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: Max 3 trades reached for the day\n")
        time.sleep(60)
        continue
          # Check if any positions are currently open - only take a new trade if no positions are open
    current_positions = mt5.positions_get(symbol=SYMBOL)
    if current_positions and len(current_positions) > 0:
        print(f"{broker_now} Positions already open. Waiting for them to close before taking a new trade.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: Waiting for open positions to close\n")
              # Reset trade lock if positions are detected but lock is false
        # This ensures proper sequential trading
        if not TRADE_LOCK:
            print(f"{broker_now} Detected open positions but trade lock was False. Resetting lock.")
            TRADE_LOCK = True
            
        time.sleep(60)
        continue
    if broker_now.hour not in SESSION_HOURS:
        print(f"{broker_now} Not in CRT session hours (Market Watch time). Waiting...")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: Not in CRT session hours\n")
        time.sleep(60)
        continue
    if is_news_blocking():
        print("Skipping trading due to high-impact news event.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: High-impact news event\n")
        time.sleep(1800)
        continue
    # --- Trend context ---
    trend = get_trend_direction()
    if trend is None:
        print(f"{broker_now} No trend detected. Skipping.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: No trend detected\n")
        time.sleep(60)
        continue
    h1_df = get_rates(SYMBOL, RANGE_TIMEFRAME, 30, 1)
    if h1_df is None:
        print("No H1 data. Waiting...")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: No H1 data\n")
        time.sleep(10)
        continue
    # --- CRT pattern detection ---
    entry_found = False
    crt_candle_idx = None
    if STRICT_CRT_MODE:
        # Strict: power-of-three pattern
        range_candle = h1_df.iloc[0]
        sweep_candle = h1_df.iloc[1]
        confirm_candle = h1_df.iloc[2]
        crt_high = range_candle['high']
        crt_low = range_candle['low']
        sweeped_high = sweep_candle['high'] > crt_high
        sweeped_low = sweep_candle['low'] < crt_low
        confirm_in_range = (crt_low < confirm_candle['close'] < crt_high)
        if not ((sweeped_high or sweeped_low) and confirm_in_range):
            print(f"{broker_now} No CRT power-of-three pattern.")
            with open("crt_skip_log.txt", "a") as f:
                f.write(f"{broker_now} SKIP: No CRT power-of-three pattern\n")
            time.sleep(60)
            continue
        direction = 'SELL' if sweeped_high else 'BUY'
        crt_candle_idx = 0
        entry_found = True
    else:
        # Flexible: any sweep and close back inside range, trend-aware, premium/discount filter
        for i in range(1, len(h1_df)):
            prev = h1_df.iloc[i-1]
            curr = h1_df.iloc[i]
            crt_high = prev['high']
            crt_low = prev['low']
            # For uptrend, look for bearish candle sweep below low and close back in range
            if trend == 'UP' and prev['close'] < prev['open']:
                if curr['low'] < crt_low and crt_low < curr['close'] < crt_high:
                    if is_in_premium_discount_zone(prev, trend, h1_df):
                        direction = 'BUY'
                        crt_candle_idx = i-1
                        entry_found = True
                        break
            # For downtrend, look for bullish candle sweep above high and close back in range
            if trend == 'DOWN' and prev['close'] > prev['open']:
                if curr['high'] > crt_high and crt_low < curr['close'] < crt_high:
                    if is_in_premium_discount_zone(prev, trend, h1_df):
                        direction = 'SELL'
                        crt_candle_idx = i-1
                        entry_found = True
                        break
        if not entry_found:
            print(f"{broker_now} No flexible CRT sweep/close-in-range pattern.")
            with open("crt_skip_log.txt", "a") as f:
                f.write(f"{broker_now} SKIP: No flexible CRT sweep/close-in-range pattern\n")
            time.sleep(60)
            continue
    # --- Lower timeframe entry (FVG, refined: closest to sweep) ---
    m5_df = get_rates(SYMBOL, ENTRY_TIMEFRAME, 20, 1)
    if m5_df is None:
        print("No M5 data. Waiting...")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: No M5 data\n")
        time.sleep(10)
        continue
    entry_candle = None
    fvg_candidates = []
    sweep_time = None
    if crt_candle_idx is not None:
        sweep_time = h1_df.iloc[crt_candle_idx+1].name  # time of sweep candle
    if direction == 'BUY':
        # Look for all bullish FVGs (gap between previous high and current low) after the sweep
        for i in range(1, len(m5_df)):
            if m5_df.iloc[i]['low'] > m5_df.iloc[i-1]['high']:
                if sweep_time is None or m5_df.index[i] >= sweep_time:
                    fvg_candidates.append(m5_df.iloc[i])
        if fvg_candidates:
            # Pick the FVG closest in time to the sweep (first after sweep)
            entry_candle = fvg_candidates[0]
        else:
            entry_candle = m5_df.iloc[-1]  # fallback: use last candle
        price = mt5.symbol_info_tick(SYMBOL).ask
    else:
        # Look for all bearish FVGs (gap between previous low and current high) after the sweep
        for i in range(1, len(m5_df)):
            if m5_df.iloc[i]['high'] < m5_df.iloc[i-1]['low']:
                if sweep_time is None or m5_df.index[i] >= sweep_time:
                    fvg_candidates.append(m5_df.iloc[i])
        if fvg_candidates:
            # Pick the FVG closest in time to the sweep (first after sweep)
            entry_candle = fvg_candidates[0]
        else:
            entry_candle = m5_df.iloc[-1]  # fallback: use last candle
        price = mt5.symbol_info_tick(SYMBOL).bid
    if entry_candle is None:
        print(f"{broker_now} No CRT entry signal.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: No CRT entry signal\n")
        time.sleep(60)
        continue
    # Prevent duplicate trades in same hour    if last_trade_time and entry_candle.name <= last_trade_time:
        time.sleep(60)
        continue
    last_trade_time = entry_candle.name
    
    # --- SL/TP and R:R Calculation with ATR-based dynamic stops ---
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print("Failed to get symbol info")
        time.sleep(60)
        continue
    
    # Get stop level in points and convert to price units
    # Access properties via the _asdict() method which is the proper way to access named tuple attributes
    symbol_dict = symbol_info._asdict()
    
    # Get the trade_stops_level from the dictionary
    stops_level = symbol_dict.get('trade_stops_level', 0)
    point = symbol_dict.get('point', 0.001)
    digits = symbol_dict.get('digits', 3)
    
    print(f"Symbol info: trade_stops_level={stops_level}, point={point}, digits={digits}")
    
    # Calculate ATR for dynamic stop-loss based on market volatility
    # For XAUUSDm, this will give appropriate stop distance based on current market conditions
    atr_value = calculate_atr(SYMBOL, RANGE_TIMEFRAME, period=14)
    if atr_value is None:
        print("Failed to calculate ATR, using fixed buffer")
        atr_value = SL_BUFFER
    else:
        print(f"ATR value for {SYMBOL} on {RANGE_TIMEFRAME} timeframe: {atr_value:.2f}")
    
    # For gold specifically, ensure minimum stop distance is adequate
    # Gold is typically quoted with 2 decimal places (e.g., 1945.00)
    if SYMBOL.startswith("XAU"):
        # Use 1.2x ATR or minimum buffer, whichever is larger (reduced multiplier from 1.5x)
        dynamic_sl_buffer = max(atr_value * 1.2, MIN_SL_DISTANCE)
        # Use a fixed minimum SL distance for gold that we know works
        min_stop_price = MIN_SL_DISTANCE
    else:
        dynamic_sl_buffer = max(atr_value * 1.2, SL_BUFFER)  # Reduced multiplier from 1.5x
        min_stop_price = stops_level * point
        if min_stop_price < 0.0001:
            min_stop_price = MIN_SL_DISTANCE
    
    print(f"Symbol {SYMBOL} | Using dynamic SL buffer: {dynamic_sl_buffer:.2f} | Min stop in price: {min_stop_price:.2f}")
    
    if direction == 'BUY':
        # Calculate preferred SL based on entry candle and ATR
        preferred_sl = entry_candle['low'] - dynamic_sl_buffer
        
        # Enforce minimum broker stop distance
        required_sl = price - min_stop_price
        
        # Use the lower (further from price) of the two values for safety
        sl = min(preferred_sl, required_sl)
        sl = round(sl, digits)
          # Calculate take profits - more conservative to prevent frequent SL hits
        # Use closer targets for higher profitability rate (0.65:1 and 1.3:1)
        tp1 = round(price + (dynamic_sl_buffer * 0.65), digits)  # 0.65:1 R:R for first target (closer)
        tp2 = round(price + (dynamic_sl_buffer * 1.3), digits)  # 1.3:1 R:R for second target (closer)
        
        # Calculate risk and reward
        risk = abs(price - sl)
        rr1 = abs(tp1 - price) / risk if risk > 0 else 0
        rr2 = abs(tp2 - price) / risk if risk > 0 else 0
    else:  # SELL
        # Calculate preferred SL based on entry candle and ATR
        preferred_sl = entry_candle['high'] + dynamic_sl_buffer
        
        # Enforce minimum broker stop distance
        required_sl = price + min_stop_price
        
        # Use the higher (further from price) of the two values for safety
        sl = max(preferred_sl, required_sl)
        sl = round(sl, digits)
          # Calculate take profits - more conservative to prevent frequent SL hits
        tp1 = round(price - (dynamic_sl_buffer * 0.65), digits)  # 0.65:1 R:R for first target (closer)
        tp2 = round(price - (dynamic_sl_buffer * 1.3), digits)  # 1.3:1 R:R for second target (closer)
        
        # Calculate risk and reward
        risk = abs(price - sl)
        rr1 = abs(price - tp1) / risk if risk > 0 else 0
        rr2 = abs(price - tp2) / risk if risk > 0 else 0
        
    # Add detailed debugging to diagnose stop level issues
    print(f"Order details: {direction} | price={price} | sl={sl} | preferred_sl={preferred_sl if direction=='BUY' else preferred_sl} | required_sl={required_sl if direction=='BUY' else required_sl}")
    print(f"Order validation: SL distance={abs(price-sl):.2f} | Min required={min_stop_price:.2f} | Valid={abs(price-sl) >= min_stop_price}")
      # Double-check SL validity before sending order
    if direction == 'BUY' and price - sl < min_stop_price:
        # Recalculate SL with a small safety buffer for gold
        if SYMBOL.startswith("XAU"):
            sl = price - 1.0  # $1.00 minimum SL distance for gold
        else:
            sl = price - (min_stop_price * 1.1)  # Add 10% safety margin
        sl = round(sl, digits)
        print(f"⚠️ Buy SL too close! Adjusted to: {sl}, distance: {price-sl:.2f}")
    elif direction == 'SELL' and sl - price < min_stop_price:
        # Recalculate SL with a small safety buffer for gold
        if SYMBOL.startswith("XAU"):
            sl = price + 1.0  # $1.00 minimum SL distance for gold
        else:
            sl = price + (min_stop_price * 1.1)  # Add 10% safety margin
        sl = round(sl, digits)
        print(f"⚠️ Sell SL too close! Adjusted to: {sl}, distance: {sl-price:.2f}")
        
    # Recalculate risk and R:R after any SL adjustments
    risk = abs(price - sl)
    if direction == 'BUY':
        rr1 = abs(tp1 - price) / risk if risk > 0 else 0
        rr2 = abs(tp2 - price) / risk if risk > 0 else 0
    else:
        rr1 = abs(price - tp1) / risk if risk > 0 else 0
        rr2 = abs(price - tp2) / risk if risk > 0 else 0
    # --- Dynamic lot size for 1% risk per trade ---    account = mt5.account_info()
    balance = account.balance if account else 10000
    
    # Get symbol info and safely access trade_contract_size through dictionary
    symbol_info_obj = mt5.symbol_info(SYMBOL)
    if symbol_info_obj:
        symbol_info_dict = symbol_info_obj._asdict()
        contract_size = symbol_info_dict.get('trade_contract_size', 100)
    else:
        contract_size = 100
    max_risk = balance * RISK_PER_TRADE
    # For gold, pip value is usually $1 per lot per $1 move, but use contract_size for safety
    lot_size = max_risk / (risk * contract_size) if risk > 0 else 0.01
    lot_size = max(lot_size, 0.01)  # enforce broker minimum
    half_lot = round(lot_size / 2, 2)
    # Only trade if R:R to at least one TP is MIN_RR+
    if max(rr1, rr2) < MIN_RR:
        print(f"{broker_now} R:R too low (TP1: {rr1:.2f}, TP2: {rr2:.2f}). Skipping trade.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: R:R too low (TP1: {rr1:.2f}, TP2: {rr2:.2f})\n")
        time.sleep(60)
        continue    # Check if trade lock is active
    if TRADE_LOCK:
        print(f"{broker_now} Trading lock active. Skipping signal.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: Trading lock active\n")
        time.sleep(60)
        continue
          
    # Activate the trade lock to prevent duplicate entries
    TRADE_LOCK = True
    
    # Use the already calculated dynamic SL distance that considers ATR
    # We've already calculated this in the previous section
    min_stop_price = MIN_SL_DISTANCE

    print(f"Using minimum SL distance of {min_stop_price:.2f} for {SYMBOL}")
    
    # Get current exact price
    current_tick = mt5.symbol_info_tick(SYMBOL)
    if current_tick is None:
        print("Failed to get current price tick")
        TRADE_LOCK = False  # Release lock
        time.sleep(10)
        continue
    
    # Use the exact current price with zero slippage for more accurate SL calculation
    if direction == 'BUY':
        current_price = current_tick.ask
        # Set SL at a safe distance - fixed value for gold
        sl = current_price - min_stop_price
        sl = round(sl, digits)
        print(f"Setting BUY SL at {min_stop_price:.2f} distance: price={current_price}, sl={sl}")
    else:  # SELL
        current_price = current_tick.bid
        # Set SL at a safe distance - fixed value for gold
        sl = current_price + min_stop_price
        sl = round(sl, digits)
        print(f"Setting SELL SL at {min_stop_price:.2f} distance: price={current_price}, sl={sl}")
    
    # Place order (split into two positions for partial TP)
    # First position: TP1 (mid-range)
    request1 = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": half_lot,
        "type": mt5.ORDER_TYPE_SELL if direction == 'SELL' else mt5.ORDER_TYPE_BUY,
        "price": current_price,  # Use exact current price instead of calculated price
        "sl": sl,
        "tp": tp1,
        "deviation": 20,
        "magic": 123456,
        "comment": "CRT advanced TP1",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # Second position: TP2 (full range)
    request2 = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": half_lot,
        "type": mt5.ORDER_TYPE_SELL if direction == 'SELL' else mt5.ORDER_TYPE_BUY,
        "price": current_price,  # Use exact current price instead of calculated price
        "sl": sl,
        "tp": tp2,
        "deviation": 20,
        "magic": 123457,
        "comment": "CRT advanced TP2",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # Calculate final risk-reward after all adjustments
    risk = abs(current_price - sl)
    if direction == 'BUY':
        rr1 = abs(tp1 - current_price) / risk if risk > 0 else 0
        rr2 = abs(tp2 - current_price) / risk if risk > 0 else 0
    else:
        rr1 = abs(current_price - tp1) / risk if risk > 0 else 0
        rr2 = abs(current_price - tp2) / risk if risk > 0 else 0
    
    # Check R:R one last time
    if max(rr1, rr2) < MIN_RR:
        print(f"{broker_now} Final R:R too low after SL adjustments (TP1: {rr1:.2f}, TP2: {rr2:.2f}). Skipping trade.")
        with open("crt_skip_log.txt", "a") as f:
            f.write(f"{broker_now} SKIP: Final R:R too low after SL adjustments (TP1: {rr1:.2f}, TP2: {rr2:.2f})\n")
        time.sleep(60)
        continue
    
    # Send first order
    print(f"Sending order 1: {direction} | Price: {current_price} | SL: {sl} | TP: {tp1} | SL Distance: {abs(current_price-sl):.2f}")
    result1 = mt5.order_send(request1)
    if result1 is None:
        print("Error: Order 1 returned None")
        time.sleep(60)
        continue
        
    if result1.retcode == 10016:  # Invalid stops error
        print(f"⚠️ INVALID STOPS ERROR for order 1:")
        print(f"  Symbol: {SYMBOL}")
        print(f"  Direction: {direction}")
        print(f"  Price: {current_price}")
        print(f"  SL: {sl} (distance: {abs(current_price-sl):.2f})")
        print(f"  Min required: {min_stop_price:.2f}")
        print(f"  Point value: {symbol_details['point'] if symbol_details else 'unknown'}")
        print(f"  Stops level: {symbol_details['stops_level'] if symbol_details else 'unknown'}")
        
        # Exness sometimes requires larger stop-loss for XAUUSDm
        # Instead of trying multiple values, immediately use a large enough value
        if SYMBOL.startswith("XAU"):
            # Use a fixed SL distance that we know works with Exness
            safe_distance = MIN_SL_DISTANCE * 1.1  # 10% larger than our minimum (reduced from 20%)
            
            if direction == 'BUY':
                new_sl = round(current_price - safe_distance, digits)
            else:
                new_sl = round(current_price + safe_distance, digits)
                
            print(f"Using safe SL distance of {safe_distance:.2f} → SL: {new_sl}")
            
            # Update request with new SL
            request1_retry = request1.copy()
            request1_retry["sl"] = new_sl
            retry_result1 = mt5.order_send(request1_retry)
            
            if retry_result1 and retry_result1.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"SUCCESS with safe SL distance!")
                result1 = retry_result1  # Use the successful result
                sl = new_sl  # Update SL for second order
        
        # If still failed, try alternative: first open without SL, then modify
        if result1.retcode == 10016:
            request1_no_sl = request1.copy()
            request1_no_sl.pop('sl', None)
            request1_no_sl.pop('tp', None)
            print("Trying alternative method: Open position without SL/TP first")
            alt_result1 = mt5.order_send(request1_no_sl)
            
            if alt_result1 and alt_result1.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Position opened without SL/TP. Adding SL/TP...")
                # Add SL/TP in a separate request
                modify_request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": alt_result1.order,
                    "symbol": SYMBOL,
                    "sl": sl,
                    "tp": tp1,
                }
                modify_result = mt5.order_send(modify_request)
                if modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Successfully added SL/TP")
                    result1 = alt_result1  # Consider it successful
                else:
                    print(f"Failed to add SL/TP: {modify_result.retcode} {modify_result.comment}")
                    
                    # Try again with a larger stop distance
                    if SYMBOL.startswith("XAU"):
                        larger_sl = current_price - 5.0 if direction == 'BUY' else current_price + 5.0
                        larger_sl = round(larger_sl, digits)
                        modify_request["sl"] = larger_sl
                        print(f"Trying with much larger SL: {larger_sl}")
                        modify_result = mt5.order_send(modify_request)
                        if modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"Successfully added SL/TP with larger distance")
                            result1 = alt_result1  # Consider it successful
    
    # If first order succeeded, try the second
    if result1.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"{entry_candle.name} {direction} TP1 order placed at {current_price} | SL: {sl} | TP: {tp1} | RR1: {rr1:.2f}")
        log_trade(result1.order, str(broker_now), SYMBOL, direction, current_price, sl, tp1, half_lot, rr1, rr2, "OPEN", "", "", request1['comment'])
        
        # Send second order
        print(f"Sending order 2: {direction} | Price: {current_price} | SL: {sl} | TP: {tp2} | SL Distance: {abs(current_price-sl):.2f}")
        result2 = mt5.order_send(request2)
        
        if result2 and result2.retcode == 10016:  # Invalid stops error for second order
            print(f"⚠️ INVALID STOPS ERROR for order 2:")
            
            # For XAUUSDm, use the same safe SL distance that worked for order 1
            if SYMBOL.startswith("XAU"):
                # Use the same safe SL value that worked for order 1
                print(f"Using same safe SL for order 2: {sl}")
                
                # Update request with new SL (which should now be the successful SL from order 1)
                request2_retry = request2.copy()
                retry_result2 = mt5.order_send(request2_retry)
                
                if retry_result2 and retry_result2.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"SUCCESS with safe SL for order 2!")
                    result2 = retry_result2  # Use the successful result
            
            # If still failed, try alternative for second order
            if result2.retcode == 10016:
                request2_no_sl = request2.copy()
                request2_no_sl.pop('sl', None)
                request2_no_sl.pop('tp', None)
                print("Trying alternative method for order 2: Open position without SL/TP first")
                alt_result2 = mt5.order_send(request2_no_sl)
                
                if alt_result2 and alt_result2.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Position 2 opened without SL/TP. Adding SL/TP...")
                    # Add SL/TP in a separate request
                    modify_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": alt_result2.order,
                        "symbol": SYMBOL,
                        "sl": sl,
                        "tp": tp2,
                    }
                    modify_result = mt5.order_send(modify_request)
                    if modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"Successfully added SL/TP to position 2")
                        result2 = alt_result2  # Consider it successful
                    else:
                        print(f"Failed to add SL/TP to position 2: {modify_result.retcode} {modify_result.comment}")
                        
                        # Try again with a larger stop distance
                        if SYMBOL.startswith("XAU"):
                            larger_sl = current_price - 5.0 if direction == 'BUY' else current_price + 5.0
                            larger_sl = round(larger_sl, digits)
                            modify_request["sl"] = larger_sl
                            print(f"Trying position 2 with much larger SL: {larger_sl}")
                            modify_result = mt5.order_send(modify_request)
                            if modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                                print(f"Successfully added SL/TP to position 2 with larger distance")
                                result2 = alt_result2  # Consider it successful
        
        if result2 and result2.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"{entry_candle.name} {direction} TP2 order placed at {current_price} | SL: {sl} | TP: {tp2} | RR2: {rr2:.2f}")
            log_trade(result2.order, str(broker_now), SYMBOL, direction, current_price, sl, tp2, half_lot, rr1, rr2, "OPEN", "", "", request2['comment'])
            trades_today += 1
            
            # Trade successfully placed - set cooldown time
            print(f"Setting trade cooldown for {COOLDOWN_MINUTES} minutes")
            time.sleep(60)  # Wait a minute before releasing lock to ensure no duplicate trades
              # Create a background thread to release the trade lock after cooldown
            from threading import Thread
            
            def release_lock_after_cooldown():
                global TRADE_LOCK
                time.sleep(COOLDOWN_MINUTES * 60)
                TRADE_LOCK = False
                print(f"Trade lock released after {COOLDOWN_MINUTES} min cooldown")
                
            Thread(target=release_lock_after_cooldown, daemon=True).start()
        else:
            print(f"Order 2 failed: {result2.retcode if result2 else 'None'} {result2.comment if result2 else 'No result'}")
            TRADE_LOCK = False  # Release lock on failure
    else:
        print(f"Order 1 failed: {result1.retcode if result1 else 'None'} {result1.comment if result1 else 'No result'}")
        TRADE_LOCK = False  # Release lock on failure
        
# Monitor for TP1 hit to move SL to breakeven for TP2
    if result1 and result2 and result1.retcode == mt5.TRADE_RETCODE_DONE and result2.retcode == mt5.TRADE_RETCODE_DONE:
        print("Both orders placed successfully. Will monitor for TP1 hit to move TP2 to breakeven...")        # Create a background thread to monitor without blocking the main loop
        from threading import Thread
        
        def monitor_tp1():
            max_checks = 720  # 2 hours max (10 seconds * 720 = 7200 seconds = 2 hours)
            checks = 0
            tp1_hit = False
            entry_price = current_price  # Use the actual entry price
            trade_completed = False
            
            while not tp1_hit and checks < max_checks:
                time.sleep(10)
                checks += 1
                
                # Check if TP1 position still exists
                try:
                    pos = mt5.positions_get(ticket=result1.order)
                    if not pos:
                        # TP1 closed - either hit TP or was manually closed
                        tp1_hit = True
                        
                        # Get TP2 position to verify it still exists
                        pos2 = mt5.positions_get(ticket=result2.order)
                        if pos2:
                            # Move SL to breakeven for TP2
                            # Add small buffer (0.1 point) to ensure we're actually in profit
                            if direction == 'BUY':
                                be_level = entry_price + (point * 0.1)
                            else:
                                be_level = entry_price - (point * 0.1)
                                  # Round to appropriate decimals
                            be_level = round(be_level, digits)
                            move_sl_to_breakeven(result2.order, be_level)
                            print(f"{datetime.now()} Moved SL to breakeven ({be_level}) for TP2 position {result2.order}")
                            # Log the breakeven move
                            with open("crt_skip_log.txt", "a") as f:
                                f.write(f"{datetime.now()} INFO: Moved TP2 position {result2.order} SL to breakeven ({be_level})\n")
                        else:
                            print("TP2 position no longer exists - both positions closed")
                            # Release trade lock so new trades can be taken
                            TRADE_LOCK = False
                            print(f"{datetime.now()} Trade lock released - both positions closed")
                            
                            # Set trade_completed flag to True
                            trade_completed = True
                            print(f"{datetime.now()} Trade completed successfully")
                except Exception as e:
                    print(f"Error monitoring TP1: {e}")
                    # Continue monitoring despite error
        
        # Start monitoring thread
        monitor_thread = Thread(target=monitor_tp1, daemon=True)
        monitor_thread.start()
        
        # Increment trades today count
        trades_today += 1
        print(f"{datetime.now()} Started trade {trades_today}/3 for today")
    else:
        time.sleep(60)

mt5.shutdown()
