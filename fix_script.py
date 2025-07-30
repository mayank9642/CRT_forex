# Fix indentation issues in the main trading script
import re

# Read the current file
file_path = "exness_crt_trader.py"
with open(file_path, "r") as file:
    lines = file.readlines()

# Process lines to fix indentation
fixed_lines = []
in_order_section = False
indent_level = 0

for line in lines:
    # Keep track if we're in the order placement section
    if "# Send first order" in line:
        in_order_section = True
        
    # Fix indentation in the problematic section
    if in_order_section and "if result" in line and "retcode ==" in line and line.strip().startswith("if"):
        # Make sure these lines have proper indentation
        stripped = line.lstrip()
        fixed_line = " " * 8 + stripped  # 8 spaces for proper nesting
        fixed_lines.append(fixed_line)
    else:
        fixed_lines.append(line)

# Write the fixed file
with open(file_path, "w") as file:
    file.writelines(fixed_lines)

print("Fixed indentation issues in", file_path)
