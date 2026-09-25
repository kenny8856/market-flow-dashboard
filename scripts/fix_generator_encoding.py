import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Clean up corrupted unitName assignment
content = re.sub(
    r"const isIndex = \(\['TAIEX', 'TPEx'\]\.includes\('\{stock_id\}'\)\);\n\s*const unitName = [^\n]*;",
    r"const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));\n            const unitName = isIndex ? '\u5104' : '\u842c';",
    content
)

# 2. Fix the tooltip formatter in instChart
# We will use \u842c for 萬 to avoid any encoding problems
# Let's just find all corrupted formatters and replace them
content = re.sub(
    r"return Number\(val\)\.toFixed\(1\) \+ ' ' \+ \(typeof unitName !== 'undefined' \? unitName : '[^']*'\);",
    r"return Number(val).toFixed(1) + ' ' + (typeof unitName !== 'undefined' ? unitName : '\u842c');",
    content
)

# Wait, if Warrants chart ALSO uses unitName, it will show 億!
# We MUST fix Warrants chart to ONLY use 萬 (\u842c)!
# The Warrants chart starts at: // 4. 繪製副圖3：權證多空資金流
warrant_idx = content.find("instChart.syncCrosshair") # roughly where warrants start
if warrant_idx == -1:
    warrant_idx = content.find("warrantChart")

if warrant_idx != -1:
    top_part = content[:warrant_idx]
    bottom_part = content[warrant_idx:]
    
    # In bottom_part, replace unitName back to \u842c
    bottom_part = re.sub(
        r"return Number\(val\)\.toFixed\(1\) \+ ' ' \+ \(typeof unitName !== 'undefined' \? unitName : '\u842c'\);",
        r"return Number(val).toFixed(1) + ' \u842c';",
        bottom_part
    )
    # Also replace any corrupted ones
    bottom_part = re.sub(
        r"return Number\(val\)\.toFixed\(1\) \+ ' ' \+ \(typeof unitName !== 'undefined' \? unitName : '[^']*'\);",
        r"return Number(val).toFixed(1) + ' \u842c';",
        bottom_part
    )
    content = top_part + bottom_part

# 3. Fix the HTML legends if they got corrupted
content = re.sub(r"\{\'[^']*\' if stock_id in \['TAIEX', 'TPEx'\] else \'[^']*\'\}", "{'\u5104\u5143' if stock_id in ['TAIEX', 'TPEx'] else '\u842c\u5143'}", content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed generator encoding issues")
