import sqlite3

def clean_fake_dates():
    conn_twse = sqlite3.connect('db/twse_market.db')
    conn_tpex = sqlite3.connect('db/tpex_market.db', timeout=10)
    
    twse_dates = set([r[0] for r in conn_twse.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
    tpex_dates = set([r[0] for r in conn_tpex.cursor().execute('SELECT DISTINCT date FROM daily_quotes').fetchall()])
    
    fake_dates = sorted(list(tpex_dates - twse_dates))
    print(f"Fake dates found in TPEx: {fake_dates}")
    
    if fake_dates:
        c = conn_tpex.cursor()
        for d in fake_dates:
            print(f"Deleting data for {d}...")
            c.execute('DELETE FROM daily_quotes WHERE date=?', (d,))
            c.execute('DELETE FROM daily_institutional WHERE date=?', (d,))
        conn_tpex.commit()
        print("Cleanup successful.")

if __name__ == '__main__':
    clean_fake_dates()
