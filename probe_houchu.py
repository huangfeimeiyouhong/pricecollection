# -*- coding: utf-8 -*-
"""探测：通过复用 houchuguanjia MCP server 的底层函数，登录并拉取商品主数据，观察返回结构。"""
import sys, json

HCG_DIR = "/Users/phil/WorkBuddy/2026-07-16-11-31-47/houchuguanjia_mcp"
if HCG_DIR not in sys.path:
    sys.path.insert(0, HCG_DIR)
import server as hcg

print("=== login ===")
lr = hcg.login("xmszf001", "xmszf123#")
print(lr[:700])

print("\n=== query_goods (no params) ===")
qg = hcg.query_goods({})
d = json.loads(qg)
print("success:", d.get("success"), "| msg:", d.get("message"))
data = d.get("data")
print("data type:", type(data).__name__)
if isinstance(data, list):
    print("list len:", len(data))
    if data:
        print("first item:\n", json.dumps(data[0], ensure_ascii=False, indent=2)[:900])
elif isinstance(data, dict):
    print("dict keys:", list(data.keys()))
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  field '{k}' len={len(v)}")
            if v:
                print("  first item:\n", json.dumps(v[0], ensure_ascii=False, indent=2)[:900])
    if not any(isinstance(v, list) for v in data.values()):
        print("full:", json.dumps(data, ensure_ascii=False)[:1200])

print("\n=== page_goods pageNo=1 pageSize=3 ===")
pg = hcg.page_goods({"pageNo": 1, "pageSize": 3})
pd = json.loads(pg)
print("success:", pd.get("success"), "| msg:", pd.get("message"))
pdata = pd.get("data")
print("page data type:", type(pdata).__name__)
if isinstance(pdata, dict):
    print("page dict keys:", list(pdata.keys()))
    print("page full keys sample:", json.dumps(pdata, ensure_ascii=False)[:900])
elif isinstance(pdata, list):
    print("page list len:", len(pdata))
