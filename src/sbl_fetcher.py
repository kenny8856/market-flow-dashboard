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

def clean_float(val: Any) -> Optional[float]:
    """清理浮點數字串（收盤價等）"""
    if val is None:
        return None
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "X0.00", "N/A", "---", "X"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None

class SBLFetcher:
    """
    負責自臺灣證券交易所 (TWSE) 與 證券櫃檯買賣中心 (TPEx) 下載借券相關數據：
    1. TWT72U: 借券餘額合計表 (官方同時涵蓋集中市場與櫃檯買賣中心)
    2. TWT93U: 上市 信用額度總量管制餘額表 (借券賣出與融券)
    3. TPEx margin_sbl: 上櫃 信用額度總量管制餘額表 (借券賣出與融券)
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
                    # Rate limit block -> 暫停冷卻後重試
                    wait_sec = 8 + attempt * 5
                    print(f"\n[警示] 伺服器頻率管制 (HTTP {e.code})，自動冷卻 {wait_sec} 秒後重試...")
                    time.sleep(wait_sec)
                else:
                    if attempt < retries - 1:
                        time.sleep(2.0 + attempt)
                    else:
                        return None
            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2.0 + attempt)
                else:
                    return None
        return None

    def fetch_sbl_balance(self, date_str: str) -> List[Dict[str, Any]]:
        """
        抓取 TWSE TWT72U (證交所借券系統與證商/證金營業處所借券餘額合計表)
        官方此表同時收錄『集中市場』與『櫃檯買賣中心』全市場個股。
        date_str 格式: 'YYYY-MM-DD'
        """
        ymd = date_str.replace("-", "")
        url = f"https://www.twse.com.tw/rwd/zh/lending/TWT72U?date={ymd}&response=json"
        
        data = self._get_json(url)
        time.sleep(self.polite_delay)

        if not data or data.get("stat") != "OK":
            return []

        rows = data.get("data", [])
        results = []
        for r in rows:
            if len(r) >= 9:
                stock_id = str(r[0]).strip()
                stock_name = str(r[1]).strip()
                prev_bal = clean_int(r[2])
                today_borrow = clean_int(r[3])
                today_return = clean_int(r[4])
                today_bal = clean_int(r[5])
                close_p = clean_float(r[6])
                mkt_val = clean_int(r[7])
                raw_mkt = str(r[8]).strip()
                
                # 市場別標準化
                if "櫃" in raw_mkt:
                    market_type = "上櫃"
                elif "集中" in raw_mkt:
                    market_type = "上市"
                else:
                    continue

                if stock_id and stock_id not in ("合計", "總計") and "計" not in stock_id:
                    results.append({
                        "date": date_str,
                        "stock_id": stock_id,
                        "stock_name": stock_name,
                        "market_type": market_type,
                        "prev_balance": prev_bal,
                        "today_borrow": today_borrow,
                        "today_return": today_return,
                        "today_balance": today_bal,
                        "close_price": close_p,
                        "market_value": mkt_val,
                    })

        return results

    def fetch_twse_sbl_short(self, date_str: str) -> List[Dict[str, Any]]:
        """
        抓取 TWSE TWT93U (上市 信用額度總量管制餘額表)
        涵蓋上市個股之借券賣出與融券餘額。
        date_str 格式: 'YYYY-MM-DD'
        """
        ymd = date_str.replace("-", "")
        url = f"https://www.twse.com.tw/rwd/zh/marginTrading/TWT93U?date={ymd}&response=json"

        data = self._get_json(url)
        time.sleep(self.polite_delay)

        if not data or data.get("stat") != "OK":
            return []

        rows = data.get("data", [])
        results = []
        for r in rows:
            if len(r) >= 14:
                stock_id = str(r[0]).strip()
                stock_name = str(r[1]).strip()

                # 融券欄位 (indices 2..7)
                margin_prev = clean_int(r[2])
                margin_sell = clean_int(r[3])
                margin_buy = clean_int(r[4])
                margin_cash = clean_int(r[5])
                margin_bal = clean_int(r[6])
                margin_quota = clean_int(r[7])

                # 借券賣出欄位 (indices 8..13)
                sbl_prev = clean_int(r[8])
                sbl_sell = clean_int(r[9])
                sbl_return = clean_int(r[10])
                sbl_adj = clean_int(r[11])
                sbl_bal = clean_int(r[12])
                sbl_limit = clean_int(r[13])
                note = str(r[14]).strip() if len(r) > 14 else ""

                if stock_id and stock_id not in ("合計", "總計"):
                    results.append({
                        "date": date_str,
                        "stock_id": stock_id,
                        "stock_name": stock_name,
                        "market_type": "上市",
                        "sbl_prev_bal": sbl_prev,
                        "sbl_sell": sbl_sell,
                        "sbl_return": sbl_return,
                        "sbl_adjust": sbl_adj,
                        "sbl_bal": sbl_bal,
                        "sbl_next_limit": sbl_limit,
                        "margin_prev_bal": margin_prev,
                        "margin_sell": margin_sell,
                        "margin_buy": margin_buy,
                        "margin_cash_redemption": margin_cash,
                        "margin_bal": margin_bal,
                        "margin_quota": margin_quota,
                        "note": note,
                    })

        return results

    def fetch_tpex_sbl_short(self, date_str: str) -> List[Dict[str, Any]]:
        """
        抓取 TPEx margin_sbl (上櫃 信用額度總量管制餘額表)
        涵蓋上櫃個股之借券賣出與融券餘額。
        date_str 格式: 'YYYY-MM-DD'
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        roc_year = dt.year - 1911
        roc_date_slash = f"{roc_year}/{dt.strftime('%m/%d')}"

        url = f"https://www.tpex.org.tw/web/stock/margin_trading/margin_sbl/margin_sbl_result.php?l=zh-tw&d={roc_date_slash}&o=json"

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
            if len(r) >= 14:
                stock_id = str(r[0]).strip()
                stock_name = str(r[1]).strip()

                # 融券欄位 (indices 2..7)
                margin_prev = clean_int(r[2])
                margin_sell = clean_int(r[3])
                margin_buy = clean_int(r[4])
                margin_cash = clean_int(r[5])
                margin_bal = clean_int(r[6])
                margin_quota = clean_int(r[7])

                # 借券賣出欄位 (indices 8..13)
                sbl_prev = clean_int(r[8])
                sbl_sell = clean_int(r[9])
                sbl_return = clean_int(r[10])
                sbl_adj = clean_int(r[11])
                sbl_bal = clean_int(r[12])
                sbl_limit = clean_int(r[13])
                note = str(r[14]).strip() if len(r) > 14 else ""

                if stock_id and stock_id not in ("合計", "總計"):
                    results.append({
                        "date": date_str,
                        "stock_id": stock_id,
                        "stock_name": stock_name,
                        "market_type": "上櫃",
                        "sbl_prev_bal": sbl_prev,
                        "sbl_sell": sbl_sell,
                        "sbl_return": sbl_return,
                        "sbl_adjust": sbl_adj,
                        "sbl_bal": sbl_bal,
                        "sbl_next_limit": sbl_limit,
                        "margin_prev_bal": margin_prev,
                        "margin_sell": margin_sell,
                        "margin_buy": margin_buy,
                        "margin_cash_redemption": margin_cash,
                        "margin_bal": margin_bal,
                        "margin_quota": margin_quota,
                        "note": note,
                    })

        return results
