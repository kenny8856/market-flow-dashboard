"""
TAIFEX Options Data Fetcher
Downloads and parses:
1. TXO Put/Call Ratio (daily)
2. TXO Strike-by-Strike Quotes and Open Interest (for Max Pain calculation)
3. Institutional Options Positions (Foreign, Trust, Dealer)
4. Large Trader Options Positions
"""

import os
import sys
import ssl
import csv
import io
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

TAIFEX_PC_RATIO_URL = "https://www.taifex.com.tw/cht/3/pcRatioDown"
TAIFEX_OPT_DATA_URL = "https://www.taifex.com.tw/cht/3/optDataDown"
TAIFEX_INST_OPT_URL = "https://www.taifex.com.tw/cht/3/callsAndPutsDateDown"
TAIFEX_LARGE_OPT_URL = "https://www.taifex.com.tw/cht/3/largeTraderOptDown"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def clean_num(val: Any, is_float: bool = False) -> Any:
    """清理數值（去除逗號、空格、破折號）"""
    if val is None:
        return 0.0 if is_float else 0
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "N/A", "---", "-"):
        return 0.0 if is_float else 0
    try:
        return float(s) if is_float else int(float(s))
    except ValueError:
        return 0.0 if is_float else 0

def format_date(d_str: str) -> str:
    """將 YYYY/MM/DD 或 YYYY-MM-DD 統一格式化為 YYYY-MM-DD"""
    s = d_str.strip().replace("/", "-")
    return s

class TaifexOptionsFetcher:
    """期交所選擇權市場數據抓取器"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def _post_request(self, url: str, params: Dict[str, str], max_retries: int = 3) -> str:
        """發送 POST 請求並自動嘗試多種中文編碼解碼"""
        post_data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=post_data, headers=REQUEST_HEADERS)

        last_err = None
        for attempt in range(max_retries):
            try:
                with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout) as resp:
                    raw = resp.read()
                    for enc in ("cp950", "big5", "utf-8", "utf-8-sig"):
                        try:
                            return raw.decode(enc)
                        except UnicodeDecodeError:
                            continue
                    return raw.decode("cp950", errors="ignore")
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))

        raise RuntimeError(f"下載失敗 [{url}]: {last_err}")

    # =========================================================================
    # 1. 臺指選擇權 Put/Call Ratio
    # =========================================================================
    def fetch_pc_ratio(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        抓取臺指選擇權 Put/Call Ratio (買賣權未平倉比率)
        start_date, end_date 格式: YYYY-MM-DD
        """
        d_start = start_date.replace("-", "/")
        d_end = end_date.replace("-", "/")

        text = self._post_request(TAIFEX_PC_RATIO_URL, {
            "queryStartDate": d_start,
            "queryEndDate": d_end
        })

        results = []
        reader = csv.reader(io.StringIO(text))
        header = None
        for row in reader:
            if not row or len(row) < 7:
                continue
            if header is None:
                header = [c.strip() for c in row]
                continue
            # 日期, 賣權成交量, 買權成交量, 買賣權成交量比率%, 賣權未平倉量, 買權未平倉量, 買賣權未平倉量比率%
            d = format_date(row[0])
            if not d or not d.startswith("20"):
                continue
            results.append({
                "date": d,
                "put_volume": clean_num(row[1]),
                "call_volume": clean_num(row[2]),
                "pc_ratio_volume": clean_num(row[3], is_float=True),
                "put_oi": clean_num(row[4]),
                "call_oi": clean_num(row[5]),
                "pc_ratio_oi": clean_num(row[6], is_float=True),
            })
        return results

    # =========================================================================
    # 2. 臺指選擇權各履約價行情與未沖銷契約數 (TXO Strike Quotes & OI)
    # =========================================================================
    def fetch_strike_quotes(self, start_date: str, end_date: str, commodity_id: str = "TXO") -> List[Dict[str, Any]]:
        """
        抓取臺指選擇權各履約價行情與 OI (一般交易時段盤後定案值)
        """
        d_start = start_date.replace("-", "/")
        d_end = end_date.replace("-", "/")

        text = self._post_request(TAIFEX_OPT_DATA_URL, {
            "down_type": "1",
            "commodity_id": commodity_id,
            "commodity_id2": "",
            "queryStartDate": d_start,
            "queryEndDate": d_end
        })

        results = []
        reader = csv.reader(io.StringIO(text))
        header = None
        for row in reader:
            if not row or len(row) < 12:
                continue
            if header is None:
                header = [c.strip() for c in row]
                continue

            # 交易日期, 契約, 到期月份(週別), 履約價, 買賣權, 開盤價, 最高價, 最低價, 收盤價, 成交量, 結算價, 未沖銷契約數, ... 交易時段
            # 優先採集一般時段 (包含完整結算價與未平倉契約數)
            session = row[17].strip() if len(row) > 17 else "一般"
            if session != "一般":
                continue

            d = format_date(row[0])
            if not d or not d.startswith("20"):
                continue

            contract = row[1].strip()
            expiry = row[2].strip()
            strike = clean_num(row[3], is_float=True)
            cp = row[4].strip() # 買權 / 賣權
            cp_norm = "CALL" if "買" in cp or "CALL" in cp.upper() else "PUT"

            open_p = clean_num(row[5], is_float=True)
            high_p = clean_num(row[6], is_float=True)
            low_p = clean_num(row[7], is_float=True)
            close_p = clean_num(row[8], is_float=True)
            volume = clean_num(row[9])
            settle_p = clean_num(row[10], is_float=True)
            oi = clean_num(row[11])

            results.append({
                "date": d,
                "commodity_id": contract,
                "expiry_month": expiry,
                "strike_price": strike,
                "call_put": cp_norm,
                "open_price": open_p,
                "high_price": high_p,
                "low_price": low_p,
                "close_price": close_p,
                "settle_price": settle_p,
                "volume": volume,
                "open_interest": oi
            })

        return results

    # =========================================================================
    # 3. 三大法人選擇權未平倉契約金額與口數
    # =========================================================================
    def fetch_institutional_positions(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        抓取三大法人選擇權契約金額與口數
        """
        d_start = start_date.replace("-", "/")
        d_end = end_date.replace("-", "/")

        text = self._post_request(TAIFEX_INST_OPT_URL, {
            "queryStartDate": d_start,
            "queryEndDate": d_end
        })

        results = []
        reader = csv.reader(io.StringIO(text))
        header = None
        for row in reader:
            if not row or len(row) < 16:
                continue
            if header is None:
                header = [c.strip() for c in row]
                continue

            d = format_date(row[0])
            if not d or not d.startswith("20"):
                continue

            commodity = row[1].strip()
            cp = row[2].strip().upper()
            inst_type = row[3].strip()

            results.append({
                "date": d,
                "commodity_name": commodity,
                "call_put": cp,
                "institution_type": inst_type,
                "buy_lots": clean_num(row[4]),
                "buy_amount": clean_num(row[5], is_float=True),
                "sell_lots": clean_num(row[6]),
                "sell_amount": clean_num(row[7], is_float=True),
                "net_lots": clean_num(row[8]),
                "net_amount": clean_num(row[9], is_float=True),
                "buy_oi_lots": clean_num(row[10]),
                "buy_oi_amount": clean_num(row[11], is_float=True),
                "sell_oi_lots": clean_num(row[12]),
                "sell_oi_amount": clean_num(row[13], is_float=True),
                "net_oi_lots": clean_num(row[14]),
                "net_oi_amount": clean_num(row[15], is_float=True),
            })

        return results

    # =========================================================================
    # 4. 選擇權大額交易人部位
    # =========================================================================
    def fetch_large_trader_positions(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """
        抓取選擇權大額交易人與特定法人部位
        """
        d_start = start_date.replace("-", "/")
        d_end = end_date.replace("-", "/")

        text = self._post_request(TAIFEX_LARGE_OPT_URL, {
            "queryStartDate": d_start,
            "queryEndDate": d_end
        })

        results = []
        reader = csv.reader(io.StringIO(text))
        header = None
        for row in reader:
            if not row or len(row) < 11:
                continue
            if header is None:
                header = [c.strip() for c in row]
                continue

            d = format_date(row[0])
            if not d or not d.startswith("20"):
                continue

            contract_code = row[1].strip()
            contract_name = row[2].strip()
            cp = row[3].strip()
            cp_norm = "CALL" if "買" in cp or "CALL" in cp.upper() else "PUT"
            expiry = row[4].strip()
            trader_type = clean_num(row[5]) # 0: 大額交易人合計, 1: 特定法人

            results.append({
                "date": d,
                "contract_code": contract_code,
                "contract_name": contract_name,
                "call_put": cp_norm,
                "expiry_month": expiry,
                "trader_type": trader_type,
                "top5_buy": clean_num(row[6]),
                "top5_sell": clean_num(row[7]),
                "top10_buy": clean_num(row[8]),
                "top10_sell": clean_num(row[9]),
                "total_oi": clean_num(row[10]),
            })

        return results
