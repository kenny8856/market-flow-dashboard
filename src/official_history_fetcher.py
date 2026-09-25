import urllib.request
import ssl
import json
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from .config import REQUEST_HEADERS

def clean_int(val: Any) -> int:
    """清理整數字串（處理千分位逗號、空白、負號）"""
    if val is None:
        return 0
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "N/A", "---"):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0

def clean_float(val: Any) -> Optional[float]:
    """清理浮點數字串（開高低收等價格）"""
    if val is None:
        return None
    s = str(val).replace(",", "").replace(" ", "").replace("+", "").strip()
    if not s or s in ("--", "X0.00", "N/A", "---"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None

def clean_change(sign_val: Any, diff_val: Any = None) -> float:
    """清理漲跌價差（結合正負號或 HTML 標籤）"""
    if diff_val is None:
        # 單一字串如 "+0.15" 或 "-1.50"
        return clean_float(sign_val) or 0.0
    diff = clean_float(diff_val) or 0.0
    s_sign = str(sign_val)
    if "-" in s_sign:
        return -diff
    return diff

class OfficialHistoryFetcher:
    """
    官方資料獲取引擎（僅透過 TWSE 臺灣證券交易所 與 TPEx 證券櫃檯買賣中心）
    支援全市場上市與上櫃之歷史任意日期收盤行情與三大法人買賣超明細抓取。
    """

    def __init__(self, polite_delay: float = 1.2):
        self.ssl_context = ssl._create_unverified_context()
        self.polite_delay = polite_delay

    def _get_json(self, url: str) -> Optional[Dict[str, Any]]:
        req = urllib.request.Request(url, headers=REQUEST_HEADERS)
        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=25) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                return json.loads(text)
        except Exception:
            return None

    @staticmethod
    def get_candidate_trading_dates(start_date: str = "2020-01-01", days: int = None) -> List[str]:
        """產生工作日清單（排除週六與週日）"""
        today = datetime.now().date()
        dates = []
        if days is not None:
            # Fallback to older days-based logic if explicitly provided
            start_dt = today - timedelta(days=days)
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        
        current_dt = start_dt
        while current_dt <= today:
            # 0=週一, 4=週五, 5=週六, 6=週日
            if current_dt.weekday() < 5:
                dates.append(current_dt.strftime("%Y-%m-%d"))
            current_dt += timedelta(days=1)
        return sorted(dates)

    # ---------------------------------------------------------------------
    # 上市 (TWSE) 資料抓取
    # ---------------------------------------------------------------------
    def fetch_twse_daily_data(self, date_str: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        獲取特定交易日之 TWSE 上市每日收盤行情與三大法人買賣超明細
        date_str 格式: 'YYYY-MM-DD'
        """
        ymd = date_str.replace("-", "")
        
        # 1. 抓取每日收盤行情 (MI_INDEX)
        url_quotes = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={ymd}&type=ALLBUT0999&response=json"
        res_quotes = self._get_json(url_quotes)
        time.sleep(self.polite_delay)

        quotes_list = []
        if res_quotes and res_quotes.get("stat") == "OK":
            for table in res_quotes.get("tables", []):
                if "每日收盤行情" in table.get("title", ""):
                    for row in table.get("data", []):
                        if len(row) >= 11:
                            sid = str(row[0]).strip()
                            sname = str(row[1]).strip()
                            vol_shares = clean_int(row[2])
                            tx_count = clean_int(row[3])
                            amount = clean_int(row[4])
                            open_p = clean_float(row[5])
                            high_p = clean_float(row[6])
                            low_p = clean_float(row[7])
                            close_p = clean_float(row[8])
                            change_p = clean_change(row[9], row[10])

                            quotes_list.append({
                                "date": date_str,
                                "stock_id": sid,
                                "stock_name": sname,
                                "open_price": open_p,
                                "high_price": high_p,
                                "low_price": low_p,
                                "close_price": close_p,
                                "change_price": change_p,
                                "volume_shares": vol_shares,
                                "volume_lots": vol_shares // 1000,
                                "amount": amount,
                                "transaction_count": tx_count
                            })
                    break

        # 2. 抓取三大法人買賣超 (T86)
        url_inst = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={ymd}&selectType=ALLBUT0999&response=json"
        res_inst = self._get_json(url_inst)
        time.sleep(self.polite_delay)

        inst_list = []
        if res_inst and res_inst.get("stat") == "OK":
            for row in res_inst.get("data", []):
                if len(row) >= 19:
                    sid = str(row[0]).strip()
                    sname = str(row[1]).strip()
                    f_buy = clean_int(row[2])
                    f_sell = clean_int(row[3])
                    f_net = clean_int(row[4])
                    
                    t_buy = clean_int(row[8])
                    t_sell = clean_int(row[9])
                    t_net = clean_int(row[10])

                    d_net = clean_int(row[11])
                    d_self_buy = clean_int(row[12])
                    d_self_sell = clean_int(row[13])
                    d_self_net = clean_int(row[14])
                    d_hedge_buy = clean_int(row[15])
                    d_hedge_sell = clean_int(row[16])
                    d_hedge_net = clean_int(row[17])

                    tot_net = clean_int(row[18])

                    inst_list.append({
                        "date": date_str,
                        "stock_id": sid,
                        "stock_name": sname,
                        "foreign_buy": f_buy,
                        "foreign_sell": f_sell,
                        "foreign_net": f_net,
                        "trust_buy": t_buy,
                        "trust_sell": t_sell,
                        "trust_net": t_net,
                        "dealer_net": d_net,
                        "dealer_self_buy": d_self_buy,
                        "dealer_self_sell": d_self_sell,
                        "dealer_self_net": d_self_net,
                        "dealer_hedge_buy": d_hedge_buy,
                        "dealer_hedge_sell": d_hedge_sell,
                        "dealer_hedge_net": d_hedge_net,
                        "total_net": tot_net,
                        "foreign_net_lots": f_net // 1000,
                        "trust_net_lots": t_net // 1000,
                        "total_net_lots": tot_net // 1000,
                    })

        return quotes_list, inst_list

    # ---------------------------------------------------------------------
    # 上櫃 (TPEx) 資料抓取 (完整支援歷史任意交易日)
    # ---------------------------------------------------------------------
    def fetch_tpex_daily_data(self, date_str: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        獲取特定交易日之 TPEx 上櫃每日收盤行情與三大法人買賣超明細
        date_str 格式: 'YYYY-MM-DD'
        自動轉換為民國年格式查詢官方伺服器
        """
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        roc_year = dt.year - 1911
        roc_date_slash = f"{roc_year}/{dt.strftime('%m/%d')}"

        quotes_list = []
        inst_list = []

        # 1. 抓取每日收盤行情 (stk_quote_result.php)
        url_quotes = f"https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&d={roc_date_slash}&o=json"
        res_quotes = self._get_json(url_quotes)
        time.sleep(self.polite_delay)

        if res_quotes and "tables" in res_quotes:
            for t in res_quotes.get("tables", []):
                for row in t.get("data", []):
                    if len(row) >= 11:
                        sid = str(row[0]).strip()
                        sname = str(row[1]).strip()
                        if sid and sname:
                            close_p = clean_float(row[2])
                            change_p = clean_change(row[3])
                            open_p = clean_float(row[4])
                            high_p = clean_float(row[5])
                            low_p = clean_float(row[6])
                            vol_shares = clean_int(row[8])
                            amount = clean_int(row[9])
                            tx_count = clean_int(row[10])

                            quotes_list.append({
                                "date": date_str,
                                "stock_id": sid,
                                "stock_name": sname,
                                "open_price": open_p,
                                "high_price": high_p,
                                "low_price": low_p,
                                "close_price": close_p,
                                "change_price": change_p,
                                "volume_shares": vol_shares,
                                "volume_lots": vol_shares // 1000,
                                "amount": amount,
                                "transaction_count": tx_count
                            })
                if quotes_list:
                    break

        # 若官網歷史端點無資料（例如當日最新），嘗試 OpenAPI 備援
        if not quotes_list and date_str == datetime.now().strftime("%Y-%m-%d"):
            url_open = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
            res_open = self._get_json(url_open)
            time.sleep(self.polite_delay)
            if isinstance(res_open, list):
                expected_roc_date = f"{roc_year}{dt.strftime('%m%d')}"
                for row in res_open:
                    # 避免在休市日抓到上一交易日的資料並錯誤標記為今日
                    if str(row.get("Date", "")).strip() != expected_roc_date:
                        continue
                        
                    sid = str(row.get("SecuritiesCompanyCode", "")).strip()
                    sname = str(row.get("CompanyName", "")).strip()
                    if sid and sname:
                        quotes_list.append({
                            "date": date_str,
                            "stock_id": sid,
                            "stock_name": sname,
                            "open_price": clean_float(row.get("Open")),
                            "high_price": clean_float(row.get("High")),
                            "low_price": clean_float(row.get("Low")),
                            "close_price": clean_float(row.get("Close")),
                            "change_price": clean_float(row.get("Change")) or 0.0,
                            "volume_shares": clean_int(row.get("TradingShares")),
                            "volume_lots": clean_int(row.get("TradingShares")) // 1000,
                            "amount": clean_int(row.get("TransactionAmount")),
                            "transaction_count": clean_int(row.get("TransactionNumber"))
                        })

        # 2. 抓取三大法人明細 (3itrade_hedge_result.php)
        url_inst = f"https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php?l=zh-tw&d={roc_date_slash}&se=EW&t=D&o=json"
        res_inst = self._get_json(url_inst)
        time.sleep(self.polite_delay)

        if res_inst and "tables" in res_inst:
            for t in res_inst.get("tables", []):
                for row in t.get("data", []):
                    if len(row) >= 24:
                        sid = str(row[0]).strip()
                        sname = str(row[1]).strip()
                        if sid and sname:
                            f_buy = clean_int(row[8])   # 外陸資合計買進
                            f_sell = clean_int(row[9])  # 外陸資合計賣出
                            f_net = clean_int(row[10])  # 外陸資合計買賣超

                            t_buy = clean_int(row[11])  # 投信買進
                            t_sell = clean_int(row[12]) # 投信賣出
                            t_net = clean_int(row[13])  # 投信買賣超

                            d_self_buy = clean_int(row[14]) # 自營商自行買賣
                            d_self_sell = clean_int(row[15])
                            d_self_net = clean_int(row[16])

                            d_hedge_buy = clean_int(row[17]) # 自營商避險
                            d_hedge_sell = clean_int(row[18])
                            d_hedge_net = clean_int(row[19])

                            d_net = clean_int(row[22]) # 自營商合計買賣超
                            tot_net = clean_int(row[23]) # 三大法人合計

                            inst_list.append({
                                "date": date_str,
                                "stock_id": sid,
                                "stock_name": sname,
                                "foreign_buy": f_buy,
                                "foreign_sell": f_sell,
                                "foreign_net": f_net,
                                "trust_buy": t_buy,
                                "trust_sell": t_sell,
                                "trust_net": t_net,
                                "dealer_net": d_net,
                                "dealer_self_buy": d_self_buy,
                                "dealer_self_sell": d_self_sell,
                                "dealer_self_net": d_self_net,
                                "dealer_hedge_buy": d_hedge_buy,
                                "dealer_hedge_sell": d_hedge_sell,
                                "dealer_hedge_net": d_hedge_net,
                                "total_net": tot_net,
                                "foreign_net_lots": f_net // 1000,
                                "trust_net_lots": t_net // 1000,
                                "total_net_lots": tot_net // 1000,
                            })
                if inst_list:
                    break

        return quotes_list, inst_list
