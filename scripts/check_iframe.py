import re
s = open(r'C:\TW_Stock\docs\index.html', 'r', encoding='utf-8').read()
m = re.search(r'<div id="tab-taiex".*?</div>\s*</div>', s, re.DOTALL)
print(m.group(0) if m else 'not found')
