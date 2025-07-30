#!/usr/bin/env python
# Test script for CRT order placement with proper stop-loss

import MetaTrader5 as mt5
import time
from datetime import datetime
import sys

# --- EXNESS TERMINAL PATH (set this to your Exness terminal64.exe) ---
EXNESS_MT5_PATH = r"C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"  # Update if needed

def place_test_order(symbol="XAUUSDm", direction="BUY", lot_size=0.01):
    """Place a test order with proper SL/TP handling"""
    print(f"\n===== TESTING {direction} ORDER WITH PROPER STOP HANDLING =====")
    
    # Get symbol info
    info = mt5.symbol_info(symbol)
    if info is None:
        print(f"Failed to get symbol info for {symbol}")
        return False
    
    # Print symbol details
    digits = info.digits
    point = info.point
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"Failed to get current price for {symbol}")
        return False
    
    ask = tick.ask
    bid = tick.bid
    
    # Calculate SL/TP
    if direction == "BUY":
        entry_price = ask
        sl_price = entry_price - 1.0  # $1.00 SL distance for gold
        tp_price = entry_price + 3.0  # $3.00 TP for 1:3 R:R
    else:  # SELL
        entry_price = bid
        sl_price = entry_price + 1.0  # $1.00 SL distance for gold
        tp_price = entry_price - 3.0  # $3.00 TP for 1:3 R:R
    
    # Round to proper digits
    sl_price = round(sl_price, digits)
    tp_price = round(tp_price, digits)
    
    print(f"Symbol: {symbol}")
    print(f"Direction: {direction}")
    print(f"Entry price: {entry_price}")
    print(f"SL price: {sl_price} (distance: {abs(entry_price-sl_price):.2f})")
    print(f"TP price: {tp_price} (distance: {abs(entry_price-tp_price):.2f})")
    
    # Create trade request
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_size,
        "type": mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": entry_price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 20,
        "magic": 12345,
        "comment": f"CRT test order",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    # Send order
    print("Sending order...")
    result = mt5.order_send(request)
    
    if result is None:
        print("Order send returned None!")
        return False
        
    print(f"Order result: {result.retcode} - {result.comment}")
    
    # Handle "Invalid stops" error
    if result.retcode == 10016:  # Invalid stops
        print("INVALID STOPS ERROR - trying with larger SL distance")
        
        # Try with larger SL distances
        for distance in [2.0, 3.0, 5.0]:
            if direction == "BUY":
                new_sl = round(entry_price - distance, digits)
            else:
                new_sl = round(entry_price + distance, digits)
                
            print(f"Trying SL distance of {distance:.1f} → SL: {new_sl}")
            request["sl"] = new_sl
            
            retry_result = mt5.order_send(request)
            if retry_result and retry_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"SUCCESS with SL distance {distance:.1f}")
                result = retry_result
                break
        
        # If still failed, try two-step approach
        if result.retcode == 10016:
            print("Still failing - trying two-step approach (open then modify)")
            request_no_sl = request.copy()
            request_no_sl.pop('sl', None)
            request_no_sl.pop('tp', None)
            
            print("Opening position without SL/TP first...")
            no_sl_result = mt5.order_send(request_no_sl)
            
            if no_sl_result and no_sl_result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"Position opened without SL/TP. Position ID: {no_sl_result.order}")
                time.sleep(1)  # Small delay
                
                # Now add SL/TP
                modify_request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "position": no_sl_result.order,
                    "symbol": symbol,
                    "sl": sl_price,
                    "tp": tp_price,
                }
                
                print(f"Adding SL ({sl_price}) and TP ({tp_price})...")
                modify_result = mt5.order_send(modify_request)
                
                if modify_result and modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                    print("Successfully added SL/TP!")
                    result = no_sl_result
                else:
                    print(f"Failed to add SL/TP: {modify_result.retcode} - {modify_result.comment}")
                    
                    # Try again with larger SL
                    if direction == "BUY":
                        larger_sl = round(entry_price - 5.0, digits)
                    else:
                        larger_sl = round(entry_price + 5.0, digits)
                        
                    print(f"Trying with larger SL: {larger_sl}")
                    modify_request["sl"] = larger_sl
                    
                    modify_result = mt5.order_send(modify_request)
                    if modify_result and modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                        print("Successfully added SL/TP with larger SL!")
                        result = no_sl_result
    
    # Check final result
    if result.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"Order successfully placed! Position ID: {result.order}")
        print("Waiting 5 seconds to check position details...")
        time.sleep(5)
        
        # Verify position details
        position = mt5.positions_get(ticket=result.order)
        if position:
            pos = position[0]
            print(f"Position verified:")
            print(f"  Symbol: {pos.symbol}")
            print(f"  Type: {'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL'}")
            print(f"  Entry Price: {pos.price_open}")
            print(f"  Current Price: {pos.price_current}")
            print(f"  SL: {pos.sl}")
            print(f"  TP: {pos.tp}")
            print(f"  SL Distance: {abs(pos.price_open-pos.sl):.2f}")
            
            # Close the test position
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": result.order,
                "symbol": symbol,
                "volume": lot_size,
                "type": mt5.ORDER_TYPE_SELL if direction == "BUY" else mt5.ORDER_TYPE_BUY,
                "price": pos.price_current,
                "deviation": 20,
                "magic": 12345,
                "comment": "Close test position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            print("Closing test position...")
            close_result = mt5.order_send(close_request)
            if close_result and close_result.retcode == mt5.TRADE_RETCODE_DONE:
                print("Test position closed successfully")
            else:
                print(f"Failed to close position: {close_result.retcode} - {close_result.comment}")
        else:
            print("Could not find position details after opening")
        
        return True
    else:
        print(f"Order placement failed: {result.retcode} - {result.comment}")
        return False

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
    
    # Test orders
    place_test_order(symbol="XAUUSDm", direction="BUY", lot_size=0.01)
    print("\nWaiting 5 seconds before next test...")
    time.sleep(5)
    place_test_order(symbol="XAUUSDm", direction="SELL", lot_size=0.01)
    
    print("\nTest completed!")
    mt5.shutdown()

if __name__ == "__main__":
    main()
