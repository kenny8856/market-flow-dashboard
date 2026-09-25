import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix corrupted U or ? back to 萬
content = content.replace("U", "\u842c")
content = content.replace("U", "\u842c")
content = content.replace("??", "\u842c")
content = content.replace("", "\u5104") # fix corrupted 億

inst_block_start = content.find("const instChart = ")
warrant_block_start = content.find("const warrantChart = ")

top = content[:inst_block_start]
mid = content[inst_block_start:warrant_block_start]
bot = content[warrant_block_start:]

if "const unitName" not in mid:
    mid = mid.replace("const instChart = ", "const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));\n            const unitName = isIndex ? '\u5104' : '\u842c';\n            const instChart = ")
else:
    mid = re.sub(r"const unitName = [^;]+;", "const unitName = isIndex ? '\u5104' : '\u842c';", mid)

# DO NOT use raw string for repl if it contains \u
mid = re.sub(
    r"return Number\(val\)\.toFixed\(1\).+?;",
    "return Number(val).toFixed(1) + ' ' + (typeof unitName !== 'undefined' ? unitName : '\u842c');",
    mid
)

bot = re.sub(
    r"return Number\(val\)\.toFixed\(1\).+?;",
    "return Number(val).toFixed(1) + ' \u842c';",
    bot
)

content = top + mid + bot

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed encoding v3")
