file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace("return Number(val).toFixed(1) + ' 萬';", "return Number(val).toFixed(1) + ' ' + (typeof unitName !== 'undefined' ? unitName : '萬');")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced 萬 successfully")
