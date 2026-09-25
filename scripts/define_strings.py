import re

file_path = r"C:\TW_Stock\src\stock_page_generator.py"
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

definition = """
        trust_5d_val = inst_summary.get('trust_5d', 0)
        foreign_5d_val = inst_summary.get('foreign_5d', 0)
        margin_5d_val = inst_summary.get('margin_5d', 0)
        
        if stock_id in ['TAIEX', 'TPEx']:
            trust_5d_str = f"{trust_5d_val:+.1f} 億"
            foreign_5d_str = f"{foreign_5d_val:+.1f} 億"
            margin_5d_str = f"{margin_5d_val:+.1f} 億" if margin_5d_val != 0 else "+0 億"
        else:
            trust_5d_str = f"{int(trust_5d_val):+d} 張"
            foreign_5d_str = f"{int(foreign_5d_val):+d} 張"
            margin_5d_str = f"{int(margin_5d_val):+d} 張"

        # HTML
        html = f\"\"\"<!DOCTYPE html>"""

content = content.replace("        # HTML \n        html = f\"\"\"<!DOCTYPE html>", definition)
# If it was '# HTML 模型模板' or something else in Chinese, let's use regex
content = re.sub(r'([ \t]+)# [^\n]+\n[ \t]+html = f"""<!DOCTYPE html>', definition, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Defined strings before HTML starts")
