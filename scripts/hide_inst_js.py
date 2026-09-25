import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Conditionally wrap the JavaScript for instChart
target_js = """            // 3. 繪製副圖 2
            const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));
            const unitName = isIndex ? '\u5104' : '\u842c';
            const instContainer = document.getElementById('inst-chart-container');"""

replacement_js = """            // 3. 繪製副圖 2
            const isIndex = (['TAIEX', 'TPEx'].includes('{stock_id}'));
            const unitName = isIndex ? '\u5104' : '\u842c';
            const instContainer = document.getElementById('inst-chart-container');
            let instChart = null;
            if ('{stock_id}' !== 'TPEx') {{
"""

# And find where the instChart logic ends, right before warrantChart
target_js_end = """            // 4. 繪製副圖3"""

replacement_js_end = """            } // end if not TPEx
            // 4. 繪製副圖3"""

content = content.replace(target_js, replacement_js)
content = content.replace(target_js_end, replacement_js_end)

# Also fix syncCrosshair calls
target_sync = """            instChart.subscribeCrosshairMove(p => syncCrosshair(instChart, p));"""
replacement_sync = """            if(instChart) instChart.subscribeCrosshairMove(p => syncCrosshair(instChart, p));"""
content = content.replace(target_sync, replacement_sync)

target_sync_2 = """                    try { instChart.setCrosshairPosition(instMap.get(t), t, netLineSeries); } catch(e) {}"""
replacement_sync_2 = """                    if(instChart) try { instChart.setCrosshairPosition(instMap.get(t), t, netLineSeries); } catch(e) {}"""
content = content.replace(target_sync_2, replacement_sync_2)

target_sync_3 = """                if (instChart !== sourceChart && instMap.has(t)) {"""
replacement_sync_3 = """                if (instChart && instChart !== sourceChart && instMap.has(t)) {"""
content = content.replace(target_sync_3, replacement_sync_3)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Wrapped instChart in if-statement for safety")
