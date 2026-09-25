import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace header formatting logic
replacement = """
        trust_5d_val = stock_info.get('inst_5d', {}).get('trust_5d', 0)
        foreign_5d_val = stock_info.get('inst_5d', {}).get('foreign_5d', 0)
        margin_5d_val = stock_info.get('inst_5d', {}).get('margin_5d', 0)
        
        if stock_id in ['TAIEX', 'TPEx']:
            trust_5d_str = f"{trust_5d_val:+.1f} 億"
            foreign_5d_str = f"{foreign_5d_val:+.1f} 億"
            margin_5d_str = f"{margin_5d_val:+.1f} 億" if margin_5d_val != 0 else "+0 億"
        else:
            trust_5d_str = f"{int(trust_5d_val):+d} 張"
            foreign_5d_str = f"{int(foreign_5d_val):+d} 張"
            margin_5d_str = f"{int(margin_5d_val):+d} 張"

        header_stats = f\"\"\"
"""

target = """        header_stats = f\"\"\"
"""

# Replace in content, inserting our variable logic right before header_stats
# We must find the line `header_stats = f"""`
content = content.replace(target, replacement)

# Now fix the f-string inside header_stats
content = content.replace(
    "{stock_info.get('inst_5d', {}).get('trust_5d', 0):+d} 張",
    "{trust_5d_str}"
)
content = content.replace(
    "{stock_info.get('inst_5d', {}).get('foreign_5d', 0):+d} 張",
    "{foreign_5d_str}"
)
content = content.replace(
    "{stock_info.get('inst_5d', {}).get('margin_5d', 0):+d} 張",
    "{margin_5d_str}"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed header formatting")
