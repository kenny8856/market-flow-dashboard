import time
from datetime import datetime
from src.twse_tpex_client import OfficialDataClient
from src.geo_engine import GeoEngine
from src.db_manager import DatabaseManager

def run_weekly_sync():
    print("=" * 70)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 開始執行台股關鍵地緣券商每週資料庫同步作業")
    print("=" * 70)
    start_time = time.time()

    client = OfficialDataClient()
    db = DatabaseManager()

    # 1. 抓取上市與上櫃公司
    listed_stocks = client.get_listed_companies()
    otc_stocks = client.get_otc_companies()
    all_stocks = listed_stocks + otc_stocks
    print(f">> 全市場公司總計: {len(all_stocks)} 家")

    # 2. 抓取券商分公司與總公司名冊
    branches = client.get_broker_branches()
    hqs = client.get_broker_headquarters()
    all_brokers = branches + hqs
    print(f">> 全市場證券商營業據點總計: {len(all_brokers)} 家")

    # 3. 解析地址地理資訊
    print("\n[5/6] 正在進行地理空間與行政區地址解析 (Geo-Parsing)...")
    for s in all_stocks:
        geo = GeoEngine.parse_address(s["address"])
        s["city"] = geo["city"]
        s["district"] = geo["district"]
        s["park"] = geo["park"]

    for b in all_brokers:
        geo = GeoEngine.parse_address(b["address"])
        b["city"] = geo["city"]
        b["district"] = geo["district"]
        b["park"] = geo["park"]

    # 4. 寫入基本資料表
    print("\n[6/6] 正在將公司與券商分點寫入本地 SQLite 資料庫...")
    db.upsert_stocks(all_stocks)
    db.upsert_brokers(all_brokers)

    # 5. 執行地緣關聯匹配引擎
    print("\n[7/7] 正在運算每檔個股之地緣券商關聯矩陣...")
    geo_relations = []
    core_count = 0

    for s in all_stocks:
        s_geo = {"city": s["city"], "district": s["district"], "park": s["park"]}
        for b in all_brokers:
            b_geo = {"city": b["city"], "district": b["district"], "park": b["park"]}
            eval_res = GeoEngine.evaluate_geo_relation(s_geo, b_geo, b["broker_name"])
            if eval_res:
                geo_level, match_reason = eval_res
                if geo_level == 1:
                    core_count += 1
                geo_relations.append({
                    "stock_id": s["stock_id"],
                    "stock_name": s["stock_name"],
                    "broker_id": b["broker_id"],
                    "broker_name": b["broker_name"],
                    "geo_level": geo_level,
                    "match_reason": match_reason,
                    "company_address": s["address"],
                    "broker_address": b["address"]
                })

    print(f"      -> 運算完成！匹配出地緣關聯 {len(geo_relations)} 筆（其中核心 Level 1 地緣券商 {core_count} 筆）")

    # 6. 重構關聯資料表
    db.rebuild_geo_relations(geo_relations)

    duration = round(time.time() - start_time, 2)
    db.record_sync_log(
        stocks_count=len(all_stocks),
        brokers_count=len(all_brokers),
        geo_count=len(geo_relations),
        status="SUCCESS",
        duration_sec=duration
    )

    stats = db.get_summary_stats()
    print("\n" + "=" * 70)
    print("【每週同步作業完成報告】")
    print(f"  * 耗費時間: {duration} 秒")
    print(f"  * 上市/上櫃公司總數: {stats['stocks_count']} 檔")
    print(f"  * 券商營業分點總數: {stats['brokers_count']} 家")
    print(f"  * 核心地緣券商關聯 (Level 1): {stats['core_geo_relations_count']} 筆")
    print(f"  * 總地緣關聯數: {stats['geo_relations_count']} 筆")
    print(f"  * 資料庫檔案: {db.db_path}")
    print("=" * 70)

if __name__ == "__main__":
    run_weekly_sync()
