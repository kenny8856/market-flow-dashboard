import os
import sys
import ssl
import csv
import io
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

TAIFEX_DOWNLOAD_URL = "https://www.taifex.com.tw/cht/3/largeTraderFutDown"
TAIFEX_OPENAPI_URL = "https://openapi.taifex.com.tw/v1/OpenInterestOfLargeTradersFutures"

REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

KNOWN_NAMES = {
    "TX": "臺股期貨",
    "TE": "電子期貨",
    "TF": "金融期貨",
    "MTX": "小型臺指期貨",
    "TMF": "微型臺指期貨",
    "ZEF": "小型電子期貨",
    "ZFF": "小型金融期貨",
}

def clean_int(val: Any) -> int:
    """清理整數字串（移除逗號、空白、負號處理）"""
    if val is None:
        return 0
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "N/A", "---", "-"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0

def clean_contract_name(code: str, raw_name: str) -> str:
    """清理期貨商品名稱，標準化主要指數期貨簡稱，保留個股期貨全名"""
    c_code = code.strip()
    if c_code in KNOWN_NAMES:
        return KNOWN_NAMES[c_code]
    name = raw_name.strip()
    # 若有 (TX+...) 類似後綴，移除括號內的加權換算公式
    if "(" in name and any(k in name for k in ("+", "/", "*")):
        idx = name.find("(")
        if idx > 0:
            name = name[:idx].strip()
    return name

class TaifexLargeTraderFetcher:
    """期交所大額交易人未沖銷部位抓取與解析器 (支援全市場所有期貨與個股期貨)"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    def download_range_csv(self, start_date: str, end_date: str, max_retries: int = 3) -> str:
        """
        向期交所發送 POST 請求，下載指定日期範圍的 CSV (格式: YYYY-MM-DD 或 YYYY/MM/DD)
        注意：期交所單次請求限制在 3 個月內
        """
        d_start = start_date.replace("-", "/")
        d_end = end_date.replace("-", "/")

        post_data = urllib.parse.urlencode({
            "queryStartDate": d_start,
            "queryEndDate": d_end,
        }).encode("utf-8")

        req = urllib.request.Request(TAIFEX_DOWNLOAD_URL, data=post_data, headers=REQUEST_HEADERS)

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
                time.sleep(2.0 * (attempt + 1))

        raise RuntimeError(f"下載期交所大額交易人 CSV 失敗 [{d_start} ~ {d_end}]: {last_err}")

    def _process_grouped_data(self, grouped: Dict[str, Dict[str, Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        通用的聚合運算邏輯：
        遍歷各日期與商品，計算：
        1. 當月契約 (最小交割月份)
        2. 所有契約 (999999 或 999912)
        3. 週契約 (666666 或含週/W)
        4. 遠月契約 (公式: 所有契約 - 當月契約)
        """
        output_records: List[Dict[str, Any]] = []

        for date_iso, contracts in grouped.items():
            for code, c_info in contracts.items():
                contract_name = c_info["name"]
                expiries = c_info["expiries"]

                front_month_expiry = None
                all_contracts_expiry = None
                weekly_expiry = None

                for exp_key in expiries.keys():
                    if exp_key in ("999999", "999912"):
                        all_contracts_expiry = exp_key
                    elif exp_key == "666666" or "週" in exp_key or "W" in exp_key:
                        weekly_expiry = exp_key
                    elif exp_key.isdigit() and len(exp_key) == 6:
                        if front_month_expiry is None or exp_key < front_month_expiry:
                            front_month_expiry = exp_key

                def build_record(exp_key: str, c_type: str) -> Optional[Dict[str, Any]]:
                    data_0 = expiries.get(exp_key, {}).get("0", {})
                    data_1 = expiries.get(exp_key, {}).get("1", {})
                    if not data_0 and not data_1:
                        return None

                    buy_top5 = data_0.get("buy_top5", 0)
                    buy_top5_spec = data_1.get("buy_top5", 0)
                    buy_top10 = data_0.get("buy_top10", 0)
                    buy_top10_spec = data_1.get("buy_top10", 0)

                    sell_top5 = data_0.get("sell_top5", 0)
                    sell_top5_spec = data_1.get("sell_top5", 0)
                    sell_top10 = data_0.get("sell_top10", 0)
                    sell_top10_spec = data_1.get("sell_top10", 0)

                    market_oi = data_0.get("market_oi", 0) or data_1.get("market_oi", 0)

                    return {
                        "date": date_iso,
                        "contract_code": code,
                        "contract_name": contract_name,
                        "contract_type": c_type,
                        "expiry_month": exp_key,
                        "buy_top5": buy_top5,
                        "buy_top5_spec": buy_top5_spec,
                        "buy_top10": buy_top10,
                        "buy_top10_spec": buy_top10_spec,
                        "sell_top5": sell_top5,
                        "sell_top5_spec": sell_top5_spec,
                        "sell_top10": sell_top10,
                        "sell_top10_spec": sell_top10_spec,
                        "market_oi": market_oi,
                        "net_top5": buy_top5 - sell_top5,
                        "net_top5_spec": buy_top5_spec - sell_top5_spec,
                        "net_top10": buy_top10 - sell_top10,
                        "net_top10_spec": buy_top10_spec - sell_top10_spec,
                    }

                front_rec = build_record(front_month_expiry, "當月") if front_month_expiry else None
                all_rec = build_record(all_contracts_expiry, "所有契約") if all_contracts_expiry else None
                week_rec = build_record(weekly_expiry, "週契約") if weekly_expiry else None

                if front_rec:
                    output_records.append(front_rec)
                if all_rec:
                    output_records.append(all_rec)
                if week_rec:
                    output_records.append(week_rec)

                # 計算 遠月契約 = 所有契約 - 當月
                if front_rec and all_rec:
                    far_buy_top5 = all_rec["buy_top5"] - front_rec["buy_top5"]
                    far_buy_top5_spec = all_rec["buy_top5_spec"] - front_rec["buy_top5_spec"]
                    far_buy_top10 = all_rec["buy_top10"] - front_rec["buy_top10"]
                    far_buy_top10_spec = all_rec["buy_top10_spec"] - front_rec["buy_top10_spec"]

                    far_sell_top5 = all_rec["sell_top5"] - front_rec["sell_top5"]
                    far_sell_top5_spec = all_rec["sell_top5_spec"] - front_rec["sell_top5_spec"]
                    far_sell_top10 = all_rec["sell_top10"] - front_rec["sell_top10"]
                    far_sell_top10_spec = all_rec["sell_top10_spec"] - front_rec["sell_top10_spec"]

                    far_market_oi = all_rec["market_oi"] - front_rec["market_oi"]

                    far_rec = {
                        "date": date_iso,
                        "contract_code": code,
                        "contract_name": contract_name,
                        "contract_type": "遠月",
                        "expiry_month": "FAR",
                        "buy_top5": far_buy_top5,
                        "buy_top5_spec": far_buy_top5_spec,
                        "buy_top10": far_buy_top10,
                        "buy_top10_spec": far_buy_top10_spec,
                        "sell_top5": far_sell_top5,
                        "sell_top5_spec": far_sell_top5_spec,
                        "sell_top10": far_sell_top10,
                        "sell_top10_spec": far_sell_top10_spec,
                        "market_oi": far_market_oi,
                        "net_top5": far_buy_top5 - far_sell_top5,
                        "net_top5_spec": far_buy_top5_spec - far_sell_top5_spec,
                        "net_top10": far_buy_top10 - far_sell_top10,
                        "net_top10_spec": far_buy_top10_spec - far_sell_top10_spec,
                    }
                    output_records.append(far_rec)

        return output_records

    def parse_csv_data(self, csv_text: str) -> List[Dict[str, Any]]:
        """
        解析期交所大額交易人 CSV 資料 (支援全市場所有期貨商品與個股期貨)
        """
        if not csv_text or not csv_text.strip():
            return []

        reader = csv.reader(io.StringIO(csv_text.strip()))
        try:
            header = next(reader)
        except StopIteration:
            return []

        # 暫存結構: grouped[date_iso][contract_code] = {"name": contract_name, "expiries": {expiry: {trader_type: pos_data}}}
        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for row in reader:
            if len(row) < 10:
                continue

            raw_date = row[0].strip()
            raw_code = row[1].strip()
            raw_name = row[2].strip()
            raw_expiry = row[3].strip()
            trader_type = row[4].strip() # '0'=全體, '1'=特定法人

            if not raw_code:
                continue

            date_iso = raw_date.replace("/", "-")
            contract_name = clean_contract_name(raw_code, raw_name)

            pos_data = {
                "buy_top5": clean_int(row[5]),
                "sell_top5": clean_int(row[6]),
                "buy_top10": clean_int(row[7]),
                "sell_top10": clean_int(row[8]),
                "market_oi": clean_int(row[9]),
            }

            if date_iso not in grouped:
                grouped[date_iso] = {}
            if raw_code not in grouped[date_iso]:
                grouped[date_iso][raw_code] = {"name": contract_name, "expiries": {}}
            if raw_expiry not in grouped[date_iso][raw_code]["expiries"]:
                grouped[date_iso][raw_code]["expiries"][raw_expiry] = {}

            grouped[date_iso][raw_code]["expiries"][raw_expiry][trader_type] = pos_data

        return self._process_grouped_data(grouped)

    def fetch_chunked_history(
        self,
        start_date: str,
        end_date: str,
        chunk_days: int = 80,
        delay_seconds: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        將起訖日切分為小於 85 天的區間，分段向期交所下載 CSV 並聚合所有大額交易人記錄
        """
        dt_start = datetime.strptime(start_date.replace("/", "-"), "%Y-%m-%d")
        dt_end = datetime.strptime(end_date.replace("/", "-"), "%Y-%m-%d")

        all_records: List[Dict[str, Any]] = []
        curr_start = dt_start

        chunks: List[Tuple[str, str]] = []
        while curr_start <= dt_end:
            curr_end = min(curr_start + timedelta(days=chunk_days), dt_end)
            chunks.append((curr_start.strftime("%Y-%m-%d"), curr_end.strftime("%Y-%m-%d")))
            curr_start = curr_end + timedelta(days=1)

        print(f"[*] 歷史資料同步規劃：共分為 {len(chunks)} 個區間請求下載 (起: {start_date} ~ 迄: {end_date})")

        for idx, (c_start, c_end) in enumerate(chunks, 1):
            print(f"  -> [{idx}/{len(chunks)}] 正在下載區間: {c_start} 至 {c_end} ...", end=" ", flush=True)
            try:
                csv_text = self.download_range_csv(c_start, c_end)
                records = self.parse_csv_data(csv_text)
                all_records.extend(records)
                print(f"成功 (取得 {len(records):,} 筆明細)")
            except Exception as e:
                print(f"失敗: {e}")

            if idx < len(chunks):
                time.sleep(delay_seconds)

        return all_records

    def fetch_latest_openapi(self) -> List[Dict[str, Any]]:
        """
        向期交所官方 OpenAPI 取得最新交易日資料 (備用 / 每日收盤更新)
        """
        req = urllib.request.Request(TAIFEX_OPENAPI_URL, headers={"User-Agent": REQUEST_HEADERS["User-Agent"]})
        try:
            with urllib.request.urlopen(req, context=self.ssl_ctx, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            raise RuntimeError(f"OpenAPI 請求失敗: {e}")

        grouped: Dict[str, Dict[str, Dict[str, Any]]] = {}

        for item in data:
            raw_code = item.get("Contract", "").strip()
            raw_name = item.get("ContractName", "").strip()
            raw_date = item.get("Date", "").strip()
            raw_expiry = item.get("SettlementMonth", "").strip()
            trader_type = item.get("TypeOfTraders", "").strip()

            if not raw_code:
                continue

            if len(raw_date) == 8:
                date_iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
            else:
                date_iso = raw_date.replace("/", "-")

            contract_name = clean_contract_name(raw_code, raw_name)

            pos_data = {
                "buy_top5": clean_int(item.get("Top5Buy")),
                "sell_top5": clean_int(item.get("Top5Sell")),
                "buy_top10": clean_int(item.get("Top10Buy")),
                "sell_top10": clean_int(item.get("Top10Sell")),
                "market_oi": clean_int(item.get("OIOfMarket")),
            }

            if date_iso not in grouped:
                grouped[date_iso] = {}
            if raw_code not in grouped[date_iso]:
                grouped[date_iso][raw_code] = {"name": contract_name, "expiries": {}}
            if raw_expiry not in grouped[date_iso][raw_code]["expiries"]:
                grouped[date_iso][raw_code]["expiries"][raw_expiry] = {}

            grouped[date_iso][raw_code]["expiries"][raw_expiry][trader_type] = pos_data

        return self._process_grouped_data(grouped)
