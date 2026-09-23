"""
TD Sequential 9 (九轉序列) 與 TD Countdown 13 (13不連續序列) 演算法引擎
================================================================================
依據經典 Tom DeMark TD 指標體系實現：
1. TD Setup (九轉結構):
   - 買入九轉 (Buy Setup 9): 連續 9 日 Close[t] < Close[t-4]
   - 賣出九轉 (Sell Setup 9): 連續 9 日 Close[t] > Close[t-4]
2. TD Countdown (13不連續計數):
   - 買入 13 (Buy Countdown 13): 九轉成立後，當 Close[t] <= Low[t-2] 累計滿 13 次 (不需連續)
   - 賣出 13 (Sell Countdown 13): 九轉成立後，當 Close[t] >= High[t-2] 累計滿 13 次 (不需連續)
================================================================================
"""

from typing import List, Dict, Any


def calculate_td_sequential(quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    計算給定 K 線序列的九轉序列與 13 不連續計數
    quotes: 包含 date, open, high, low, close, volume 的 dict list (依日期升冪排序)
    回傳擴充後帶有 td 指標欄位的 list
    """
    n = len(quotes)
    if n == 0:
        return []

    results = []
    for q in quotes:
        results.append({
            'date': q['date'],
            'open': float(q['open']),
            'high': float(q['high']),
            'low': float(q['low']),
            'close': float(q['close']),
            'volume': float(q.get('volume', 0)),
            'buy_setup': 0,
            'sell_setup': 0,
            'buy_countdown': 0,
            'sell_countdown': 0,
            'td_signal': None,  # 'BUY_9', 'SELL_9', 'BUY_13', 'SELL_13'
            'td_label': None,
            'td_color': None
        })

    # 1. 計算 TD Setup 9 (九轉序列)
    curr_buy_setup = 0
    curr_sell_setup = 0

    for i in range(n):
        if i >= 4:
            c = results[i]['close']
            c_prev4 = results[i - 4]['close']

            # 買入結構檢查: Close[i] < Close[i-4]
            if c < c_prev4:
                curr_buy_setup += 1
                curr_sell_setup = 0
                if curr_buy_setup > 9:
                    curr_buy_setup = 1  # 滿9後重啟新循環
            # 賣出結構檢查: Close[i] > Close[i-4]
            elif c > c_prev4:
                curr_sell_setup += 1
                curr_buy_setup = 0
                if curr_sell_setup > 9:
                    curr_sell_setup = 1
            else:
                curr_buy_setup = 0
                curr_sell_setup = 0
        else:
            curr_buy_setup = 0
            curr_sell_setup = 0

        results[i]['buy_setup'] = curr_buy_setup
        results[i]['sell_setup'] = curr_sell_setup

    # 2. 計算 TD Countdown 13 (13不連續計數)
    # 九轉完成後啟動 Countdown 倒數，直到計數滿 13 或被反向 Setup 打斷
    in_buy_countdown = False
    buy_cd_count = 0

    in_sell_countdown = False
    sell_cd_count = 0

    for i in range(n):
        # 觸發買入 Setup 9 完成
        if results[i]['buy_setup'] == 9:
            in_buy_countdown = True
            buy_cd_count = 0
            in_sell_countdown = False  # 反向中止
            results[i]['td_signal'] = 'BUY_9'
            results[i]['td_label'] = '買9'
            results[i]['td_color'] = '#10b981'  # 綠色買點

        # 觸發賣出 Setup 9 完成
        elif results[i]['sell_setup'] == 9:
            in_sell_countdown = True
            sell_cd_count = 0
            in_buy_countdown = False
            results[i]['td_signal'] = 'SELL_9'
            results[i]['td_label'] = '賣9'
            results[i]['td_color'] = '#ef4444'  # 紅色賣點

        # 進行 Countdown 13 計數 (需依賴前第 2 根 K 棒)
        if i >= 2:
            c = results[i]['close']

            # 買入 13: Close[i] <= Low[i-2] (不連續累加)
            if in_buy_countdown:
                low_prev2 = results[i - 2]['low']
                if c <= low_prev2:
                    buy_cd_count += 1
                    results[i]['buy_countdown'] = buy_cd_count
                    if buy_cd_count == 13:
                        results[i]['td_signal'] = 'BUY_13'
                        results[i]['td_label'] = '買13'
                        results[i]['td_color'] = '#059669'  # 強化買訊
                        in_buy_countdown = False  # 完成倒數
                else:
                    results[i]['buy_countdown'] = buy_cd_count

            # 賣出 13: Close[i] >= High[i-2] (不連續累加)
            if in_sell_countdown:
                high_prev2 = results[i - 2]['high']
                if c >= high_prev2:
                    sell_cd_count += 1
                    results[i]['sell_countdown'] = sell_cd_count
                    if sell_cd_count == 13:
                        results[i]['td_signal'] = 'SELL_13'
                        results[i]['td_label'] = '賣13'
                        results[i]['td_color'] = '#dc2626'  # 強化賣訊
                        in_sell_countdown = False  # 完成倒數
                else:
                    results[i]['sell_countdown'] = sell_cd_count

    return results


def get_current_td_summary(td_quotes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    取得最新一根 K 棒的 TD 序列診斷狀態與意義摘要
    """
    if not td_quotes:
        return {
            'status': '無數據',
            'detail': '尚無足夠 K 棒數據計算九轉序列',
            'badge_class': 'badge-neutral'
        }

    latest = td_quotes[-1]
    b_setup = latest['buy_setup']
    s_setup = latest['sell_setup']
    b_cd = latest['buy_countdown']
    s_cd = latest['sell_countdown']

    # 檢查最近 5 根是否有重大觸發
    recent_signal = None
    recent_date = None
    for q in reversed(td_quotes[-5:]):
        if q['td_signal']:
            recent_signal = q['td_signal']
            recent_date = q['date']
            break

    if recent_signal == 'BUY_13':
        return {
            'status': '觸發【買入 13 序列】終極轉折',
            'detail': f'於 {recent_date} 觸發 TD Countdown 13 買點，空頭趨勢力竭訊號確立，高勝率右側反轉區間。',
            'badge_class': 'badge-bull',
            'highlight': True
        }
    elif recent_signal == 'SELL_13':
        return {
            'status': '觸發【賣出 13 序列】終極力竭',
            'detail': f'於 {recent_date} 觸發 TD Countdown 13 賣點，多頭波段拉升超買頂背離，高度防範波段拉回。',
            'badge_class': 'badge-bear',
            'highlight': True
        }
    elif recent_signal == 'BUY_9':
        return {
            'status': '觸發【買九轉折】(Buy Setup 9)',
            'detail': f'於 {recent_date} 形成連續 9 日低於 4 日前收盤，空頭動能衰竭，目前正往 13 不連續計數推進中。',
            'badge_class': 'badge-bull',
            'highlight': True
        }
    elif recent_signal == 'SELL_9':
        return {
            'status': '觸發【賣九高檔】(Sell Setup 9)',
            'detail': f'於 {recent_date} 形成連續 9 日高於 4 日前收盤，短線過熱轉折點，目前正往 13 不連續計數推進中。',
            'badge_class': 'badge-bear',
            'highlight': True
        }

    # 進行中的計數
    if s_cd > 0:
        return {
            'status': f'賣出 13 倒數中 (第 {s_cd}/13 步)',
            'detail': f'賣九已成立，目前多頭持續創新高累計第 {s_cd} 根 (滿足 Close >= High[t-2])，逼近頂部力竭區。',
            'badge_class': 'badge-neutral',
            'highlight': False
        }
    elif b_cd > 0:
        return {
            'status': f'買入 13 倒數中 (第 {b_cd}/13 步)',
            'detail': f'買九已成立，目前弱勢盤跌累計第 {b_cd} 根 (滿足 Close <= Low[t-2])，逼近底部轉折區。',
            'badge_class': 'badge-neutral',
            'highlight': False
        }
    elif s_setup > 0:
        return {
            'status': f'賣出九轉推進中 (第 {s_setup}/9 天)',
            'detail': f'連續 {s_setup} 個交易日收盤價高於 4 天前收盤價，多頭趨勢延續中。',
            'badge_class': 'badge-bull',
            'highlight': False
        }
    elif b_setup > 0:
        return {
            'status': f'買入九轉推進中 (第 {b_setup}/9 天)',
            'detail': f'連續 {b_setup} 個交易日收盤價低於 4 天前收盤價，空方修正延續中。',
            'badge_class': 'badge-bear',
            'highlight': False
        }
    else:
        return {
            'status': '區間震盪整理 (九轉計數未滿)',
            'detail': '價格在 4 日均線上下震盪，尚未形成單向連續性 9 轉趨勢。',
            'badge_class': 'badge-neutral',
            'highlight': False
        }
