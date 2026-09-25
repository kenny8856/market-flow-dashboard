import os

file_path = r"C:\TW_Stock\src\stock_page_generator.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """        # 2. 查詢該股每日認購/認售權證成交額
        c.execute(\"\"\"
            SELECT date,
                   SUM(CASE WHEN warrant_id NOT LIKE '%P' AND warrant_name NOT LIKE '%售%' AND warrant_name NOT LIKE '%熊%' THEN trade_amount ELSE 0 END) as call_amt,
                   SUM(CASE WHEN warrant_id LIKE '%P' OR warrant_name LIKE '%售%' OR warrant_name LIKE '%熊%' THEN trade_amount ELSE 0 END) as put_amt
            FROM daily_warrants
            WHERE underlying_stock_id = ? AND date >= '2025-01-01'
            GROUP BY date
            ORDER BY date ASC
        \"\"\", (stock_id,))"""

replacement = """        # 2. 查詢該股每日認購/認售權證成交額 (加權指數的標的代號為 IX0001)
        underlying_param = 'IX0001' if stock_id == 'TAIEX' else stock_id
        c.execute(\"\"\"
            SELECT date,
                   SUM(CASE WHEN warrant_id NOT LIKE '%P' AND warrant_name NOT LIKE '%售%' AND warrant_name NOT LIKE '%熊%' THEN trade_amount ELSE 0 END) as call_amt,
                   SUM(CASE WHEN warrant_id LIKE '%P' OR warrant_name LIKE '%售%' OR warrant_name LIKE '%熊%' THEN trade_amount ELSE 0 END) as put_amt
            FROM daily_warrants
            WHERE underlying_stock_id = ? AND date >= '2025-01-01'
            GROUP BY date
            ORDER BY date ASC
        \"\"\", (underlying_param,))"""

if target in content:
    content = content.replace(target, replacement)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Warrants fixed in stock_page_generator.py")
else:
    print("Target not found for warrants.")
