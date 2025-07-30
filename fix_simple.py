#!/usr/bin/env python
# Simple script to fix indentation issues in exness_crt_trader.py

def fix_indentation():
    print("Fixing indentation in exness_crt_trader.py...")
    
    with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix specific indentation issues
    # 1. Issue on line 637 with "if result1.retcode == 10016:"
    content = content.replace("    if result1.retcode == 10016:", "if result1.retcode == 10016:")
    content = content.replace("        print(f\"⚠️ INVALID STOPS ERROR", "    print(f\"⚠️ INVALID STOPS ERROR")
    
    # Fix other common indentation issues
    content = content.replace("            # Use a fixed large SL distance", "        # Use a fixed large SL distance")
    content = content.replace("            safe_distance", "        safe_distance")
    
    # Fix inconsistent indentation in the order placement section
    lines = content.split('\n')
    in_order_placement = False
    fixed_lines = []
    
    for line in lines:
        # Check if we're in the order placement section
        if "# Place order (split into two positions for partial TP)" in line:
            in_order_placement = True
            fixed_lines.append(line)
            continue
            
        # Check if we've left the order placement section
        if in_order_placement and "# Monitor for TP1 hit to move SL to breakeven for TP2" in line:
            in_order_placement = False
            fixed_lines.append(line)
            continue
            
        # Fix indentation in order placement section
        if in_order_placement:
            # Check for wrong indentation
            if line.startswith("        ") and not line.startswith("            "):
                line = "    " + line
            elif line.startswith("            "):
                line = "        " + line[12:]
            
        fixed_lines.append(line)
    
    # Write fixed content back to file
    with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print("Indentation fixed.")

if __name__ == "__main__":
    fix_indentation()
