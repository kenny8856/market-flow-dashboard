import re

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add import and generation of us_giants_html
target_import = """        tpex_info = get_index_stats('db/tpex_market.db', 'TPEx', '櫃買指數', 'TPEX')
        stock_gen.generate_page(tpex_info)
        
        print("Generated TAIEX and TPEx pages with POC.")"""

replacement_import = """        tpex_info = get_index_stats('db/tpex_market.db', 'TPEx', '櫃買指數', 'TPEX')
        stock_gen.generate_page(tpex_info)
        
        print("Generated TAIEX and TPEx pages with POC.")
    except Exception as e:
        print(f"Error generating index pages: {e}")

    try:
        from scripts.generate_us_giants_component import generate_us_giants_html
        us_giants_html = generate_us_giants_html()
        print("Generated US Giants Supply Chain radar component.")
    except Exception as e:
        print(f"Error generating us_giants_html: {e}")
        us_giants_html = "<div style='color:red;'>無法載入美股巨頭雷達</div>" """

content = content.replace(target_import, replacement_import)

# 2. Add Tab button in tabs-nav
target_button = """                <button class="tab-btn" onclick="switchTab(event, 'tab-tpex')">📈 櫃買指數</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-longs')">🟢 多方標的 ({len(longs)})</button>"""

replacement_button = """                <button class="tab-btn" onclick="switchTab(event, 'tab-tpex')">📈 櫃買指數</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-us-giants')">🏛️ 美股巨頭雷達</button>
                <button class="tab-btn" onclick="switchTab(event, 'tab-longs')">🟢 多方標的 ({len(longs)})</button>"""

content = content.replace(target_button, replacement_button)

# 3. Add Tab content div
target_tab_content = """        <div id="tab-tpex" class="tab-content">
            <div class="iframe-container">
                <iframe src="stock_TPEx.html?v=1790331785" style="width:100%; height:100%; border:none;"></iframe>
            </div>
        </div>

        <div id="tab-longs" class="tab-content">"""

# Note: the cache-buster timestamp might vary, so we can use regex or target the structure
content = re.sub(
    r'(<div id="tab-tpex" class="tab-content">.*?</div>\s*</div>)',
    r'\1\n\n        <div id="tab-us-giants" class="tab-content">\n            {us_giants_html}\n        </div>',
    content,
    flags=re.DOTALL
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched generate_quant_regime.py with US Giants Tab successfully.")
