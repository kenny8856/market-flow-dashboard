import sqlite3

c = sqlite3.connect("db/twse_market.db").cursor()
print("Total Market Warrant Vol:", c.execute("SELECT SUM(trade_amount) FROM daily_warrants WHERE date='2026-09-24'").fetchone()[0])
print("IX0001 Call Vol:", c.execute("SELECT SUM(trade_amount) FROM daily_warrants WHERE date='2026-09-24' AND underlying_stock_id='IX0001' AND warrant_id NOT LIKE '%P' AND warrant_name NOT LIKE '%售%' AND warrant_name NOT LIKE '%熊%'").fetchone()[0])
print("IX0001 Put Vol:", c.execute("SELECT SUM(trade_amount) FROM daily_warrants WHERE date='2026-09-24' AND underlying_stock_id='IX0001' AND (warrant_id LIKE '%P' OR warrant_name LIKE '%售%' OR warrant_name LIKE '%熊%')").fetchone()[0])
