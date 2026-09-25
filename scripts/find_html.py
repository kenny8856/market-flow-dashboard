import re

with open(r'C:\TW_Stock\generate_quant_regime.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "html_out" in line:
        print(f"Line {i}: {line.strip()[:100]}")
