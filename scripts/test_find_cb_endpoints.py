import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with open(r"C:\Users\kenny\.gemini\antigravity\brain\27499339-cf00-4362-8740-5c97ef4713b2\.system_generated\steps\184\content.md", "r", encoding="utf-8") as f:
    text = f.read()

import re
m = re.search(r'\{"openapi":[\s\S]*\}', text)
data = json.loads(m.group(0))

schemas = data.get("components", {}).get("schemas", {})

for target in ["bond_cb_daily", "bond_ISSBD5_data"]:
    print(f"================ {target} ================")
    path_info = data.get("paths", {}).get(f"/{target}", {})
    print("Summary:", path_info.get("get", {}).get("summary"))
    print("Parameters:", path_info.get("get", {}).get("parameters"))
    schema_info = schemas.get(target, {})
    props = schema_info.get("properties", {})
    if not props and "items" in schema_info:
        props = schema_info["items"].get("properties", {})
    print("Columns/Properties:")
    for k, v in props.items():
        print(f"  {k}: {v.get('description', '')} ({v.get('type')})")
