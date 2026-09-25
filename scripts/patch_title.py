import os

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target3 = "外資與投信每日多空金額 (萬元)"
replacement3 = "外資與投信每日多空金額 ({'億元' if stock_id in ['TAIEX', 'TPEx'] else '萬元'})"
content = content.replace(target3, replacement3)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated HTML title")
