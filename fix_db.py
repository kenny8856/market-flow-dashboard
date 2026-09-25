import sqlite3
conn_twse = sqlite3.connect('db/twse_market.db')
conn_tpex = sqlite3.connect('db/tpex_market.db')
twse = set([r[0] for r in conn_twse.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
tpex = set([r[0] for r in conn_tpex.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
fake_dates = sorted(list(tpex - twse))
print('Fake dates:', fake_dates)
if fake_dates:
    c = conn_tpex.cursor()
    for d in fake_dates:
        c.execute('DELETE FROM daily_quotes WHERE date=?', (d,))
        c.execute('DELETE FROM daily_institutional WHERE date=?', (d,))
    conn_tpex.commit()
    print('Cleaned up fake dates in TPEx DB.')

