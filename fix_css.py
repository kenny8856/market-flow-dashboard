import os

with open('generate_quant_regime.py', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix .stock-card width issue
target = ".stock-card {\n            background: var(--bg-card);"
replacement = ".stock-card {\n            background: var(--bg-card);\n            min-width: 0; /* Fix mobile grid overflow */\n            max-width: 100%;"
if target in code:
    code = code.replace(target, replacement)

# Fix minmax(400px, 1fr) for new sections
if 'minmax(400px,1fr)' in code:
    code = code.replace('minmax(400px,1fr)', 'minmax(min(100%, 400px), 1fr)')

# Ensure all grids don't overflow
grid_fixes = [
    ('.cards-list {\n            display: grid;\n            grid-template-columns: 1fr;', '.cards-list {\n            display: grid;\n            grid-template-columns: minmax(0, 1fr);'),
    ('grid-template-columns: 1fr;', 'grid-template-columns: minmax(0, 1fr);') # general fix for media query 1fr
]
for t, r in grid_fixes:
    code = code.replace(t, r)

with open('generate_quant_regime.py', 'w', encoding='utf-8') as f:
    f.write(code)

# Fix stock_page_generator.py
stock_gen_path = os.path.join('src', 'stock_page_generator.py')
if os.path.exists(stock_gen_path):
    with open(stock_gen_path, 'r', encoding='utf-8') as f2:
        stock_code = f2.read()
    
    if 'xiaoge-table-wrapper' not in stock_code:
        stock_code = stock_code.replace('<table class="xiaoge-table">', '<div class="xiaoge-table-wrapper" style="overflow-x: auto; max-width: 100%; width: 100%;"><table class="xiaoge-table">')
        stock_code = stock_code.replace('</table>\n        </div>', '</table></div>\n        </div>')
        
    with open(stock_gen_path, 'w', encoding='utf-8') as f2:
        f2.write(stock_code)
