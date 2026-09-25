import sqlite3
conn_twse = sqlite3.connect('db/twse_market.db')
conn_tpex = sqlite3.connect('db/tpex_market.db')
twse_dates = set([r[0] for r in conn_twse.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
tpex_dates = set([r[0] for r in conn_tpex.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
print('In TPEx but not TWSE:', sorted(list(tpex_dates - twse_dates)))

