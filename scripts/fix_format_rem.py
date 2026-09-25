import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    "{inst_summary.get('trust_5d', 0):+d} 張",
    "{trust_5d_str}"
)
content = content.replace(
    "{inst_summary.get('foreign_5d', 0):+d} 張",
    "{foreign_5d_str}"
)
content = content.replace(
    "{inst_summary.get('margin_5d', 0):+d} 張",
    "{margin_5d_str}"
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed remaining +d formatting")
