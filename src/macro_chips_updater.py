"""
大盤宏觀籌碼自動彙總與同步模組 (Macro Chips & Margin Summary Updater)
================================================================================
自動串接並計算：
1. 交易所 (TWSE) 與 櫃買中心 (TPEx) 官方全市場融資融券「金額 (億元)」與「維持率」
   - 自動即時向官方端點 (MI_MARGN 與 margin_bal_result.php) 取得全市場融資金額與增減
   - 自動聯動本地個股收盤價與各股融資餘額，精確計算大盤全體擔保品總市值與維持率
   - 存儲入 margin_trading.db 之 market_margin_summary 表
2. 期交所 (TAIFEX) 外資期貨未平倉多空口數與金額 (億元)
   - 自動向期交所 futContractsDateDown 抓取外資臺指期未平倉口數與契約金額
   - 存儲入 taifex_large_trader.db 之 futures_foreign_institutional 表
"""

import os
import sys
import json
import csv
import io
import ssl
import urllib.request
import urllib.parse
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, "db")

MARGIN_DB = os.path.join(DB_DIR, "margin_trading.db")
TWSE_DB = os.path.join(DB_DIR, "twse_market.db")
TPEX_DB = os.path.join(DB_DIR, "tpex_market.db")
TAIFEX_DB = os.path.join(DB_DIR, "taifex_large_trader.db")

SSL_CTX = ssl._create_unverified_context()


def ensure_tables():
    """確保所需彙總表格已建置"""
    with sqlite3.connect(MARGIN_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS market_margin_summary (
                date TEXT PRIMARY KEY,
                twse_margin_bal_yi REAL,
                twse_margin_chg_yi REAL,
                twse_collateral_yi REAL,
                twse_maint_ratio REAL,
                tpex_margin_bal_yi REAL,
                tpex_margin_chg_yi REAL,
                tpex_collateral_yi REAL,
                tpex_maint_ratio REAL,
                total_margin_bal_yi REAL,
                total_margin_chg_yi REAL,
                total_collateral_yi REAL,
                total_maint_ratio REAL
            )
        """)
        conn.commit()

    with sqlite3.connect(TAIFEX_DB) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS futures_foreign_institutional (
                date TEXT PRIMARY KEY,
                foreign_buy_oi INTEGER,
                foreign_sell_oi INTEGER,
                foreign_net_oi INTEGER,
                foreign_net_amt_yi REAL
            )
        """)
        conn.commit()


def update_market_margin_summary(date_str: str) -> Optional[Dict[str, Any]]:
    """
    抓取並計算特定交易日的大盤融資總金額 (億元) 與維持率
    """
    ensure_tables()
    
    # 1. 抓取 TWSE 上市融資總金額 (仟元 -> 億元)
    ymd = date_str.replace("-", "")
    url_twse = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd}&selectType=ALL&response=json"
    req_twse = urllib.request.Request(url_twse, headers={'User-Agent': 'Mozilla/5.0'})
    twse_bal = 0.0
    twse_chg = 0.0
    try:
        with urllib.request.urlopen(req_twse, context=SSL_CTX, timeout=12) as r:
            d = json.loads(r.read().decode('utf-8'))
            tables = d.get("tables", [])
            if tables:
                t0 = tables[0]
                for row in t0.get("data", []):
                    item = str(row[0]).strip()
                    if "融資金額" in item:
                        prev_k = float(str(row[4]).replace(",", ""))
                        today_k = float(str(row[5]).replace(",", ""))
                        twse_bal = round(today_k / 100000.0, 2)
                        twse_chg = round((today_k - prev_k) / 100000.0, 2)
                        break
    except Exception as e:
        print(f"[!] 抓取 TWSE 融資總金額失敗 ({date_str}): {e}")

    # 2. 抓取 TPEx 上櫃融資總金額 (仟元 -> 億元)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        roc_year = dt.year - 1911
        roc_date_slash = f"{roc_year}/{dt.strftime('%m/%d')}"
    except Exception:
        return None

    url_tpex = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&d={roc_date_slash}&o=json"
    req_tpex = urllib.request.Request(url_tpex, headers={'User-Agent': 'Mozilla/5.0'})
    tpex_bal = 0.0
    tpex_chg = 0.0
    try:
        with urllib.request.urlopen(req_tpex, context=SSL_CTX, timeout=12) as r:
            d = json.loads(r.read().decode('utf-8', errors='replace'))
            tables = d.get("tables", [])
            if tables:
                s = tables[0].get("summary", [])
                if len(s) >= 2:
                    prev_k = float(str(s[1][2]).replace(",", ""))
                    today_k = float(str(s[1][6]).replace(",", ""))
                    tpex_bal = round(today_k / 100000.0, 2)
                    tpex_chg = round((today_k - prev_k) / 100000.0, 2)
    except Exception as e:
        print(f"[!] 抓取 TPEx 融資總金額失敗 ({date_str}): {e}")

    if twse_bal == 0.0 and tpex_bal == 0.0:
        return None

    # 3. 計算上市櫃融資擔保品總市值與維持率
    try:
        with sqlite3.connect(MARGIN_DB) as c_m, sqlite3.connect(TWSE_DB) as c_tw, sqlite3.connect(TPEX_DB) as c_tp:
            tw_closes = dict(c_tw.execute("SELECT stock_id, close_price FROM daily_quotes WHERE date = ?", (date_str,)).fetchall())
            tp_closes = dict(c_tp.execute("SELECT stock_id, close_price FROM daily_quotes WHERE date = ?", (date_str,)).fetchall())

            tw_rows = c_m.execute("SELECT stock_id, margin_today_bal FROM daily_margin_trading WHERE date = ? AND market_type = '上市'", (date_str,)).fetchall()
            tp_rows = c_m.execute("SELECT stock_id, margin_today_bal FROM daily_margin_trading WHERE date = ? AND market_type = '上櫃'", (date_str,)).fetchall()

            tw_col = sum([bal * (tw_closes.get(sid) or 0.0) * 1000.0 for sid, bal in tw_rows if bal and tw_closes.get(sid)])
            tp_col = sum([bal * (tp_closes.get(sid) or 0.0) * 1000.0 for sid, bal in tp_rows if bal and tp_closes.get(sid)])

            tw_col_yi = round(tw_col / 1e8, 2)
            tp_col_yi = round(tp_col / 1e8, 2)

            tw_maint = round((tw_col_yi / twse_bal * 100.0), 2) if twse_bal > 0 else 0.0
            tp_maint = round((tp_col_yi / tpex_bal * 100.0), 2) if tpex_bal > 0 else 0.0

            tot_bal = round(twse_bal + tpex_bal, 2)
            tot_chg = round(twse_chg + tpex_chg, 2)
            tot_col = round(tw_col_yi + tp_col_yi, 2)
            tot_maint = round((tot_col / tot_bal * 100.0), 2) if tot_bal > 0 else 0.0

            summary_data = {
                "date": date_str,
                "twse_margin_bal_yi": twse_bal,
                "twse_margin_chg_yi": twse_chg,
                "twse_collateral_yi": tw_col_yi,
                "twse_maint_ratio": tw_maint,
                "tpex_margin_bal_yi": tpex_bal,
                "tpex_margin_chg_yi": tpex_chg,
                "tpex_collateral_yi": tp_col_yi,
                "tpex_maint_ratio": tp_maint,
                "total_margin_bal_yi": tot_bal,
                "total_margin_chg_yi": tot_chg,
                "total_collateral_yi": tot_col,
                "total_maint_ratio": tot_maint
            }

            c_m.execute("""
                INSERT OR REPLACE INTO market_margin_summary
                (date, twse_margin_bal_yi, twse_margin_chg_yi, twse_collateral_yi, twse_maint_ratio,
                 tpex_margin_bal_yi, tpex_margin_chg_yi, tpex_collateral_yi, tpex_maint_ratio,
                 total_margin_bal_yi, total_margin_chg_yi, total_collateral_yi, total_maint_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary_data["date"], summary_data["twse_margin_bal_yi"], summary_data["twse_margin_chg_yi"],
                summary_data["twse_collateral_yi"], summary_data["twse_maint_ratio"],
                summary_data["tpex_margin_bal_yi"], summary_data["tpex_margin_chg_yi"],
                summary_data["tpex_collateral_yi"], summary_data["tpex_maint_ratio"],
                summary_data["total_margin_bal_yi"], summary_data["total_margin_chg_yi"],
                summary_data["total_collateral_yi"], summary_data["total_maint_ratio"]
            ))
            c_m.commit()
            return summary_data
    except Exception as e:
        print(f"[!] 計算維持率與寫入資料庫失敗 ({date_str}): {e}")
        return None


def update_foreign_futures(date_str: str) -> Optional[Dict[str, Any]]:
    """
    抓取特定交易日之期交所外資臺指期未平倉口數與金額
    """
    ensure_tables()
    d_slash = date_str.replace("-", "/")
    url = "https://www.taifex.com.tw/cht/3/futContractsDateDown"
    data = urllib.parse.urlencode({"queryStartDate": d_slash, "queryEndDate": d_slash}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})

    result = None
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=12) as r:
            raw = r.read().decode("big5", errors="ignore")
            reader = csv.reader(io.StringIO(raw))
            for row in reader:
                if len(row) >= 15 and "臺股期貨" in row[1] and "外資" in row[2]:
                    buy_oi = int(row[9].replace(",", ""))
                    sell_oi = int(row[11].replace(",", ""))
                    net_oi = int(row[13].replace(",", ""))
                    net_amt_yi = round(float(row[14].replace(",", "")) / 100000.0, 2)
                    result = {
                        "date": date_str,
                        "foreign_buy_oi": buy_oi,
                        "foreign_sell_oi": sell_oi,
                        "foreign_net_oi": net_oi,
                        "foreign_net_amt_yi": net_amt_yi
                    }
                    break
    except Exception as e:
        print(f"[!] 抓取 TAIFEX 外資期貨失敗 ({date_str}): {e}")

    if result:
        try:
            with sqlite3.connect(TAIFEX_DB) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO futures_foreign_institutional
                    (date, foreign_buy_oi, foreign_sell_oi, foreign_net_oi, foreign_net_amt_yi)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    result["date"], result["foreign_buy_oi"], result["foreign_sell_oi"],
                    result["foreign_net_oi"], result["foreign_net_amt_yi"]
                ))
                conn.commit()
        except Exception as e:
            print(f"[!] 寫入 futures_foreign_institutional 失敗: {e}")

    return result


def auto_sync_missing_summaries():
    """
    自動掃描並補齊所有缺漏的 market_margin_summary 與 futures_foreign_institutional
    """
    ensure_tables()
    
    # 1. 檢查融資彙總
    try:
        with sqlite3.connect(MARGIN_DB) as conn:
            m_dates = [r[0] for r in conn.execute("SELECT DISTINCT date FROM daily_margin_trading ORDER BY date DESC LIMIT 15").fetchall()]
            existing_s_dates = set(r[0] for r in conn.execute("SELECT DISTINCT date FROM market_margin_summary").fetchall())
        
        missing_m = [d for d in m_dates if d not in existing_s_dates]
        if missing_m:
            print(f"[*] 偵測到 {len(missing_m)} 個交易日缺少大盤融資維持率彙總，正在自動計算補齊: {missing_m}")
            for d in reversed(missing_m):
                res = update_market_margin_summary(d)
                if res:
                    print(f"  [+] 成功補齊 {d} 融資彙總: 總融資 {res['total_margin_bal_yi']:,} 億元, 維持率 {res['total_maint_ratio']}%")
    except Exception as e:
        print(f"[!] 檢查融資彙總缺漏異常: {e}")

    # 2. 檢查外資期貨
    try:
        with sqlite3.connect(TAIFEX_DB) as conn:
            f_dates = [r[0] for r in conn.execute("SELECT DISTINCT date FROM futures_large_traders WHERE contract_code = 'TX' ORDER BY date DESC LIMIT 15").fetchall()]
            existing_f_dates = set(r[0] for r in conn.execute("SELECT DISTINCT date FROM futures_foreign_institutional").fetchall())
            
        missing_f = [d for d in f_dates if d not in existing_f_dates]
        if missing_f:
            print(f"[*] 偵測到 {len(missing_f)} 個交易日缺少外資期貨淨留倉，正在自動補齊: {missing_f}")
            for d in reversed(missing_f):
                res = update_foreign_futures(d)
                if res:
                    print(f"  [+] 成功補齊 {d} 外資期貨: 淨留倉 {res['foreign_net_oi']:,} 口 ({res['foreign_net_amt_yi']:,} 億元)")
    except Exception as e:
        print(f"[!] 檢查外資期貨缺漏異常: {e}")


if __name__ == "__main__":
    auto_sync_missing_summaries()
