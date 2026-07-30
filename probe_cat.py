# -*- coding: utf-8 -*-
import sys, json
from collections import Counter

HCG_DIR = "/Users/phil/WorkBuddy/2026-07-16-11-31-47/houchuguanjia_mcp"
if HCG_DIR not in sys.path:
    sys.path.insert(0, HCG_DIR)
import server as hcg
hcg.login("xmszf001", "xmszf123#")

goods = json.loads(hcg.query_goods({})).get("data") or []
print("total goods:", len(goods))

c1 = Counter()
for g in goods:
    c1[g.get("firstCategoryName") or "(未分类)"] += 1
print("\n[firstCategoryName 分布]")
for k, v in c1.most_common():
    print(f"  {k}: {v}")

c2 = Counter()
for g in goods:
    c2[g.get("goodsType") or "?"] += 1
print("\n[goodsType 分布]")
for k, v in c2.most_common():
    print(f"  {k}: {v}")

print("\n[level=1 分类]")
print(json.dumps(json.loads(hcg.query_goods_category({"level": 1})), ensure_ascii=False)[:1500])
print("\n[level=2 分类]")
print(json.dumps(json.loads(hcg.query_goods_category({"level": 2})), ensure_ascii=False)[:1800])
