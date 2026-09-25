import os
import sys
import argparse
import csv
from datetime import datetime
from typing import Optional, List, Dict, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.taifex_db import TaifexLargeTraderDB

KNOWN_SHORTCUTS = {
    "台指": "TX", "台指期": "TX", "臺股期貨": "TX", "大台": "TX",
    "小台": "MTX", "小台指": "MTX", "小型台指": "MTX",
    "微台": "TMF", "微型台指": "TMF",
    "電子": "TE", "電子期": "TE", "電子期貨": "TE",
    "小電子": "ZEF", "小型電子": "ZEF",
    "金融": "TF", "金融期": "TF", "金融期貨": "TF",
    "小金融": "ZFF", "小型金融": "ZFF",
    "台積電": "CD", "台積期": "CD", "台積電期貨": "CD",
    "鴻海": "DH", "鴻海期": "DH", "鴻海期貨": "DH",
    "聯發科": "DV", "發哥": "DV", "聯發科期貨": "DV",
    "聯電": "CC", "聯電期": "CC", "聯電期貨": "CC",
    "長榮": "CZ", "長榮期": "CZ", "長榮期貨": "CZ",
    "陽明": "DA", "陽明期": "DA", "陽明期貨": "DA",
    "中砂": "EO", "中砂期": "EO", "中砂期貨": "EO",
    "緯創": "DX", "緯創期": "DX", "緯創期貨": "DX",
    "廣達": "DK", "廣達期": "DK", "廣達期貨": "DK",
}

def format_signed(val: int) -> str:
    """格式化帶有正負號與千分位的數值"""
    if val > 0:
        return f"+{val:,}"
    elif val < 0:
        return f"{val:,}"
    return "0"

def show_stats(db: TaifexLargeTraderDB):
    earliest = db.get_earliest_date()
    latest = db.get_latest_date()
    day_count = db.get_date_count()
    all_c = db.get_all_contracts()

    print("================================================================================")
    print("  [期交所大額交易人未沖銷部位結構資料庫 - 狀態統計]")
    print(f"  資料庫檔案: {db.db_path}")
    print(f"  涵蓋交易日數: {day_count} 天")
    print(f"  最早交易日期: {earliest or '無資料'}")
    print(f"  最新交易日期: {latest or '無資料'}")
    print(f"  收錄商品總數: {len(all_c)} 檔期貨與個股期貨")
    print("  契約結構: 當月契約、所有契約、遠月契約 (公式: 所有-當月)、週契約")
    print("================================================================================")

def list_contracts(db: TaifexLargeTraderDB, filter_kw: Optional[str] = None):
    all_c = db.search_contracts(filter_kw) if filter_kw else db.get_all_contracts()
    if not all_c:
        print(f"查無符合 '{filter_kw}' 之商品。" if filter_kw else "資料庫中尚無任何商品資料。")
        return

    print("================================================================================")
    print(f"  [期交所商品清單] 共 {len(all_c)} 檔商品" + (f" (關鍵字: '{filter_kw}')" if filter_kw else ""))
    print("================================================================================")
    print(f"{'代碼':<8s} {'商品簡稱':<24s} {'收錄天數':<10s} {'最新交易日':<12s}")
    print("-" * 60)
    for c in all_c:
        print(f"{c['contract_code']:<8s} {c['contract_name']:<24s} {c['days']:<10d} {c['latest_date']:<12s}")

def resolve_contract(db: TaifexLargeTraderDB, user_input: str) -> Optional[tuple]:
    """解析使用者輸入的代碼或名稱，回傳 (code, name)"""
    target = user_input.strip()
    if target in KNOWN_SHORTCUTS:
        target = KNOWN_SHORTCUTS[target]

    # 1. 嘗試完全比對代碼 (大寫)
    code_matches = db.search_contracts(target.upper())
    for m in code_matches:
        if m["contract_code"].upper() == target.upper():
            return m["contract_code"], m["contract_name"]

    # 2. 嘗試搜尋名稱或代碼
    matches = db.search_contracts(target)
    if len(matches) == 1:
        return matches[0]["contract_code"], matches[0]["contract_name"]
    elif len(matches) > 1:
        # 尋找完全比對名稱者
        for m in matches:
            if m["contract_name"] == target or m["contract_name"] == f"{target}期貨":
                return m["contract_code"], m["contract_name"]
        # 無完全比對時提示候選商品
        print(f"[!] 找到多個相符商品，請指定具體代碼：")
        for m in matches[:10]:
            print(f"  - {m['contract_code']}: {m['contract_name']}")
        return matches[0]["contract_code"], matches[0]["contract_name"]

    return None

def run_query(args):
    db = TaifexLargeTraderDB()

    if args.stats:
        show_stats(db)
        return

    if args.list:
        list_contracts(db, args.contract)
        return

    raw_target = args.contract.strip() if args.contract else "TX"
    res = resolve_contract(db, raw_target)
    if not res:
        print(f"[!] 找不到商品: '{raw_target}'。您可以使用 'python query_taifex_trader.py --list' 檢視所有可用商品清單。")
        return

    code, contract_name = res
    type_filter = args.type if args.type and args.type != "all" else None

    # 日期範圍過濾
    start_date = args.start
    end_date = args.end

    if not start_date and not end_date:
        with db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT date FROM futures_large_traders 
                WHERE contract_code = ? 
                ORDER BY date DESC LIMIT ?
            """, (code, args.days))
            dates = [r[0] for r in cursor.fetchall()]
        if not dates:
            print(f"[!] 資料庫中尚無 {contract_name} ({code}) 之紀錄。請先執行 'python sync_taifex_history.py' 同步資料。")
            return
        start_date = dates[-1]
        end_date = dates[0]

    records = db.get_records(
        contract_code=code,
        contract_type=type_filter,
        start_date=start_date,
        end_date=end_date,
        order_desc=True
    )

    if not records:
        print(f"[!] 查無符合條件之資料 (商品: {contract_name} [{code}], 區間: {start_date} ~ {end_date})")
        return

    print("========================================================================================================================")
    print(f"  [期交所大額交易人未沖銷部位結構表] - {contract_name} ({code})")
    print(f"  查詢區間: {start_date} ~ {end_date} (共 {len(records)} 筆合約明細)")
    print("========================================================================================================================")
    
    header_fmt = "{:<10} {:<6} {:>10} {:>10} | {:>10} {:>10} | {:>10} {:>10} | {:>10}"
    print(header_fmt.format(
        "日期", "契約", "買前五(特法)", "賣前五(特法)", "前五淨(特法)", "買前十(特法)", "賣前十(特法)", "前十淨(特法)", "市場OI"
    ))
    print("-" * 120)

    for r in records:
        c_type = r["contract_type"]
        b5_str = f"{r['buy_top5']:,}({r['buy_top5_spec']:,})"
        s5_str = f"{r['sell_top5']:,}({r['sell_top5_spec']:,})"
        n5_str = f"{format_signed(r['net_top5'])}({format_signed(r['net_top5_spec'])})"

        b10_str = f"{r['buy_top10']:,}({r['buy_top10_spec']:,})"
        s10_str = f"{r['sell_top10']:,}({r['sell_top10_spec']:,})"
        n10_str = f"{format_signed(r['net_top10'])}({format_signed(r['net_top10_spec'])})"

        oi_str = f"{r['market_oi']:,}"

        print(header_fmt.format(
            r["date"], c_type, b5_str, s5_str, n5_str, b10_str, s10_str, n10_str, oi_str
        ))

    print("========================================================================================================================")
    print("說明: (特法) 表示前述部位中『特定法人』合計口數。淨部位 = 買方口數 - 賣方口數。")
    print("      遠月契約 = 所有契約 - 當月契約 (自動依期交所部位相減推算)。")

    if args.export:
        filename = f"taifex_{code}_{start_date}_{end_date}.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)
        print(f"[√] 查詢結果已匯出至 CSV: {os.path.abspath(filename)}")

def main():
    parser = argparse.ArgumentParser(description="期交所大額交易人未沖銷部位籌碼查詢工具 (支援全市場商品與個股期貨)")
    parser.add_argument("contract", nargs="?", default="TX", help="商品名稱或代碼 (如 TX, TE, CD, 台積電, 鴻海, 聯發科)")
    parser.add_argument("--type", choices=["當月", "遠月", "所有契約", "週契約", "all"], default="all", help="契約種類過濾")
    parser.add_argument("--days", type=int, default=5, help="查詢最近 N 個開盤日 (預設 5 天)")
    parser.add_argument("--start", type=str, help="起始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="結束日期 (YYYY-MM-DD)")
    parser.add_argument("--stats", action="store_true", help="顯示資料庫狀態統計資訊")
    parser.add_argument("--list", action="store_true", help="列出資料庫收錄之所有期貨商品清單")
    parser.add_argument("--export", action="store_true", help="匯出查詢結果至 CSV 檔案")

    args = parser.parse_args()
    run_query(args)

if __name__ == "__main__":
    main()
