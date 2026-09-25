import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# We need to find the instChart and warrantChart blocks and replace the formatters
# using explicit strings. We will write the file in utf-8.

# First, let's fix any corrupted 'U' back to '\u842c' (萬)
content = content.replace("U", "\u842c")
content = content.replace("??", "\u842c")

# 1. instChart formatting
# We need to use `unitName` instead of hardcoded 萬 for instChart.
# The code defining unitName is:
# const unitName = isIndex ? '億' : '萬';
# We will use \u5104 for 億 and \u842c for 萬

inst_block_start = content.find("const instChart = ")
warrant_block_start = content.find("const warrantChart = ")

top = content[:inst_block_start]
mid = content[inst_block_start:warrant_block_start]
bot = content[warrant_block_start:]

# Fix mid (instChart)
# Make sure unitName is correctly defined
if "const unitName" not in mid:
    mid = mid.replace("const instChart = ", "const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));\n            const unitName = isIndex ? '\u5104' : '\u842c';\n            const instChart = ")
else:
    mid = re.sub(r"const unitName = [^;]+;", "const unitName = isIndex ? '\u5104' : '\u842c';", mid)

# Fix formatter in mid
mid = re.sub(
    r"return Number\(val\)\.toFixed\(1\).+?;",
    r"return Number(val).toFixed(1) + ' ' + (typeof unitName !== 'undefined' ? unitName : '\u842c');",
    mid
)

# Fix bot (warrantChart)
# Warrant chart should ALWAYS use 萬 (\u842c)
bot = re.sub(
    r"return Number\(val\)\.toFixed\(1\).+?;",
    r"return Number(val).toFixed(1) + ' \u842c';",
    bot
)

content = top + mid + bot

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed generator encoding carefully")
