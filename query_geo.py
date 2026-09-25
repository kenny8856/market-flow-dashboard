import sys
import argparse
import csv
from pathlib import Path
from src.db_manager import DatabaseManager

# 修正 Windows 控制台輸出編碼
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def query_single_stock(db: DatabaseManager, keyword: str, level: int = 1, export_csv: bool = False):
    conn = db.get_connection()
    cursor = conn.cursor()

    # 支援股票代碼或公司名稱搜尋
    cursor.execute("""
    SELECT stock_id, stock_name, market_type, industry, address, city, district, park, tel
    FROM stocks
    WHERE stock_id = ? OR stock_name LIKE ?;
    """, (keyword, f"%{keyword}%"))
    stock = cursor.fetchone()

    if not stock:
        print(f"\n[!] 查無此股票：{keyword}，請確認股票代碼或名稱是否正確。")
        return

    stock_id = stock["stock_id"]
    stock_name = stock["stock_name"]
    print("\n" + "=" * 78)
    print(f"【個股檔案】 {stock_id} {stock_name}  [{stock['market_type']}]")
    print(f"  * 產業類別: {stock['industry']}")
    print(f"  * 公司地址: {stock['address']}")
    print(f"  * 歸屬區域: 縣市【{stock['city'] or '未載明'}】 / 行政區【{stock['district'] or '未載明'}】" + (f" / 園區【{stock['park']}】" if stock['park'] else ""))
    if stock['tel']:
        print(f"  * 連絡電話: {stock['tel']}")
    print("-" * 78)

    brokers = db.get_stock_geo_brokers(stock_id, level_limit=level)
    core_brokers = [b for b in brokers if b["geo_level"] == 1]
    regional_brokers = [b for b in brokers if b["geo_level"] == 2]

    print(f"【關鍵地緣券商列表】（共找到 {len(brokers)} 家，其中核心地緣 Level 1: {len(core_brokers)} 家）")
    if not brokers:
        print("  暫無符合之地緣券商記錄。")
    else:
        print(f"{'代號':<6} | {'券商分點名稱':<16} | {'地緣等級':<8} | {'判定理由':<30} | {'營業地址'}")
        print("-" * 78)
        for b in brokers:
            level_str = "Level 1 (核心)" if b["geo_level"] == 1 else "Level 2 (生活圈)"
            print(f"{b['broker_id']:<6} | {b['broker_name']:<16} | {level_str:<10} | {b['match_reason']:<30} | {b['broker_address']}")

    print("=" * 78)

    # 匯出 CSV
    if export_csv and brokers:
        filename = f"geo_brokers_{stock_id}_{stock_name}.csv"
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["股票代號", "股票名稱", "券商代號", "券商分點名稱", "地緣等級", "判定理由", "公司地址", "券商營業地址"])
            for b in brokers:
                writer.writerow([stock_id, stock_name, b["broker_id"], b["broker_name"],
                                 b["geo_level"], b["match_reason"], b["company_address"], b["broker_address"]])
        print(f"[匯出成功] 已儲存至檔案: {filename}")

def main():
    parser = argparse.ArgumentParser(description="台股個股關鍵地緣券商資料庫查詢工具")
    parser.add_argument("stocks", nargs="*", help="股票代碼或公司簡稱（支援多檔批次查詢，例如 2330 2317 2454）")
    parser.add_argument("--level", type=int, default=1, choices=[1, 2], help="地緣等級上限 (1: 僅核心地緣, 2: 包含同縣市生活圈，預設 1)")
    parser.add_argument("--export", action="store_true", help="是否將查詢結果匯出為 CSV 檔")
    parser.add_argument("--stats", action="store_true", help="顯示資料庫當前收錄統計資訊")

    args = parser.parse_args()
    db = DatabaseManager()

    if args.stats or not args.stocks:
        stats = db.get_summary_stats()
        print("=" * 60)
        print("【台股地緣券商資料庫目前狀態】")
        print(f"  * 上市/上櫃公司總數: {stats['stocks_count']} 檔")
        print(f"  * 營業券商分點總數: {stats['brokers_count']} 家")
        print(f"  * 核心地緣券商關聯 (Level 1): {stats['core_geo_relations_count']} 筆")
        print(f"  * 總地緣關聯數: {stats['geo_relations_count']} 筆")
        print(f"  * 最近同步更新時間: {stats['last_sync_time']}")
        print("=" * 60)
        if not args.stocks:
            print("\n使用說明: python query_geo.py <股票代號或簡稱> [--level 1|2] [--export]")
            print("範例: python query_geo.py 2330")
            print("範例: python query_geo.py 2317 2454 --level 2 --export")
            return

    for target in args.stocks:
        query_single_stock(db, target, level=args.level, export_csv=args.export)

if __name__ == "__main__":
    main()
