import urllib.request
import ssl
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0",
]

def clean_int(val: Any) -> int:
    """清理整數字串（處理千分位逗號、空白、負號）"""
    if val is None:
        return 0
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "N/A", "---", "X"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0

def clean_float(val: Any) -> float:
    """清理浮點數字串（比率、百分比）"""
    if val is None:
        return 0.0
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").replace("%", "").strip()
    if not s or s in ("--", "X0.00", "N/A", "---", "X"):
        return 0.0
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0

class MarginFetcher:
    """
    負責自臺灣證券交易所 (TWSE) 與 證券櫃檯買賣中心 (TPEx) 下載個股融資融券每日數據：
    1. TWSE: MI_MARGN (融資融券彙總表 - 全部)
    2. TPEx: margin_balance (上櫃股票融資融券餘額)
    """

    def __init__(self, polite_delay: float = 1.2):
        self.ssl_context = ssl._create_unverified_context()
        self.polite_delay = polite_delay

    def _get_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _get_json(self, url: str, retries: int = 4) -> Optional[Dict[str, Any]]:
        for attempt in range(retries):
            headers = self._get_headers()
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, context=self.ssl_context, timeout=25) as resp:
                    text = resp.read().decode("utf-8", errors="ignore")
                    return json.loads(text)
            except urllib.error.HTTPError as e:
                if e.code in (307, 429, 403):
                    wait_sec = 8 + attempt * 5
                    print(f"\n[警示] 伺服器頻率管制 (HTTP {e.code})，自動冷卻 {wait_sec} 秒後重試...")
                    time.sleep(wait_sec)
                else:
                    if attempt < retries - 1:
                        time.sleep(2.0 + attempt)
                    else:
                        return None
            except Exception:
                if attempt < retries - 1:
                    time.sleep(2.0 + attempt)
                else:
                    return None
        return None

    def fetch_twse_margin(self, date_str: str) -> List[Dict[str, Any]]:
        """
        抓取 TWSE MI_MARGN (上市 融資融券彙總表)
        date_str 格式: 'YYYY-MM-DD'
        """
        ymd = date_str.replace("-", "")
        url = f"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={ymd}&selectType=ALL&response=json"

        data = self._get_json(url)
        time.sleep(self.polite_delay)

        if not data or data.get("stat") != "OK":
            return []

        tables = data.get("tables", [])
        if len(tables) < 2:
            return []

        # Table 1: 融資融券彙總 (全部)
        rows = tables[1].get("data", [])
        results = []
        for r in rows:
            if len(r) >= 15:
                stock_id = str(r[0]).strip()
                stock_name = str(r[1]).strip()

                if not stock_id or stock_id in ("合計", "總計") or "計" in stock_id:
                    continue

                # 融資部分 (張)
                m_buy = clean_int(r[2])
                m_sell = clean_int(r[3])
                m_cash_redemp = clean_int(r[4])
                m_prev_bal = clean_int(r[5])
                m_today_bal = clean_int(r[6])
                m_limit = clean_int(r[7])

                # 融券部分 (張)
                s_buy = clean_int(r[8])
                s_sell = clean_int(r[9])
                s_cash_redemp = clean_int(r[10])
                s_prev_bal = clean_int(r[11])
                s_today_bal = clean_int(r[12])
                s_limit = clean_int(r[13])

                offset = clean_int(r[14])
                note = str(r[15]).strip() if len(r) > 15 else ""

                m_change = m_today_bal - m_prev_bal
                s_change = s_today_bal - s_prev_bal

                m_util_rate = round(m_today_bal * 100.0 / m_limit, 2) if m_limit > 0 else 0.0
                s_util_rate = round(s_today_bal * 100.0 / s_limit, 2) if s_limit > 0 else 0.0
                ratio = round(s_today_bal * 100.0 / m_today_bal, 2) if m_today_bal > 0 else 0.0

                results.append({
                    "date": date_str,
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "market_type": "上市",
                    "margin_buy": m_buy,
                    "margin_sell": m_sell,
                    "margin_cash_redemption": m_cash_redemp,
                    "margin_prev_bal": m_prev_bal,
                    "margin_today_bal": m_today_bal,
                    "margin_change": m_change,
                    "margin_limit": m_limit,
                    "margin_utilization_rate": m_util_rate,
                    "short_buy": s_buy,
                    "short_sell": s_sell,
                    "short_cash_redemption": s_cash_redemp,
                    "short_prev_bal": s_prev_bal,
                    "short_today_bal": s_today_bal,
                    "short_change": s_change,
                    "short_limit": s_limit,
                    "short_utilization_rate": s_util_rate,
                    "short_margin_ratio": ratio,
                    "offset_shares": offset,
                    "note": note,
                })

        return results

    def fetch_tpex_margin(self, date_str: str) -> List[Dict[str, Any]]:
        """
        抓取 TPEx margin_balance (上櫃股票融資融券餘額)
        date_str 格式: 'YYYY-MM-DD'
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        roc_year = dt.year - 1911
        roc_date_slash = f"{roc_year}/{dt.strftime('%m/%d')}"

        url = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&d={roc_date_slash}&o=json"

        data = self._get_json(url)
        time.sleep(self.polite_delay)

        if not data:
            return []

        tables = data.get("tables", [])
        if not tables:
            return []

        rows = tables[0].get("data", [])
        results = []
        for r in rows:
            if len(r) >= 19:
                stock_id = str(r[0]).strip()
                stock_name = str(r[1]).strip()

                if not stock_id or stock_id in ("合計", "總計") or "計" in stock_id:
                    continue

                # 融資部分 (張)
                m_prev_bal = clean_int(r[2])
                m_buy = clean_int(r[3])
                m_sell = clean_int(r[4])
                m_cash_redemp = clean_int(r[5])
                m_today_bal = clean_int(r[6])
                m_util_rate = clean_float(r[8]) if len(r) > 8 else 0.0
                m_limit = clean_int(r[9]) if len(r) > 9 else 0

                # 融券部分 (張)
                s_prev_bal = clean_int(r[10])
                s_sell = clean_int(r[11])   # 券賣
                s_buy = clean_int(r[12])    # 券買
                s_cash_redemp = clean_int(r[13])
                s_today_bal = clean_int(r[14])
                s_util_rate = clean_float(r[16]) if len(r) > 16 else 0.0
                s_limit = clean_int(r[17]) if len(r) > 17 else 0

                offset = clean_int(r[18])
                note = str(r[19]).strip() if len(r) > 19 else ""

                m_change = m_today_bal - m_prev_bal
                s_change = s_today_bal - s_prev_bal

                ratio = round(s_today_bal * 100.0 / m_today_bal, 2) if m_today_bal > 0 else 0.0

                results.append({
                    "date": date_str,
                    "stock_id": stock_id,
                    "stock_name": stock_name,
                    "market_type": "上櫃",
                    "margin_buy": m_buy,
                    "margin_sell": m_sell,
                    "margin_cash_redemption": m_cash_redemp,
                    "margin_prev_bal": m_prev_bal,
                    "margin_today_bal": m_today_bal,
                    "margin_change": m_change,
                    "margin_limit": m_limit,
                    "margin_utilization_rate": m_util_rate,
                    "short_buy": s_buy,
                    "short_sell": s_sell,
                    "short_cash_redemption": s_cash_redemp,
                    "short_prev_bal": s_prev_bal,
                    "short_today_bal": s_today_bal,
                    "short_change": s_change,
                    "short_limit": s_limit,
                    "short_utilization_rate": s_util_rate,
                    "short_margin_ratio": ratio,
                    "offset_shares": offset,
                    "note": note,
                })

        return results

    def fetch_all_margin_data(self, date_str: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """抓取上市與上櫃當日融資融券全量數據"""
        twse_data = self.fetch_twse_margin(date_str)
        tpex_data = self.fetch_tpex_margin(date_str)
        return twse_data, tpex_data
