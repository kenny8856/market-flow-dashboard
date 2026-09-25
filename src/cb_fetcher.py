"""
Convertible Bond (CB) Fetcher Module
Fetches Taiwan Convertible Bond quotes and issuance metadata from TPEx.
"""

import urllib.request
import ssl
import csv
import json
import os
import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# SSL context for TPEx requests
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "db")
GEO_DB_PATH = os.path.join(DB_DIR, "stock_geography.db")


class CBFetcher:
    """Fetcher for Convertible Bond market data."""

    def __init__(self):
        self._basic_cache: Dict[str, Dict[str, Any]] = {}
        self._stock_cache: Dict[str, str] = {}
        self._load_stock_geography_cache()

    def _load_stock_geography_cache(self) -> None:
        """Load underlying stock map from stock_geography.db if available."""
        if os.path.exists(GEO_DB_PATH):
            try:
                conn = sqlite3.connect(GEO_DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT stock_id, stock_name FROM stocks")
                self._stock_cache = dict(cur.fetchall())
                conn.close()
            except Exception:
                pass

    def fetch_cb_basic_info(self) -> List[Dict[str, Any]]:
        """
        Fetch CB basic information from TPEx OpenAPI bond_ISSBD5_data.
        Returns list of basic info dictionaries.
        """
        url = "https://www.tpex.org.tw/openapi/v1/bond_ISSBD5_data"
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, context=_SSL_CTX, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"[CBFetcher] Warning: failed to fetch bond_ISSBD5_data: {e}")
            return []

        results = []
        for item in data:
            bond_code = item.get("BondCode", "").strip()
            if not bond_code:
                continue

            def parse_date(d_str: str) -> Optional[str]:
                if d_str and len(d_str) == 8 and d_str.isdigit():
                    return f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}"
                return None

            issue_amt_raw = item.get("IssueAmount", "").replace(",", "").strip()
            issue_amt = int(issue_amt_raw) * 1000 if issue_amt_raw.isdigit() else None
            issue_lots = (issue_amt // 100000) if issue_amt else None

            conv_price_raw = item.get("Conversion/ExchangePriceAtIssuance", "").replace(",", "").strip()
            try:
                conv_price = float(conv_price_raw) if conv_price_raw else None
            except ValueError:
                conv_price = None

            record = {
                "cb_id": bond_code,
                "cb_name": item.get("ShortName", "").strip(),
                "underlying_id": item.get("IssuerCode", "").strip(),
                "underlying_name": item.get("IssuerName", "").strip(),
                "issue_date": parse_date(item.get("IssueDate", "")),
                "listing_date": parse_date(item.get("ListingDate", "")),
                "maturity_date": parse_date(item.get("MaturityDate", "")),
                "issue_amount": issue_amt,
                "issue_lots": issue_lots,
                "initial_conversion_price": conv_price,
            }
            results.append(record)
            self._basic_cache[bond_code] = record

        return results

    def _get_underlying(self, cb_id: str, cb_name: str) -> Tuple[str, str]:
        """Resolve underlying stock code and name."""
        if cb_id in self._basic_cache:
            m = self._basic_cache[cb_id]
            return m.get("underlying_id", ""), m.get("underlying_name", "")

        # Derivation fallback: standard Taiwan CB code begins with 4-digit stock code
        stock_id = cb_id[:4]
        stock_name = self._stock_cache.get(stock_id, "")
        if not stock_name:
            # Try to trim trailing numbers or 'KY' from cb_name
            name_cand = cb_name.replace("KY", "").strip()
            for digit in ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "永", "1", "2", "3"]:
                if name_cand.endswith(digit):
                    name_cand = name_cand[:-len(digit)]
            stock_name = name_cand.strip()

        return stock_id, stock_name

    def fetch_cb_daily(self, date_str: str) -> List[Dict[str, Any]]:
        """
        Fetch and parse daily CB quotes and board stats for a given date.
        Date format: 'YYYY-MM-DD' or 'YYYYMMDD'.
        Returns empty list if market was closed or holiday.
        """
        clean_date = date_str.replace("-", "").replace("/", "")
        if len(clean_date) != 8:
            raise ValueError(f"Invalid date format: {date_str}")

        yyyy = clean_date[:4]
        yyyymm = clean_date[:6]
        formatted_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"

        url_drs = f"https://www.tpex.org.tw/storage/bond_zone/tradeinfo/cb/{yyyy}/{yyyymm}/RSdrs001.{clean_date}-C.csv"
        url_sta = f"https://www.tpex.org.tw/storage/bond_zone/tradeinfo/cb/{yyyy}/{yyyymm}/RSta0113.{clean_date}-C.csv"

        try:
            # 1. Fetch RSdrs001 (CB Information Board)
            req_drs = urllib.request.Request(url_drs, headers=HEADERS)
            with urllib.request.urlopen(req_drs, context=_SSL_CTX, timeout=15) as resp:
                drs_raw = resp.read()
                if b"<!DOCTYPE html" in drs_raw or b"TITLE" not in drs_raw:
                    return []
                drs_text = drs_raw.decode("cp950", errors="ignore")

            # 2. Fetch RSta0113 (CB Daily Trading Quotes)
            req_sta = urllib.request.Request(url_sta, headers=HEADERS)
            with urllib.request.urlopen(req_sta, context=_SSL_CTX, timeout=15) as resp:
                sta_raw = resp.read()
                if b"<!DOCTYPE html" in sta_raw or b"TITLE" not in sta_raw:
                    return []
                sta_text = sta_raw.decode("cp950", errors="ignore")
        except Exception:
            # HTTP Error 404 or connection error -> non-trading day
            return []

        # Parse RSdrs001
        drs_map = {}
        for row in csv.reader(drs_text.splitlines()):
            if len(row) > 17 and row[0] == "BODY":
                cb_id = row[1].strip()
                if not cb_id or cb_id == "合計":
                    continue

                def to_float(val: str) -> Optional[float]:
                    v = val.replace(",", "").strip()
                    try:
                        return float(v) if v else None
                    except ValueError:
                        return None

                def to_int(val: str) -> Optional[int]:
                    v = val.replace(",", "").strip()
                    try:
                        return int(v) if v else None
                    except ValueError:
                        return None

                conv_end = row[4].strip()
                if "/" in conv_end and len(conv_end) == 10:
                    conv_end = conv_end.replace("/", "-")

                issue_amt = to_int(row[14])
                out_amt = to_int(row[15])

                drs_map[cb_id] = {
                    "cb_id": cb_id,
                    "cb_name": row[2].strip(),
                    "conv_end": conv_end,
                    "conversion_price": to_float(row[5]),
                    "issue_amount": issue_amt,
                    "outstanding_amount": out_amt,
                    "issue_lots": (issue_amt // 100000) if issue_amt else None,
                    "outstanding_lots": (out_amt // 100000) if out_amt else None,
                    "reference_price": to_float(row[16]),
                    "underlying_stock_price": to_float(row[17]),
                }

        # Parse RSta0113
        sta_map = {}
        for row in csv.reader(sta_text.splitlines()):
            if len(row) > 11 and row[0] == "BODY" and row[3].strip() == "等價":
                cb_id = row[1].strip()
                if not cb_id or cb_id == "合計":
                    continue

                def to_float(val: str) -> Optional[float]:
                    v = val.replace(",", "").strip()
                    try:
                        return float(v) if v else None
                    except ValueError:
                        return None

                def to_int(val: str) -> int:
                    v = val.replace(",", "").strip()
                    try:
                        return int(v) if v else 0
                    except ValueError:
                        return 0

                sta_map[cb_id] = {
                    "cb_id": cb_id,
                    "cb_name": row[2].strip(),
                    "close_price": to_float(row[4]),
                    "open_price": to_float(row[6]),
                    "high_price": to_float(row[7]),
                    "low_price": to_float(row[8]),
                    "volume_lots": to_int(row[10]),
                    "trade_amount": to_int(row[11]),
                }

        # Combine DRS and STA
        all_cb_ids = sorted(list(set(drs_map.keys()) | set(sta_map.keys())))
        results = []

        for cb_id in all_cb_ids:
            drs = drs_map.get(cb_id, {})
            sta = sta_map.get(cb_id, {})
            cb_name = drs.get("cb_name") or sta.get("cb_name", "")

            underlying_id, underlying_name = self._get_underlying(cb_id, cb_name)

            open_p = sta.get("open_price")
            high_p = sta.get("high_price")
            low_p = sta.get("low_price")
            close_p = sta.get("close_price")
            ref_p = drs.get("reference_price")
            vol = sta.get("volume_lots", 0)
            amt = sta.get("trade_amount", 0)

            conv_price = drs.get("conversion_price")
            stock_p = drs.get("underlying_stock_price")

            # 轉換價值 = (標的股票價格 / 轉換價格) * 100
            conv_val = None
            if stock_p and conv_price and conv_price > 0:
                conv_val = round((stock_p / conv_price) * 100, 2)

            # 折溢價率 = ((CB價格 - 轉換價值) / 轉換價值) * 100%
            # 若有成交價以收盤價為主，無成交價則採用轉債參考價
            price_for_prem = close_p if close_p is not None else ref_p
            prem_rate = None
            if price_for_prem is not None and conv_val and conv_val > 0:
                prem_rate = round(((price_for_prem - conv_val) / conv_val) * 100, 2)

            basic = self._basic_cache.get(cb_id, {})
            listing_d = basic.get("listing_date")
            maturity_d = basic.get("maturity_date") or drs.get("conv_end")

            results.append({
                "date": formatted_date,
                "cb_id": cb_id,
                "cb_name": cb_name,
                "underlying_id": underlying_id,
                "underlying_name": underlying_name,
                "open_price": open_p,
                "high_price": high_p,
                "low_price": low_p,
                "close_price": close_p,
                "reference_price": ref_p,
                "volume_lots": vol,
                "trade_amount": amt,
                "conversion_price": conv_price,
                "underlying_close_price": stock_p,
                "conversion_value": conv_val,
                "premium_rate": prem_rate,
                "issue_lots": drs.get("issue_lots") or basic.get("issue_lots"),
                "outstanding_lots": drs.get("outstanding_lots"),
                "listing_date": listing_d,
                "maturity_date": maturity_d,
            })

        return results
