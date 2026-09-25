import re

with open('generate_quant_regime.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_func = '''def render_xiaoge_warrants_html(warrants, opt_type_label="認購 CALL"):
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
'''

pattern = r'def render_xiaoge_warrants_html.*?return f"""\n        <div class="xiaoge-warrant-box">.*?</div>\n        """'
code = re.sub(pattern, new_func, code, flags=re.DOTALL)

with open('generate_quant_regime.py', 'w', encoding='utf-8') as f:
    f.write(code)
