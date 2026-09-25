"""
Master All-In-One Synchronizer for Taiwan Stock Market Databases
Automatically detects database progress and syncs all 5 market databases to latest:
1. TWSE & TPEx Quotes and Institutional Investors (daily_sync.py)
2. TAIFEX Futures & Stock Futures Large Traders (sync_taifex_history.py --catchup)
3. TPEx Convertible Bonds Quotes & Issuance (sync_cb_history.py --catchup)
4. TWSE & TPEx Stock SBL & SBL Short (sync_sbl_history.py --catchup)
5. TWSE & TPEx Margin Trading & Short-to-Margin Ratio (sync_margin_history.py --catchup)
"""

import sys
import os
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.sync_utils import CUTOFF_RULES, get_sync_cutoff_info


def main():
    print("=" * 90)
    print("  【臺股全市場 7 大核心籌碼資料庫 - 一鍵智慧總同步大師系統】")
    print(f"  啟動時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  適用場景: 出差多日歸來、盤後例行總體更新、自動排程一鍵維護")
    print("=" * 90)

    print("\n[1/5] 當前官方資料發布時程檢驗：")
    now = datetime.now()
    for key, rule in CUTOFF_RULES.items():
        info = get_sync_cutoff_info(key, now)
        status_tag = "[可下載今日]" if info["is_today_included"] else "[防呆跳過今日]"
        print(f"  * {rule['name']:<35} (門檻 {info['cutoff_str']}) -> {status_tag} 終點: {info['target_end_date']}")

    print("\n" + "-" * 90)
    print("開始依序執行各資料庫智慧接續同步...")
    print("-" * 90 + "\n")

    summary_results = []
    total_start = time.time()

    tasks = [
        ("market", "臺股收盤行情與三大法人", "python daily_sync.py"),
        ("taifex", "期貨與個股期大額交易人", "python sync_taifex_history.py --catchup"),
        ("options", "選擇權市場與Put/Call比率", "python sync_options_history.py --catchup"),
        ("cb", "櫃買中心可轉債行情與指標", "python sync_cb_history.py --catchup"),
        ("sbl", "全市場個股借券與借券賣出", "python sync_sbl_history.py --catchup"),
        ("margin", "全市場個股融資融券與券資比", "python sync_margin_history.py --catchup"),
        ("tdcc", "集保戶股權分散表 (每週五)", "python sync_tdcc.py"),
    ]

    for idx, (mkey, mname, cmd) in enumerate(tasks, 1):
        print("=" * 90)
        print(f"  >>> [{idx}/{len(tasks)}] 正在同步：{mname} <<<")
        print("=" * 90)
        t0 = time.time()
        ret = os.system(cmd)
        cost = round(time.time() - t0, 1)
        status = "成功" if ret == 0 else f"失敗({ret})"
        summary_results.append({
            "name": mname,
            "status": status,
            "cost": cost
        })
        print("\n")
        time.sleep(1.0)

    # 智慧校驗與補齊大盤融資維持率與外資期貨留倉摘要
    try:
        from src.macro_chips_updater import auto_sync_missing_summaries
        print("\n" + "=" * 90)
        print("  >>> [8/8] 正在自動核驗與補齊：大盤融資維持率與外資期貨留倉 <<<")
        print("=" * 90)
        auto_sync_missing_summaries()
    except Exception as e:
        print(f"[!] 宏觀籌碼自動補齊異常: {e}")

    total_cost = round(time.time() - total_start, 1)

    print("=" * 90)
    print("  【全市場 5 大核心籌碼資料庫總同步 - 執行結果報告】")
    print("=" * 90)
    print(f"{'編號':<4} {'資料庫名稱':<35} {'狀態':<10} {'耗時(秒)':>10}")
    print("-" * 90)
    for idx, r in enumerate(summary_results, 1):
        print(f"[{idx}]  {r['name']:<35} {r['status']:<10} {r['cost']:>10.1f}s")
    print("-" * 90)
    print(f"全流程總執行時間: {total_cost} 秒")
    print("=" * 90)


if __name__ == "__main__":
    main()
