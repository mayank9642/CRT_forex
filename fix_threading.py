import re

with open('exness_crt_trader.py', 'r') as f:
    content = f.read()

# Fix the threading import and monitor_tp1 definition
content = content.replace('print("Both orders placed successfully. Will monitor for TP1 hit to move TP2 to breakeven...")        # Create a background thread to monitor without blocking the main loop', 
                        'print("Both orders placed successfully. Will monitor for TP1 hit to move TP2 to breakeven...")\n        # Create a background thread to monitor without blocking the main loop')

# Fix the indent issue with move_sl_to_breakeven
content = content.replace('be_level = round(be_level, digits)\n                              # Round to appropriate decimals',
                        'be_level = round(be_level, digits)\n                                # Round to appropriate decimals')

with open('exness_crt_trader.py', 'w') as f:
    f.write(content)

print("Indentation fixes applied to exness_crt_trader.py")
