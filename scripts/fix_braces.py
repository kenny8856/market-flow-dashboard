import re

file_path = r"C:\TW_Stock\generate_quant_regime.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the CSS block perfectly
# Find exactly the .tab-content {{ ... }} and .tab-content.active {{ ... }}
# And replace them with the double brace version.
import textwrap

target = """        .tab-content {{
            position: absolute;
            top: -9999px;
            left: -9999px;
            visibility: hidden;
            width: 100%;
        }}
        .tab-content.active {{
            position: relative;
            top: 0;
            left: 0;
            visibility: visible;
            animation: fadeIn 0.4s ease;
        }}"""

# Try to find what's actually there
m1 = re.search(r'\.tab-content\s*\{[^}]+\}\}', content)
if m1:
    content = content.replace(m1.group(0), "")
m2 = re.search(r'\.tab-content\.active\s*\{[^}]+\}\}', content)
if m2:
    content = content.replace(m2.group(0), "")

# Now insert the correct one before .iframe-container
content = content.replace(".iframe-container {{", target + "\n        .iframe-container {{")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed tab-content CSS")
