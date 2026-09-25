"""
個股專屬量化分析頁面生成器 (Stock Detail Page Generator)
================================================================================
功能說明：
1. 查詢個股歷史日 K 線 (OHLCV)
2. 計算經典 Tom DeMark TD Sequential 9 (九轉序列) 與 TD Countdown 13 (13不連續計數)
3. 統計每日個股關聯權證之認購、認售成交金額走勢 (Warrant Money Flow)
4. 生成現代化金融交互儀表板 HTML (包含 TradingView 級互動 K 線圖、九轉標籤、成交量、權證資金流副圖與小哥推薦權證)
5. 同步輸出至根目錄與 docs/ 目錄供 GitHub Pages 點擊跳轉
================================================================================
"""

import os
import json
import sqlite3
import datetime
from typing import Dict, Any, List, Optional
from src.td_indicator import calculate_td_sequential, get_current_td_summary


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DOCS_DIR = os.path.join(ROOT_DIR, "docs")


class StockPageGenerator:
    def __init__(self, twse_db_path="db/twse_market.db", tpex_db_path="db/tpex_market.db"):
        self.twse_db = os.path.join(ROOT_DIR, twse_db_path)
        self.tpex_db = os.path.join(ROOT_DIR, tpex_db_path)

    def fetch_stock_quotes_and_warrants(self, stock_id: str, market_type: str = "TWSE") -> Dict[str, Any]:
        """
        從資料庫查詢個股完整歷史 K 線與每日權證資金流數據
        """
        db_path = self.tpex_db if "TPEX" in market_type.upper() or "OTC" in market_type.upper() else self.twse_db
        if not os.path.exists(db_path):
            db_path = self.twse_db  # fallback

        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # 1. 查詢日 K 線 (過濾 2025-01-01 至今連續有效歷史)
        c.execute("""
            SELECT date, open_price, high_price, low_price, close_price, volume_lots, amount
            FROM daily_quotes
            WHERE stock_id = ? AND close_price > 0 AND date >= '2025-01-01'
            ORDER BY date ASC
        """, (stock_id,))
        raw_quotes = c.fetchall()

        # 2. 查詢該股每日認購/認售權證成交額 (加權指數的標的代號為 IX0001)
        underlying_param = 'IX0001' if stock_id == 'TAIEX' else stock_id
        c.execute("""
            SELECT date,
                   SUM(CASE WHEN warrant_id NOT LIKE '%P' AND warrant_name NOT LIKE '%售%' AND warrant_name NOT LIKE '%熊%' THEN trade_amount ELSE 0 END) as call_amt,
                   SUM(CASE WHEN warrant_id LIKE '%P' OR warrant_name LIKE '%售%' OR warrant_name LIKE '%熊%' THEN trade_amount ELSE 0 END) as put_amt
            FROM daily_warrants
            WHERE underlying_stock_id = ? AND date >= '2025-01-01'
            GROUP BY date
            ORDER BY date ASC
        """, (underlying_param,))
        raw_warrants = c.fetchall()

        # 3. 查詢該股每日外資與投信買賣超 (股數與張數)
        c.execute("""
            SELECT date, foreign_net, trust_net, foreign_net_lots, trust_net_lots
            FROM daily_institutional
            WHERE stock_id = ? AND date >= '2025-01-01'
            ORDER BY date ASC
        """, (stock_id,))
        raw_inst = c.fetchall()
        conn.close()

        inst_map = {}
        for r in raw_inst:
            inst_map[r[0]] = {
                'foreign_net_shares': float(r[1] or 0),
                'trust_net_shares': float(r[2] or 0),
                'foreign_net_lots': float(r[3] or 0),
                'trust_net_lots': float(r[4] or 0)
            }

        warrant_map = {}
        for r in raw_warrants:
            w_date, c_amt, p_amt = r[0], float(r[1] or 0), float(r[2] or 0)
            total = c_amt + p_amt
            c_ratio = (c_amt / total * 100.0) if total > 0 else 0.0
            p_ratio = (p_amt / total * 100.0) if total > 0 else 0.0
            net_amt = c_amt - p_amt
            warrant_map[w_date] = {
                'call_amt': c_amt,
                'put_amt': p_amt,
                'total_amt': total,
                'call_amt_wan': round(c_amt / 10000.0, 1),
                'put_amt_wan': round(p_amt / 10000.0, 1),
                'net_amt_wan': round(net_amt / 10000.0, 1),
                'call_ratio': round(c_ratio, 1),
                'put_ratio': round(p_ratio, 1)
            }

        quotes_list = []
        for r in raw_quotes:
            q_date = r[0]
            close_p = float(r[4])
            w_info = warrant_map.get(q_date, {
                'call_amt': 0, 'put_amt': 0, 'total_amt': 0,
                'call_amt_wan': 0, 'put_amt_wan': 0, 'net_amt_wan': 0,
                'call_ratio': 0, 'put_ratio': 0
            })
            inst_info = inst_map.get(q_date, {
                'foreign_net_shares': 0, 'trust_net_shares': 0,
                'foreign_net_lots': 0, 'trust_net_lots': 0
            })
            # 計算多空金額
            if stock_id in ['TAIEX', 'TPEx']:
                # 指數的大盤金額已經在資料庫中是「元」，我們除以一億換算成「億元」
                inst_info['foreign_amt_wan'] = round(inst_info['foreign_net_shares'] / 100000000.0, 1)
                inst_info['trust_amt_wan'] = round(inst_info['trust_net_shares'] / 100000000.0, 1)
            else:
                # 個股: 淨買賣股數 * 當日收盤價 / 10000 = 萬元
                inst_info['foreign_amt_wan'] = round((inst_info['foreign_net_shares'] * close_p) / 10000.0, 1)
                inst_info['trust_amt_wan'] = round((inst_info['trust_net_shares'] * close_p) / 10000.0, 1)

            quotes_list.append({
                'date': q_date,
                'open': float(r[1]),
                'high': float(r[2]),
                'low': float(r[3]),
                'close': close_p,
                'volume': float(r[5]),
                'amount': float(r[6] or 0),
                'warrant': w_info,
                'inst': inst_info
            })

        return {
            'quotes': quotes_list,
            'warrant_history_days': len(raw_warrants)
        }


    def _calculate_poc(self, quotes, days: int):
        if not quotes: return None
        target = quotes[-days:] if len(quotes) > days else quotes
        if not target: return None
        min_p = min(q['low'] for q in target)
        max_p = max(q['high'] for q in target)
        if min_p == max_p: return min_p
        bins = 50
        tick = (max_p - min_p) / bins
        profile = {}
        for q in target:
            idx = int((q['close'] - min_p) / tick) if tick > 0 else 0
            profile[idx] = profile.get(idx, 0) + q['volume']
        best_idx = max(profile, key=profile.get)
        return round(min_p + best_idx * tick + (tick / 2), 2)

    def generate_page(self, stock_info: Dict[str, Any]) -> str:
        """
        為單一標的生成專屬 HTML 頁面並儲存
        """
        stock_id = stock_info['id']
        stock_name = stock_info['name']
        side = stock_info.get('side', 'LONG')
        rank = stock_info.get('rank', 1)
        market_type = stock_info.get('market_type', 'TWSE')
        curr_price = stock_info.get('price', 0.0)
        ret_5d = stock_info.get('ret_5d', 0.0)
        vp = stock_info.get('vp', {})
        inst_summary = stock_info.get('inst_5d', {})
        w_summary = stock_info.get('warrant_summary', {})
        w_recommends = stock_info.get('warrant_recommends', [])

        data = self.fetch_stock_quotes_and_warrants(stock_id, market_type)
        quotes = data['quotes']

        poc_60 = self._calculate_poc(quotes, 60)
        poc_120 = self._calculate_poc(quotes, 120)
        poc_240 = self._calculate_poc(quotes, 240)
        poc_60_str = str(poc_60) if poc_60 else "null"
        poc_120_str = str(poc_120) if poc_120 else "null"
        poc_240_str = str(poc_240) if poc_240 else "null"


        # 計算九轉序列與 13 不連續計數
        td_quotes = calculate_td_sequential(quotes)
        td_summary = get_current_td_summary(td_quotes)

        # 整理 Lightweight Charts 所需 JSON 數據
        chart_candlesticks = []
        chart_volumes = []
        chart_markers = []
        chart_inst_foreign = []
        chart_inst_trust = []
        chart_warrants_call = []
        chart_warrants_put = []
        chart_warrants_net = []

        for q in td_quotes:
            d_str = q['date']
            o, h, l, c = q['open'], q['high'], q['low'], q['close']
            vol = q['volume']
            is_up = c >= o

            chart_candlesticks.append({
                'time': d_str,
                'open': o,
                'high': h,
                'low': l,
                'close': c
            })

            chart_volumes.append({
                'time': d_str,
                'value': vol,
                'color': '#ef444488' if is_up else '#10b98188'
            })

            # TD 序列 Markers
            if q.get('td_signal'):
                sig = q['td_signal']
                if sig == 'BUY_9':
                    chart_markers.append({
                        'time': d_str,
                        'position': 'belowBar',
                        'color': '#10b981',
                        'shape': 'arrowUp',
                        'text': '買9'
                    })
                elif sig == 'SELL_9':
                    chart_markers.append({
                        'time': d_str,
                        'position': 'aboveBar',
                        'color': '#ef4444',
                        'shape': 'arrowDown',
                        'text': '賣9'
                    })
                elif sig == 'BUY_13':
                    chart_markers.append({
                        'time': d_str,
                        'position': 'belowBar',
                        'color': '#06b6d4',
                        'shape': 'circle',
                        'text': '★買13'
                    })
                elif sig == 'SELL_13':
                    chart_markers.append({
                        'time': d_str,
                        'position': 'aboveBar',
                        'color': '#f59e0b',
                        'shape': 'circle',
                        'text': '★賣13'
                    })

            # 外資與投信多空金額數據
            q_inst = q.get('inst', {})
            f_amt_wan = q_inst.get('foreign_amt_wan', 0.0)
            t_amt_wan = q_inst.get('trust_amt_wan', 0.0)
            chart_inst_foreign.append({
                'time': d_str,
                'value': f_amt_wan,
                'color': 'rgba(56, 189, 248, 0.75)' if f_amt_wan >= 0 else 'rgba(100, 116, 139, 0.75)'
            })
            chart_inst_trust.append({
                'time': d_str,
                'value': t_amt_wan
            })

            # 權證副圖數據
            w = q.get('warrant', {})
            c_amt_wan = w.get('call_amt_wan', 0)
            p_amt_wan = w.get('put_amt_wan', 0)
            net_amt_wan = w.get('net_amt_wan', 0)

            chart_warrants_call.append({'time': d_str, 'value': c_amt_wan})
            chart_warrants_put.append({'time': d_str, 'value': p_amt_wan})
            chart_warrants_net.append({'time': d_str, 'value': net_amt_wan})

        # 渲染權證推薦表格
        warrant_table_html = self._render_warrant_table(w_recommends, side)

        # 側向標籤與顏色
        if side == 'LONG':
            side_badge = f"<span class='badge-bull'>▲ LONG #{rank} 結構走強</span>"
            side_theme_color = "#ef4444"
        else:
            side_badge = f"<span class='badge-bear'>▼ SHORT #{rank} 率先破位</span>"
            side_theme_color = "#10b981"

        ret_color = "text-bull" if ret_5d >= 0 else "text-bear"
        ret_sign = "+" if ret_5d >= 0 else ""

        # HTML 模板組裝
        html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{stock_id} {stock_name} 專業量化分析 (K線/九轉序列/13不連續/權證資金流) - 投行機構風控系統</title>
    <style>
        :root {{
            --bg-base: #0a0e17;
            --bg-card: #111827;
            --bg-card-hover: #1f2937;
            --border-color: #2d3748;
            --border-light: #374151;
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --bull-red: #ef4444;
            --bear-green: #10b981;
            --accent-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --accent-purple: #8b5cf6;
            --accent-yellow: #f59e0b;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background-color: var(--bg-base);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Noto Sans TC", sans-serif;
            line-height: 1.5;
            padding-bottom: 60px;
        }}
        .container {{ max-width: 1380px; margin: 0 auto; padding: 20px 24px; }}
        
        /* 導航 Header */
        .top-navbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 14px 20px;
            background: rgba(17, 24, 39, 0.95);
            backdrop-filter: blur(10px);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            margin-bottom: 24px;
        }}
        .btn-back {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: #1e293b;
            color: #ffffff;
            text-decoration: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid #3b82f6;
            transition: all 0.2s;
        }}
        .btn-back:hover {{
            background: #3b82f6;
            color: #ffffff;
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.5);
        }}
        .header-title-box {{
            display: flex;
            align-items: baseline;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .stock-main-title {{
            font-size: 26px;
            font-weight: 800;
            letter-spacing: 0.5px;
        }}
        .stock-price-box {{
            display: flex;
            align-items: baseline;
            gap: 10px;
        }}
        .stock-price {{
            font-size: 30px;
            font-weight: 900;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
        .stock-ret {{
            font-size: 16px;
            font-weight: 700;
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}
        
        /* 通用 Card */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 22px;
            margin-bottom: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }}
        .card-title {{
            font-size: 17px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        /* 網格統計欄 */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 24px;
        }}
        .stat-item {{
            background: #172033;
            border: 1px solid var(--border-color);
            border-radius: 10px;
            padding: 14px 16px;
        }}
        .stat-label {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 4px;
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .stat-value {{
            font-size: 18px;
            font-weight: 800;
            font-family: ui-monospace, SFMono-Regular, monospace;
        }}
        
        /* TD 診斷卡片 */
        .td-alert-box {{
            padding: 16px 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 5px solid #3b82f6;
            background: rgba(30, 41, 59, 0.7);
        }}
        .td-alert-title {{
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 6px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .td-alert-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        
        /* 圖表容器 (主圖與三大副圖) */
        .chart-box {{
            position: relative;
            width: 100%;
            height: 380px;
            border-radius: 8px;
            background: #0f172a;
            border: 1px solid var(--border-light);
            margin-bottom: 12px;
            overflow: hidden;
        }}
        .chart-box-vol {{
            position: relative;
            width: 100%;
            height: 120px;
            border-radius: 8px;
            background: #0f172a;
            border: 1px solid var(--border-light);
            margin-bottom: 12px;
            overflow: hidden;
        }}
        .chart-box-inst {{
            position: relative;
            width: 100%;
            height: 140px;
            border-radius: 8px;
            background: #0f172a;
            border: 1px solid var(--border-light);
            margin-bottom: 12px;
            overflow: hidden;
        }}
        .chart-box-sub {{
            position: relative;
            width: 100%;
            height: 150px;
            border-radius: 8px;
            background: #0f172a;
            border: 1px solid var(--border-light);
            margin-bottom: 8px;
            overflow: hidden;
        }}
        .chart-legend {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
            display: inline-block;
        }}
        
        /* 標籤 Badge */
        .badge-bull {{ background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid #ef4444; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
        .badge-bear {{ background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
        .badge-neutral {{ background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #f59e0b; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; }}
        .text-bull {{ color: var(--bull-red); }}
        .text-bear {{ color: var(--bear-green); }}
        .text-muted {{ color: var(--text-muted); }}
        
        /* 表格樣式 */
        .xiaoge-warrant-box {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-top: 14px;
        }}
        .xiaoge-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            text-align: left;
        }}
        .xiaoge-table th {{
            background: #1e293b;
            color: var(--text-secondary);
            padding: 10px 8px;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
        }}
        .xiaoge-table td {{
            padding: 10px 8px;
            border-bottom: 1px solid #1e293b;
        }}
        .badge-xiaoge-pass {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
        .badge-xiaoge-relax {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: 700; }}
        .badge-diff-lever {{ background: rgba(16, 185, 129, 0.15); color: #10b981; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
        .badge-diff-lever-relax {{ background: rgba(245, 158, 11, 0.15); color: #f59e0b; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
        
        /* 響應式 */
        @media (max-width: 768px) {{
            .top-navbar {{ flex-direction: column; align-items: flex-start; gap: 12px; }}
            .chart-box {{ height: 420px; }}
            .chart-box-sub {{ height: 220px; }}
            .stats-grid {{ grid-template-columns: 1fr 1fr; }}
        }}
    </style>
    <!-- 本地優先載入 Lightweight Charts，外網 CDN 雙重備援 -->
    <script src="assets/lightweight-charts.standalone.production.js"></script>
    <script>
        if (typeof LightweightCharts === 'undefined') {{
            document.write('<script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"><\\/script>');
        }}
    </script>
</head>
<body>
    <div class="container">
        <!-- 頂部導航 -->
        <div class="top-navbar">
            <div style="display:flex; align-items:center; gap:16px;">
                <a href="index.html" class="btn-back">← 返回市場全域儀表板</a>
                <div class="header-title-box">
                    <span class="stock-main-title">{stock_id} {stock_name}</span>
                    <span style="font-size:13px; color:var(--text-muted);">{market_type}</span>
                    {side_badge}
                </div>
            </div>
            <div class="stock-price-box">
                <span class="stock-price {ret_color}">{curr_price:.2f}</span>
                <span class="stock-ret {ret_color}">5日: {ret_sign}{ret_5d:.2f}%</span>
            </div>
        </div>

        <!-- 關鍵量化指標卡片格 -->
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">🎯 POC 最大量核心價</div>
                <div class="stat-value text-bull">{vp.get('poc_price', 0):.2f} 元</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">🛡️ 價值區間 (Value Area 70%)</div>
                <div class="stat-value" style="font-size:15px;">{vp.get('va_low', vp.get('val_price', 0)):.2f} ~ {vp.get('va_high', vp.get('vah_price', 0)):.2f} 元</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">⚡ 投信 5日淨買賣</div>
                <div class="stat-value" style="color:var(--accent-cyan);">{inst_summary.get('trust_5d', 0):+d} 張</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">🌐 外資 5日淨買賣</div>
                <div class="stat-value" style="color:var(--accent-blue);">{inst_summary.get('foreign_5d', 0):+d} 張</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">📊 融資 5日增減</div>
                <div class="stat-value" style="color:var(--accent-yellow);">{inst_summary.get('margin_5d', 0):+d} 張</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">🔥 今日權證多空比</div>
                <div class="stat-value" style="font-size:15px;">認購 {w_summary.get('call_ratio', 0)}% : 認售 {w_summary.get('put_ratio', 0)}%</div>
            </div>
        </div>

        <!-- TD Sequential & Countdown 序列診斷狀態卡 -->
        <div class="card" style="border-left: 5px solid {side_theme_color};">
            <div class="card-header">
                <div class="card-title">
                    <span>⏱️ Tom DeMark 九轉序列 (TD Setup 9) 與 13 不連續計數診斷</span>
                </div>
                <span class="{td_summary['badge_class']}">{td_summary['status']}</span>
            </div>
            <div class="td-alert-box">
                <div class="td-alert-title">
                    <span>💡 當前 K 線計數解讀：</span>
                </div>
                <div class="td-alert-desc">
                    {td_summary['detail']}<br>
                    • <strong>九轉結構 (TD Setup 9)</strong>：當連續 9 日收盤價低於前第 4 日收盤價即觸發【買9】，代表空方動能竭盡轉折點；反之連續 9 日高於前第 4 日收盤價即觸發【賣9】。<br>
                    • <strong>13 不連續序列 (TD Countdown 13)</strong>：九轉成立後，統計收盤價與前第 2 日極值（Close &lt;= Low[t-2] 或 Close &gt;= High[t-2]），累計滿 13 根觸發極限背離訊號！
                </div>
            </div>

            <!-- 主圖：K線與九轉標籤 -->
            <div class="chart-legend">
                <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> 上漲K棒 (紅)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> 下跌K棒 (綠)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> ▲ 買9 (空頭力竭買點)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> ▼ 賣9 (多頭超買賣點)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#06b6d4;"></span> ★ 買13 (終極底部背離)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#f59e0b;"></span> ★ 賣13 (終極頂部反轉)</div>
            </div>
            <div id="kline-chart-container" class="chart-box"></div>

            <!-- 副圖 1：獨立成交量 (Volume) -->
            <div class="chart-legend" style="margin-top: 10px; margin-bottom: 4px;">
                <div class="legend-item" style="font-weight:700; color:var(--text-primary);">📊 每日成交量 (Volume)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> 陽線量 (紅)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> 陰線量 (綠)</div>
            </div>
            <div id="volume-chart-container" class="chart-box-vol"></div>

            <!-- 副圖 2：外資與投信每日多空金額 (Institutional Flow) -->
            <div class="chart-legend" style="margin-top: 10px; margin-bottom: 4px;">
                <div class="legend-item" style="font-weight:700; color:var(--text-primary);">🏛️ 外資與投信每日多空金額 ({'億元' if stock_id in ['TAIEX', 'TPEx'] else '萬元'})</div>
                <div class="legend-item"><span class="legend-dot" style="background:#38bdf8;"></span> 外資買超 (天藍柱)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#64748b;"></span> 外資賣超 (灰柱)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#f43f5e;"></span> 投信多空淨額 (桃紅線)</div>
            </div>
            <div id="inst-chart-container" class="chart-box-inst"></div>

            <!-- 副圖 3：個股關聯權證每日多空資金流 (Warrant Flow) -->
            <div class="chart-legend" style="margin-top: 10px; margin-bottom: 4px;">
                <div class="legend-item" style="font-weight:700; color:var(--text-primary);">🎯 權證每日多空資金流 (萬元)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#ef4444;"></span> 認購成交額 (多方買氣, 萬元)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#10b981;"></span> 認售成交額 (空方避險, 萬元)</div>
                <div class="legend-item"><span class="legend-dot" style="background:#38bdf8;"></span> 權證多空淨額 (認購 - 認售, 萬元)</div>
            </div>
            <div id="warrant-chart-container" class="chart-box-sub"></div>
        </div>

        <!-- 權證小哥 5 大指標推薦名單 -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">
                    <span>⚡ 權證小哥 5 大指標嚴選標的 (實戰交易優先推薦)</span>
                </div>
                <span style="font-size:12px; color:var(--text-secondary);">每日 16:00 元大權證網直連 ｜ 天數 &gt; 120天 ｜ 差槓比 &lt; 0.3%~0.7%</span>
            </div>
            {warrant_table_html}
        </div>
    </div>

    <!-- 圖表初始化腳本 -->
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            const klineData = {json.dumps(chart_candlesticks)};
            const volumeData = {json.dumps(chart_volumes)};
            const markersData = {json.dumps(chart_markers)};
            const instForeignData = {json.dumps(chart_inst_foreign)};
            const instTrustData = {json.dumps(chart_inst_trust)};
            const warrantCallData = {json.dumps(chart_warrants_call)};
            const warrantPutData = {json.dumps(chart_warrants_put)};
            const warrantNetData = {json.dumps(chart_warrants_net)};

            // 通用圖表配置 (統一格式化只顯示日期、消除 00:00:00、鎖定右側軸寬達成精準垂直對齊)
            const commonChartOptions = {{
                layout: {{
                    background: {{ color: '#0f172a' }},
                    textColor: '#94a3b8',
                }},
                grid: {{
                    vertLines: {{ color: '#1e293b' }},
                    horzLines: {{ color: '#1e293b' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                localization: {{
                    locale: 'zh-TW',
                    dateFormat: 'yyyy-MM-dd',
                    timeFormatter: function(t) {{
                        if (typeof t === 'string') return t;
                        if (t && t.year) {{
                            const m = String(t.month).padStart(2, '0');
                            const d = String(t.day).padStart(2, '0');
                            return `${{t.year}}-${{m}}-${{d}}`;
                        }}
                        return String(t);
                    }}
                }},
                leftPriceScale: {{
                    visible: false,
                }},
                rightPriceScale: {{
                    borderColor: '#334155',
                    minimumWidth: 105,
                }},
                timeScale: {{
                    borderColor: '#334155',
                    timeVisible: false,
                    secondsVisible: false,
                }},
            }};

            // 1. 初始化 K 線主圖 (純 K 線 + 九轉標籤)
            const klineContainer = document.getElementById('kline-chart-container');
            const klineChart = LightweightCharts.createChart(klineContainer, Object.assign({{}}, commonChartOptions, {{
                width: klineContainer.clientWidth,
                height: klineContainer.clientHeight,
            }}));

            const candleSeries = klineChart.addCandlestickSeries({{
                upColor: '#ef4444',
                downColor: '#10b981',
                borderUpColor: '#ef4444',
                borderDownColor: '#10b981',
                wickUpColor: '#ef4444',
                wickDownColor: '#10b981',
                priceFormat: {{
                    type: 'price',
                    precision: 1,
                    minMove: 0.1,
                }},
            }});
            candleSeries.setData(klineData);
            candleSeries.setMarkers(markersData);

            const poc60 = {poc_60_str};
            if (poc60 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc60,
                    color: '#eab308',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: 'POC(60)'
                }});
            }}
            const poc120 = {poc_120_str};
            if (poc120 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc120,
                    color: '#f97316',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                    axisLabelVisible: true,
                    title: 'POC(120)'
                }});
            }}
            const poc240 = {poc_240_str};
            if (poc240 !== null) {{
                candleSeries.createPriceLine({{
                    price: poc240,
                    color: '#ec4899',
                    lineWidth: 2,
                    lineStyle: LightweightCharts.LineStyle.LargeDashed,
                    axisLabelVisible: true,
                    title: 'POC(240)'
                }});
            }}


            // 2. 初始化副圖 1：獨立成交量 (解決重疊問題)
            const volumeContainer = document.getElementById('volume-chart-container');
            const volumeChart = LightweightCharts.createChart(volumeContainer, Object.assign({{}}, commonChartOptions, {{
                width: volumeContainer.clientWidth,
                height: volumeContainer.clientHeight,
            }}));

            const volumeSeries = volumeChart.addHistogramSeries({{
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        if (Math.abs(val) >= 10000) {{
                            return (val / 10000).toFixed(1) + ' 萬張';
                        }}
                        return Number(val).toFixed(0) + ' 張';
                    }}
                }},
                title: '成交量'
            }});
            volumeSeries.setData(volumeData);

            // 3. 初始化副圖 2：外資與投信多空金額 (萬元)
            const instContainer = document.getElementById('inst-chart-container');
            const instChart = LightweightCharts.createChart(instContainer, Object.assign({{}}, commonChartOptions, {{
                width: instContainer.clientWidth,
                height: instContainer.clientHeight,
            }}));

            const foreignSeries = instChart.addHistogramSeries({{
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        return Number(val).toFixed(1) + ' 萬';
                    }}
                }},
                title: '外資多空金額'
            }});
            foreignSeries.setData(instForeignData);

            const trustSeries = instChart.addLineSeries({{
                color: '#f43f5e',
                lineWidth: 2,
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        return Number(val).toFixed(1) + ' 萬';
                    }}
                }},
                title: '投信多空淨額'
            }});
            trustSeries.setData(instTrustData);

            // 4. 初始化副圖 3：權證多空資金流 (嚴格限制 Y 軸頂多 1 位小數)
            const warrantContainer = document.getElementById('warrant-chart-container');
            const warrantChart = LightweightCharts.createChart(warrantContainer, Object.assign({{}}, commonChartOptions, {{
                width: warrantContainer.clientWidth,
                height: warrantContainer.clientHeight,
            }}));

            const callSeries = warrantChart.addHistogramSeries({{
                color: 'rgba(239, 68, 68, 0.75)',
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        return Number(val).toFixed(1) + ' 萬';
                    }}
                }},
                title: '認購額(萬)',
            }});
            callSeries.setData(warrantCallData);

            const putSeries = warrantChart.addHistogramSeries({{
                color: 'rgba(16, 185, 129, 0.75)',
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        return Number(val).toFixed(1) + ' 萬';
                    }}
                }},
                title: '認售額(萬)',
            }});
            putSeries.setData(warrantPutData);

            const netLineSeries = warrantChart.addLineSeries({{
                color: '#38bdf8',
                lineWidth: 2,
                priceFormat: {{
                    type: 'custom',
                    formatter: function(val) {{
                        return Number(val).toFixed(1) + ' 萬';
                    }}
                }},
                title: '多空淨額(萬)',
            }});
            netLineSeries.setData(warrantNetData);

            const allCharts = [klineChart, volumeChart, instChart, warrantChart];

            // 四圖時間軸與邏輯區間連動 (Smooth Logical Range Sync)
            allCharts.forEach(c1 => {{
                c1.timeScale().subscribeVisibleLogicalRangeChange(range => {{
                    if (!range) return;
                    allCharts.forEach(c2 => {{
                        if (c1 !== c2) {{
                            c2.timeScale().setVisibleLogicalRange(range);
                        }}
                    }});
                    syncPriceScaleWidths();
                }});
            }});

            // 四圖十字游標無縫連動 (Crosshair Synchronization)
            const candleMap = new Map(klineData.map(d => [d.time, d.close]));
            const volumeMap = new Map(volumeData.map(d => [d.time, d.value]));
            const instMap = new Map(instForeignData.map(d => [d.time, d.value]));
            const warrantMap = new Map(warrantNetData.map(d => [d.time, d.value]));

            function syncCrosshair(sourceChart, param) {{
                if (!param || !param.time || !param.point) {{
                    allCharts.forEach(c => {{
                        if (c !== sourceChart) {{
                            try {{ c.clearCrosshairPosition(); }} catch(e) {{}}
                        }}
                    }});
                    return;
                }}
                const t = param.time;
                if (klineChart !== sourceChart && candleMap.has(t)) {{
                    try {{ klineChart.setCrosshairPosition(candleMap.get(t), t, candleSeries); }} catch(e) {{}}
                }}
                if (volumeChart !== sourceChart && volumeMap.has(t)) {{
                    try {{ volumeChart.setCrosshairPosition(volumeMap.get(t), t, volumeSeries); }} catch(e) {{}}
                }}
                if (instChart !== sourceChart && instMap.has(t)) {{
                    try {{ instChart.setCrosshairPosition(instMap.get(t), t, foreignSeries); }} catch(e) {{}}
                }}
                if (warrantChart !== sourceChart && warrantMap.has(t)) {{
                    try {{ warrantChart.setCrosshairPosition(warrantMap.get(t), t, netLineSeries); }} catch(e) {{}}
                }}
            }}

            klineChart.subscribeCrosshairMove(p => syncCrosshair(klineChart, p));
            volumeChart.subscribeCrosshairMove(p => syncCrosshair(volumeChart, p));
            instChart.subscribeCrosshairMove(p => syncCrosshair(instChart, p));
            warrantChart.subscribeCrosshairMove(p => syncCrosshair(warrantChart, p));

            // 精確同步右側價格刻度寬度 (保證四張圖繪圖區與網格線 100% 垂直對齊)
            let currentSyncedWidth = 105;
            function syncPriceScaleWidths() {{
                let maxW = 105;
                allCharts.forEach(c => {{
                    try {{
                        const w = c.priceScale('right').width();
                        if (w > maxW) maxW = w;
                    }} catch(e) {{}}
                }});
                if (maxW !== currentSyncedWidth) {{
                    currentSyncedWidth = maxW;
                    allCharts.forEach(c => {{
                        try {{
                            c.priceScale('right').applyOptions({{ minimumWidth: currentSyncedWidth }});
                        }} catch(e) {{}}
                    }});
                }}
            }}
            setTimeout(syncPriceScaleWidths, 80);

            // 視窗縮放自適應
            window.addEventListener('resize', () => {{
                klineChart.applyOptions({{ width: klineContainer.clientWidth }});
                volumeChart.applyOptions({{ width: volumeContainer.clientWidth }});
                instChart.applyOptions({{ width: instContainer.clientWidth }});
                warrantChart.applyOptions({{ width: warrantContainer.clientWidth }});
                syncPriceScaleWidths();
            }});
        }});
    </script>
</body>
</html>
"""

        # 輸出至本地根目錄與 docs/
        out_filename = f"stock_{stock_id}.html"
        out_root = os.path.join(ROOT_DIR, out_filename)
        out_docs = os.path.join(DOCS_DIR, out_filename)

        os.makedirs(DOCS_DIR, exist_ok=True)
        with open(out_root, "w", encoding="utf-8") as f:
            f.write(html)
        with open(out_docs, "w", encoding="utf-8") as f:
            f.write(html)

        return out_root

    def _render_warrant_table(self, warrants: List[Dict[str, Any]], side: str) -> str:
        """渲染權證推薦表格"""
        opt_type_label = "認購 CALL" if side == 'LONG' else "認售 PUT"
        if not warrants:
            return f"""
            <div class="xiaoge-warrant-box">
                <div style="color:var(--text-muted); font-size:13px; text-align:center; padding:16px;">
                    ⚠️ 本標的目前市場「無符合權證小哥指標」之權證（剩餘天數不足 120 天或差槓比 &gt; 0.7%）。<br>
                    💡 小哥操作紀律：寧可直接操作現股，絕不妥協買進劣質權證承擔時間價值加速衰減！
                </div>
            </div>
            """

        rows = ""
        for idx, w in enumerate(warrants, 1):
            is_tier1 = w.get('is_strict_pass', True)
            badge_html = f'<span class="badge-xiaoge-pass">★ 小哥嚴選 #{idx}</span>' if is_tier1 else f'<span class="badge-xiaoge-relax">◆ 次選放寬 #{idx}</span>'
            diff_class = "badge-diff-lever" if is_tier1 else "badge-diff-lever-relax"
            rows += f"""
            <tr>
                <td>{badge_html}</td>
                <td><strong>{w['warrant_id']}</strong> {w['warrant_name']}</td>
                <td>{w['buy_price']:.2f} / {w['sell_price']:.2f}</td>
                <td>{w['strike_price']:.2f} ({w['in_out_dec']:+.1f}%)</td>
                <td style="color:var(--bull-red); font-weight:700;">{w['period']} 天</td>
                <td>{w['leverage']:.2f}x</td>
                <td>{w['buy_sell_rate']:.2f}%</td>
                <td><span class="{diff_class}">{w['diff_lever_ratio']:.3f}%</span></td>
                <td>{w['out_vol_rate']:.1f}%</td>
                <td><strong style="color:var(--accent-blue);">{w['issuer_name']}</strong></td>
            </tr>
            """

        return f"""
        <div class="xiaoge-warrant-box">
            <div class="xiaoge-table-wrapper" style="overflow-x: auto; max-width: 100%; width: 100%;"><table class="xiaoge-table">
                <thead>
                    <tr>
                        <th>評級</th>
                        <th>權證代碼 / 名稱</th>
                        <th>委買 / 委賣</th>
                        <th>履約價 (價外%)</th>
                        <th>剩餘天數</th>
                        <th>實質槓桿</th>
                        <th>買賣價差比</th>
                        <th>差槓比</th>
                        <th>流通在外</th>
                        <th>造市券商</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table></div>
        </div>
        """
