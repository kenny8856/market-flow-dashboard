import sqlite3
c = sqlite3.connect("db/twse_market.db").cursor()
print(c.execute("SELECT DISTINCT underlying_stock_id, underlying_stock_name FROM daily_warrants WHERE underlying_stock_name LIKE '%臺股指%'").fetchall())
