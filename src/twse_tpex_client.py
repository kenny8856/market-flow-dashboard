import json
import ssl
import urllib.request
from typing import List, Dict, Any
from .config import TWSE_API_URLS, TPEX_API_URLS, REQUEST_HEADERS

class OfficialDataClient:
    """
    負責與臺灣證券交易所 (TWSE) 及 證券櫃檯買賣中心 (TPEx) 官方 OpenAPI 連線通訊，
    獲取最新全市場公司基本資料及全體證券商分點名冊。
    """

    def __init__(self):
        self.ssl_context = ssl._create_unverified_context()

    def _fetch_json(self, url: str) -> Any:
        req = urllib.request.Request(url, headers=REQUEST_HEADERS)
        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=20) as resp:
                raw_bytes = resp.read()
                # 嘗試 utf-8 與 cp950 解碼
                try:
                    text = raw_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw_bytes.decode("cp950", errors="ignore")
                return json.loads(text)
        except Exception as e:
            print(f"[警告] 請求失敗 {url}: {e}")
            return []

    def get_listed_companies(self) -> List[Dict[str, Any]]:
        """取得 TWSE 所有上市公司基本資料（含中文地址）"""
        print("[1/4] 正從臺灣證券交易所 (TWSE) 獲取上市公司基本資料...")
        data = self._fetch_json(TWSE_API_URLS["listed_companies"])
        results = []
        if isinstance(data, list):
            for item in data:
                stock_id = item.get("公司代號", "").strip()
                stock_name = item.get("公司簡稱", "").strip() or item.get("公司名稱", "").strip()
                addr = item.get("住址", "").strip()
                industry = item.get("產業別", "").strip()
                if stock_id and stock_name:
                    results.append({
                        "stock_id": stock_id,
                        "stock_name": stock_name,
                        "market_type": "上市",
                        "industry": industry,
                        "address": addr,
                        "tel": item.get("總機電話", "").strip(),
                        "chairman": item.get("董事長", "").strip(),
                    })
        print(f"      -> 成功取得上市公司 {len(results)} 家")
        return results

    def get_otc_companies(self) -> List[Dict[str, Any]]:
        """取得 TPEx 櫃買中心所有上櫃公司基本資料"""
        print("[2/4] 正從證券櫃檯買賣中心 (TPEx) 獲取上櫃公司基本資料...")
        data = self._fetch_json(TPEX_API_URLS["otc_companies"])
        results = []
        if isinstance(data, list):
            for item in data:
                stock_id = item.get("SecuritiesCompanyCode", "").strip()
                stock_name = item.get("CompanyAbbreviation", "").strip() or item.get("CompanyName", "").strip()
                addr = item.get("Address", "").strip()
                industry = item.get("SecuritiesIndustryCode", "").strip()
                if stock_id and stock_name:
                    results.append({
                        "stock_id": stock_id,
                        "stock_name": stock_name,
                        "market_type": "上櫃",
                        "industry": industry,
                        "address": addr,
                        "tel": item.get("Telephone", "").strip(),
                        "chairman": item.get("Chairman", "").strip(),
                    })
        print(f"      -> 成功取得上櫃公司 {len(results)} 家")
        return results

    def get_broker_branches(self) -> List[Dict[str, Any]]:
        """取得 TWSE 全體證券商分公司營業處所基本資料（代號、名稱、地址、電話）"""
        print("[3/4] 正從 TWSE 獲取全台證券商分公司營業分點名冊...")
        data = self._fetch_json(TWSE_API_URLS["broker_branches"])
        results = []
        if isinstance(data, list):
            for item in data:
                broker_id = item.get("證券商代號", "").strip()
                broker_name = item.get("證券商名稱", "").strip()
                addr = item.get("地址", "").strip()
                tel = item.get("電話", "").strip()
                if broker_id and broker_name:
                    results.append({
                        "broker_id": broker_id,
                        "broker_name": broker_name,
                        "address": addr,
                        "tel": tel,
                        "is_headquarter": 0
                    })
        print(f"      -> 成功取得證券商分公司 {len(results)} 家")
        return results

    def get_broker_headquarters(self) -> List[Dict[str, Any]]:
        """取得 TWSE 全體證券商總公司營業處所資料"""
        print("[4/4] 正從 TWSE 獲取全台證券商總公司資料...")
        data = self._fetch_json(TWSE_API_URLS["broker_headquarters"])
        results = []
        if isinstance(data, list):
            for item in data:
                broker_id = item.get("證券商代號", "").strip()
                broker_name = item.get("(證券商IB)簡稱", "").strip()
                addr = item.get("營業處所", "").strip() or item.get("總公司地址", "").strip()
                tel = item.get("電話", "").strip()
                if broker_id and broker_name:
                    results.append({
                        "broker_id": broker_id,
                        "broker_name": f"{broker_name}-總公司",
                        "address": addr,
                        "tel": tel,
                        "is_headquarter": 1
                    })
        print(f"      -> 成功取得證券商總公司 {len(results)} 家")
        return results
