#!/usr/bin/env python
# Script to test the fixed CRT trading system

import MetaTrader5 as mt5
import time
import os
from datetime import datetime, timedelta

# Path to Exness MT5 terminal
EXNESS_MT5_PATH = r"C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"
SYMBOL = "XAUUSDm"

def initialize_mt5():
    """Initialize connection to MT5 terminal"""
    print(f"Connecting to MT5 at {EXNESS_MT5_PATH}...")
    if not mt5.initialize(EXNESS_MT5_PATH, portable=True):
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return False
    
    # Check if connected
    if not mt5.terminal_info():
        print("Failed to get terminal info")
        return False
    
    account = mt5.account_info()
    if account is None:
        print("Failed to get account info. Please log in manually to the terminal.")
        return False
    
    print(f"Connected to account: {account.login} ({account.company})")
    print(f"Balance: {account.balance} {account.currency}")
    return True

def test_atr_calculation():
    """Test the ATR calculation for gold"""
    from exness_crt_trader import calculate_atr, get_rates
    
    # Test on different timeframes
    for tf in [mt5.TIMEFRAME_D1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_H1]:
        atr = calculate_atr(SYMBOL, tf, 14)
        print(f"ATR for {SYMBOL} on timeframe {tf}: {atr:.2f} USD")

def test_sl_distance():
    """Test different stop-loss distances for gold"""
    # Get current price
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        print("Failed to get current tick")
        return
    
    print(f"Current price for {SYMBOL}: Ask={tick.ask:.2f}, Bid={tick.bid:.2f}")
    
    # Test BUY order with different SL distances
    test_distances = [0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 50.0]
    
    for dist in test_distances:
        print(f"\nTesting BUY with SL distance: {dist:.2f}")
        sl_price = tick.ask - dist
        
        # Create minimal request to test
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "sl": sl_price,
            "deviation": 10,
            "magic": 12345,
            "comment": f"Test SL {dist}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Just check if the request is valid, don't actually place it
        result = mt5.order_check(request)
        
        if result is None:
            print(f"Check failed: {mt5.last_error()}")
        elif result.retcode != 0:
            print(f"Check error: {result.retcode} - {result.comment}")
        else:
            print(f"Check OK! SL distance of {dist:.2f} is valid")
    
    # Test SELL orders
    print("\n--- Testing SELL orders ---")
    for dist in test_distances:
        print(f"\nTesting SELL with SL distance: {dist:.2f}")
        sl_price = tick.bid + dist
        
        # Create minimal request to test
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": 0.01,
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "sl": sl_price,
            "deviation": 10,
            "magic": 12345,
            "comment": f"Test SL {dist}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Just check if the request is valid, don't actually place it
        result = mt5.order_check(request)
        
        if result is None:
            print(f"Check failed: {mt5.last_error()}")
        elif result.retcode != 0:
            print(f"Check error: {result.retcode} - {result.comment}")
        else:
            print(f"Check OK! SL distance of {dist:.2f} is valid")

def main():
    """Main test function"""
    if not initialize_mt5():
        print("Failed to initialize. Exiting.")
        return
    
    try:
        print("\n=== Testing ATR Calculation ===")
        test_atr_calculation()
        
        print("\n=== Testing Stop-Loss Distances ===")
        test_sl_distance()
        
    finally:
        print("\nShutting down MT5...")
        mt5.shutdown()
        print("Test completed.")

if __name__ == "__main__":
    main()
