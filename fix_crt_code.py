#!/usr/bin/env python
# Script to completely fix the CRT trader file
import sys
import os
import re

def remove_duplicate_atr():
    """Remove duplicate ATR function"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the duplicate ATR function and remove it
    duplicate_found = False
    start_idx = None
    end_idx = None
    
    for i, line in enumerate(lines):
        if "# --- Helper: Calculate ATR (Average True Range) ---" in line:
            start_idx = i
        if start_idx is not None and start_idx < i:
            if "def get_symbol_details" in line:
                end_idx = i
                break
    
    if start_idx is not None and end_idx is not None:
        print(f"Found duplicate ATR function at lines {start_idx} to {end_idx-1}")
        # Delete the duplicate
        lines = lines[:start_idx] + lines[end_idx:]
    else:
        print("No duplicate ATR function found")
    
    # Write back the file
    with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
        
def fix_trade_lock():
    """Fix TRADE_LOCK variable declaration and usage"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add proper global declaration before setting TRADE_LOCK
    pattern = r'(TRADE_LOCK = True)'
    replacement = r'global TRADE_LOCK\n    \1'
    content = re.sub(pattern, replacement, content)
    
    # Fix the trade lock release function
    pattern = r'def release_lock_after_cooldown\(\):[\s\S]*?TRADE_LOCK = False'
    replacement = """def release_lock_after_cooldown():
            global TRADE_LOCK
            time.sleep(COOLDOWN_MINUTES * 60)
            TRADE_LOCK = False"""
    content = re.sub(pattern, replacement, content)
    
    # Write back the file
    with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
        f.write(content)

def fix_if_statements():
    """Fix indentation in if statements"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Fix indentation issues in if statements
    for i, line in enumerate(lines):
        if re.match(r'^\s{2}if', line) and not re.match(r'^\s{4}if', line):
            lines[i] = re.sub(r'^(\s{2})', r'    ', line)
    
    # Write back the file
    with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)

def fix_sl_calculation():
    """Fix the SL calculation section"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix issues with min_stop_price for gold
    pattern = r'if SYMBOL.startswith\("XAU"\):.*?min_stop_price = MIN_SL_DISTANCE.*?else:.*?min_stop_price = stops_level \* point.*?if min_stop_price < 0\.0001:.*?min_stop_price = MIN_SL_DISTANCE'
    replacement = """if SYMBOL.startswith("XAU"):
        # Use 1.5x ATR or minimum buffer, whichever is larger
        dynamic_sl_buffer = max(atr_value * 1.5, MIN_SL_DISTANCE)
        # Use a fixed minimum SL distance for gold that we know works
        min_stop_price = MIN_SL_DISTANCE
    else:
        dynamic_sl_buffer = max(atr_value * 1.5, SL_BUFFER)
        min_stop_price = stops_level * point
        if min_stop_price < 0.0001:
            min_stop_price = MIN_SL_DISTANCE"""
    
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Write back the file
    with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
        f.write(content)

def completely_fix_order_placement():
    """Completely rewrite the order placement section to fix all issues"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the order placement section
    start_pattern = r'# Place order \(split into two positions for partial TP\)'
    end_pattern = r'# Monitor for TP1 hit to move SL to breakeven for TP2'
    
    start_idx = content.find(start_pattern)
    end_idx = content.find(end_pattern)
    
    if start_idx != -1 and end_idx != -1:
        # Extract everything before and after the order placement section
        before = content[:start_idx]
        after = content[end_idx:]
        
        # New, clean order placement code
        new_order_placement = """# Place order (split into two positions for partial TP)
    # Double-check SL one final time for Gold
    if SYMBOL.startswith("XAU"):
        # Ensure minimum SL distance for Gold
        if direction == 'BUY':
            min_required_sl = current_price - MIN_SL_DISTANCE
            if sl > min_required_sl:  # SL too close to price
                sl = min_required_sl
                sl = round(sl, digits)
                print(f"Adjusted BUY SL to ensure minimum distance: {sl}, distance: {current_price-sl:.2f}")
        else:  # SELL
            min_required_sl = current_price + MIN_SL_DISTANCE
            if sl < min_required_sl:  # SL too close to price
                sl = min_required_sl
                sl = round(sl, digits)
                print(f"Adjusted SELL SL to ensure minimum distance: {sl}, distance: {sl-current_price:.2f}")
    
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
            f.write(f"{broker_now} SKIP: Final R:R too low after SL adjustments (TP1: {rr1:.2f}, TP2: {rr2:.2f})\\n")
        
        # Release the trade lock
        TRADE_LOCK = False
        time.sleep(60)
        continue
    
    # --- Order Placement with comprehensive error handling ---
    # Send first order
    print(f"Sending order 1: {direction} | Price: {current_price} | SL: {sl} | TP: {tp1} | SL Distance: {abs(current_price-sl):.2f}")
    result1 = mt5.order_send(request1)
    
    if result1 is None:
        print("Error: Order 1 returned None")
        TRADE_LOCK = False
        time.sleep(60)
        continue
    
    # Handle invalid stops error
    if result1.retcode == 10016:  # Invalid stops error
        print(f"⚠️ INVALID STOPS ERROR for order 1:")
        print(f"  Symbol: {SYMBOL}")
        print(f"  Direction: {direction}")
        print(f"  Price: {current_price}")
        print(f"  SL: {sl} (distance: {abs(current_price-sl):.2f})")
        print(f"  Min required: {min_stop_price:.2f}")
        
        # Try a larger SL distance for Gold
        if SYMBOL.startswith("XAU"):
            # Use a larger safe distance
            safe_distance = MIN_SL_DISTANCE * 2.0  # Double the minimum
            
            if direction == 'BUY':
                new_sl = round(current_price - safe_distance, digits)
            else:
                new_sl = round(current_price + safe_distance, digits)
                
            print(f"Using larger SL distance of {safe_distance:.2f} → SL: {new_sl}")
            
            # Update request with new SL
            request1_retry = request1.copy()
            request1_retry["sl"] = new_sl
            retry_result1 = mt5.order_send(request1_retry)
            
            if retry_result1 and retry_result1.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"SUCCESS with larger SL distance!")
                result1 = retry_result1  # Use the successful result
                sl = new_sl  # Update SL for second order
            else:
                # Try alternative approach: place without SL/TP first, then modify
                print("Trying alternative: place without SL/TP first")
                request1_no_sl = request1.copy()
                request1_no_sl.pop('sl', None)
                request1_no_sl.pop('tp', None)
                alt_result1 = mt5.order_send(request1_no_sl)
                
                if alt_result1 and alt_result1.retcode == mt5.TRADE_RETCODE_DONE:
                    # Add SL/TP in a separate request
                    modify_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": alt_result1.order,
                        "symbol": SYMBOL,
                        "sl": new_sl,
                        "tp": tp1,
                    }
                    modify_result = mt5.order_send(modify_request)
                    
                    if modify_result and modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                        print("Successfully added SL/TP after position opened")
                        result1 = alt_result1  # Use the successful result
                        sl = new_sl  # Update SL for second order
                    else:
                        print(f"Failed to add SL/TP: {modify_result.retcode} {modify_result.comment}")
                        # At least we have a position open, continue with order 2
                else:
                    print(f"All attempts to open position 1 failed")
                    TRADE_LOCK = False
                    time.sleep(60)
                    continue
    
    # If first order succeeded or we've updated the SL, proceed with second order
    if result1.retcode == mt5.TRADE_RETCODE_DONE:
        print(f"{entry_candle.name} {direction} TP1 order placed at {current_price} | SL: {sl} | TP: {tp1} | RR1: {rr1:.2f}")
        log_trade(result1.order, str(broker_now), SYMBOL, direction, current_price, sl, tp1, half_lot, rr1, rr2, "OPEN", "", "", request1['comment'])
        
        # Update second order request with potentially modified SL
        request2["sl"] = sl
        
        # Send second order
        print(f"Sending order 2: {direction} | Price: {current_price} | SL: {sl} | TP: {tp2}")
        result2 = mt5.order_send(request2)
        
        if result2 is None:
            print("Error: Order 2 returned None")
            # Continue anyway, we at least have one position open
        elif result2.retcode == 10016:  # Invalid stops error for second order
            print(f"⚠️ INVALID STOPS ERROR for order 2 - unexpected since we used same SL as order 1")
            
            # Try alternative for second order too
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
                
                if modify_result and modify_result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"Successfully added SL/TP to position 2")
                    result2 = alt_result2  # Consider it successful
                else:
                    print(f"Failed to add SL/TP to position 2: {modify_result.retcode} {modify_result.comment}")
            else:
                print(f"Failed to open position 2: {alt_result2.retcode if alt_result2 else 'Unknown error'}")
                
        if result2 and result2.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"{entry_candle.name} {direction} TP2 order placed at {current_price} | SL: {sl} | TP: {tp2} | RR2: {rr2:.2f}")
            log_trade(result2.order, str(broker_now), SYMBOL, direction, current_price, sl, tp2, half_lot, rr1, rr2, "OPEN", "", "", request2['comment'])
        else:
            print(f"Order 2 failed or partially succeeded. Continuing with at least order 1 active")
    else:
        print(f"Order 1 failed: {result1.retcode} {result1.comment}")
        TRADE_LOCK = False
        time.sleep(60)
        continue
        
    # Schedule the trade lock to be released after cooldown
    from threading import Thread
    def release_lock_after_cooldown():
        global TRADE_LOCK
        time.sleep(COOLDOWN_MINUTES * 60)
        TRADE_LOCK = False
        print(f"Trade lock released after {COOLDOWN_MINUTES} minute cooldown")
    
    # Start the cooldown in a separate thread
    Thread(target=release_lock_after_cooldown, daemon=True).start()
    
    # Increment trades count for today
    trades_today += 1"""
        
        # Replace the section
        new_content = before + new_order_placement + after
        
        with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("Successfully replaced the order placement section")
    else:
        print("Failed to find the order placement section")

def fix_monitoring_section():
    """Fix the monitoring section for TP1 hit"""
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the monitoring section
    start_pattern = r'# Monitor for TP1 hit to move SL to breakeven for TP2'
    end_pattern = r'mt5.shutdown()'
    
    start_idx = content.find(start_pattern)
    end_idx = content.rfind(end_pattern)
    
    if start_idx != -1 and end_idx != -1:
        # Extract everything before and after the monitoring section
        before = content[:start_idx]
        after = content[end_idx:]
        
        # New, clean monitoring code
        new_monitoring = """# Monitor for TP1 hit to move SL to breakeven for TP2
    if result1 and result2 and result1.retcode == mt5.TRADE_RETCODE_DONE and result2.retcode == mt5.TRADE_RETCODE_DONE:
        print("Both orders placed successfully. Will monitor for TP1 hit to move TP2 to breakeven...")
        # Create a background thread to monitor without blocking the main loop
        from threading import Thread
        
        def monitor_tp1():
            max_checks = 720  # 12 hours max (60 seconds * 720 = 43200 seconds = 12 hours)
            checks = 0
            tp1_hit = False
            entry_price = current_price  # Use the actual entry price
            
            while not tp1_hit and checks < max_checks:
                time.sleep(60)  # Check every minute instead of every 10 seconds
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
                                be_level = entry_price + (point * 1)
                            else:
                                be_level = entry_price - (point * 1)
                                
                            # Round to appropriate decimals
                            be_level = round(be_level, digits)
                            
                            move_sl_to_breakeven(result2.order, be_level)
                            print(f"{datetime.now()} Moved SL to breakeven ({be_level}) for TP2 position {result2.order}")
                            
                            # Log the breakeven move
                            with open("crt_skip_log.txt", "a") as f:
                                f.write(f"{datetime.now()} INFO: Moved TP2 position {result2.order} SL to breakeven ({be_level})\\n")
                        else:
                            print("TP2 position no longer exists - both positions closed")
                except Exception as e:
                    print(f"Error monitoring TP1: {e}")
                    # Continue monitoring despite error
        
        # Start monitoring thread
        Thread(target=monitor_tp1, daemon=True).start()
    
    time.sleep(60)  # Wait before looking for next setup
"""
        
        # Replace the section
        new_content = before + new_monitoring + after
        
        with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        print("Successfully fixed the monitoring section")
    else:
        print("Failed to find the monitoring section")

def main():
    print("Starting comprehensive fixes to the CRT trader file...")
    
    # Fix functions in the correct order
    remove_duplicate_atr()
    fix_trade_lock()
    fix_if_statements()
    fix_sl_calculation()
    completely_fix_order_placement()
    fix_monitoring_section()
    
    print("All fixes applied. The CRT trader file should now be properly formatted and functional.")
    
if __name__ == "__main__":
    main()
