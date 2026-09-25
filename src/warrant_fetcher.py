import urllib.request
import ssl
import json
import time
import gzip
from datetime import datetime
from typing import List, Dict, Any, Tuple
from .warrant_linker import WarrantLinker

WARRANT_HEADERS = {
    "accept": "application/json",
    "If-Modified-Since": "Mon, 26 Jul 1997 05:00:00 GMT",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
}

TWSE_MI_INDEX_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date_clean}&response=json&type={wtype}"
TWSE_WARRANT_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap42_L"
TPEX_WARRANT_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap42_O"

def clean_num(val: Any, is_float: bool = False) -> Any:
    if val is None:
        return 0.0 if is_float else 0
    s = str(val).replace(",", "").replace(" ", "").strip()
    if not s or s in ("--", "N/A"):
        return 0.0 if is_float else 0
    try:
        return float(s) if is_float else int(float(s))
    except ValueError:
        return 0.0 if is_float else 0

def roc_to_iso_date(roc_str: str) -> str:
    """將民國年月日 (如 '1150916') 轉換為標準格式 '2026-09-16'"""
    s = str(roc_str).strip()
    if len(s) == 7:
        roc_y = int(s[:3])
        ad_y = roc_y + 1911
        m = s[3:5]
        d = s[5:7]
        return f"{ad_y}-{m}-{d}"
    elif len(s) == 6:
        roc_y = int(s[:2])
        ad_y = roc_y + 1911
        m = s[2:4]
        d = s[4:6]
        return f"{ad_y}-{m}-{d}"
    return s

class WarrantFetcher:
    """
    權證公開資料獲取與個股關聯擴充處理模組。
    對接 TWSE (t187ap42_L) 與 TPEx (mopsfin_t187ap42_O) 官方端點，
    並於原 JSON 格式旁自動附加【個股代號】與【個股名稱】。
    """

    def __init__(self):
        self.ssl_context = ssl._create_unverified_context()
        self.linker = WarrantLinker()

    def _fetch_raw_json(self, url: str) -> List[Dict[str, Any]]:
        req = urllib.request.Request(url, headers=WARRANT_HEADERS)
        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                data = json.loads(text)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[警告] 權證 API 請求異常 ({url}): {e}")
            return []

    def fetch_twse_mi_index(self, date_str: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        從 TWSE 官方盤後行情系統取得指定交易日之全部上市權證行情 (涵蓋 0999 認購權證 與 0999P 認售權證)。
        優點：每日 15:30 盤後實時發布，零 OpenAPI 延遲，且第 17, 18 欄位自帶官方標的代號與標的名稱。
        回傳: (date_str, normalized_db_rows, enhanced_json_records)
        """
        date_clean = date_str.replace("-", "")
        # 0999: 認購權證(含牛熊證), 0999P: 認售權證(含牛熊證)
        warrant_types = ["0999", "0999P"]
        
        all_raw_rows = []
        for wtype in warrant_types:
            url = TWSE_MI_INDEX_URL.format(date_clean=date_clean, wtype=wtype)
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
            })

            data = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, context=self.ssl_context, timeout=30) as resp:
                        raw = resp.read()
                        if resp.info().get("Content-Encoding") == "gzip":
                            raw = gzip.decompress(raw)
                        data = json.loads(raw.decode("utf-8", errors="ignore"))
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  [警告] TWSE MI_INDEX ({wtype}) 取得失敗 ({date_str}): {e}")
                    time.sleep(1.0 * (attempt + 1))

            if data and data.get("stat") == "OK":
                for t in data.get("tables", []):
                    t_data = t.get("data", [])
                    if len(t_data) > 0:
                        all_raw_rows.extend(t_data)
                        break

        if not all_raw_rows:
            return date_str, [], []

        db_rows = []
        enhanced_records = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for r in all_raw_rows:
            wid = str(r[1]).strip()
            wname = str(r[2]).strip()
            vol_shares = clean_num(r[3])
            amt = clean_num(r[5], is_float=True)

            # 證交所 MI_INDEX 第 17, 18 欄位為官方標的代號與標的名稱
            sid = str(r[17]).strip() if len(r) > 17 else ""
            sname = str(r[18]).strip() if len(r) > 18 else ""
            if not sid:
                sid, sname = self.linker.link(wname)

            db_rows.append({
                "date": date_str,
                "warrant_id": wid,
                "warrant_name": wname,
                "trade_amount": amt,
                "trade_volume": vol_shares,
                "trade_lots": vol_shares // 1000 if vol_shares >= 1000 else vol_shares,
                "underlying_stock_id": sid,
                "underlying_stock_name": sname,
                "created_at": now_str
            })

            enhanced_records.append({
                "交易日期": date_str,
                "權證代號": wid,
                "權證名稱": wname,
                "成交金額": amt,
                "成交張數": vol_shares // 1000 if vol_shares >= 1000 else vol_shares,
                "個股代號": sid,
                "個股名稱": sname
            })

        return date_str, db_rows, enhanced_records

    def fetch_twse_warrants(self, date_str: str = None) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        獲取 TWSE 上市權證交易資料。
        優先級：
        1. 若指定 date_str，優先呼叫 fetch_twse_mi_index(date_str)；
        2. 若未指定 date_str，若今日已過 15:00 且為平日，優先抓取今日 MI_INDEX；
        3. 若 MI_INDEX 無資料或失敗，則降級調用 OpenAPI (TWSE_WARRANT_URL)。
        回傳: (date_str, normalized_db_rows, enhanced_json_records)
        """
        target = date_str
        if not target:
            now = datetime.now()
            if now.weekday() < 5 and (now.hour > 15 or (now.hour == 15 and now.minute >= 0)):
                target = now.strftime("%Y-%m-%d")

        if target:
            t_date, t_rows, t_enh = self.fetch_twse_mi_index(target)
            if t_rows:
                return t_date, t_rows, t_enh

        # 備援：OpenAPI 端點
        raw_list = self._fetch_raw_json(TWSE_WARRANT_URL)
        db_rows = []
        enhanced_records = []
        found_date = datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in raw_list:
            roc_date = item.get("交易日期") or item.get("出表日期") or ""
            iso_date = roc_to_iso_date(roc_date)
            if iso_date and len(iso_date) == 10:
                found_date = iso_date

            wid = str(item.get("權證代號", "")).strip()
            wname = str(item.get("權證名稱", "")).strip()
            amount = clean_num(item.get("成交金額"), is_float=True)
            vol_raw = clean_num(item.get("成交張數") or item.get("成交數量"))

            stock_id, stock_name = self.linker.link(wname)

            db_rows.append({
                "date": found_date,
                "warrant_id": wid,
                "warrant_name": wname,
                "trade_amount": amount,
                "trade_volume": vol_raw,
                "trade_lots": vol_raw // 1000 if vol_raw >= 1000 else vol_raw,
                "underlying_stock_id": stock_id,
                "underlying_stock_name": stock_name,
                "created_at": now_str
            })

            rec = dict(item)
            rec["個股代號"] = stock_id
            rec["個股名稱"] = stock_name
            enhanced_records.append(rec)

        return found_date, db_rows, enhanced_records

    def fetch_tpex_warrants(self) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        獲取 TPEx 上櫃權證最新交易資料，並與上市櫃個股進行 link 擴充。
        回傳: (date_str, normalized_db_rows, enhanced_json_records)
        """
        raw_list = self._fetch_raw_json(TPEX_WARRANT_URL)
        db_rows = []
        enhanced_records = []
        found_date = datetime.now().strftime("%Y-%m-%d")

        for item in raw_list:
            # 欄位名: ['Date', '交易日期', '權證代號', '權證名稱', '成交金額', '成交數量']
            roc_date = item.get("交易日期") or item.get("Date") or ""
            iso_date = roc_to_iso_date(roc_date)
            if iso_date and len(iso_date) == 10:
                found_date = iso_date

            wid = str(item.get("權證代號", "")).strip()
            wname = str(item.get("權證名稱", "")).strip()
            amount = clean_num(item.get("成交金額"), is_float=True)
            vol_raw = clean_num(item.get("成交數量") or item.get("成交張數"))

            # 智慧關聯標的個股
            stock_id, stock_name = self.linker.link(wname)

            # 1. 資料庫入庫結構
            db_rows.append({
                "date": found_date,
                "warrant_id": wid,
                "warrant_name": wname,
                "trade_amount": amount,
                "trade_volume": vol_raw,
                "trade_lots": vol_raw // 1000 if vol_raw >= 1000 else vol_raw,
                "underlying_stock_id": stock_id,
                "underlying_stock_name": stock_name
            })

            # 2. 依使用者要求擴充的 JSON 結構 (原格式多加兩欄)
            rec = dict(item)
            rec["個股代號"] = stock_id
            rec["個股名稱"] = stock_name
            enhanced_records.append(rec)

        return found_date, db_rows, enhanced_records
