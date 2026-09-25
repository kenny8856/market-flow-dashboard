import re

with open('generate_quant_regime.py', 'r', encoding='utf-8') as f:
    code = f.read()

data_fetch_code = '''
def get_extra_data():
    import sqlite3, os
    fut_date, cb_date = "", ""
    top20_fut, hot_cbs = [], []
    try:
        conn = sqlite3.connect('db/taifex_large_trader.db')
        c = conn.cursor()
        c.execute('SELECT MAX(date) FROM futures_large_traders')
        row = c.fetchone()
        if row and row[0]:
            fut_date = row[0]
            exclude = ['臺股', '臺指', '電子', '金融', '半導體', '航運', 'ETF', '非金電', '櫃買', '生技', '富櫃']
            c.execute("SELECT contract_code, contract_name, sell_top10, net_top10, market_oi FROM futures_large_traders WHERE date=? AND contract_type='所有契約' ORDER BY sell_top10 DESC", (fut_date,))
            for r in c.fetchall():
                if not any(k in r[1] for k in exclude):
                    top20_fut.append(r)
                if len(top20_fut) >= 20: break
        conn.close()
    except: pass
    try:
        if os.path.exists('db/cb_market.db'):
            conn = sqlite3.connect('db/cb_market.db')
            c = conn.cursor()
            c.execute('SELECT MAX(date) FROM daily_cb_quotes')
            row = c.fetchone()
            if row and row[0]:
                cb_date = row[0]
                c.execute("SELECT cb_id, cb_name, close_price, premium_rate, volume_lots, underlying_name FROM daily_cb_quotes WHERE date=? AND close_price IS NOT NULL AND premium_rate IS NOT NULL AND volume_lots >= 50 AND premium_rate <= 10.0 AND close_price BETWEEN 98 AND 120 ORDER BY volume_lots DESC LIMIT 20", (cb_date,))
                hot_cbs = c.fetchall()
            conn.close()
    except: pass
    return fut_date, top20_fut, cb_date, hot_cbs

def generate_html(output_path="quant_regime.html"):
'''

if 'get_extra_data' not in code:
    code = code.replace('def generate_html(output_path="quant_regime.html"):', data_fetch_code)

extra_html_prep_code = '''
    fut_date, top20_fut, cb_date, hot_cbs = get_extra_data()
    fut_rows = "".join([f"<tr><td>#{i}</td><td>{r[0]}</td><td style='font-weight:bold;color:#facc15;'>{r[1]}</td><td class='text-bear'>{r[2]:,}</td><td class='{'text-bear' if r[3]<0 else 'text-bull'}'>{r[3]:,}</td><td>{r[4]:,}</td></tr>" for i, r in enumerate(top20_fut, 1)])
    if not fut_rows: fut_rows = "<tr><td colspan='6'>尚無資料</td></tr>"
    cb_rows = "".join([f"<tr><td>#{i}</td><td>{r[0]}</td><td style='font-weight:bold;color:#60a5fa;'>{r[1]}</td><td>{r[5]}</td><td>{r[2]:.2f}</td><td class='{'text-bull' if r[3]<=0 else ''}'>{r[3]:.2f}%</td><td style='color:#fbbf24;'>{r[4]:,}</td></tr>" for i, r in enumerate(hot_cbs, 1)])
    if not cb_rows: cb_rows = "<tr><td colspan='7'>今日無符合低溢價且具流動性之可轉債</td></tr>"
    extra_section = f"""<div style="margin-top:40px;border-top:2px dashed #334155;padding-top:30px;"><h2 style="color:#fff;margin-bottom:20px;font-size:22px;">🔥 市場籌碼焦點：個股期貨與可轉債</h2><div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(400px,1fr));gap:20px;"><div style="background:rgba(15,23,42,0.7);border:1px solid rgba(239,68,68,0.3);border-radius:10px;padding:15px;"><h3 style="color:#fca5a5;margin-top:0;">📉 個股期貨「前十大交易人空單」排行 Top 20</h3><div style="font-size:12px;color:#94a3b8;margin-bottom:10px;">資料日期：{fut_date} (排除大盤與指數期貨)</div><div class="xiaoge-table-wrapper"><table class="xiaoge-table"><thead><tr><th>排名</th><th>代號</th><th>契約名稱</th><th>前十大空單</th><th>前十大淨額</th><th>市場未平倉</th></tr></thead><tbody>{fut_rows}</tbody></table></div></div><div style="background:rgba(15,23,42,0.7);border:1px solid rgba(59,130,246,0.3);border-radius:10px;padding:15px;"><h3 style="color:#93c5fd;margin-top:0;">💡 值得關注的可轉債 (低溢價+流動性)</h3><div style="font-size:12px;color:#94a3b8;margin-bottom:10px;">資料日期：{cb_date} (條件：溢價率&lt;10%, 成交量&gt;50張, 價格98~120)</div><div class="xiaoge-table-wrapper"><table class="xiaoge-table"><thead><tr><th>排名</th><th>代號</th><th>CB名稱</th><th>現股</th><th>收盤價</th><th>溢價率</th><th>成交量(張)</th></tr></thead><tbody>{cb_rows}</tbody></table></div></div></div></div>"""
    
    html_content = f"""<!DOCTYPE html>
'''

if 'extra_section =' not in code:
    code = code.replace('    html_content = f"""<!DOCTYPE html>', extra_html_prep_code)

if '{extra_section}' not in code:
    code = code.replace('        <div class="footer">', '        {extra_section}\n        <div class="footer">')

with open('generate_quant_regime.py', 'w', encoding='utf-8') as f:
    f.write(code)
