import urllib.request
import ssl
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .config import REQUEST_HEADERS

class InstitutionalClient:
    """
    三大法人買賣超數據獲取與統計模組。
    支援查詢指定個股在過去 30 天、180 天或任意天數之三大法人（外資、投信、自營商）累計進出狀況。
    """

    def __init__(self):
        self.ssl_context = ssl._create_unverified_context()
        self.base_url = "https://api.finmindtrade.com/api/v4/data"

    def fetch_stock_institutional(self, stock_id: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        獲取特定個股在過去 N 天之三大法人買賣超統計。
        """
        today = datetime.now()
        start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = today.strftime("%Y-%m-%d")

        url = f"{self.base_url}?dataset=TaiwanStockInstitutionalInvestorsBuySell&data_id={stock_id}&start_date={start_date}&end_date={end_date}"
        req = urllib.request.Request(url, headers=REQUEST_HEADERS)

        try:
            with urllib.request.urlopen(req, context=self.ssl_context, timeout=15) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                data = result.get("data", [])
        except Exception as e:
            print(f"[警告] 獲取 {stock_id} 法人資料失敗: {e}")
            return None

        if not data:
            return None

        # 彙總統計
        foreign_buy = foreign_sell = 0
        trust_buy = trust_sell = 0
        dealer_buy = dealer_sell = 0

        # 計算特定法人連續買超特徵
        daily_trust = {}
        daily_foreign = {}

        for row in data:
            d = row["date"]
            name = row.get("name", "")
            buy = row.get("buy", 0)
            sell = row.get("sell", 0)

            if "Foreign" in name:
                foreign_buy += buy
                foreign_sell += sell
                daily_foreign[d] = daily_foreign.get(d, 0) + (buy - sell)
            elif "Trust" in name:
                trust_buy += buy
                trust_sell += sell
                daily_trust[d] = daily_trust.get(d, 0) + (buy - sell)
            else:
                dealer_buy += buy
                dealer_sell += sell

        foreign_net = (foreign_buy - foreign_sell) // 1000  # 轉為張數
        trust_net = (trust_buy - trust_sell) // 1000
        dealer_net = (dealer_buy - dealer_sell) // 1000
        total_net = foreign_net + trust_net + dealer_net

        # 投信認養天數比率 (買超天數 / 總交易天數)
        trust_trading_days = len(daily_trust)
        trust_positive_days = sum(1 for v in daily_trust.values() if v > 0)
        trust_buy_rate = round((trust_positive_days / trust_trading_days * 100), 1) if trust_trading_days > 0 else 0.0

        # 外資買超天數比率
        foreign_trading_days = len(daily_foreign)
        foreign_positive_days = sum(1 for v in daily_foreign.values() if v > 0)
        foreign_buy_rate = round((foreign_positive_days / foreign_trading_days * 100), 1) if foreign_trading_days > 0 else 0.0

        return {
            "stock_id": stock_id,
            "period_days": days,
            "start_date": start_date,
            "end_date": end_date,
            "trading_days": foreign_trading_days,
            "foreign_net": foreign_net,
            "trust_net": trust_net,
            "dealer_net": dealer_net,
            "total_net": total_net,
            "trust_buy_days": trust_positive_days,
            "trust_buy_rate": trust_buy_rate,
            "foreign_buy_days": foreign_positive_days,
            "foreign_buy_rate": foreign_buy_rate,
        }
