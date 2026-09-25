# -*- coding: utf-8 -*-
import sqlite3
import datetime
import os

def get_top_futures_shorts():
    conn = sqlite3.connect('db/taifex_large_trader.db')
    c = conn.cursor()
    c.execute('SELECT MAX(date) FROM futures_large_traders')
    latest_date = c.fetchone()[0]
    if not latest_date: return '', []
    
    exclude_keywords = ['臺股', '臺指', '電子', '金融', '半導體', '航運', 'ETF', '非金電', '櫃買', '生技', '富櫃', '道瓊', '那斯達克', '標普', '東證', '美元', '匯率', '選擇權']
    
    c.execute('''
        SELECT contract_code, contract_name, sell_top10, net_top10, market_oi
        FROM futures_large_traders
        WHERE date=? AND contract_type='所有契約'
        ORDER BY sell_top10 DESC
    ''', (latest_date,))
    rows = c.fetchall()
    
    top20 = []
    for r in rows:
        name = r[1]
        if not any(k in name for k in exclude_keywords):
            top20.append(r)
        if len(top20) >= 20:
            break
            
    conn.close()
    return latest_date, top20

def get_hot_cbs():
    if not os.path.exists('db/cb_market.db'):
        return '', []
    conn = sqlite3.connect('db/cb_market.db')
    c = conn.cursor()
    c.execute('SELECT MAX(date) FROM daily_cb_quotes')
    latest_date = c.fetchone()[0]
    if not latest_date: return '', []
    
    c.execute('''
        SELECT cb_id, cb_name, close_price, premium_rate, volume_lots, underlying_name
        FROM daily_cb_quotes
        WHERE date=? AND close_price IS NOT NULL AND premium_rate IS NOT NULL
        AND volume_lots >= 50 AND premium_rate <= 10.0 AND close_price BETWEEN 98 AND 120
        ORDER BY volume_lots DESC
        LIMIT 20
    ''', (latest_date,))
    rows = c.fetchall()
    conn.close()
    return latest_date, rows

if __name__ == '__main__':
    fut_date, fut_shorts = get_top_futures_shorts()
    cb_date, hot_cbs = get_hot_cbs()
    print('Futures:', len(fut_shorts), fut_date)
    for r in fut_shorts[:5]:
        print(r)
    print('CBs:', len(hot_cbs), cb_date)
    for r in hot_cbs[:5]:
        print(r)
