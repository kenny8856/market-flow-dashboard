import re

with open(r'C:\TW_Stock\generate_quant_regime.py', 'r', encoding='utf-8') as f:
    text = f.read()

m = re.search(r'<body[^>]*>(.+?)</body>', text, re.DOTALL)
if m:
    with open('body.txt', 'w', encoding='utf-8') as f:
        f.write(m.group(1))
    print("Saved body.txt")
else:
    print("Not found")
