"""
Centralized Data Cutoff Schedule and Smart Catch-up Utilities
for Taiwan Stock Market, Futures, CB, SBL, and Margin Trading Databases.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

CUTOFF_RULES: Dict[str, Dict[str, Any]] = {
    "market": {
        "name": "臺股收盤行情與三大法人 (TWSE/TPEx)",
        "hour": 15,
        "minute": 30,
        "desc": "每日約 15:00~15:30 證交所與櫃買中心公布三大法人買賣超與完整行情。"
    },
    "taifex": {
        "name": "期交所期貨與個股期大額交易人 (TAIFEX)",
        "hour": 15,
        "minute": 30,
        "desc": "每日約 15:00~15:30 期交所公布大額交易人未沖銷部位結構表。"
    },
    "cb": {
        "name": "櫃買中心可轉債 (CB) 行情與發行 (TPEx)",
        "hour": 16,
        "minute": 0,
        "desc": "每日約 15:30~16:00 櫃買中心完成可轉債收盤價與標的股票折溢價結算。"
    },
    "sbl": {
        "name": "全市場個股借券與借券賣出 (SBL)",
        "hour": 20,
        "minute": 30,
        "desc": "每日約 20:00~20:30 證交所與櫃買中心公布借券總餘額與借券賣出管制表。"
    },
    "margin": {
        "name": "全市場個股融資融券 (Margin Trading)",
        "hour": 21,
        "minute": 30,
        "desc": "每日約 21:00~21:30 券商申報統整，雙交易所正式公布融資融券彙總。"
    },
    "options": {
        "name": "期交所選擇權市場與 Put/Call Ratio (TAIFEX)",
        "hour": 15,
        "minute": 30,
        "desc": "每日約 15:00~15:30 期交所公布選擇權交易行情與 Put/Call Ratio。"
    },
    "tdcc": {
        "name": "集保戶股權分散表 (TDCC)",
        "hour": 19,
        "minute": 0,
        "desc": "每週五約 18:30~19:00 集保中心公布當週股權分散級距表。"
    }
}


def get_sync_cutoff_info(module_key: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    依據當前時間與官方公布時間，精確判定今日資料是否已可下載，並提供目標終點日期與說明。
    """
    if now is None:
        now = datetime.now()

    rule = CUTOFF_RULES.get(module_key, {
        "name": module_key,
        "hour": 16,
        "minute": 0,
        "desc": "每日盤後公布"
    })

    cutoff_str = f"{rule['hour']:02d}:{rule['minute']:02d}"
    today_date = now.date()
    weekday = now.weekday()

    if weekday == 5:
        target_end_dt = today_date - timedelta(days=1)
        is_today = False
        desc = f"今日為週六 (非交易日)，系統自動將同步終點設為昨日週五 ({target_end_dt.strftime('%Y-%m-%d')})。"
    elif weekday == 6:
        target_end_dt = today_date - timedelta(days=2)
        is_today = False
        desc = f"今日為週日 (非交易日)，系統自動將同步終點設為前週五 ({target_end_dt.strftime('%Y-%m-%d')})。"
    else:
        cutoff_passed = (now.hour, now.minute) >= (rule["hour"], rule["minute"])
        if cutoff_passed:
            target_end_dt = today_date
            is_today = True
            desc = f"當前時間 ({now.strftime('%H:%M')}) 已過官方公布時間 ({cutoff_str})，同步範圍包含今日 ({target_end_dt.strftime('%Y-%m-%d')})。"
        else:
            if weekday == 0:
                target_end_dt = today_date - timedelta(days=3)
            else:
                target_end_dt = today_date - timedelta(days=1)
            is_today = False
            desc = f"當前時間 ({now.strftime('%H:%M')}) 尚未超過官方公布時間 ({cutoff_str})，為防抓取空資料，系統已自動排除今日，終點設為前一營業日 ({target_end_dt.strftime('%Y-%m-%d')})。"

    return {
        "module_name": rule["name"],
        "cutoff_str": cutoff_str,
        "is_today_included": is_today,
        "target_end_date": target_end_dt.strftime("%Y-%m-%d"),
        "status_desc": desc,
        "schedule_desc": rule["desc"]
    }


def print_cutoff_banner(module_key: str, now: Optional[datetime] = None):
    """印出該模組的時間防呆說明橫幅"""
    info = get_sync_cutoff_info(module_key, now)
    print("=" * 85)
    print(f"  【官方資料公布時程與防呆機制備註】")
    print(f"  * 資料項目: {info['module_name']}")
    print(f"  * 官方公布: 營業日 {info['cutoff_str']} 之後  ({info['schedule_desc']})")
    print(f"  * 判定結果: {info['status_desc']}")
    print("=" * 85 + "\n")


def get_smart_catchup_range(
    module_key: str,
    latest_db_date: Optional[str],
    default_start: str = "2020-01-01",
    now: Optional[datetime] = None
) -> Tuple[str, str, bool, str]:
    """
    智慧出差接續補齊範圍計算器：
    自動根據資料庫最後收錄日期與官方發布時程，計算精確的 (start_date, end_date, needs_sync, message)。
    """
    info = get_sync_cutoff_info(module_key, now)
    target_end = info["target_end_date"]

    if not latest_db_date:
        return default_start, target_end, True, f"資料庫尚無收錄記錄，將自起始日 {default_start} 全量同步至 {target_end}"

    latest_dt = datetime.strptime(latest_db_date, "%Y-%m-%d").date()
    target_end_dt = datetime.strptime(target_end, "%Y-%m-%d").date()

    if latest_dt >= target_end_dt:
        msg = f"資料庫已是最新狀態 (已完整收錄至 {latest_db_date})，無需進行更新。"
        return latest_db_date, target_end, False, msg

    msg = f"偵測到資料庫目前收錄至 {latest_db_date}，將自動接續補齊至最新可用交易日 {target_end}。"
    return latest_db_date, target_end, True, msg
