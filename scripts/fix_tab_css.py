import re

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the tab CSS
old_css = """        .tab-content {
            display: none;
            animation: fadeIn 0.4s ease;
        }
        .tab-content.active {
            display: block;
        }"""

new_css = """        .tab-content {
            position: absolute;
            top: -9999px;
            left: -9999px;
            visibility: hidden;
            width: 100%;
        }
        .tab-content.active {
            position: relative;
            top: 0;
            left: 0;
            visibility: visible;
            animation: fadeIn 0.4s ease;
        }"""

if old_css in content:
    content = content.replace(old_css, new_css)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed Tab CSS")
else:
    print("Old CSS not found. Trying flexible replacement.")
    # More flexible regex
    content = re.sub(r'\.tab-content\s*\{[^}]+\}', '.tab-content {\n            position: absolute;\n            top: -9999px;\n            left: -9999px;\n            visibility: hidden;\n            width: 100%;\n        }', content, count=1)
    content = re.sub(r'\.tab-content\.active\s*\{[^}]+\}', '.tab-content.active {\n            position: relative;\n            top: 0;\n            left: 0;\n            visibility: visible;\n            animation: fadeIn 0.4s ease;\n        }', content, count=1)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fixed Tab CSS (Regex)")
