"""
Generate US Top 10 Giants vs Taiwan Supply Chain Dashboard Component
File: scripts/generate_us_giants_component.py
"""

import os
import json
import sqlite3
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'db', 'us_tw_supply_chain.db')

def generate_us_giants_html():
    if not os.path.exists(DB_PATH):
        return "<div style='color:red;'>Database us_tw_supply_chain.db not found.</div>"

    conn = sqlite3.connect(DB_PATH)
    
    # 讀取巨頭與排名
    df_giants = pd.read_sql("""
        SELECT g.*, m.total_partners_count, m.weighted_tw_mcap_influence_bil_twd, m.key_sector_focus
        FROM us_giants g
        JOIN giant_macro_impact m ON g.us_ticker = m.us_ticker
        ORDER BY m.weighted_tw_mcap_influence_bil_twd DESC
    """, conn)

    # 讀取全部關聯
    df_rel = pd.read_sql("""
        SELECT r.*, c.industry, c.est_market_cap_bil_twd
        FROM supply_chain_relations r
        JOIN tw_companies c ON r.tw_ticker = c.tw_ticker
        ORDER BY r.us_ticker, r.est_revenue_pct_mid DESC
    """, conn)

    # 讀取全部台廠
    df_tw = pd.read_sql("SELECT * FROM tw_companies ORDER BY est_market_cap_bil_twd DESC", conn)

    conn.close()

    # 轉為 JSON 供前端純原生 JS 即時互動
    giants_list = df_giants.to_dict(orient='records')
    rel_list = df_rel.to_dict(orient='records')
    tw_list = df_tw.to_dict(orient='records')

    giants_json = json.dumps(giants_list, ensure_ascii=False)
    rel_json = json.dumps(rel_list, ensure_ascii=False)
    tw_json = json.dumps(tw_list, ensure_ascii=False)

    html = f"""
    <!-- US Top 10 Giants Component -->
    <style>
        .us-giants-wrapper {{
            padding: 10px 0 30px 0;
            color: #e2e8f0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }}
        .giant-hero-banner {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%);
            border: 1px solid rgba(56, 189, 248, 0.25);
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 24px;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 16px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}
        .giant-hero-title {{
            font-size: 22px;
            font-weight: 800;
            color: #38bdf8;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .giant-hero-sub {{
            font-size: 13px;
            color: #94a3b8;
            margin-top: 4px;
        }}
        .giant-metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 12px;
            width: 100%;
            margin-top: 14px;
        }}
        .giant-stat-card {{
            background: rgba(17, 24, 39, 0.8);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 12px 16px;
        }}
        .giant-stat-val {{
            font-size: 20px;
            font-weight: 700;
            color: #f1f5f9;
        }}
        .giant-stat-lbl {{
            font-size: 12px;
            color: #64748b;
            margin-top: 2px;
        }}

        /* 巨頭卡片選擇列 */
        .giants-cards-scroll {{
            display: flex;
            gap: 12px;
            overflow-x: auto;
            padding-bottom: 12px;
            margin-bottom: 24px;
        }}
        .giants-cards-scroll::-webkit-scrollbar {{
            height: 6px;
        }}
        .giants-cards-scroll::-webkit-scrollbar-thumb {{
            background: #334155;
            border-radius: 3px;
        }}
        .giant-select-card {{
            flex: 0 0 160px;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 10px;
            padding: 14px 16px;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            overflow: hidden;
        }}
        .giant-select-card:hover {{
            border-color: #38bdf8;
            transform: translateY(-2px);
        }}
        .giant-select-card.active {{
            border-color: #38bdf8;
            background: linear-gradient(180deg, rgba(56, 189, 248, 0.15) 0%, rgba(17, 24, 39, 0.9) 100%);
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.25);
        }}
        .giant-badge-rank {{
            position: absolute;
            top: 8px;
            right: 8px;
            font-size: 11px;
            font-weight: 700;
            color: #64748b;
        }}
        .giant-card-ticker {{
            font-size: 18px;
            font-weight: 800;
            color: #f8fafc;
        }}
        .giant-card-name {{
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 8px;
        }}
        .giant-card-mcap {{
            font-size: 11px;
            color: #f59e0b;
            font-weight: 600;
        }}
        .giant-card-twcount {{
            font-size: 11px;
            color: #10b981;
            margin-top: 4px;
        }}

        /* 雙欄主內容 */
        .giants-main-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
        }}
        @media (max-width: 1024px) {{
            .giants-main-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .giant-panel {{
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 12px;
            padding: 20px;
        }}
        .panel-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1f2937;
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}
        .panel-title {{
            font-size: 16px;
            font-weight: 700;
            color: #f1f5f9;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* 供應鏈表格 */
        .sc-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .sc-table th {{
            text-align: left;
            padding: 10px 12px;
            color: #94a3b8;
            font-weight: 600;
            border-bottom: 1px solid #1f2937;
            background: rgba(15, 23, 42, 0.4);
        }}
        .sc-table td {{
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            vertical-align: middle;
        }}
        .sc-table tr:hover td {{
            background: rgba(56, 189, 248, 0.04);
        }}
        .tw-stock-tag {{
            font-weight: 700;
            color: #38bdf8;
            display: inline-block;
        }}
        .tw-stock-name {{
            color: #e2e8f0;
            font-weight: 600;
            margin-left: 4px;
        }}
        .pct-bar-wrap {{
            width: 100%;
            background: rgba(255,255,255,0.06);
            height: 8px;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 4px;
        }}
        .pct-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #38bdf8, #818cf8);
            border-radius: 4px;
        }}
        .tier-badge {{
            display: inline-block;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .tier-1 {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }}
        .tier-2 {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        /* 事件驅動模擬器卡片 */
        .simulator-box {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(244, 63, 94, 0.25);
            border-radius: 10px;
            padding: 16px;
            margin-bottom: 20px;
        }}
        .sim-input-row {{
            display: flex;
            gap: 10px;
            align-items: center;
            margin-top: 12px;
            flex-wrap: wrap;
        }}
        .sim-btn {{
            background: #ef4444;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 700;
            transition: all 0.2s;
        }}
        .sim-btn:hover {{
            background: #dc2626;
            box-shadow: 0 0 10px rgba(239,68,68,0.4);
        }}
        .sim-btn-preset {{
            background: #1e293b;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            cursor: pointer;
        }}
        .sim-btn-preset:hover {{
            border-color: #38bdf8;
            color: #38bdf8;
        }}
        .sim-output-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 14px;
        }}
        .sim-out-card {{
            background: #0f172a;
            border-radius: 6px;
            padding: 10px 12px;
            border: 1px solid #1e293b;
        }}
    </style>

    <div class="us-giants-wrapper">
        <!-- Banner Header -->
        <div class="giant-hero-banner">
            <div>
                <div class="giant-hero-title">
                    <span>🏛️ 美股十大巨頭 × 台灣供應鏈雷達</span>
                </div>
                <div class="giant-hero-sub">
                    即時剖析美股 Magnificient 7 + 半導體三巨頭（NVDA, AAPL, MSFT, AMZN, GOOGL, META, TSLA, AVGO, AMD, QCOM）對台股營收佔比與市值牽引權重
                </div>
                <div class="giant-metrics-grid">
                    <div class="giant-stat-card">
                        <div class="giant-stat-val" style="color:#38bdf8;">21.4 兆美元</div>
                        <div class="giant-stat-lbl">美股十大巨頭總市值</div>
                    </div>
                    <div class="giant-stat-card">
                        <div class="giant-stat-val" style="color:#10b981;">28+ 檔核心大廠</div>
                        <div class="giant-stat-lbl">台股核心供應鏈成員</div>
                    </div>
                    <div class="giant-stat-card">
                        <div class="giant-stat-val" style="color:#f59e0b;">20.1 兆新台幣</div>
                        <div class="giant-stat-lbl">台股市值總牽引規模</div>
                    </div>
                    <div class="giant-stat-card">
                        <div class="giant-stat-val" style="color:#f43f5e;">AAPL & NVDA</div>
                        <div class="giant-stat-lbl">牽動力最高前兩大巨頭</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 橫向滑動卡片：選擇十大巨頭 -->
        <div class="giants-cards-scroll" id="giantSelectorScroll">
            <!-- 由 JS 動態注入 10 大巨頭卡片 -->
        </div>

        <!-- 主內容區塊 (左側供應鏈詳細表，右側事件驅動試算器 + 台廠通吃反查) -->
        <div class="giants-main-grid">
            <!-- 左側：供應鏈深度透視 -->
            <div class="giant-panel">
                <div class="panel-header">
                    <div class="panel-title" id="activeGiantTitle">
                        <span>🎯 供應鏈營收曝險與供貨產品</span>
                    </div>
                    <div style="font-size:12px; color:#64748b;" id="activeGiantSub"></div>
                </div>

                <div style="overflow-x: auto;">
                    <table class="sc-table">
                        <thead>
                            <tr>
                                <th>受惠台廠</th>
                                <th>供應鏈環節</th>
                                <th>供應具體產品 / 專案</th>
                                <th style="width:130px;">估計營收佔比</th>
                                <th>層級</th>
                            </tr>
                        </thead>
                        <tbody id="scTableBody">
                            <!-- JS 動態填入 -->
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- 右側：事件驅動即時推算器 + 台廠反查 -->
            <div style="display:flex; flex-direction:column; gap:20px;">
                <!-- 模組 A: 事件驅動試算器 -->
                <div class="giant-panel" style="border-color:rgba(239, 68, 68, 0.3);">
                    <div class="panel-title" style="color:#f87171;">
                        <span>⚡ 跨市場事件驅動試算器</span>
                    </div>
                    <div style="font-size:12px; color:#94a3b8; margin: 4px 0 12px 0;">
                        當該巨頭盤後財報或昨夜美股暴漲暴跌時，推算隔日台廠理論開盤波動與大盤點數牽引
                    </div>

                    <div style="display:flex; gap:6px; flex-wrap:wrap; margin-bottom:10px;">
                        <button class="sim-btn-preset" onclick="setSimChange(8.0)">財報大好 (+8%)</button>
                        <button class="sim-btn-preset" onclick="setSimChange(4.0)">強勢上漲 (+4%)</button>
                        <button class="sim-btn-preset" onclick="setSimChange(-4.0)">重挫回檔 (-4%)</button>
                        <button class="sim-btn-preset" onclick="setSimChange(-8.0)">財報利空 (-8%)</button>
                    </div>

                    <div class="sim-input-row">
                        <span style="font-size:13px;">設定美股波動:</span>
                        <input type="number" id="simChgInput" value="8.0" step="0.5" style="width:70px; background:#0f172a; border:1px solid #334155; color:#fff; padding:6px 8px; border-radius:6px; font-weight:700;">
                        <span>%</span>
                        <button class="sim-btn" onclick="executeSimulation()">試算衝擊</button>
                    </div>

                    <div class="sim-output-grid" id="simOutputBox">
                        <!-- JS 填入 -->
                    </div>
                </div>

                <!-- 模組 B: 台廠反查通吃巨頭 -->
                <div class="giant-panel">
                    <div class="panel-title" style="color:#38bdf8;">
                        <span>🔍 台廠通吃哪幾家美股巨頭？</span>
                    </div>
                    <div style="font-size:12px; color:#94a3b8; margin: 4px 0 12px 0;">
                        選擇特定指標台廠，檢視其客戶分散度與各大巨頭合計佔比
                    </div>
                    <select id="twStockSelect" onchange="renderTwReverseLookup()" style="width:100%; background:#0f172a; border:1px solid #334155; color:#38bdf8; padding:8px 12px; border-radius:6px; font-weight:700; font-size:14px; margin-bottom:12px;">
                        <!-- JS 填入 options -->
                    </select>

                    <div id="twReverseResult">
                        <!-- JS 填入反查內容 -->
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 巨頭雷達前端互動邏輯 -->
    <script>
    (function() {{
        const GIANTS_DATA = {giants_json};
        const REL_DATA = {rel_json};
        const TW_DATA = {tw_json};

        let currentGiant = GIANTS_DATA[0].us_ticker; // 預設 NVDA

        // 初始化
        function initGiants() {{
            renderGiantSelector();
            renderActiveGiant(currentGiant);
            initTwDropdown();
            renderTwReverseLookup();
            executeSimulation();
        }}

        // 渲染上方巨頭卡片列
        function renderGiantSelector() {{
            const container = document.getElementById('giantSelectorScroll');
            container.innerHTML = GIANTS_DATA.map((g, idx) => `
                <div class="giant-select-card ${{g.us_ticker === currentGiant ? 'active' : ''}}" onclick="selectGiant('${{g.us_ticker}}')">
                    <div class="giant-badge-rank">#${{idx + 1}}</div>
                    <div class="giant-card-ticker">${{g.us_ticker}}</div>
                    <div class="giant-card-name">${{g.name_zh}}</div>
                    <div class="giant-card-mcap">市值 $${{Math.round(g.market_cap_bil_usd)}}B</div>
                    <div class="giant-card-twcount">直連台廠: ${{g.total_partners_count}} 家</div>
                </div>
            `).join('');
        }}

        window.selectGiant = function(ticker) {{
            currentGiant = ticker;
            renderGiantSelector();
            renderActiveGiant(ticker);
            executeSimulation();
        }};

        // 渲染選取之巨頭供應鏈表
        function renderActiveGiant(ticker) {{
            const g = GIANTS_DATA.find(x => x.us_ticker === ticker);
            if (!g) return;

            document.getElementById('activeGiantTitle').innerHTML = `
                <span>🏛️ 【${{g.name_zh}} ${{g.us_ticker}}】台灣主要供應鏈清單</span>
            `;
            document.getElementById('activeGiantSub').innerText = `${{g.core_segment}} • 核心產品: ${{g.key_products}}`;

            const relations = REL_DATA.filter(r => r.us_ticker === ticker).sort((a,b) => b.est_revenue_pct_mid - a.est_revenue_pct_mid);
            const tbody = document.getElementById('scTableBody');

            tbody.innerHTML = relations.map(r => `
                <tr>
                    <td>
                        <span class="tw-stock-tag">${{r.tw_ticker}}</span>
                        <span class="tw-stock-name">${{r.tw_name}}</span>
                    </td>
                    <td style="color:#94a3b8;">${{r.relation_category}}</td>
                    <td style="font-weight:500;">${{r.supplied_product}}</td>
                    <td>
                        <div style="display:flex; justify-content:space-between; font-weight:700; color:#38bdf8;">
                            <span>${{r.est_revenue_pct_mid}}%</span>
                            <span style="font-size:11px; color:#64748b;">(${{r.est_revenue_pct_low}}~${{r.est_revenue_pct_high}}%)</span>
                        </div>
                        <div class="pct-bar-wrap">
                            <div class="pct-bar-fill" style="width:${{Math.min(100, r.est_revenue_pct_mid * 1.5)}}%;"></div>
                        </div>
                    </td>
                    <td>
                        <span class="tier-badge ${{r.tier_level.includes('Tier 1') ? 'tier-1' : 'tier-2'}}">${{r.tier_level.split(' ')[0]}}</span>
                    </td>
                </tr>
            `).join('');
        }}

        // 事件驅動試算器
        window.setSimChange = function(val) {{
            document.getElementById('simChgInput').value = val;
            executeSimulation();
        }};

        window.executeSimulation = function() {{
            const g = GIANTS_DATA.find(x => x.us_ticker === currentGiant);
            const chg = parseFloat(document.getElementById('simChgInput').value) || 0.0;
            const relations = REL_DATA.filter(r => r.us_ticker === currentGiant).sort((a,b) => b.est_revenue_pct_mid - a.est_revenue_pct_mid);

            let pointSum = 0;
            if (relations.length > 0) {{
                // 估計台積電與權值點數
                relations.forEach(r => {{
                    let beta = 1.0;
                    if (r.supplied_product.includes('水冷') || r.supplied_product.includes('導軌')) beta = 1.45;
                    else if (r.supplied_product.includes('ASIC') || r.supplied_product.includes('設計')) beta = 1.40;
                    else if (r.supplied_product.includes('機櫃') || r.supplied_product.includes('伺服器')) beta = 1.25;

                    const impact = chg * Math.pow(r.est_revenue_pct_mid / 100.0, 0.65) * beta;
                    if (r.tw_ticker === '2330') pointSum += impact * 85.0;
                    else if (r.tw_ticker === '2317') pointSum += impact * 10.0;
                    else if (r.tw_ticker === '2382') pointSum += impact * 5.0;
                }});
            }}

            const topPick = relations[0] ? relations[0] : null;
            const topImpact = topPick ? (chg * Math.pow(topPick.est_revenue_pct_mid / 100.0, 0.65) * 1.45) : 0;

            const box = document.getElementById('simOutputBox');
            box.innerHTML = `
                <div class="sim-out-card">
                    <div style="font-size:11px; color:#94a3b8;">大盤開盤理論跳空</div>
                    <div style="font-size:18px; font-weight:800; color:${{pointSum >= 0 ? '#ef4444' : '#10b981'}};">
                        ${{pointSum >= 0 ? '+' : ''}}${{pointSum.toFixed(1)}} 點
                    </div>
                </div>
                <div class="sim-out-card">
                    <div style="font-size:11px; color:#94a3b8;">最高彈性標的衝擊</div>
                    <div style="font-size:18px; font-weight:800; color:${{topImpact >= 0 ? '#ef4444' : '#10b981'}};">
                        ${{topImpact >= 0 ? '+' : ''}}${{topImpact.toFixed(1)}}%
                    </div>
                    <div style="font-size:11px; color:#38bdf8;">${{topPick ? topPick.tw_ticker + ' ' + topPick.tw_name : '-'}}</div>
                </div>
            `;
        }};

        // 初始化台廠反查下拉選單
        function initTwDropdown() {{
            const sel = document.getElementById('twStockSelect');
            // 只列出有出現在 relations 的台廠代號
            const validTickers = [...new Set(REL_DATA.map(r => r.tw_ticker))];
            const twValid = TW_DATA.filter(t => validTickers.includes(t.tw_ticker));

            sel.innerHTML = twValid.map(t => `
                <option value="${{t.tw_ticker}}">${{t.tw_ticker}} ${{t.name}} (${{t.industry}})</option>
            `).join('');

            sel.value = '2330'; // 預設台積電
        }}

        window.renderTwReverseLookup = function() {{
            const ticker = document.getElementById('twStockSelect').value;
            const rels = REL_DATA.filter(r => r.tw_ticker === ticker).sort((a,b) => b.est_revenue_pct_mid - a.est_revenue_pct_mid);
            const container = document.getElementById('twReverseResult');

            if (rels.length === 0) {{
                container.innerHTML = "<div style='color:#64748b;'>暫無關聯資料</div>";
                return;
            }}

            const totalPct = rels.reduce((sum, r) => sum + r.est_revenue_pct_mid, 0);

            container.innerHTML = `
                <div style="background:#0f172a; border-radius:8px; padding:12px; border:1px solid #1e293b;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:13px;">
                        <span style="color:#94a3b8;">美股巨頭合計佔比:</span>
                        <span style="font-weight:700; color:#f59e0b;">${{totalPct.toFixed(1)}}%</span>
                    </div>
                    ${{rels.map(r => `
                        <div style="margin-bottom:10px;">
                            <div style="display:flex; justify-content:space-between; font-size:12px; margin-bottom:2px;">
                                <span style="font-weight:700; color:#f1f5f9;">${{r.us_ticker}} (${{r.us_name}})</span>
                                <span style="color:#38bdf8; font-weight:700;">${{r.est_revenue_pct_mid}}%</span>
                            </div>
                            <div class="pct-bar-wrap">
                                <div class="pct-bar-fill" style="width:${{Math.min(100, r.est_revenue_pct_mid * 1.6)}}%;"></div>
                            </div>
                            <div style="font-size:11px; color:#64748b; margin-top:2px;">${{r.supplied_product}}</div>
                        </div>
                    `).join('')}}
                </div>
            `;
        }};

        // 當切換到此 tab 時觸發一次調整
        window.addEventListener('load', initGiants);
        setTimeout(initGiants, 300);
    }})();
    </script>
    """
    return html

if __name__ == '__main__':
    html = generate_us_giants_html()
    print(f"Generated US Giants HTML component, length: {len(html)} chars.")
