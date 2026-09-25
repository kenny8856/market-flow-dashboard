"""
TDCC Equity Distribution Fetcher (集保戶股權分散表抓取器)
1. Fetches latest all-market snapshot (2,000+ stocks) from TDCC Open Data.
2. Supports fetching single stock historical weeks from TDCC web portal.
"""

import os
import sys
import ssl
import csv
import io
import time
import re
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

TDCC_OPEN_DATA_URL = "https://smart.tdcc.com.tw/opendata/getOD.ashx?id=1-5"
TDCC_PORTAL_URL = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

class TdccFetcher:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def fetch_latest_all_market(self) -> List[Dict[str, Any]]:
        """
        從政府開放資料平台下載當週最新全市場集保股權分散表 CSV (約 2.3MB，涵蓋全市場上市櫃)
        """
        req = urllib.request.Request(TDCC_OPEN_DATA_URL, headers=REQUEST_HEADERS)
        with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout) as resp:
            raw = resp.read()
            text = None
            for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if text is None:
                text = raw.decode("utf-8", errors="ignore")

        reader = csv.reader(io.StringIO(text))
        header = None
        records = []
        for row in reader:
            if not row or len(row) < 6:
                continue
            if header is None:
                header = [c.strip() for c in row]
                continue

            # 資料日期, 證券代號, 持股分級, 人數, 股數, 占集保庫存數比例%
            raw_d = str(row[0]).strip().replace("-", "").replace("/", "")
            if len(raw_d) == 8:
                date_str = f"{raw_d[:4]}-{raw_d[4:6]}-{raw_d[6:]}"
            else:
                date_str = raw_d

            stock_id = str(row[1]).strip()
            if not stock_id:
                continue

            try:
                level = int(str(row[2]).strip())
                holders = int(str(row[3]).replace(",", "").strip())
                shares = int(str(row[4]).replace(",", "").strip())
                pct = float(str(row[5]).replace(",", "").replace("%", "").strip())
            except ValueError:
                continue

            records.append({
                "date": date_str,
                "stock_id": stock_id,
                "holding_level": level,
                "shareholders": holders,
                "shares": shares,
                "share_percent": pct
            })

        return records

    def fetch_stock_history_web(self, stock_id: str) -> List[Dict[str, Any]]:
        """
        透過 TDCC 官網查詢單一個股近 1 年的所有週歷史股權分散數據
        """
        # 第一步：先訪問首頁取得 session cookies 與 SYNCHRONIZER_TOKEN, dates
        req = urllib.request.Request(TDCC_PORTAL_URL, headers=REQUEST_HEADERS)
        cookie = ""
        with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
            set_cookie = r.headers.get("Set-Cookie")
            if set_cookie:
                cookie = set_cookie.split(";")[0]

            dates = re.findall(r'<option[^>]*value=[\'"](\d{8})[\'"]', html)
            token_match = re.search(r'name="SYNCHRONIZER_TOKEN"\s+value="([^"]+)"', html)
            token = token_match.group(1) if token_match else ""

        if not dates or not token:
            return []

        all_stock_records = []
        for d in dates:
            post_data = urllib.parse.urlencode({
                "SYNCHRONIZER_TOKEN": token,
                "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
                "method": "submit",
                "firDate": dates[0],
                "scaDate": d,
                "sqlMethod": "StockNo",
                "stockNo": stock_id,
                "stockName": ""
            }).encode("utf-8")

            h = REQUEST_HEADERS.copy()
            h["Content-Type"] = "application/x-www-form-urlencoded"
            h["Referer"] = TDCC_PORTAL_URL
            if cookie:
                h["Cookie"] = cookie

            req_post = urllib.request.Request(TDCC_PORTAL_URL, data=post_data, headers=h)
            try:
                with urllib.request.urlopen(req_post, context=self.ssl_ctx, timeout=10) as r_p:
                    res_html = r_p.read().decode("utf-8", errors="ignore")
                    # 更新下一次 request 用的 token
                    tok_m = re.search(r'name="SYNCHRONIZER_TOKEN"\s+value="([^"]+)"', res_html)
                    if tok_m:
                        token = tok_m.group(1)

                    # 解析表格列
                    rows = re.findall(r'<tr>\s*<td[^>]*>(\d+)</td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([\d,]+)</td>\s*<td[^>]*>([\d,]+)</td>\s*<td[^>]*>([\d.]+)%?</td>\s*</tr>', res_html)
                    date_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"
                    for r_item in rows:
                        level = int(r_item[0])
                        holders = int(r_item[2].replace(",", ""))
                        shares = int(r_item[3].replace(",", ""))
                        pct = float(r_item[4])
                        all_stock_records.append({
                            "date": date_fmt,
                            "stock_id": stock_id,
                            "holding_level": level,
                            "shareholders": holders,
                            "shares": shares,
                            "share_percent": pct
                        })
                time.sleep(0.4)
            except Exception as e:
                print(f"[!] 抓取 {stock_id} 在 {d} 失敗: {e}")
                continue

        return all_stock_records
