"""
離線版 投行機構 3 模組市場狀態與執行風控系統 網頁生成器 (V3: 純 SVG 向量儀表盤 + 嚴格權證過濾遞補)
================================================================================
生成完全自給自足、100% 離線可用的現代化儀表板 (quant_regime.html)
零外部 CDN 依賴，採用純向量 SVG 渲染半圓儀表盤 (保證 100% 載入且不依賴 JavaScript)
"""

import os
import json
import math
import datetime
from src.quant_regime_screener import QuantRegimeScreener


def render_svg_half_gauge(val, min_v, max_v, val_text, color_zones, needle_color="#ffffff", w=180, h=110):
    """
    產生純向量 SVG 半圓儀表盤標籤
    優點：由瀏覽器原生圖形引擎直接渲染，100% 離線可用，零 JavaScript 依賴，永遠不出現黑框或留白
    """
    cx = w / 2.0
    cy = h - 20.0
    r = 62.0
    stroke_w = 12.0
    
    paths = []
    for zone in color_zones:
        z_from = zone['from']
        z_to = zone['to']
        color = zone['color']
        
        # 弧度轉換 (從 PI 到 2*PI)
        a1 = math.pi + math.pi * ((z_from - min_v) / (max_v - min_v))
        a2 = math.pi + math.pi * ((z_to - min_v) / (max_v - min_v))
        
        x1 = cx + r * math.cos(a1)
        y1 = cy + r * math.sin(a1)
        x2 = cx + r * math.cos(a2)
        y2 = cy + r * math.sin(a2)
        
        large_arc = 1 if (a2 - a1) > math.pi else 0
        path = f'<path d="M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large_arc} 1 {x2:.2f} {y2:.2f}" fill="none" stroke="{color}" stroke-width="{stroke_w}" stroke-linecap="butt" />'
        paths.append(path)
        
    # 計算指針端點
    clamped = max(min_v, min(max_v, val))
    needle_angle = math.pi + math.pi * ((clamped - min_v) / (max_v - min_v))
    nx = cx + (r - 14.0) * math.cos(needle_angle)
    ny = cy + (r - 14.0) * math.sin(needle_angle)
    
    needle_svg = f'<line x1="{cx:.2f}" y1="{cy:.2f}" x2="{nx:.2f}" y2="{ny:.2f}" stroke="{needle_color}" stroke-width="3" stroke-linecap="round" />'
    center_dot = f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="5" fill="#ffffff" />'
    text_svg = f'<text x="{cx:.2f}" y="{cy - 8:.2f}" text-anchor="middle" fill="#ffffff" font-size="13" font-weight="bold" font-family="monospace">{val_text}</text>'
    
    svg = f"""<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="display:block; margin:0 auto; max-width:100%; height:auto;">
        {''.join(paths)}
        {needle_svg}
        {center_dot}
        {text_svg}
    </svg>"""
    return svg


def render_xiaoge_warrants_html(warrants, opt_type_label="認購 CALL"):
    if not warrants:
        return f"""
        <div class="xiaoge-warrant-box">
            <div class="xiaoge-header">
                <div class="xiaoge-title">
                    <span>🎯 etfinfo_Go 多因子量化權證推薦 ({opt_type_label})</span>
                </div>
                <div class="xiaoge-subtitle">模型綜合評分：差槓比(30分) + 到期天數(20分) + 價內外(20分) + Delta(15分) + Theta(10分)</div>
            </div>
            <div class="xiaoge-empty-strict">
                <div class="empty-strict-title">💡 系統判定本檔股票「無值得推薦之優質權證」</div>
                <div class="empty-strict-desc">
                    全市場流通權證皆因 <strong>即將到期(剩餘天數&lt;30天)、深度價外、仙股無流動性、或差槓比過高(&gt;1.5%)</strong> 遭系統淘汰。<br>
                    🛡️ <strong>實戰紀律</strong>：寧可直接操作現股，絕不妥協買進劣質權證承擔不合理之時間價值流失與摩擦成本！
                </div>
            </div>
        </div>
        """
        
    rows_html = ""
    for idx, w in enumerate(warrants, 1):
        tag = w.get('recommend_tag', '標準')
        score = w.get('total_score', 0)
        
        if score >= 80:
            badge_html = f'<span class="badge-xiaoge-pass">{tag}</span>'
            diff_class = "badge-diff-lever"
        elif score >= 60:
            badge_html = f'<span class="badge-xiaoge-relax">{tag}</span>'
            diff_class = "badge-diff-lever-relax"
        else:
            badge_html = f'<span style="background:#334155;color:#cbd5e1;padding:3px 6px;border-radius:4px;font-size:10px;">{tag}</span>'
            diff_class = ""
            
        moneyness_color = "text-bull" if -15.0 <= w['in_out_dec'] <= 5.0 else "text-muted"
        period_color = "text-bull" if w['period'] >= 60 else "text-muted"
        out_vol_color = "text-bull" if w['out_vol_rate'] <= 80.0 else "text-muted"
        
        rows_html += f"""
        <tr>
            <td>
                <div style="font-size:14px;font-weight:700;color:#facc15;margin-bottom:4px;">{score:.1f}分</div>
                {badge_html}
            </td>
            <td>
                <strong style="color:#ffffff; font-size:13px;">{w['warrant_id']}</strong>
                <div style="font-size:11px; color:var(--text-secondary);">{w['warrant_name']}</div>
            </td>
            <td>{w['buy_price']:.2f} / {w['sell_price']:.2f}</td>
            <td>
                <span>{w['strike_price']:.2f}</span>
                <small class="{moneyness_color}">({w['in_out_dec']:+.1f}%)</small>
            </td>
            <td class="{period_color}"><strong>{w['period']}</strong> 天</td>
            <td>
                <strong style="color:var(--text-primary);">{w['leverage']:.2f}x</strong>
                <div style="font-size:10px; color:var(--text-muted);">Delta: {w['delta']:.2f}</div>
            </td>
            <td>
                <span>{w['buy_sell_rate']:.2f}%</span>
                <div style="font-size:10px; color:var(--text-muted);">Theta損: {w.get('theta_loss_ratio', 99):.2f}%</div>
            </td>
            <td><span class="{diff_class}">{w['diff_lever_ratio']:.3f}%</span></td>
            <td class="{out_vol_color}">{w['out_vol_rate']:.1f}%</td>
            <td><span style="color:var(--accent-blue); font-weight:700;">{w['issuer_name']}</span></td>
        </tr>
        """
        
    footer_note = f"""
    <div class="xiaoge-table-footer">
        ⚠️ <strong>實戰黃金法則</strong>：優先挑選 <strong>差槓比 &lt; 0.3% (翠綠色)</strong> + <strong>剩餘天數 &gt; 90天</strong> + <strong>價外 3%~15%</strong> 之標的。差槓比代表「現股需上漲多少%才能弭平權證一檔買賣價差」，數值越低勝率越高！
    </div>
    """
        
    return f"""
    <div class="xiaoge-warrant-box">
        <div class="xiaoge-header">
            <div class="xiaoge-title">
                <span>🎯 etfinfo_Go 多因子量化權證推薦 ({opt_type_label})</span>
            </div>
            <div class="xiaoge-subtitle">模型綜合評分：差槓比(30分) + 到期天數(20分) + 價內外(20分) + Delta(15分) + Theta(10分) + 流動性與風控修正</div>
        </div>
        <div class="xiaoge-table-wrapper">
            <table class="xiaoge-table">
                <thead>
                    <tr>
                        <th>綜合評分</th>
                        <th>權證名稱</th>
                        <th>買/賣價</th>
                        <th>履約價(價內外)</th>
                        <th>剩餘天數</th>
                        <th>實質槓桿(Delta)</th>
                        <th>價差比(日損)</th>
                        <th>差槓比</th>
                        <th>流通比</th>
                        <th>券商</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
        {footer_note}
    </div>
    """

        
    has_relaxed = any(not w.get('is_strict_pass', True) for w in warrants)
    rows_html = ""
    for idx, w in enumerate(warrants, 1):
        is_tier1 = w.get('is_strict_pass', True)
        if is_tier1:
            badge_html = f'<span class="badge-xiaoge-pass">★ 小哥嚴選 #{idx}</span>'
            diff_class = "badge-diff-lever"
        else:
            badge_html = f'<span class="badge-xiaoge-relax">◆ 次選放寬 #{idx}</span>'
            diff_class = "badge-diff-lever-relax"

        moneyness_color = "text-bull" if -25.0 <= w['in_out_dec'] <= 5.0 else "text-muted"
        period_color = "text-bull" if w['period'] > 120 else "text-muted"
        out_vol_color = "text-bull" if 10.0 <= w['out_vol_rate'] <= 60.0 else "text-muted"
        
        rows_html += f"""
        <tr>
            <td>{badge_html}</td>
            <td>
                <strong style="color:#ffffff; font-size:13px;">{w['warrant_id']}</strong>
                <div style="font-size:11px; color:var(--text-secondary);">{w['warrant_name']}</div>
            </td>
            <td>{w['buy_price']:.2f} / {w['sell_price']:.2f}</td>
            <td>
                <span>{w['strike_price']:.2f}</span>
                <small class="{moneyness_color}">({w['in_out_dec']:+.1f}%)</small>
            </td>
            <td class="{period_color}"><strong>{w['period']}</strong> 天</td>
            <td><strong style="color:var(--text-primary);">{w['leverage']:.2f}x</strong></td>
            <td>{w['buy_sell_rate']:.2f}%</td>
            <td><span class="{diff_class}">{w['diff_lever_ratio']:.3f}%</span></td>
            <td class="{out_vol_color}">{w['out_vol_rate']:.1f}%</td>
            <td><span style="color:var(--accent-blue); font-weight:700;">{w['issuer_name']}</span></td>
        </tr>
        """
        
    if has_relaxed:
        footer_note = f"""
        <div class="xiaoge-table-footer">
            💡 差槓比放寬說明：標示【◆ 次選放寬】者為差槓比介於 0.3%~0.7% 之放寬標的（抗摩擦成本稍降），其餘「剩餘天數 &gt; 120天」、「價平~價外25%」、「流通10%~60%」等小哥四大核心風控指標仍 100% 嚴格符合！
        </div>
        """
    elif len(warrants) < 3:
        footer_note = f"""
        <div class="xiaoge-table-footer">
            💡 市場嚴選結果：全市場僅此 <strong>{len(warrants)} 檔</strong>完全符合小哥五大硬性指標（差槓比&lt;0.3%、天數&gt;120天），其餘標的因不合規已全數淘汰，絕不妥協湊數！
        </div>
        """
    else:
        footer_note = f"""
        <div class="xiaoge-table-footer">
            💡 小哥嚴選全過：全數標的 100% 符合小哥五大硬性指標（差槓比 &lt; 0.3%、天數 &gt; 120天、流通 10%~60%）。
        </div>
        """

    return f"""
    <div class="xiaoge-warrant-box">
        <div class="xiaoge-header">
            <div class="xiaoge-title">
                <span>⚡ 權證小哥 5 大指標嚴選 Top {len(warrants)} 標的 ({opt_type_label})</span>
            </div>
            <div class="xiaoge-subtitle">元大權證網每日 16:00 盤後直連 ｜ 剩餘天數 &gt; 120天 ｜ 價平~價外25% ｜ 流通 10%~60% ｜ 差槓比 &lt; 0.3% (若無放寬至 0.7%)</div>
        </div>
        <div class="xiaoge-table-wrapper">
            <table class="xiaoge-table font-mono">
                <thead>
                    <tr>
                        <th>評級</th>
                        <th>代碼 / 名稱</th>
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
                    {rows_html}
                </tbody>
            </table>
            {footer_note}
        </div>
    </div>
    """


def generate_html(output_path="quant_regime.html"):
    screener = QuantRegimeScreener()
    data = screener.run_analysis()
    
    m1 = data['module_1']
    radar = data['radar']
    wm = data['warrant_market']
    longs = data['top_longs']
    shorts = data['top_shorts']
    
    # 為每檔選出的多方/空方標的自動產出專屬獨立分析頁面 (含K棒/九轉序列/13不連續/權證資金流)
    try:
        from src.stock_page_generator import StockPageGenerator
        stock_gen = StockPageGenerator()
        for idx, x in enumerate(longs, 1):
            stock_info = {
                'id': x['id'],
                'name': x['name'],
                'side': 'LONG',
                'rank': idx,
                'market_type': x.get('market', 'TWSE'),
                'price': x.get('close', 0.0),
                'ret_5d': x.get('ret_20d', 0.0),
                'vp': x.get('volume_profile', {}),
                'inst_5d': {
                    'trust_5d': x.get('t_5d', 0),
                    'foreign_5d': x.get('f_5d', 0),
                    'margin_5d': x.get('m_chg5', 0),
                    'sbl_5d': x.get('sbl_chg5', 0)
                },
                'warrant_summary': {
                    'call_ratio': x['warrant'].get('call_pct', 0),
                    'put_ratio': x['warrant'].get('put_pct', 0)
                },
                'warrant_recommends': x.get('xiaoge_warrants', [])
            }
            stock_gen.generate_page(stock_info)

        for idx, x in enumerate(shorts, 1):
            stock_info = {
                'id': x['id'],
                'name': x['name'],
                'side': 'SHORT',
                'rank': idx,
                'market_type': x.get('market', 'TWSE'),
                'price': x.get('close', 0.0),
                'ret_5d': x.get('ret_20d', 0.0),
                'vp': x.get('volume_profile', {}),
                'inst_5d': {
                    'trust_5d': x.get('t_5d', 0),
                    'foreign_5d': x.get('f_5d', 0),
                    'margin_5d': x.get('m_chg5', 0),
                    'sbl_5d': x.get('sbl_chg5', 0)
                },
                'warrant_summary': {
                    'call_ratio': x['warrant'].get('call_pct', 0),
                    'put_ratio': x['warrant'].get('put_pct', 0)
                },
                'warrant_recommends': x.get('xiaoge_warrants', [])
            }
            stock_gen.generate_page(stock_info)
    except Exception as e:
        print(f"  [!] 生成個股專屬頁面警告: {e}")
    
    # 判斷市場狀態顏色與標籤
    if m1['regime_code'] == 'RISK_ON':
        regime_color = "#10b981"
        regime_badge_class = "badge-bull"
        kill_switch_badge = "<span class='badge-normal'>● NORMAL / 正常未觸發</span>"
    elif m1['regime_code'] == 'RISK_OFF':
        regime_color = "#ef4444"
        regime_badge_class = "badge-bear"
        kill_switch_badge = "<span class='badge-alert'>🚨 ACTIVATED / 全域多單清倉熔斷</span>"
    else:
        regime_color = "#f59e0b"
        regime_badge_class = "badge-neutral"
        kill_switch_badge = "<span class='badge-normal'>● NORMAL / 警戒中未觸發</span>"
        
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 生成原生 SVG 儀表盤
    breadth_svg = render_svg_half_gauge(
        val=m1['breadth_pct'],
        min_v=0,
        max_v=100,
        val_text=f"{m1['breadth_pct']}%",
        color_zones=[
            {'from': 0, 'to': 40, 'color': '#10b981'},
            {'from': 40, 'to': 55, 'color': '#f59e0b'},
            {'from': 55, 'to': 100, 'color': '#ef4444'}
        ],
        needle_color="#ffffff"
    )
    
    radar_svg = render_svg_half_gauge(
        val=radar['composite_score'],
        min_v=0,
        max_v=100,
        val_text=f"{radar['composite_score']}分",
        color_zones=[
            {'from': 0, 'to': 45, 'color': '#10b981'},
            {'from': 45, 'to': 55, 'color': '#3b82f6'},
            {'from': 55, 'to': 75, 'color': '#f59e0b'},
            {'from': 75, 'to': 100, 'color': '#ef4444'}
        ],
        needle_color=radar['color']
    )
    
    # 產生多頭標的卡片 HTML (含個股權證與 90日 Volume Profile)
    long_cards_html = ""
    for i, x in enumerate(longs, 1):
        w = x['warrant']
        vp = x.get('volume_profile')
        
        # Volume Profile 區塊 HTML
        if vp:
            if vp['relation'] == 'SUPPORT_ABOVE':
                vp_badge_class = "vp-badge-support"
            elif vp['relation'] == 'RESISTANCE_BELOW':
                vp_badge_class = "vp-badge-resistance"
            else:
                vp_badge_class = "vp-badge-inside"

            vp_html = f"""
            <div class="vp-box">
                <div class="vp-header">
                    <span>📊 90日 Volume Profile (成交量分佈與交易密集區)</span>
                    <span class="vp-badge {vp_badge_class}">{vp['relation_label']}</span>
                </div>
                <div class="vp-metrics-row font-mono">
                    <div>POC 最大量核心價: <strong class="text-bull">{vp['poc_price']:.2f} 元</strong></div>
                    <div>價值區間 (Value Area 70%): <strong style="color:var(--text-primary);">{vp['va_low']:.2f} ~ {vp['va_high']:.2f} 元</strong></div>
                </div>
                <div class="vp-pos-desc">
                    💡 <strong>定價與避巴邏輯：</strong>{vp['pos_desc']}
                </div>
            </div>
            """
        else:
            vp_html = ""

        if w['has_warrants'] and w['tot_amt_wan'] > 0:
            warrant_html = f"""
            <div class="warrant-box">
                <div class="warrant-title">
                    <span>🎯 個股關聯權證多空分析 (Warrant Flow)</span>
                    <span class="warrant-tag font-bold">{w['sentiment']}</span>
                </div>
                <div class="warrant-grid">
                    <div class="warrant-item">
                        <span class="w-label">認購成交總額</span>
                        <span class="w-val text-bull">{w['call_amt_wan']:,} 萬元 <small>({w['call_pct']}%, {w['call_cnt']}檔)</small></span>
                    </div>
                    <div class="warrant-item">
                        <span class="w-label">認售成交總額</span>
                        <span class="w-val text-bear">{w['put_amt_wan']:,} 萬元 <small>({w['put_pct']}%, {w['put_cnt']}檔)</small></span>
                    </div>
                    <div class="warrant-item">
                        <span class="w-label">權證多空金額比</span>
                        <span class="w-val font-mono">認購 {w['call_pct']}% : 認售 {w['put_pct']}%</span>
                    </div>
                </div>
            </div>
            """
        else:
            warrant_html = f"""
            <div class="warrant-box warrant-box-empty">
                <span class="warrant-tag">{w['sentiment']}</span>
            </div>
            """
            
        xiaoge_html = render_xiaoge_warrants_html(x.get('xiaoge_warrants', []), opt_type_label="認購 CALL")

        long_cards_html += f"""
        <div class="stock-card card-long">
            <div class="card-header">
                <div class="stock-title-group">
                    <span class="rank-tag rank-tag-long">LONG #{i}</span>
                    <a href="stock_{x['id']}.html" class="stock-title-link" title="點擊進入 {x['id']} {x['name']} (K線 / 九轉序列 / 13不連續 / 每日權證資金流)">
                        <span class="stock-id">{x['id']}</span>
                        <span class="stock-name">{x['name']}</span>
                        <span class="stock-market">{x['market']}</span>
                        <span class="stock-jump-badge">📊 個股K線/九轉/權證 ↗</span>
                    </a>
                </div>
                <div class="stock-price-group">
                    <span class="price-val text-bull">{x['close']:.2f}</span>
                    <span class="ret-badge ret-bull">20D +{x['ret_20d']}%</span>
                </div>
            </div>
            
            <div class="chips-grid">
                <div class="chip-item">
                    <span class="chip-label">投信 5 日</span>
                    <span class="chip-val text-bull">+{x['t_5d']:,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">外資 5 日</span>
                    <span class="chip-val {'text-bull' if x['f_5d']>=0 else 'text-bear'}">{x['f_5d']:+,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">融資 5 日</span>
                    <span class="chip-val {'text-bull' if x['m_chg5']<=0 else 'text-bear'}">{x['m_chg5']:+,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">借券變化</span>
                    <span class="chip-val {'text-bull' if x['sbl_chg5']<=0 else 'text-bear'}">{x['sbl_chg5']:+,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">均線排列</span>
                    <span class="chip-val font-mono">5M:{x['ma5']:.1f} | 20M:{x['ma20']:.1f}</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">真實波幅</span>
                    <span class="chip-val font-mono">ATR(14)={x['atr14']:.2f}</span>
                </div>
            </div>
            
            {vp_html}
            {warrant_html}
            {xiaoge_html}
            
            <div class="execution-box box-long">
                <div class="exec-title">
                    <span>⚡ 模組 3：籌碼密集區精準定價與風控指示 (避免追高雙巴)</span>
                    <span class="rr-tag">風報比 1 : {x['rr_ratio']}</span>
                </div>
                <div class="exec-grid">
                    <div class="exec-col">
                        <span class="exec-label">🎯 密集區進場點 (避免雙巴)</span>
                        <span class="exec-val text-bull">{x['entry_price']:.2f} 元</span>
                        <span class="exec-sub">{x.get('entry_desc', f"站穩前高 {x['prev_high']:.2f} 開倉")}</span>
                    </div>
                    <div class="exec-col">
                        <span class="exec-label">🛑 密集區防守停損</span>
                        <span class="exec-val text-bear">{x['stop_loss']:.2f} 元</span>
                        <span class="exec-sub">最大回撤 -{x['stop_pct']}%</span>
                    </div>
                    <div class="exec-col">
                        <span class="exec-label">🏆 波段停利目標</span>
                        <span class="exec-val text-bull">{x['take_profit']:.2f} 元</span>
                        <span class="exec-sub">預期利潤 +{x['profit_pct']}%</span>
                    </div>
                </div>
                <div class="exec-warning">
                    ⚠️ <strong>離場警示：</strong>{x['exit_rule']}
                </div>
            </div>
        </div>
        """
        
    # 產生空頭標的卡片 HTML (含個股權證與 90日 Volume Profile)
    short_cards_html = ""
    for i, x in enumerate(shorts, 1):
        w = x['warrant']
        vp = x.get('volume_profile')

        # Volume Profile 區塊 HTML
        if vp:
            if vp['relation'] == 'RESISTANCE_BELOW':
                vp_badge_class = "vp-badge-resistance"
            elif vp['relation'] == 'SUPPORT_ABOVE':
                vp_badge_class = "vp-badge-support"
            else:
                vp_badge_class = "vp-badge-inside"

            vp_html = f"""
            <div class="vp-box">
                <div class="vp-header">
                    <span>📊 90日 Volume Profile (成交量分佈與交易密集區)</span>
                    <span class="vp-badge {vp_badge_class}">{vp['relation_label']}</span>
                </div>
                <div class="vp-metrics-row font-mono">
                    <div>POC 最大量核心價: <strong class="text-bear">{vp['poc_price']:.2f} 元</strong></div>
                    <div>價值區間 (Value Area 70%): <strong style="color:var(--text-primary);">{vp['va_low']:.2f} ~ {vp['va_high']:.2f} 元</strong></div>
                </div>
                <div class="vp-pos-desc">
                    💡 <strong>定價與避巴邏輯：</strong>{vp['pos_desc']}
                </div>
            </div>
            """
        else:
            vp_html = ""

        if w['has_warrants'] and w['tot_amt_wan'] > 0:
            warrant_html = f"""
            <div class="warrant-box">
                <div class="warrant-title">
                    <span>🎯 個股關聯權證多空分析 (Warrant Flow)</span>
                    <span class="warrant-tag font-bold">{w['sentiment']}</span>
                </div>
                <div class="warrant-grid">
                    <div class="warrant-item">
                        <span class="w-label">認購成交總額</span>
                        <span class="w-val text-bull">{w['call_amt_wan']:,} 萬元 <small>({w['call_pct']}%, {w['call_cnt']}檔)</small></span>
                    </div>
                    <div class="warrant-item">
                        <span class="w-label">認售成交總額</span>
                        <span class="w-val text-bear">{w['put_amt_wan']:,} 萬元 <small>({w['put_pct']}%, {w['put_cnt']}檔)</small></span>
                    </div>
                    <div class="warrant-item">
                        <span class="w-label">權證多空金額比</span>
                        <span class="w-val font-mono">認購 {w['call_pct']}% : 認售 {w['put_pct']}%</span>
                    </div>
                </div>
            </div>
            """
        else:
            warrant_html = f"""
            <div class="warrant-box warrant-box-empty">
                <span class="warrant-tag">{w['sentiment']}</span>
            </div>
            """
            
        xiaoge_html = render_xiaoge_warrants_html(x.get('xiaoge_warrants', []), opt_type_label="認售 PUT")

        short_cards_html += f"""
        <div class="stock-card card-short">
            <div class="card-header">
                <div class="stock-title-group">
                    <span class="rank-tag rank-tag-short">SHORT #{i}</span>
                    <a href="stock_{x['id']}.html" class="stock-title-link" title="點擊進入 {x['id']} {x['name']} (K線 / 九轉序列 / 13不連續 / 每日權證資金流)">
                        <span class="stock-id">{x['id']}</span>
                        <span class="stock-name">{x['name']}</span>
                        <span class="stock-market">{x['market']}</span>
                        <span class="stock-jump-badge">📊 個股K線/九轉/權證 ↗</span>
                    </a>
                </div>
                <div class="stock-price-group">
                    <span class="price-val text-bear">{x['close']:.2f}</span>
                    <span class="ret-badge ret-bear">破 60MA 季線 {x['ma60']:.2f}</span>
                </div>
            </div>
            
            <div class="chips-grid">
                <div class="chip-item">
                    <span class="chip-label">外資 5 日</span>
                    <span class="chip-val text-bear">{x['f_5d']:+,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">融資套牢</span>
                    <span class="chip-val text-bear">+{x['m_chg5']:,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">借券佔比</span>
                    <span class="chip-val text-bear">{x['sbl_ratio']}% (暴增)</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">當日借賣</span>
                    <span class="chip-val text-bear">{x['sbl_sell_today']:,} 張</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">均線下彎</span>
                    <span class="chip-val font-mono">20M:{x['ma20']:.1f} | 60M:{x['ma60']:.1f}</span>
                </div>
                <div class="chip-item">
                    <span class="chip-label">真實波幅</span>
                    <span class="chip-val font-mono">ATR(14)={x['atr14']:.2f}</span>
                </div>
            </div>
            
            {vp_html}
            {warrant_html}
            {xiaoge_html}
            
            <div class="execution-box box-short">
                <div class="exec-title">
                    <span>⚡ 模組 3：籌碼密集區遇阻放空與風控指示</span>
                    <span class="rr-tag">風報比 1 : {x['rr_ratio']}</span>
                </div>
                <div class="exec-grid">
                    <div class="exec-col">
                        <span class="exec-label">🎯 密集區遇阻放空點</span>
                        <span class="exec-val text-bear">{x['short_entry']:.2f} 元</span>
                        <span class="exec-sub">{x.get('short_desc', f"跌破前低 {x['prev_low']:.2f} 打入空單")}</span>
                    </div>
                    <div class="exec-col">
                        <span class="exec-label">🛑 密集區防守停損</span>
                        <span class="exec-val text-bear">{x['stop_loss']:.2f} 元</span>
                        <span class="exec-sub">停損空間 +{x['stop_pct']}%</span>
                    </div>
                    <div class="exec-col">
                        <span class="exec-label">🏆 空單回補目標</span>
                        <span class="exec-val text-bull">{x['take_profit']:.2f} 元</span>
                        <span class="exec-sub">回補利潤 -{x['profit_pct']}%</span>
                    </div>
                </div>
                <div class="exec-warning">
                    ⚠️ <strong>空單出場警示：</strong>{x['exit_rule']}
                </div>
            </div>
        </div>
        """

    # 組合複製用的作戰計畫字串 (含 Volume Profile 與 權證小哥首選標的)
    long_plan_items = []
    for i, x in enumerate(longs, 1):
        xw = x.get('xiaoge_warrants', [])
        w_rec = f"首選權證: {xw[0]['warrant_id']} {xw[0]['warrant_name']}(差槓比{xw[0]['diff_lever_ratio']:.3f}%, 槓桿{xw[0]['leverage']}x, 天數{xw[0]['period']}天)" if xw else "權證: 無合規標的(建議直接操作現股)"
        if x.get('volume_profile'):
            long_plan_items.append(f"#{i} {x['id']} {x['name']} | 現價: {x['close']:.2f} | 密集區進場: {x['entry_price']:.2f} | 停損: {x['stop_loss']:.2f} (-{x['stop_pct']}%) | 目標: {x['take_profit']:.2f} (+{x['profit_pct']}%) | POC: {x['volume_profile']['poc_price']:.2f} | {w_rec}")
        else:
            long_plan_items.append(f"#{i} {x['id']} {x['name']} | 進場: {x['entry_price']:.2f} | 停損: {x['stop_loss']:.2f} (-{x['stop_pct']}%) | 目標: {x['take_profit']:.2f} (+{x['profit_pct']}%) | {w_rec}")
    long_plan_lines = "\n".join(long_plan_items)

    short_plan_items = []
    for i, x in enumerate(shorts, 1):
        xw = x.get('xiaoge_warrants', [])
        w_rec = f"首選權證: {xw[0]['warrant_id']} {xw[0]['warrant_name']}(差槓比{xw[0]['diff_lever_ratio']:.3f}%, 槓桿{xw[0]['leverage']}x, 天數{xw[0]['period']}天)" if xw else "權證: 無合規標的(建議直接操作現股)"
        if x.get('volume_profile'):
            short_plan_items.append(f"#{i} {x['id']} {x['name']} | 現價: {x['close']:.2f} | 密集區放空: {x['short_entry']:.2f} | 停損: {x['stop_loss']:.2f} (+{x['stop_pct']}%) | 回補: {x['take_profit']:.2f} (-{x['profit_pct']}%) | POC: {x['volume_profile']['poc_price']:.2f} | {w_rec}")
        else:
            short_plan_items.append(f"#{i} {x['id']} {x['name']} | 放空: {x['short_entry']:.2f} | 停損: {x['stop_loss']:.2f} (+{x['stop_pct']}%) | 回補: {x['take_profit']:.2f} (-{x['profit_pct']}%) | {w_rec}")
    short_plan_lines = "\n".join(short_plan_items)

    long_sec_title = f"🟢【做多標的 Top {len(longs)} (Volume Profile 90日密集區定價 + 權證小哥嚴選推薦)】" if longs else "🟢【做多標的池 (多方 0 檔)】"
    long_sec_content = long_plan_lines if longs else f"大盤處於偏空格局 ({radar['composite_score']}分)，啟動避險防禦機制，全面暫停做多選股。"

    short_sec_title = f"🔴【反向做空標的 Top {len(shorts)} (Volume Profile 90日密集區破位放空 + 權證小哥嚴選推薦)】" if shorts else "🔴【反向做空標的池 (空方 0 檔)】"
    short_sec_content = short_plan_lines if shorts else f"大盤處於中性偏多位階 ({radar['composite_score']}分)，啟動順勢集中做多機制，暫停逆勢放空。"

    copy_text = f"""【台股投行機構 3 模組實戰計畫】基準日: {m1['date']}
============================================================
[模組 1: 市場狀態] {m1['regime_title']} | 總曝險上限: {m1['exposure_limit']}
市場季線寬度: {m1['breadth_pct']}% | 加權維持率: {m1['margin']['twse_maint_ratio']}% | 櫃買維持率: {m1['margin']['tpex_maint_ratio']}%
大盤融資金額: 加權 {m1['margin']['twse_bal_yi']:,}億 ({m1['margin']['twse_chg_yi']:+,}億) | 櫃買 {m1['margin']['tpex_bal_yi']:,}億 ({m1['margin']['tpex_chg_yi']:+,}億)
TX 特法結構: 前五大 {m1['tx_details']['top5_spec_all']:+,}口 (近月 {m1['tx_details']['top5_spec_near']:+,} / 遠月 {m1['tx_details']['top5_spec_far']:+,})
外資期貨淨空單: {m1['tx_details']['foreign_net_oi']:,}口 ({m1['tx_details']['foreign_net_amt_yi']:,}億元)
[溫度計與聯動配置] 評分: {radar['composite_score']}分 ({radar['regime']}) | 聯動: {radar['allocation_label']} | 認購佔比: {wm['call_ratio']}%

{long_sec_title}
{long_sec_content}

{short_sec_title}
{short_sec_content}
============================================================"""

    copy_json = json.dumps(copy_text, ensure_ascii=False)

    # 建立多方與空方獨立渲染區塊 (支援偏多 Top 10/空0、震盪各5、偏空空10/多0)
    if longs:
        long_section_html = f"""
        <!-- Module 2 & 3: Long Targets -->
        <div class="section-header">
            <div>
                <div class="section-title">
                    <span style="color: var(--bull-red);">🟢 模組 2 & 3：做多標的池 Top {len(longs)}</span>
                    <span style="font-size: 13px; background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 2px 8px; border-radius: 6px;">大盤多空位階：{radar['regime']} ｜ 順勢集中做多 ｜ 90日 Volume Profile 密集區定價 ｜ 權證小哥 5 大指標嚴選</span>
                </div>
                <div class="section-desc">篩選條件：站上 60MA、近 20 日漲幅前 20% 分位數、投信與外資大買、借券回補、融資沉澱，且<strong>保證具備活躍權證交易（無權證者自動排除並向下遞補）</strong>。</div>
            </div>
        </div>
        
        <div class="cards-list">
            {long_cards_html}
        </div>
        """
    else:
        long_section_html = f"""
        <!-- Module 2 & 3: Long Targets (Empty on Bearish) -->
        <div class="section-header">
            <div>
                <div class="section-title">
                    <span style="color: var(--bull-red);">🟢 模組 2 & 3：做多標的池</span>
                    <span style="font-size: 13px; background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 2px 8px; border-radius: 6px;">大盤偏空破位 ｜ 量化風控暫停做多</span>
                </div>
            </div>
        </div>
        <div class="empty-regime-card">
            <div class="empty-regime-title">🛡️ 風控機制啟動：大盤處於「{radar['regime']}」格局，已自動暫停做多選股 (多方 0 檔)</div>
            <div class="empty-regime-desc">
                當前立體多空溫度計僅 <strong>{radar['composite_score']} 分</strong>。依照投行機構量化風控紀律：<strong>弱勢偏空格局嚴禁逆勢接刀做多</strong>，全部資源切換至反向放空避險防禦！
            </div>
        </div>
        """

    if shorts:
        short_section_html = f"""
        <!-- Module 2 & 3: Short Targets -->
        <div class="section-header">
            <div>
                <div class="section-title">
                    <span style="color: var(--bear-green);">🔴 模組 2 & 3：反向做空標的池 Top {len(shorts)}</span>
                    <span style="font-size: 13px; background: rgba(16, 185, 129, 0.15); color: #10b981; padding: 2px 8px; border-radius: 6px;">大盤多空位階：{radar['regime']} ｜ 弱勢空單避險 ｜ 90日 Volume Profile 破位空點 ｜ 權證小哥 5 大指標嚴選</span>
                </div>
                <div class="section-desc">篩選條件：跌破 60MA 與 20MA、外資大幅拋售、散戶融資逆勢接刀、借券賣出佔比高，且<strong>保證具備活躍權證交易（無權證者自動排除並向下遞補）</strong>。</div>
            </div>
        </div>
        
        <div class="cards-list">
            {short_cards_html}
        </div>
        """
    else:
        short_section_html = f"""
        <!-- Module 2 & 3: Short Targets (Empty on Bullish) -->
        <div class="section-header">
            <div>
                <div class="section-title">
                    <span style="color: var(--bear-green);">🔴 模組 2 & 3：反向做空標的池</span>
                    <span style="font-size: 13px; background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 6px;">多頭格局主導 ｜ 暫停逆勢放空 (空方 0 檔)</span>
                </div>
            </div>
        </div>
        <div class="empty-regime-card">
            <div class="empty-regime-title">🛡️ 風控機制啟動：大盤處於「{radar['regime']}」強勢格局，暫停反向做空選股 (空方 0 檔)</div>
            <div class="empty-regime-desc">
                當前立體多空溫度計評分達 <strong>{radar['composite_score']} 分</strong>，全市場認購權證佔比高達 <strong>{wm['call_ratio']}%</strong>，且期貨特法主力多單護盤。<br>
                依照投行機構量化風控紀律：<strong>多頭格局嚴禁逆勢做空被軋</strong>，全部火力集中於做多標的池 Top {len(longs)} 檔！
            </div>
        </div>
        """

    # 純原生自足 HTML5 範本 (雙欄頂部配置: 模組 1 + 溫度計，內建純 SVG 向量儀表盤)
    html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>投行機構 3 模組市場狀態與立體溫度計系統 (含全市場與個股權證分析)</title>
    <style>
        :root {{
            --bg-main: #0a0e17;
            --bg-card: #121826;
            --bg-card-hover: #172033;
            --border-color: #1e293b;
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --bull-red: #ef4444;
            --bear-green: #10b981;
            --warn-amber: #f59e0b;
            --accent-blue: #38bdf8;
            --indigo-accent: #6366f1;
        }}
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        body {{
            background-color: var(--bg-main);
            color: var(--text-primary);
            padding: 24px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 1440px;
            margin: 0 auto;
        }}
        
        /* Header */
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-left h1 {{
            font-size: 24px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #ffffff;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .header-left p {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        .header-right {{
            display: flex;
            gap: 12px;
            align-items: center;
        }}
        .date-badge {{
            background: #1e293b;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            color: var(--accent-blue);
            border: 1px solid #334155;
        }}
        .btn-copy {{
            background: #2563eb;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        .btn-copy:hover {{
            background: #1d4ed8;
            box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
        }}
        
        /* Top 50-50 Hero Grid */
        .hero-split-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 36px;
        }}
        @media (max-width: 1024px) {{
            .hero-split-grid {{ grid-template-columns: 1fr; }}
        }}
        
        .hero-card {{
            background: linear-gradient(135deg, #121826 0%, #151d2e 100%);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 22px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }}
        .hero-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .module-tag {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--indigo-accent);
            background: rgba(99, 102, 241, 0.15);
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .hero-title-wrap {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 8px;
        }}
        .hero-title {{
            font-size: 24px;
            font-weight: 800;
        }}
        
        .badge-bull {{ background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; }}
        .badge-bear {{ background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; }}
        .badge-neutral {{ background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; }}
        
        /* Gauges Layout */
        .gauge-inner-grid {{
            display: grid;
            grid-template-columns: 190px 1fr;
            gap: 16px;
            align-items: center;
            margin-bottom: 16px;
        }}
        @media (max-width: 600px) {{
            .gauge-inner-grid {{ grid-template-columns: 1fr; }}
        }}
        .gauge-box {{
            text-align: center;
            background: rgba(10, 14, 23, 0.6);
            padding: 12px;
            border-radius: 12px;
            border: 1px solid #1e293b;
        }}
        
        .sub-metrics-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        .sub-metric-item {{
            background: rgba(18, 24, 38, 0.8);
            border: 1px solid var(--border-color);
            padding: 10px 12px;
            border-radius: 10px;
        }}
        .sub-metric-label {{
            font-size: 11px;
            color: var(--text-muted);
            display: block;
        }}
        .sub-metric-val {{
            font-size: 16px;
            font-weight: 700;
            margin-top: 2px;
            color: #ffffff;
        }}
        .sub-metric-desc {{
            font-size: 10px;
            color: var(--text-secondary);
            margin-top: 2px;
            display: block;
        }}
        
        /* Dynamic Allocation Controller Panel */
        .allocation-panel {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid #1e293b;
            border-radius: 10px;
            padding: 10px 14px;
        }}
        .alloc-title-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 6px;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .alloc-badge {{
            font-size: 12px;
            font-weight: 800;
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.15);
            padding: 2px 8px;
            border-radius: 6px;
        }}
        .alloc-tag {{
            font-size: 10px;
            font-weight: 700;
            color: var(--text-muted);
            background: #1e293b;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .alloc-desc {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        .alloc-quota-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 8px;
        }}
        .alloc-quota-box {{
            padding: 6px 8px;
            border-radius: 8px;
            border: 1px solid #334155;
            background: rgba(30, 41, 59, 0.5);
            text-align: center;
        }}
        .quota-active-long {{
            border-color: rgba(239, 68, 68, 0.5);
            background: rgba(239, 68, 68, 0.1);
        }}
        .quota-active-short {{
            border-color: rgba(16, 185, 129, 0.5);
            background: rgba(16, 185, 129, 0.1);
        }}
        .quota-dormant {{
            opacity: 0.5;
        }}
        .quota-head {{
            font-size: 10px;
            color: var(--text-muted);
        }}
        .quota-val {{
            font-size: 14px;
            font-weight: 800;
            margin-top: 1px;
        }}
        .quota-active-long .quota-val {{ color: #ef4444; }}
        .quota-active-short .quota-val {{ color: #10b981; }}
        .quota-dormant .quota-val {{ color: var(--text-muted); }}
        .alloc-rule-strip {{
            font-size: 10px;
            color: var(--text-muted);
            border-top: 1px dashed rgba(255, 255, 255, 0.08);
            padding-top: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 4px;
        }}
        .rule-on {{
            color: #fbbf24;
            font-weight: 700;
        }}
        .rule-sep {{
            color: #334155;
        }}
        
        /* Empty Regime Card (When Longs or Shorts are 0) */
        .empty-regime-card {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 40px;
            text-align: center;
        }}
        .empty-regime-title {{
            font-size: 16px;
            font-weight: 800;
            color: #38bdf8;
            margin-bottom: 8px;
        }}
        .empty-regime-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        /* Warrant Special Box in Radar */
        .warrant-radar-box {{
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid #334155;
            border-radius: 10px;
            padding: 12px 14px;
            margin-top: 14px;
        }}
        .w-radar-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 8px;
        }}
        .w-radar-stats {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            flex-wrap: wrap;
            gap: 8px;
        }}

        /* Margin Matrix Box */
        .margin-matrix-box {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 12px 14px;
            margin-top: 12px;
        }}
        .margin-matrix-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .margin-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }}
        @media (max-width: 550px) {{
            .margin-grid {{ grid-template-columns: 1fr; }}
        }}
        .margin-cell {{
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid #334155;
            padding: 8px 10px;
            border-radius: 8px;
        }}
        .margin-cell-title {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 600;
        }}
        .margin-cell-main {{
            font-size: 15px;
            font-weight: 700;
            color: #ffffff;
            margin-top: 2px;
        }}
        .margin-cell-sub {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        /* TX Futures Structure Box */
        .tx-futures-box {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 12px 14px;
            margin-top: 12px;
        }}
        .tx-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .tx-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            margin-bottom: 8px;
        }}
        @media (max-width: 650px) {{
            .tx-grid {{ grid-template-columns: 1fr; }}
        }}
        .tx-card {{
            background: rgba(30, 41, 59, 0.5);
            border: 1px solid #334155;
            padding: 8px 10px;
            border-radius: 8px;
        }}
        .tx-card-label {{
            font-size: 11px;
            color: var(--text-muted);
            display: block;
        }}
        .tx-card-val {{
            font-size: 14px;
            font-weight: 700;
            margin-top: 2px;
            display: block;
        }}
        .tx-card-sub {{
            font-size: 10px;
            color: var(--text-secondary);
            margin-top: 2px;
            display: block;
        }}
        .tx-desc-note {{
            font-size: 11px;
            color: var(--text-secondary);
            background: rgba(30, 41, 59, 0.35);
            border-left: 3px solid var(--accent-blue);
            padding: 6px 10px;
            border-radius: 4px;
            line-height: 1.45;
            margin-top: 6px;
        }}

        /* Volume Profile Box */
        .vp-box {{
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }}
        .vp-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-blue);
            margin-bottom: 6px;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .vp-badge {{
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
        }}
        .vp-badge-support {{
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .vp-badge-resistance {{
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}
        .vp-badge-inside {{
            background: rgba(245, 158, 11, 0.15);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}
        .vp-metrics-row {{
            display: flex;
            gap: 16px;
            font-size: 12px;
            margin-bottom: 6px;
            flex-wrap: wrap;
        }}
        .vp-pos-desc {{
            font-size: 11px;
            color: var(--text-secondary);
            line-height: 1.45;
            border-top: 1px dashed rgba(255, 255, 255, 0.08);
            padding-top: 6px;
            margin-top: 4px;
        }}
        
        .hero-banner {{
            margin-top: 12px;
            padding: 10px 14px;
            background: rgba(30, 41, 59, 0.5);
            border-left: 4px solid var(--warn-amber);
            border-radius: 6px;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        
        /* Section Dividers */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 800;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-desc {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        
        /* Stock Cards */
        .cards-list {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 18px;
            margin-bottom: 40px;
        }}
        .stock-card {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 14px;
            padding: 20px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .stock-card:hover {{
            border-color: #334155;
            background: var(--bg-card-hover);
        }}
        .card-long {{ border-left: 5px solid var(--bull-red); }}
        .card-short {{ border-left: 5px solid var(--bear-green); }}
        
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .stock-title-group {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .rank-tag {{
            font-size: 11px;
            font-weight: 800;
            padding: 3px 8px;
            border-radius: 6px;
        }}
        .stock-title-link {{
            display: inline-flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
            padding: 4px 10px;
            border-radius: 8px;
            transition: all 0.2s;
            cursor: pointer;
        }}
        .stock-title-link:hover {{
            background: rgba(59, 130, 246, 0.2);
            box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);
            transform: translateY(-1px);
        }}
        .stock-jump-badge {{
            font-size: 11px;
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.4);
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 700;
            transition: all 0.2s;
        }}
        .stock-title-link:hover .stock-jump-badge {{
            background: #3b82f6;
            color: #ffffff;
        }}
        .stock-id {{
            font-size: 20px;
            font-weight: 800;
            color: #ffffff;
        }}
        .stock-name {{
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .stock-market {{
            font-size: 11px;
            background: #1e293b;
            color: var(--text-muted);
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .stock-price-group {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .price-val {{
            font-size: 24px;
            font-weight: 800;
            font-family: monospace;
        }}
        .ret-badge {{
            font-size: 12px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
        }}
        .ret-bull {{ background: rgba(239, 68, 68, 0.15); color: #ef4444; }}
        .ret-bear {{ background: rgba(16, 185, 129, 0.15); color: #10b981; }}
        
        /* Chips Grid */
        .chips-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
            gap: 10px;
            margin-bottom: 14px;
            background: rgba(10, 14, 23, 0.5);
            padding: 12px;
            border-radius: 10px;
            border: 1px solid #1a2234;
        }}
        .chip-item {{
            display: flex;
            flex-direction: column;
        }}
        .chip-label {{
            font-size: 11px;
            color: var(--text-muted);
        }}
        .chip-val {{
            font-size: 13px;
            font-weight: 700;
            margin-top: 2px;
        }}
        
        /* Individual Warrant Box */
        .warrant-box {{
            background: rgba(99, 102, 241, 0.05);
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 14px;
        }}
        .warrant-box-empty {{
            background: rgba(255, 255, 255, 0.02);
            border-color: #1e293b;
            padding: 8px 14px;
            font-size: 12px;
            color: var(--text-muted);
        }}
        .warrant-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            color: var(--indigo-accent);
            margin-bottom: 8px;
            font-weight: 700;
        }}
        .warrant-tag {{
            font-size: 12px;
        }}
        .warrant-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
        }}
        .warrant-item {{
            display: flex;
            flex-direction: column;
        }}
        .w-label {{
            font-size: 11px;
            color: var(--text-muted);
        }}
        .w-val {{
            font-size: 13px;
            font-weight: 700;
            margin-top: 2px;
        }}
        
        /* Xiaoge Warrant Screener Section */
        .xiaoge-warrant-box {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(245, 158, 11, 0.35);
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }}
        .xiaoge-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .xiaoge-title {{
            font-size: 13px;
            font-weight: 800;
            color: #fbbf24;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .xiaoge-subtitle {{
            font-size: 11px;
            color: var(--text-secondary);
        }}
        .xiaoge-table-wrapper {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid #1e293b;
        }}
        .xiaoge-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
            text-align: left;
            background: rgba(10, 14, 23, 0.4);
        }}
        .xiaoge-table th {{
            background: #1e293b;
            color: var(--text-secondary);
            padding: 7px 10px;
            font-size: 11px;
            font-weight: 700;
            white-space: nowrap;
            border-bottom: 1px solid #334155;
        }}
        .xiaoge-table td {{
            padding: 7px 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            white-space: nowrap;
            vertical-align: middle;
        }}
        .xiaoge-table tr:last-child td {{
            border-bottom: none;
        }}
        .xiaoge-table tr:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}
        .badge-xiaoge-pass {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.25), rgba(217, 119, 6, 0.35));
            color: #fbbf24;
            border: 1px solid #f59e0b;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 10.5px;
            font-weight: 800;
            display: inline-block;
        }}
        .badge-xiaoge-relax {{
            background: rgba(56, 189, 248, 0.18);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.45);
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 10.5px;
            font-weight: 800;
            display: inline-block;
        }}
        .badge-xiaoge-alt {{
            background: rgba(100, 116, 139, 0.2);
            color: var(--text-secondary);
            border: 1px solid #475569;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            display: inline-block;
        }}
        .badge-diff-lever {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .badge-diff-lever-relax {{
            background: rgba(56, 189, 248, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(56, 189, 248, 0.35);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .badge-diff-lever-high {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 700;
        }}
        .xiaoge-empty-strict {{
            background: rgba(245, 158, 11, 0.06);
            border: 1px dashed rgba(245, 158, 11, 0.35);
            border-radius: 8px;
            padding: 12px 14px;
        }}
        .empty-strict-title {{
            color: #fbbf24;
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .empty-strict-desc {{
            color: var(--text-secondary);
            font-size: 11px;
            line-height: 1.5;
        }}
        .xiaoge-table-footer {{
            padding: 8px 10px;
            font-size: 11px;
            color: #fbbf24;
            background: rgba(245, 158, 11, 0.06);
            border-top: 1px dashed rgba(245, 158, 11, 0.25);
            border-radius: 0 0 8px 8px;
        }}
        
        /* Execution Box */
        .execution-box {{
            padding: 16px;
            border-radius: 10px;
            border: 1px solid;
        }}
        .box-long {{
            background: rgba(239, 68, 68, 0.04);
            border-color: rgba(239, 68, 68, 0.2);
        }}
        .box-short {{
            background: rgba(16, 185, 129, 0.04);
            border-color: rgba(16, 185, 129, 0.2);
        }}
        .exec-title {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            font-size: 12px;
            font-weight: 700;
            color: var(--accent-blue);
        }}
        .rr-tag {{
            background: #1e293b;
            color: #ffffff;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 800;
        }}
        .exec-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 12px;
        }}
        .exec-col {{
            display: flex;
            flex-direction: column;
        }}
        .exec-label {{
            font-size: 11px;
            color: var(--text-muted);
        }}
        .exec-val {{
            font-size: 18px;
            font-weight: 800;
            font-family: monospace;
            margin-top: 2px;
        }}
        .exec-sub {{
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}
        .exec-warning {{
            font-size: 12px;
            color: var(--text-secondary);
            border-top: 1px dashed rgba(255, 255, 255, 0.1);
            padding-top: 10px;
            margin-top: 6px;
        }}
        
        /* Utility */
        .text-bull {{ color: var(--bull-red); }}
        .text-bear {{ color: var(--bear-green); }}
        .font-mono {{ font-family: monospace; }}
        .font-bold {{ font-weight: 700; }}
        .badge-normal {{ color: #10b981; font-weight: 700; font-size: 13px; }}
        .badge-alert {{ color: #ef4444; font-weight: 700; font-size: 13px; }}
        
        /* RWD: 響應式優化 (手機 / 平板 / 電腦自動校正) */
        html, body {{
            overflow-x: hidden;
            max-width: 100%;
            -webkit-text-size-adjust: 100%;
        }}
        @media (max-width: 900px) {{
            body {{
                padding: 14px 10px;
            }}
            .header {{
                flex-direction: column;
                align-items: stretch;
                gap: 12px;
                padding-bottom: 14px;
                margin-bottom: 16px;
            }}
            .header-left h1 {{
                font-size: 20px;
                flex-wrap: wrap;
                gap: 8px;
            }}
            .header-left p {{
                font-size: 12px;
            }}
            .header-right {{
                width: 100%;
                display: flex;
                justify-content: space-between;
                gap: 8px;
            }}
            .date-badge {{
                padding: 6px 10px;
                font-size: 12px;
                flex-shrink: 0;
            }}
            .btn-copy {{
                flex: 1;
                justify-content: center;
                padding: 8px 12px;
                font-size: 12px;
            }}
            .hero-split-grid {{
                grid-template-columns: 1fr;
                gap: 16px;
                margin-bottom: 24px;
            }}
            .hero-card {{
                padding: 16px 14px;
            }}
            .hero-title {{
                font-size: 20px;
            }}
            .gauge-inner-grid {{
                grid-template-columns: 1fr;
                gap: 14px;
            }}
            .gauge-box {{
                padding: 10px;
                max-width: 220px;
                margin: 0 auto;
                width: 100%;
            }}
            .sub-metrics-grid {{
                grid-template-columns: 1fr 1fr;
                gap: 8px;
            }}
            .sub-metric-item {{
                padding: 8px 10px;
            }}
            .sub-metric-val {{
                font-size: 15px;
            }}
            .w-radar-stats {{
                flex-direction: column;
                gap: 6px;
                font-size: 12px;
            }}
            .stock-card {{
                padding: 14px 12px;
            }}
            .card-header {{
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }}
            .stock-price-group {{
                width: 100%;
                justify-content: space-between;
            }}
            .stock-id {{
                font-size: 18px;
            }}
            .stock-name {{
                font-size: 16px;
            }}
            .price-val {{
                font-size: 22px;
            }}
            .chips-grid {{
                grid-template-columns: repeat(3, 1fr);
                gap: 6px;
                padding: 8px;
            }}
            .chip-item {{
                min-width: 0;
            }}
            .chip-label {{
                font-size: 10px;
            }}
            .chip-val {{
                font-size: 12px;
                word-break: break-all;
            }}
            .warrant-box {{
                padding: 10px 12px;
            }}
            .warrant-grid {{
                grid-template-columns: 1fr;
                gap: 8px;
            }}
            .exec-grid {{
                grid-template-columns: 1fr;
                gap: 10px;
            }}
            .exec-val {{
                font-size: 16px;
            }}
        }}

        @media (max-width: 480px) {{
            .sub-metrics-grid {{
                grid-template-columns: 1fr;
            }}
            .chips-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            .header-left h1 {{
                font-size: 17px;
            }}
            .stock-title-group {{
                gap: 6px;
                flex-wrap: wrap;
            }}
            .rank-tag {{
                padding: 2px 6px;
                font-size: 10px;
            }}
        }}

        .footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            padding-top: 20px;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <div class="header-left">
                <h1>🏛️ 投行機構 3 模組市場狀態與立體溫度計系統</h1>
                <p>Macro & Breadth Regime • 6-Pillar Radar (with Whole-Market Warrants) • Stock Ranking & ATR Execution</p>
            </div>
            <div class="header-right">
                <div class="date-badge">基準分析日: {m1['date']}</div>
                <button class="btn-copy" onclick="copyPlan()">📋 複製今日多空作戰計畫</button>
            </div>
        </div>
        
        <!-- Top 50-50 Hero Grid -->
        <div class="hero-split-grid">
            <!-- Left Panel: Module 1 Breadth Filter -->
            <div class="hero-card">
                <div>
                    <div class="hero-card-header">
                        <span class="module-tag">MODULE 1: MACRO & BREADTH REGIME</span>
                        {kill_switch_badge}
                    </div>
                    <div class="hero-title-wrap">
                        <span class="hero-title" style="color: {regime_color};">{m1['regime_title']}</span>
                    </div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 16px;">
                        總持股水位上限建議：<strong style="color: {regime_color}; font-size: 15px;">{m1['exposure_limit']}</strong>
                    </div>
                    
                    <div class="gauge-inner-grid">
                        <div class="gauge-box">
                            {breadth_svg}
                            <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                                季線寬度: <strong style="color:#ffffff;">{m1['breadth_pct']}%</strong>
                            </div>
                        </div>
                        <div class="sub-metrics-grid">
                            <div class="sub-metric-item">
                                <span class="sub-metric-label">站上 60MA 個股</span>
                                <div class="sub-metric-val">{m1['above_60ma_count']} <small style="font-size:11px; color:var(--text-muted);">/ {m1['valid_stocks_count']}</small></div>
                                <span class="sub-metric-desc">季線擴散度 {m1['breadth_pct']}%</span>
                            </div>
                            <div class="sub-metric-item">
                                <span class="sub-metric-label">全域清倉熔斷</span>
                                <div class="sub-metric-val" style="font-size: 13px; color: #10b981;">🟢 正常運作</div>
                                <span class="sub-metric-desc">寬度 &lt; 40% 觸發熔斷</span>
                            </div>
                        </div>
                    </div>

                    <!-- 大盤融資餘額與維持率矩陣 (上市+上櫃金額與維持率) -->
                    <div class="margin-matrix-box">
                        <div class="margin-matrix-header">
                            <span>🏦 全市場信用融資餘額與維持率矩陣 (Margin & Leverage)</span>
                            <span class="badge-normal" style="font-size:11px;">{m1['margin_status_desc']}</span>
                        </div>
                        <div class="margin-grid">
                            <div class="margin-cell">
                                <div class="margin-cell-title">加權指數 (上市 TWSE)</div>
                                <div class="margin-cell-main font-mono">
                                    {m1['margin']['twse_bal_yi']:,} 億元 
                                    <small class="{'text-bull' if m1['margin']['twse_chg_yi']>0 else 'text-bear'}" style="font-size:12px;">({m1['margin']['twse_chg_yi']:+,} 億)</small>
                                </div>
                                <div class="margin-cell-sub">
                                    融資維持率: <strong class="text-bull font-mono">{m1['margin']['twse_maint_ratio']}%</strong> (擔保 {m1['margin']['twse_col_yi']:,} 億)
                                </div>
                            </div>
                            <div class="margin-cell">
                                <div class="margin-cell-title">櫃買指數 (上櫃 TPEx)</div>
                                <div class="margin-cell-main font-mono">
                                    {m1['margin']['tpex_bal_yi']:,} 億元 
                                    <small class="{'text-bull' if m1['margin']['tpex_chg_yi']>0 else 'text-bear'}" style="font-size:12px;">({m1['margin']['tpex_chg_yi']:+,} 億)</small>
                                </div>
                                <div class="margin-cell-sub">
                                    融資維持率: <strong class="text-bull font-mono">{m1['margin']['tpex_maint_ratio']}%</strong> (擔保 {m1['margin']['tpex_col_yi']:,} 億)
                                </div>
                            </div>
                        </div>
                        <div style="margin-top: 8px; font-size: 11px; color: var(--text-secondary); display: flex; justify-content: space-between; border-top: 1px dashed rgba(255,255,255,0.08); padding-top: 6px; flex-wrap: wrap; gap: 4px;">
                            <span>全市場總融資: <strong class="font-mono text-bull">{m1['margin']['total_bal_yi']:,} 億元</strong> ({m1['margin']['total_chg_yi']:+,} 億)</span>
                            <span>全體維持率: <strong class="font-mono text-bull">{m1['margin']['total_maint_ratio']}%</strong> (斷頭警戒線 130% / 140%)</span>
                        </div>
                    </div>

                    <!-- TX 臺指期特法主力結構與外資對峙 -->
                    <div class="tx-futures-box">
                        <div class="tx-header">
                            <span>⚔️ TX 臺指期特法主力結構與外資對峙 (Futures OI Dynamic)</span>
                            <span class="font-mono" style="font-size:11px; color:var(--text-muted);">市場未平倉: {m1['tx_details']['market_oi']:,} 口</span>
                        </div>
                        <div class="tx-grid">
                            <div class="tx-card">
                                <span class="tx-card-label">前五大特法 (近月/遠月)</span>
                                <span class="tx-card-val {'text-bull' if m1['tx_details']['top5_spec_all']>=0 else 'text-bear'} font-mono">
                                    {m1['tx_details']['top5_spec_all']:+,} 口
                                </span>
                                <span class="tx-card-sub font-mono">近月 {m1['tx_details']['top5_spec_near']:+,} | 遠月 {m1['tx_details']['top5_spec_far']:+,}</span>
                            </div>
                            <div class="tx-card">
                                <span class="tx-card-label">前十大特法 (近月/遠月)</span>
                                <span class="tx-card-val {'text-bull' if m1['tx_details']['top10_spec_all']>=0 else 'text-bear'} font-mono">
                                    {m1['tx_details']['top10_spec_all']:+,} 口
                                </span>
                                <span class="tx-card-sub font-mono">近月 {m1['tx_details']['top10_spec_near']:+,} | 遠月 {m1['tx_details']['top10_spec_far']:+,}</span>
                            </div>
                            <div class="tx-card">
                                <span class="tx-card-label">外資期貨淨留倉 (現貨避險)</span>
                                <span class="tx-card-val text-bear font-mono">
                                    {m1['tx_details']['foreign_net_oi']:,} 口
                                </span>
                                <span class="tx-card-sub font-mono">金額: {m1['tx_details']['foreign_net_amt_yi']:,} 億元</span>
                            </div>
                        </div>
                        <div class="tx-desc-note">
                            📌 <strong>法人籌碼對峙動態：</strong>{m1['tx_details']['dynamic_desc']}
                        </div>
                    </div>
                </div>
                
                <div class="hero-banner">
                    <strong>策略動作：</strong>{m1['regime_desc']}
                </div>
            </div>
            
            <!-- Right Panel: Market Regime Radar & Dynamic Allocation Controller -->
            <div class="hero-card">
                <div>
                    <div class="hero-card-header">
                        <span class="module-tag" style="color: var(--accent-blue); background: rgba(56, 189, 248, 0.15);">MARKET REGIME RADAR (DYNAMIC ALLOCATION)</span>
                        <span class="date-badge" style="font-size: 11px; padding: 3px 8px;">權證基準: {wm['date']}</span>
                    </div>
                    <div class="hero-title-wrap">
                        <span class="hero-title" style="color: {radar['color']};">立體多空溫度計: {radar['composite_score']} 分</span>
                    </div>
                    <div style="font-size: 13px; color: var(--text-secondary); margin-top: 4px; margin-bottom: 16px;">
                        多空位階：<strong style="color: {radar['color']}; font-size:14px;">{radar['regime']}</strong> ({radar['desc']})
                    </div>
                    
                    <div class="gauge-inner-grid">
                        <div class="gauge-box">
                            {radar_svg}
                            <div style="font-size: 11px; color: var(--text-secondary); margin-top: 2px;">
                                綜合評分: <strong style="color:{radar['color']}; font-size:13px;">{radar['composite_score']} 分</strong>
                            </div>
                        </div>
                        <div class="allocation-panel">
                            <div class="alloc-title-row">
                                <span class="alloc-badge">⚡ {radar['allocation_label']}</span>
                                <span class="alloc-tag font-mono">{radar['allocation_mode']}</span>
                            </div>
                            <div class="alloc-desc font-mono">
                                💡 <strong>聯動決策：</strong>{radar['allocation_desc']}
                            </div>
                            <div class="alloc-quota-row font-mono">
                                <div class="alloc-quota-box {'quota-active-long' if radar['target_longs']>0 else 'quota-dormant'}">
                                    <div class="quota-head">🟢 做多標的池</div>
                                    <div class="quota-val">Top {radar['target_longs']} 檔</div>
                                </div>
                                <div class="alloc-quota-box {'quota-active-short' if radar['target_shorts']>0 else 'quota-dormant'}">
                                    <div class="quota-head">🔴 反向做空池</div>
                                    <div class="quota-val">{f"Top {radar['target_shorts']} 檔" if radar['target_shorts']>0 else "0 檔 (暫停放空)"}</div>
                                </div>
                            </div>
                            <div class="alloc-rule-strip font-mono">
                                <span class="{'rule-on' if radar['composite_score']>=55 else ''}">偏多(&ge;55分)➜多10/空0</span>
                                <span class="rule-sep">|</span>
                                <span class="{'rule-on' if 45<=radar['composite_score']<55 else ''}">震盪(45~55分)➜各5檔</span>
                                <span class="rule-sep">|</span>
                                <span class="{'rule-on' if radar['composite_score']<45 else ''}">偏空(&lt;45分)➜空10/多0</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Whole-Market Warrant Flow Box (Retained & Highlighted) -->
                    <div class="warrant-radar-box">
                        <div class="w-radar-header">
                            <span>★ 大盤指數權證多空買賣總額指標 (Index Warrant Money Flow)</span>
                            <span class="text-bull font-bold">{wm['warrant_sentiment']}</span>
                        </div>
                        <div class="w-radar-stats">
                            <div>認購成交總額: <strong class="text-bull">{wm['call_amount_yi']} 億元</strong> ({wm['call_ratio']}%, {wm['call_count']:,}檔)</div>
                            <div>認售成交總額: <strong class="text-bear">{wm['put_amount_yi']} 億元</strong> ({wm['put_ratio']}%, {wm['put_count']:,}檔)</div>
                            <div>P/C 比率: <strong class="font-mono">{wm['pc_ratio']}</strong></div>
                        </div>
                    </div>
                </div>
                
                <div class="hero-banner" style="border-left-color: var(--accent-blue);">
                    <strong>溫度計解析與選股聯動：</strong>全市場權證總額達 {wm['total_amount_yi']} 億元，認購佔比高達 {wm['call_ratio']}%，游資多方情緒極高。大盤位階判定為【{radar['regime']}】，已啟動【{radar['allocation_label']}】，現貨做多標的池自動擴充至 Top {len(longs)} 檔，暫停逆勢放空！
                </div>
            </div>
        </div>
        
        {long_section_html}
        {short_section_html}
        
        <!-- Footer -->
        <div class="footer">
            TW-Stock Quantitative Research System • 100% 離線純自給自足 (純 SVG 向量圖形) • 產出時間: {now_str}
        </div>
    </div>

    <!-- 剪貼簿互動腳本 (原生 JavaScript，零外網依賴) -->
    <script>
        function copyPlan() {{
            const text = {copy_json};
            if (navigator.clipboard && window.isSecureContext) {{
                navigator.clipboard.writeText(text).then(function() {{
                    alert("✓ 今日多空作戰計畫 (含權證分析) 已成功複製至剪貼簿！可直接貼至 Line 或 筆記本。");
                }}).catch(function() {{
                    fallbackCopyText(text);
                }});
            }} else {{
                fallbackCopyText(text);
            }}
        }}

        function fallbackCopyText(text) {{
            const textArea = document.createElement("textarea");
            textArea.value = text;
            textArea.style.position = "fixed";
            textArea.style.left = "-999999px";
            textArea.style.top = "-999999px";
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();
            try {{
                const successful = document.execCommand('copy');
                if (successful) {{
                    alert("✓ 今日多空作戰計畫 (含權證分析) 已成功複製至剪貼簿！");
                }} else {{
                    alert("瀏覽器限制剪貼簿存取，請手動選取複製。");
                }}
            }} catch (err) {{
                alert("瀏覽器限制剪貼簿存取，請手動選取複製。");
            }}
            document.body.removeChild(textArea);
        }}
    </script>
</body>
</html>
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    # 同步輸出至 docs/index.html 與 index.html，供 GitHub Pages 直接作為網站首頁發布
    try:
        base_dir = os.path.dirname(os.path.abspath(output_path))
        docs_dir = os.path.join(base_dir, "docs")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
        with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        print(f"  [!] 同步寫入 GitHub Pages index.html 警告: {e}")
        
    print("=" * 75)
    print(f"  [+] 投行機構 3 模組離線儀表板 (含權證 & 純 SVG 儀表盤) 已成功生成: {output_path}")
    print(f"  * 基準交易日: {m1['date']}")
    print(f"  * 市場狀態: {m1['regime_title']} (總持股上限: {m1['exposure_limit']})")
    print(f"  * 多空溫度計: {radar['composite_score']} 分 ({radar['regime']})")
    print(f"  * 全市場權證: 總額 {wm['total_amount_yi']} 億元 (認購 {wm['call_ratio']}% : 認售 {wm['put_ratio']}%)")
    print(f"  * 做多標的 (Top 5 均含權證): {[x['id'] + ' ' + x['name'] for x in longs]}")
    print(f"  * 做空標的 (Top 5 均含權證): {[x['id'] + ' ' + x['name'] for x in shorts]}")
    print("=" * 75)

if __name__ == '__main__':
    generate_html()
