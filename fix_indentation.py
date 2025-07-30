#!/usr/bin/env python
# Script to fix indentation in exness_crt_trader.py

import re
import sys
import os

def fix_indentation(input_file, output_file=None):
    """Fix indentation issues in the trading strategy file"""
    if output_file is None:
        output_file = input_file
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Fix specific indentation issues
    for i in range(len(lines)):
        # Fix basic indentation for if statements
        if re.search(r'^\s{2}if', lines[i]) and not re.search(r'^\s{4}if', lines[i]):
            lines[i] = re.sub(r'^(\s{2})', r'    ', lines[i])
        
        # Fix TRADE_LOCK global declaration
        if "TRADE_LOCK = True" in lines[i] and "global TRADE_LOCK" not in lines[i-3:i]:
            lines[i] = "    global TRADE_LOCK\n" + lines[i]
        
        # Fix indentation for cooldown function
        if "def release_lock_after_cooldown" in lines[i]:
            lines[i] = "        def release_lock_after_cooldown():\n"
        
        # Fix indentation for global statement in cooldown function
        if "global TRADE_LOCK" in lines[i] and "def release_lock_after_cooldown" in lines[i-1]:
            lines[i] = "            global TRADE_LOCK\n"
        
        # Fix other issues inside the cooldown function
        if "TRADE_LOCK = False" in lines[i] and "def release_lock_after_cooldown" in lines[i-3:i]:
            lines[i] = "            TRADE_LOCK = False\n"
        
        # Fix min_stop_price line
        if "min_stop_price = MIN_SL_DISTANCE" in lines[i]:
            lines[i] = "    # Use a fixed minimum SL distance for gold that we know works\n    min_stop_price = MIN_SL_DISTANCE\n"
    
    # Write the fixed content
    with open(output_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print(f"Fixed indentation issues and saved to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None
    else:
        input_file = 'c:\\vs code projects\\forex strategies\\crt_trading_system\\exness_crt_trader.py'
        output_file = None
    
    fix_indentation(input_file, output_file)
