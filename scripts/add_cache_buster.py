import re
import time

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add a timestamp to the iframe src
ts = int(time.time())

content = re.sub(
    r'<iframe src="stock_TAIEX\.html(\?v=\d+)?"',
    f'<iframe src="stock_TAIEX.html?v={ts}"',
    content
)
content = re.sub(
    r'<iframe src="stock_TPEx\.html(\?v=\d+)?"',
    f'<iframe src="stock_TPEx.html?v={ts}"',
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Added cache-buster to iframes")
