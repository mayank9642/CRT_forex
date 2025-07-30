# test_exness_stops.py - Utility script to test Exness stop level requirements for XAUUSDm

import MetaTrader5 as mt5
import time
from datetime import datetime
import sys

# --- EXNESS TERMINAL PATH (set this to your Exness terminal64.exe) ---
EXNESS_MT5_PATH = r"C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"  # Update if needed
SYMBOLS_TO_TEST = ["XAUUSDm"]  # Add more symbols if needed

def test_symbol_stops(symbol):
    """Test stop level requirements for a given symbol"""
    print(f"\n===== TESTING {symbol} STOP LEVELS =====")
    
    # Get symbol info
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Failed to get symbol info for {symbol}")
        return False
    
    # Print detailed symbol info    print(f"Symbol: {info.name}")
    print(f"Point value: {info.point}")
    print(f"Digits: {info.digits}")
    print(f"Trade stops level: {info.trade_stops_level} points")
    print(f"Contract size: {info.trade_contract_size}")
    print(f"Min volume: {info.volume_min}")
    print(f"Volume step: {info.volume_step}")
      # Calculate minimum stop in price units
    min_stop_price = info.trade_stops_level * info.point
    print(f"Minimum stop in price units: {min_stop_price}")
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get current price for {symbol}")
        return False
    
    ask = tick.ask
    bid = tick.bid
    print(f"Current price: Ask={ask}, Bid={bid}, Spread={ask-bid}")
    
    # Test a minimal position with various stop levels
    volume = info.volume_min
      # Test stop levels at different distances
    # For gold, test specific price distances (common for gold: 0.5, 1.0, 2.0, etc)
    if symbol.startswith("XAU"):
        stop_levels_to_test = [
            0.5,   # $0.50 (likely too small)
            1.0,   # $1.00
            2.0,   # $2.00
            3.0,   # $3.00
            5.0,   # $5.00 
            10.0   # $10.00 (almost certainly sufficient)
        ]
    else:
        # For other instruments, use percentage of minimum stop
        stop_levels_to_test = [
            min_stop_price * 0.9,  # Should fail (10% below minimum)
            min_stop_price,         # Exactly at minimum
            min_stop_price * 1.1,   # 10% above minimum
            min_stop_price * 1.5,   # 50% above minimum
        ]
    
    # Test BUY order first
    print("\n----- Testing BUY orders -----")
    for sl_distance in stop_levels_to_test:
        sl = ask - sl_distance
        tp = ask + sl_distance * 2  # 2:1 risk-reward
        
        # Format sl and tp to the correct number of digits
        sl = round(sl, info.digits)
        tp = round(tp, info.digits)
        
        print(f"\nTesting BUY with SL at {sl} (distance: {ask-sl:.{info.digits}f})")
        print(f"Minimum required: {min_stop_price:.{info.digits}f}")
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY,
            "price": ask,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 12345,
            "comment": f"Stop test {sl_distance}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"SUCCESS: Order placed with SL at {sl}")
            
            # Close the position immediately
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": result.order,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_SELL,
                "price": bid,
                "deviation": 20,
                "magic": 12345,
                "comment": "Close test position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            close_result = mt5.order_send(close_request)
            if close_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Position closed successfully")
            else:
                print(f"Failed to close position: {close_result.retcode} - {close_result.comment}")
        else:
            print(f"FAILED: {result.retcode} - {result.comment}")
    
    # Test SELL order
    print("\n----- Testing SELL orders -----")
    for sl_distance in stop_levels_to_test:
        sl = bid + sl_distance
        tp = bid - sl_distance * 2  # 2:1 risk-reward
        
        # Format sl and tp to the correct number of digits
        sl = round(sl, info.digits)
        tp = round(tp, info.digits)
        
        print(f"\nTesting SELL with SL at {sl} (distance: {sl-bid:.{info.digits}f})")
        print(f"Minimum required: {min_stop_price:.{info.digits}f}")
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_SELL,
            "price": bid,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 12345,
            "comment": f"Stop test {sl_distance}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"SUCCESS: Order placed with SL at {sl}")
            
            # Close the position immediately
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": result.order,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY,
                "price": ask,
                "deviation": 20,
                "magic": 12345,
                "comment": "Close test position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            close_result = mt5.order_send(close_request)
            if close_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Position closed successfully")
            else:
                print(f"Failed to close position: {close_result.retcode} - {close_result.comment}")
        else:
            print(f"FAILED: {result.retcode} - {result.comment}")
            
    return True

def main():
    print("Connecting to Exness MT5 terminal...")
    if not mt5.initialize(EXNESS_MT5_PATH, portable=True):
        print(f"MT5 initialize() failed: {mt5.last_error()}")
        return
    
    # Check account info
    account = mt5.account_info()
    if account is None:
        print("Failed to get account info. Please ensure you are logged in manually.")
        mt5.shutdown()
        return
    
    print(f"Connected: {account.name} | Balance: {account.balance}")
    
    # Test all symbols
    for symbol in SYMBOLS_TO_TEST:
        test_symbol_stops(symbol)
    
    print("\nStop level testing completed!")
    mt5.shutdown()

if __name__ == "__main__":
    main()
