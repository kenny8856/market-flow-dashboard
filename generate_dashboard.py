"""
Offline HTML Dashboard Generator for Taiwan Stock Market Radar
Reads from DashboardEngine and renders standalone, zero-dependency dashboard.html.
"""

import os
import sys
import json
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.dashboard_engine import DashboardEngine

def generate_html(data: dict, output_path: str = "dashboard.html"):
    regime = data["regime"]
    strategies = data["strategies"]
    pillars = regime["pillars"]
    as_of_date = regime["as_of_date"]
    gen_time = data["generated_at"]
    score = regime["composite_score"]
    badge_color = regime["badge_color"]
    regime_label = regime["regime"]
    allocation = regime["allocation"]
    action_desc = regime["action_desc"]

    # Convert data to JSON string for client-side JS
    data_json = json.dumps(data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>臺股立體籌碼多空溫度計與實戰策略選股器</title>
    <style>
        :root {{
            --bg-primary: #0b0f19;
            --bg-card: #111827;
            --bg-card-hover: #1f2937;
            --border-color: #374151;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-blue: #3b82f6;
            --accent-amber: #f59e0b;
            --accent-purple: #8b5cf6;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        html, body {{
            overflow-x: hidden;
            width: 100%;
            -webkit-text-size-adjust: 100%;
        }}
        body {{ background-color: var(--bg-primary); color: var(--text-primary); line-height: 1.5; padding: 20px 24px; min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; width: 100%; }}

        /* Header */
        header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; border-bottom: 1px solid var(--border-color); padding-bottom: 16px; flex-wrap: wrap; gap: 16px; }}
        .title-group h1 {{ font-size: 26px; font-weight: 800; letter-spacing: -0.5px; display: flex; align-items: center; gap: 10px; }}
        .title-group p {{ color: var(--text-secondary); font-size: 14px; margin-top: 4px; }}
        .meta-pills {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
        .pill {{ background: rgba(55, 65, 81, 0.5); border: 1px solid var(--border-color); padding: 6px 14px; border-radius: 9999px; font-size: 12px; color: var(--text-secondary); }}
        .pill strong {{ color: var(--text-primary); }}

        /* Layout Grid */
        .radar-grid {{ display: grid; grid-template-columns: 420px 1fr; gap: 20px; margin-bottom: 24px; }}

        .card {{ background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 12px; padding: 20px; position: relative; }}
        .card-header {{ font-size: 16px; font-weight: 700; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; }}

        /* Gauge Area */
        .gauge-container {{ display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px 0; }}
        #gaugeCanvas {{ width: 100%; max-width: 340px; height: auto; display: block; margin: 0 auto; }}
        .score-display {{ text-align: center; margin-top: -20px; }}
        .score-number {{ font-size: 52px; font-weight: 900; line-height: 1; }}
        .regime-badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; font-weight: 700; font-size: 15px; margin-top: 8px; color: #fff; }}
        .advice-box {{ margin-top: 20px; background: rgba(31, 41, 55, 0.6); border-radius: 8px; padding: 14px; border-left: 4px solid {badge_color}; }}
        .advice-alloc {{ font-weight: 800; font-size: 15px; color: {badge_color}; margin-bottom: 4px; }}
        .advice-text {{ font-size: 13px; color: var(--text-secondary); line-height: 1.4; }}

        /* Pillars Area */
        .pillars-list {{ display: flex; flex-direction: column; gap: 12px; }}
        .pillar-item {{ background: rgba(31, 41, 55, 0.4); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px 16px; display: grid; grid-template-columns: 160px 1fr 90px; align-items: center; gap: 16px; }}
        .pillar-name {{ font-weight: 700; font-size: 14px; }}
        .pillar-weight {{ font-size: 11px; color: var(--text-secondary); font-weight: 400; }}
        .pillar-progress {{ height: 8px; background: #374151; border-radius: 4px; overflow: hidden; margin-bottom: 6px; }}
        .pillar-bar {{ height: 100%; border-radius: 4px; transition: width 0.5s ease; }}
        .pillar-desc {{ font-size: 12px; color: var(--text-secondary); }}
        .pillar-score {{ text-align: right; font-weight: 800; font-size: 20px; }}

        /* History Chart */
        .chart-card {{ margin-bottom: 24px; }}
        #trendCanvas {{ width: 100%; height: 160px; display: block; }}

        /* Strategies Section */
        .tab-bar {{ display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }}
        .tab-btn {{ background: var(--bg-card); border: 1px solid var(--border-color); color: var(--text-secondary); padding: 10px 18px; border-radius: 8px; font-weight: 600; font-size: 14px; cursor: pointer; transition: all 0.2s; display: flex; align-items: center; gap: 8px; }}
        .tab-btn:hover {{ background: var(--bg-card-hover); color: var(--text-primary); }}
        .tab-btn.active {{ background: var(--accent-blue); border-color: var(--accent-blue); color: #fff; }}
        .tab-count {{ background: rgba(0, 0, 0, 0.25); padding: 2px 8px; border-radius: 12px; font-size: 12px; }}

        .table-toolbar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 12px; }}
        .search-box {{ background: #1f2937; border: 1px solid var(--border-color); border-radius: 6px; padding: 8px 14px; color: var(--text-primary); font-size: 13px; width: 260px; }}
        .search-box:focus {{ outline: none; border-color: var(--accent-blue); }}

        .table-container {{ overflow-x: auto; -webkit-overflow-scrolling: touch; border: 1px solid var(--border-color); border-radius: 8px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }}
        th {{ background: #1f2937; color: var(--text-secondary); font-weight: 700; padding: 12px 14px; cursor: pointer; user-select: none; white-space: nowrap; }}
        th:hover {{ color: var(--text-primary); }}
        td {{ padding: 12px 14px; border-top: 1px solid var(--border-color); white-space: nowrap; }}
        tr:hover td {{ background: var(--bg-card-hover); }}

        .mobile-scroll-hint {{ display: none; }}

        /* Responsive Breakpoints (Tablet & Mobile) */
        @media (max-width: 1024px) {{
            .radar-grid {{ grid-template-columns: 1fr; }}
        }}

        @media (max-width: 768px) {{
            body {{ padding: 12px 10px; }}
            header {{ flex-direction: column; align-items: stretch; gap: 12px; margin-bottom: 16px; padding-bottom: 14px; }}
            .title-group h1 {{ font-size: 20px; flex-wrap: wrap; gap: 6px; }}
            .title-group p {{ font-size: 12px; }}
            .meta-pills {{ gap: 6px; }}
            .pill {{ font-size: 11px; padding: 4px 10px; }}
            .card {{ padding: 14px 12px; }}
            .card-header {{ font-size: 15px; margin-bottom: 12px; }}
            .score-number {{ font-size: 42px; }}
            .regime-badge {{ font-size: 13px; padding: 4px 12px; }}
            .tab-bar {{
                display: flex;
                overflow-x: auto;
                flex-wrap: nowrap;
                -webkit-overflow-scrolling: touch;
                padding-bottom: 6px;
                gap: 6px;
            }}
            .tab-btn {{
                padding: 8px 12px;
                font-size: 13px;
                flex-shrink: 0;
                white-space: nowrap;
            }}
            .table-toolbar {{
                flex-direction: column;
                align-items: stretch;
                gap: 10px;
            }}
            .search-box {{
                width: 100%;
            }}
            .mobile-scroll-hint {{
                display: block;
                font-size: 12px;
                color: var(--accent-blue);
                margin-bottom: 6px;
            }}
            th, td {{
                padding: 10px 12px;
                font-size: 12px;
            }}
        }}

        @media (max-width: 640px) {{
            .pillar-item {{
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 6px;
            }}
            .pillar-item > div:nth-child(1) {{
                grid-column: 1 / 2;
            }}
            .pillar-item > div:nth-child(3) {{
                grid-column: 2 / 3;
                text-align: right;
            }}
            .pillar-item > div:nth-child(2) {{
                grid-column: 1 / 3;
                margin-top: 4px;
            }}
            .pillar-name {{ font-size: 13px; }}
            .pillar-score {{ font-size: 17px; }}
        }}

        @media (max-width: 480px) {{
            .title-group h1 {{ font-size: 18px; }}
            .score-number {{ font-size: 36px; }}
            .advice-box {{ padding: 10px 12px; }}
            .advice-alloc {{ font-size: 14px; }}
            .advice-text {{ font-size: 12px; }}
        }}

        /* Utility Badges */
        .mkt-twse {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
        .mkt-tpex {{ background: rgba(139, 92, 246, 0.15); color: #c084fc; padding: 2px 6px; border-radius: 4px; font-size: 11px; }}
        .val-up {{ color: #ef4444; font-weight: 600; }}
        .val-down {{ color: #10b981; font-weight: 600; }}
        .badge-warning {{ background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; }}
        .badge-safe {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 8px; border-radius: 4px; font-size: 11px; }}

        footer {{ text-align: center; color: var(--text-secondary); font-size: 12px; margin-top: 36px; padding-top: 16px; border-top: 1px solid var(--border-color); }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div class="title-group">
            <h1>📊 臺股立體籌碼多空溫度計與實戰選股器</h1>
            <p>橫跨證交所現貨 · 期交所特法部位 · 櫃買可轉債 · 融資融券 · 全市場借券賣出</p>
        </div>
        <div class="meta-pills">
            <span class="pill">基準交易日: <strong>{as_of_date}</strong></span>
            <span class="pill">產生時間: <strong>{gen_time}</strong></span>
            <span class="pill" style="border-color: #10b981; color: #10b981;">⚡ 100% 純離線模式</span>
        </div>
    </header>

    <!-- SECTION 1: RADAR & PILLARS -->
    <div class="radar-grid">
        <!-- GAUGE CARD -->
        <div class="card">
            <div class="card-header">
                <span>🎯 大盤多空立體綜合得分</span>
                <span style="font-size: 12px; color: var(--text-secondary);">五大權重加權</span>
            </div>
            <div class="gauge-container">
                <canvas id="gaugeCanvas" width="340" height="180"></canvas>
                <div class="score-display">
                    <div class="score-number" style="color: {badge_color};">{score}</div>
                    <div class="regime-badge" style="background-color: {badge_color};">{regime_label}</div>
                </div>
            </div>
            <div class="advice-box">
                <div class="advice-alloc">💡 {allocation}</div>
                <div class="advice-text">{action_desc}</div>
            </div>
        </div>

        <!-- 5 PILLARS CARD -->
        <div class="card">
            <div class="card-header">
                <span>🧩 五大籌碼核心維度評分</span>
                <span style="font-size: 12px; color: var(--text-secondary);">滿分 100 分</span>
            </div>
            <div class="pillars-list">
                <!-- Pillar 1 -->
                <div class="pillar-item">
                    <div>
                        <div class="pillar-name">{pillars['taifex']['name']}</div>
                        <div class="pillar-weight">權重 {pillars['taifex']['weight']}% · 台指期</div>
                    </div>
                    <div>
                        <div class="pillar-progress">
                            <div class="pillar-bar" style="width: {pillars['taifex']['score']}%; background: #3b82f6;"></div>
                        </div>
                        <div class="pillar-desc">{pillars['taifex']['status_text']}</div>
                    </div>
                    <div class="pillar-score" style="color: #3b82f6;">{pillars['taifex']['score']}分</div>
                </div>

                <!-- Pillar 2 -->
                <div class="pillar-item">
                    <div>
                        <div class="pillar-name">{pillars['institutional']['name']}</div>
                        <div class="pillar-weight">權重 {pillars['institutional']['weight']}% · 外資+投信</div>
                    </div>
                    <div>
                        <div class="pillar-progress">
                            <div class="pillar-bar" style="width: {pillars['institutional']['score']}%; background: #10b981;"></div>
                        </div>
                        <div class="pillar-desc">{pillars['institutional']['status_text']}</div>
                    </div>
                    <div class="pillar-score" style="color: #10b981;">{pillars['institutional']['score']}分</div>
                </div>

                <!-- Pillar 3 -->
                <div class="pillar-item">
                    <div>
                        <div class="pillar-name">{pillars['margin']['name']}</div>
                        <div class="pillar-weight">權重 {pillars['margin']['weight']}% · 散戶槓桿</div>
                    </div>
                    <div>
                        <div class="pillar-progress">
                            <div class="pillar-bar" style="width: {pillars['margin']['score']}%; background: #f59e0b;"></div>
                        </div>
                        <div class="pillar-desc">{pillars['margin']['status_text']}</div>
                    </div>
                    <div class="pillar-score" style="color: #f59e0b;">{pillars['margin']['score']}分</div>
                </div>

                <!-- Pillar 4 -->
                <div class="pillar-item">
                    <div>
                        <div class="pillar-name">{pillars['sbl']['name']}</div>
                        <div class="pillar-weight">權重 {pillars['sbl']['weight']}% · 機構放空</div>
                    </div>
                    <div>
                        <div class="pillar-progress">
                            <div class="pillar-bar" style="width: {pillars['sbl']['score']}%; background: #8b5cf6;"></div>
                        </div>
                        <div class="pillar-desc">{pillars['sbl']['status_text']}</div>
                    </div>
                    <div class="pillar-score" style="color: #8b5cf6;">{pillars['sbl']['score']}分</div>
                </div>

                <!-- Pillar 5 -->
                <div class="pillar-item">
                    <div>
                        <div class="pillar-name">{pillars['cb']['name']}</div>
                        <div class="pillar-weight">權重 {pillars['cb']['weight']}% · 信用利差</div>
                    </div>
                    <div>
                        <div class="pillar-progress">
                            <div class="pillar-bar" style="width: {pillars['cb']['score']}%; background: #ec4899;"></div>
                        </div>
                        <div class="pillar-desc">{pillars['cb']['status_text']}</div>
                    </div>
                    <div class="pillar-score" style="color: #ec4899;">{pillars['cb']['score']}分</div>
                </div>
            </div>
        </div>
    </div>

    <!-- SECTION 2: 30-DAY TREND -->
    <div class="card chart-card">
        <div class="card-header">
            <span>📈 近 30 個交易日大盤多空分數走勢圖</span>
            <span style="font-size: 12px; color: var(--text-secondary);">紅虛線: 65分偏多門檻 | 綠虛線: 45分偏空門檻</span>
        </div>
        <canvas id="trendCanvas" width="1350" height="150"></canvas>
    </div>

    <!-- SECTION 3: TACTICAL SCREENER -->
    <div class="card">
        <div class="card-header">
            <span>⚡ 實戰策略選股器 (Tactical Stock Screener)</span>
            <span style="font-size: 12px; color: var(--text-secondary);">點擊欄位可正逆向排序</span>
        </div>

        <div class="tab-bar">
            <button class="tab-btn active" onclick="switchTab('squeeze')">
                🚀 黃金主力軋空股 <span class="tab-count">{len(strategies['squeeze'])}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('distribution')">
                ⚠️ 高檔出貨預警股 <span class="tab-count">{len(strategies['distribution'])}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('cb_safe')">
                🛡️ 可轉債保底安全牌 <span class="tab-count">{len(strategies['cb_safe'])}</span>
            </button>
            <button class="tab-btn" onclick="switchTab('futures_whales')">
                🐋 個股期主力重押股 <span class="tab-count">{len(strategies['futures_whales'])}</span>
            </button>
        </div>

        <div class="table-toolbar">
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 快速搜尋代號或名稱..." onkeyup="filterTable()">
            <div style="font-size: 12px; color: var(--text-secondary);">共篩選出 <strong id="visibleCount" style="color: var(--text-primary);">0</strong> 檔標的</div>
        </div>

        <div class="mobile-scroll-hint">👉 提示：可左右滑動表格檢視完整多空數據與財務指標</div>

        <div class="table-container">
            <table id="dataTable">
                <thead id="tableHead"></thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
    </div>

    <footer>
        臺股立體籌碼分析系統 · 本地端自給自足資料庫架構 · 免外部網路依賴 · 更新時間: {gen_time}
    </footer>
</div>

<script>
// Embedded Data Payload
const DASHBOARD_DATA = {data_json};

// Draw Gauge Meter
function drawGauge(score) {{
    const canvas = document.getElementById('gaugeCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const cx = width / 2;
    const cy = height - 20;
    const radius = 130;

    ctx.clearRect(0, 0, width, height);

    // Track arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, Math.PI, 2 * Math.PI, false);
    ctx.lineWidth = 18;
    ctx.strokeStyle = '#1e293b';
    ctx.stroke();

    // Gradient Arc
    const gradient = ctx.createLinearGradient(cx - radius, cy, cx + radius, cy);
    gradient.addColorStop(0.0, '#ef4444'); // Red (0)
    gradient.addColorStop(0.35, '#f97316'); // Orange (35)
    gradient.addColorStop(0.5, '#f59e0b'); // Amber (50)
    gradient.addColorStop(0.7, '#3b82f6'); // Blue (70)
    gradient.addColorStop(1.0, '#10b981'); // Green (100)

    const angle = Math.PI + (score / 100) * Math.PI;
    ctx.beginPath();
    ctx.arc(cx, cy, radius, Math.PI, angle, false);
    ctx.lineWidth = 18;
    ctx.strokeStyle = gradient;
    ctx.lineCap = 'round';
    ctx.stroke();

    // Draw pointer
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(-4, 0);
    ctx.lineTo(0, -radius + 8);
    ctx.lineTo(4, 0);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.restore();

    // Center pivot
    ctx.beginPath();
    ctx.arc(cx, cy, 7, 0, 2 * Math.PI);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
}}

// Draw Trend Chart
function drawTrend(history) {{
    const canvas = document.getElementById('trendCanvas');
    if (!canvas || !history || history.length === 0) return;

    // Dynamically adjust pixel buffer width based on parent container width for crisp RWD rendering
    const parentWidth = canvas.parentElement ? canvas.parentElement.clientWidth : 800;
    const cardPad = window.innerWidth <= 768 ? 24 : 40;
    const targetWidth = Math.max(parentWidth - cardPad, 280);
    canvas.width = targetWidth;
    canvas.height = 160;

    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const isMobile = w < 520;
    const padL = isMobile ? 32 : 44, padR = 16, padT = 20, padB = 30;

    ctx.clearRect(0, 0, w, h);

    const graphW = w - padL - padR;
    const graphH = h - padT - padB;

    // Threshold lines (65 & 45)
    const y65 = padT + graphH * (1 - 65 / 100);
    const y45 = padT + graphH * (1 - 45 / 100);

    ctx.strokeStyle = 'rgba(59, 130, 246, 0.4)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(padL, y65); ctx.lineTo(w - padR, y65);
    ctx.stroke();

    ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)';
    ctx.beginPath();
    ctx.moveTo(padL, y45); ctx.lineTo(w - padR, y45);
    ctx.stroke();
    ctx.setLineDash([]);

    // Y-axis threshold labels
    ctx.fillStyle = '#60a5fa';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText('65', padL - 4, y65 + 3);
    ctx.fillStyle = '#f87171';
    ctx.fillText('45', padL - 4, y45 + 3);

    // Plot line
    const step = graphW / (history.length - 1);
    ctx.beginPath();
    ctx.lineWidth = 2.5;
    ctx.strokeStyle = '#38bdf8';

    history.forEach((pt, i) => {{
        const x = padL + i * step;
        const y = padT + graphH * (1 - pt.score / 100);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }});
    ctx.stroke();

    // Area fill
    ctx.lineTo(padL + (history.length - 1) * step, padT + graphH);
    ctx.lineTo(padL, padT + graphH);
    ctx.closePath();
    const areaGrad = ctx.createLinearGradient(0, padT, 0, padT + graphH);
    areaGrad.addColorStop(0, 'rgba(56, 189, 248, 0.25)');
    areaGrad.addColorStop(1, 'rgba(56, 189, 248, 0.0)');
    ctx.fillStyle = areaGrad;
    ctx.fill();

    // Points and labels
    const stepInterval = isMobile ? 6 : (w < 800 ? 4 : 3);
    history.forEach((pt, i) => {{
        const x = padL + i * step;
        const y = padT + graphH * (1 - pt.score / 100);

        ctx.beginPath();
        ctx.arc(x, y, isMobile ? 2.5 : 3.5, 0, 2 * Math.PI);
        ctx.fillStyle = pt.score >= 65 ? '#10b981' : (pt.score <= 45 ? '#ef4444' : '#f59e0b');
        ctx.fill();

        // X-axis dates
        if (i % stepInterval === 0 || i === history.length - 1) {{
            ctx.fillStyle = '#64748b';
            ctx.font = isMobile ? '9px sans-serif' : '10px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(pt.date.slice(5), x, h - 10);
        }}
    }});
}}

// Tab Tables Configuration
let currentTab = 'squeeze';
let currentData = [];

function switchTab(tabKey) {{
    currentTab = tabKey;
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');
    renderTable();
}}

function renderTable() {{
    const thead = document.getElementById('tableHead');
    const tbody = document.getElementById('tableBody');
    const data = DASHBOARD_DATA.strategies[currentTab] || [];
    currentData = data;

    let headers = [];
    if (currentTab === 'squeeze') {{
        headers = ['排名', '代號', '名稱', '市場', '券資比', '融券餘額(張)', '融券增減', '融資餘額(張)', '融資增減', '借券使用率', '策略評等'];
    }} else if (currentTab === 'distribution') {{
        headers = ['排名', '代號', '名稱', '市場', '融資增額(張)', '融資餘額(張)', '借券賣出(張)', '借券賣存量(張)', '警示狀態'];
    }} else if (currentTab === 'cb_safe') {{
        headers = ['排名', '轉債代號', '可轉債簡稱', '標的代號', '標的名稱', 'CB收盤價', '轉換價值', '折溢價率', '流通張數', '防禦評價'];
    }} else if (currentTab === 'futures_whales') {{
        headers = ['排名', '期貨代碼', '契約名稱', '前十大特法淨部位', '特法買方口數', '特法賣方口數', '市場未平倉(OI)', '主力多空向'];
    }}

    thead.innerHTML = '<tr>' + headers.map(h => `<th onclick="sortTable('${{h}}')">${{h}} ⇕</th>`).join('') + '</tr>';

    const search = document.getElementById('searchInput').value.trim().toLowerCase();
    const filtered = data.filter(r => {{
        if (!search) return true;
        const text = Object.values(r).join(' ').toLowerCase();
        return text.includes(search);
    }});

    document.getElementById('visibleCount').innerText = filtered.length;

    tbody.innerHTML = filtered.map((r, idx) => {{
        const mktBadge = r.market_type === '上市' ? '<span class="mkt-twse">上市</span>' : (r.market_type === '上櫃' ? '<span class="mkt-tpex">上櫃</span>' : '');
        if (currentTab === 'squeeze') {{
            return `<tr>
                <td>${{idx + 1}}</td>
                <td><strong>${{r.stock_id}}</strong></td>
                <td>${{r.stock_name}}</td>
                <td>${{mktBadge}}</td>
                <td class="val-up">${{r.short_margin_ratio}}%</td>
                <td>${{Number(r.short_today_bal).toLocaleString()}}</td>
                <td class="${{r.short_change >= 0 ? 'val-up' : 'val-down'}}">${{r.short_change > 0 ? '+' : ''}}${{r.short_change}}</td>
                <td>${{Number(r.margin_today_bal).toLocaleString()}}</td>
                <td class="${{r.margin_change >= 0 ? 'val-up' : 'val-down'}}">${{r.margin_change > 0 ? '+' : ''}}${{r.margin_change}}</td>
                <td>${{r.sbl_utilization || 0}}%</td>
                <td><span class="badge-safe">🚀 極高軋空力道</span></td>
            </tr>`;
        }} else if (currentTab === 'distribution') {{
            return `<tr>
                <td>${{idx + 1}}</td>
                <td><strong>${{r.stock_id}}</strong></td>
                <td>${{r.stock_name}}</td>
                <td>${{mktBadge}}</td>
                <td class="val-up">+${{Number(r.margin_change).toLocaleString()}}</td>
                <td>${{Number(r.margin_today_bal).toLocaleString()}}</td>
                <td class="val-up">+${{Number(r.sbl_sell_lots).toLocaleString()}}</td>
                <td>${{Number(r.sbl_bal_lots).toLocaleString()}}</td>
                <td><span class="badge-warning">⚠️ 融資與借賣雙增</span></td>
            </tr>`;
        }} else if (currentTab === 'cb_safe') {{
            return `<tr>
                <td>${{idx + 1}}</td>
                <td><strong>${{r.cb_id}}</strong></td>
                <td>${{r.cb_name}}</td>
                <td>${{r.underlying_id}}</td>
                <td>${{r.underlying_name}}</td>
                <td style="font-weight:700; color:#38bdf8;">${{r.close_price}} 元</td>
                <td>${{r.conversion_value}}</td>
                <td class="${{r.premium_rate <= 5 ? 'val-down' : ''}}">${{r.premium_rate}}%</td>
                <td>${{Number(r.outstanding_lots || 0).toLocaleString()}}</td>
                <td><span class="badge-safe">🛡️ 下檔保底 + 低溢價</span></td>
            </tr>`;
        }} else if (currentTab === 'futures_whales') {{
            const isLong = r.net_top10_spec >= 0;
            return `<tr>
                <td>${{idx + 1}}</td>
                <td><strong>${{r.contract_code}}</strong></td>
                <td>${{r.contract_name}}</td>
                <td class="${{isLong ? 'val-up' : 'val-down'}}">${{r.net_top10_spec > 0 ? '+' : ''}}${{Number(r.net_top10_spec).toLocaleString()}} 口</td>
                <td>${{Number(r.buy_top10_spec).toLocaleString()}}</td>
                <td>${{Number(r.sell_top10_spec).toLocaleString()}}</td>
                <td>${{Number(r.market_oi).toLocaleString()}}</td>
                <td><span class="${{isLong ? 'badge-safe' : 'badge-warning'}}">${{isLong ? '🐋 主力偏多' : '🔻 主力偏空'}}</span></td>
            </tr>`;
        }}
    }}).join('');
}}

function filterTable() {{
    renderTable();
}}

// Initialize
window.onload = function() {{
    drawGauge({score});
    drawTrend(DASHBOARD_DATA.regime.history_trend);
    renderTable();
}};

// Re-render responsive elements on orientation change or screen resize
let resizeTimer;
window.addEventListener('resize', function() {{
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function() {{
        drawTrend(DASHBOARD_DATA.regime.history_trend);
    }}, 100);
}});
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[✓] 離線網頁儀表板已成功生成: {output_path}")

def main():
    print("=" * 75)
    print("  【正在生成 臺股立體籌碼多空溫度計與實戰選股器 離線儀表板】")
    print("=" * 75)
    engine = DashboardEngine()
    data = engine.get_all_dashboard_data()
    out_file = "dashboard.html"
    generate_html(data, out_file)
    print(f"  * 基準交易日: {data['regime']['as_of_date']}")
    print(f"  * 綜合多空評分: {data['regime']['composite_score']} 分 ({data['regime']['regime']})")
    print(f"  * 建議持股水位: {data['regime']['allocation']}")
    print("=" * 75)

if __name__ == "__main__":
    main()
