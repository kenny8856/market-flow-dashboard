import re

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Insert CSS before </style>
css_injection = """
        /* Tabs UI */
        .tabs-container {
            margin-bottom: 24px;
        }
        .tabs-nav {
            display: flex;
            flex-wrap: nowrap;
            overflow-x: auto;
            gap: 10px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
            -webkit-overflow-scrolling: touch;
        }
        .tabs-nav::-webkit-scrollbar {
            height: 4px;
        }
        .tabs-nav::-webkit-scrollbar-thumb {
            background: var(--border-color);
            border-radius: 4px;
        }
        .tab-btn {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            color: var(--text-secondary);
            padding: 10px 18px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 15px;
            font-weight: 600;
            white-space: nowrap;
            transition: all 0.2s ease;
        }
        .tab-btn:hover {
            background: rgba(255,255,255,0.08);
            color: var(--text-primary);
        }
        .tab-btn.active {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: #fff;
            box-shadow: 0 0 15px rgba(56, 189, 248, 0.3);
        }
        .tab-content {
            display: none;
            animation: fadeIn 0.4s ease;
        }
        .tab-content.active {
            display: block;
        }
        .iframe-container {
            width: 100%;
            height: 1200px;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
            background: var(--bg-card);
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @media (max-width: 768px) {
            .tab-btn { font-size: 14px; padding: 8px 14px; }
            .iframe-container { height: 800px; }
        }
"""
content = content.replace("    </style>", css_injection + "    </style>")

# 2. Refactor body HTML layout
# Find the start of hero-split-grid
target_layout_start = """        <!-- Top 50-50 Hero Grid -->"""
target_layout_end = """        {short_section_html}"""

new_layout = """        <!-- Tabs Navigation -->
        <div class="tabs-container">
            <div class="tabs-nav">
                <button class="tab-btn active" onclick="switchTab(event, 'tab-macro')">📊 多空儀表板</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-taiex')">📈 加權指數 K 線</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-tpex')">📈 櫃買指數 K 線</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-longs')">🟢 多方選股結果 ({len(longs)})</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-shorts')">🔴 空方選股結果 ({len(shorts)})</button>
            </div>
        </div>

        <div id="tab-macro" class="tab-content active">
        <!-- Top 50-50 Hero Grid -->"""

# We need to wrap hero-split-grid
# Replace `<!-- Top 50-50 Hero Grid -->` with `new_layout`
content = content.replace("        <!-- Top 50-50 Hero Grid -->", new_layout)

# Close tab-macro and open tab-longs and tab-shorts
target_sections = """        
        {long_section_html}
        {short_section_html}"""

new_sections = """
        </div> <!-- End tab-macro -->

        <div id="tab-taiex" class="tab-content">
            <div class="iframe-container">
                <iframe src="stock_TAIEX.html" style="width:100%; height:100%; border:none;"></iframe>
            </div>
        </div>

        <div id="tab-tpex" class="tab-content">
            <div class="iframe-container">
                <iframe src="stock_TPEx.html" style="width:100%; height:100%; border:none;"></iframe>
            </div>
        </div>

        <div id="tab-longs" class="tab-content">
            {long_section_html}
        </div>

        <div id="tab-shorts" class="tab-content">
            {short_section_html}
        </div>"""

content = content.replace(target_sections, new_sections)

# 3. Insert JS logic for tabs
js_injection = """
        function switchTab(evt, tabId) {
            // Hide all tab content
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            // Remove active class from all buttons
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            // Show the current tab, and add an "active" class to the button that opened the tab
            document.getElementById(tabId).classList.add('active');
            evt.currentTarget.classList.add('active');
        }"""

content = content.replace("    <script>", "    <script>" + js_injection)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated generate_quant_regime.py for Tabs UI")
