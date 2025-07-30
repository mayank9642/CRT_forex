#!/usr/bin/env python
# Direct fix for the indentation error on line 637

with open('exness_crt_trader.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Get line 637 and check its indentation
print(f"Line 637: {lines[636]}")

# Fix the indentation - reduce by 4 spaces
if lines[636].startswith('    if'):
    lines[636] = lines[636][4:]  # Remove 4 spaces
    print(f"Fixed to: {lines[636]}")

# Check surrounding lines for context
print("\nSurrounding context:")
for i in range(max(0, 636-5), min(len(lines), 636+5)):
    print(f"Line {i+1}: {lines[i]}", end='')

# Write the fixed content back
with open('exness_crt_trader.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("\nLine 637 indentation fixed.")
