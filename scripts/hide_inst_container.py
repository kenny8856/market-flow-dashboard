import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """<div id="inst-chart-container" class="chart-box-inst"></div>"""
replacement = """<div id="inst-chart-container" class="chart-box-inst" style="{'''display:none;''' if stock_id == 'TPEx' else ''}"></div>"""

content = content.replace(target, replacement)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Hid inst chart container")
