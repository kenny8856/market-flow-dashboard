import sys
import argparse
import csv
import time
from typing import List
from src.db_manager import DatabaseManager
from src.institutional_client import InstitutionalClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 熱門權值與熱門焦點觀察群組
DEFAULT_WATCHLIST = [
    "2330", "2317", "2454", "2308", "2382", "3231", "6669", "2603",
    "2609", "2615", "2881", "2882", "2891", "3008", "3035", "3443",
    "2379", "3037", "8069", "6488", "3529", "3653", "3324", "6531"
]

def scan_stocks(stocks: List[str], days: int = 30, focus: str = "all", min_net: int = 0, export: bool = False):
    db = DatabaseManager()
    client = InstitutionalClient()

    print("=" * 88)
    print(f"【三大法人籌碼追蹤】統計區間: 近 {days} 天 | 篩選焦點: {focus.upper()} | 最低門檻: {min_net} 張")
    print("=" * 88)

    results = []
    total = len(stocks)

    for i, sid in enumerate(stocks, 1):
        stock_info = db.get_stock_info(sid)
        name = stock_info["stock_name"] if stock_info else sid
        print(f"[{i}/{total}] 正在抓取 {sid} {name} 之法人數據...", end="\r", flush=True)

        data = client.fetch_stock_institutional(sid, days=days)
        if data:
            data["stock_name"] = name
            data["market_type"] = stock_info["market_type"] if stock_info else "上市"
            
            # 取得該檔個股之核心地緣券商清單
            geo_brokers = db.get_stock_geo_brokers(sid, level_limit=1)
            data["core_geo_brokers"] = [f"{b['broker_name']}({b['broker_id']})" for b in geo_brokers]
            data["geo_count"] = len(geo_brokers)
            results.append(data)
        time.sleep(0.15)  # 禮貌延遲

    print(" " * 60, end="\r")  # 清除進度字串

    if not results:
        print("[!] 未獲取到任何有效法人數據。")
        return

    # 排序邏輯
    if focus == "trust":
        results.sort(key=lambda x: x["trust_net"], reverse=True)
    elif focus == "foreign":
        results.sort(key=lambda x: x["foreign_net"], reverse=True)
    else:
        results.sort(key=lambda x: x["total_net"], reverse=True)

    # 過濾門檻
    if min_net != 0:
        if focus == "trust":
            results = [r for r in results if r["trust_net"] >= min_net]
        elif focus == "foreign":
            results = [r for r in results if r["foreign_net"] >= min_net]
        else:
            results = [r for r in results if r["total_net"] >= min_net]

    # 輸出表格
    header = f"{'代號':<6} | {'股票名稱':<8} | {'三大法人合計':>10} | {'外資買賣超':>10} | {'投信買賣超':>10} | {'投信買超率':>8} | {'核心地緣券商範例 (Level 1)'}"
    print(header)
    print("-" * 88)

    for r in results:
        geo_str = ", ".join(r["core_geo_brokers"][:3]) + (f" 等{r['geo_count']}家" if r["geo_count"] > 3 else "")
        if not geo_str:
            geo_str = "無"
        print(f"{r['stock_id']:<6} | {r['stock_name']:<8} | {r['total_net']:>10,d}張 | {r['foreign_net']:>10,d}張 | {r['trust_net']:>10,d}張 | {r['trust_buy_rate']:>7.1f}% | {geo_str}")

    print("=" * 88)
    print(f">> 統計完成，符合條件標的共: {len(results)} 檔。")

    if export and results:
        filename = f"institutional_focus_{days}days_{focus}.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["股票代號", "股票名稱", "市場別", "統計天數", "起始日期", "結束日期",
                             "三大法人合計(張)", "外資買賣超(張)", "投信買賣超(張)", "自營商買賣超(張)",
                             "投信買超天數比率(%)", "外資買超天數比率(%)", "核心地緣券商家數", "核心地緣券商清單"])
            for r in results:
                writer.writerow([
                    r["stock_id"], r["stock_name"], r["market_type"], r["period_days"], r["start_date"], r["end_date"],
                    r["total_net"], r["foreign_net"], r["trust_net"], r["dealer_net"],
                    r["trust_buy_rate"], r["foreign_buy_rate"], r["geo_count"], "; ".join(r["core_geo_brokers"])
                ])
        print(f"[匯出成功] 資料已儲存至: {filename}")

def main():
    parser = argparse.ArgumentParser(description="台股近 30 天 / 180 天三大法人關注標的與地緣券商聯動分析工具")
    parser.add_argument("stocks", nargs="*", help="股票代碼或公司名稱（留空則自動掃描常用熱門指標股清單）")
    parser.add_argument("--days", type=int, default=30, choices=[30, 60, 90, 180], help="統計回溯天數 (支援 30, 60, 90, 180 天，預設 30)")
    parser.add_argument("--focus", type=str, default="all", choices=["all", "trust", "foreign"], help="關注篩選主軸: all (三大法人合計), trust (投信認養), foreign (外資波段)")
    parser.add_argument("--min-net", type=int, default=0, help="最低累計淨買超張數門檻 (預設 0 張)")
    parser.add_argument("--export", action="store_true", help="是否匯出為 CSV 報表")

    args = parser.parse_args()
    target_stocks = args.stocks if args.stocks else DEFAULT_WATCHLIST

    scan_stocks(
        stocks=target_stocks,
        days=args.days,
        focus=args.focus,
        min_net=args.min_net,
        export=args.export
    )

if __name__ == "__main__":
    main()
