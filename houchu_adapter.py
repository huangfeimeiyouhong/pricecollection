# -*- coding: utf-8 -*-
"""后厨管家（houchuguanjia-prod 连接器）适配器 —— 拉取基准商品库。

复用已配置的 MCP 连接器底层逻辑（同一份 server.py），登录后厨管家并拉取
该账号的全部商品主数据，作为「基准商品库」缓存到 data/houchu_goods.json。

账号凭据：
  - 优先读取环境变量 HCG_USER / HCG_PWD（推荐生产环境做法）
  - 缺省使用下方常量（原型演示用，明文存放，请勿提交到公开仓库）

说明：
  - login 内部会对密码做 MD5 后再发送（连接器约定）。
  - 商品主数据通过 query_goods（不分页，一次返回全量）获取。
"""
import os
import sys
import json
import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
BASE_LIB = os.path.join(ROOT, "data", "houchu_goods.json")

# 复用已配置的 MCP 连接器底层实现
HCG_DIR = "/Users/phil/WorkBuddy/2026-07-16-11-31-47/houchuguanjia_mcp"
if HCG_DIR not in sys.path:
    sys.path.insert(0, HCG_DIR)
import server as hcg  # 连接器 server.py（login / query_goods 等）

USER = os.environ.get("HCG_USER") or "xmszf001"
PWD = os.environ.get("HCG_PWD") or "xmszf123#"

# 非食材分类（耗材/杂项），不纳入比价基准库
NON_FOOD_CATS = {"零星采购", "零食杂品", "日常生活用品", "清洗消毒用品"}


def fetch_goods(force=False):
    """登录并拉取该账号全部商品。优先读缓存文件；force=True 时强制重新拉取。

    返回快照字典：{org, user, count, fetched_at, goods:[...], categories:{uuid:name}}
    """
    if not force and os.path.exists(BASE_LIB):
        return json.load(open(BASE_LIB, encoding="utf-8"))

    hcg.login(USER, PWD)  # 内部 MD5 加密，token 存于连接器进程内

    # 拉分类树：建 uuid→name 映射
    cat_raw = json.loads(hcg.query_goods_category({})).get("data") or []
    cat_map = {}  # uuid → name
    for c in cat_raw:
        cat_map[c["uuid"]] = c.get("name", "")

    goods = json.loads(hcg.query_goods({})).get("data") or []

    # 精简字段，去掉空/null 噪音，保留比价与绑定所需字段；
    # 同时过滤掉非食材分类（耗材/杂项），仅保留可比价的食材商品
    clean = []
    excluded = 0
    for g in goods:
        fcu = g.get("firstCategoryUuid") or ""
        scu = g.get("secondCategoryUuid") or ""
        cat1 = cat_map.get(fcu, "")
        if cat1 in NON_FOOD_CATS:
            excluded += 1
            continue
        clean.append({
            "uuid": g.get("uuid"),
            "name": g.get("name"),
            "spec": g.get("spec") or "",
            "unit": g.get("unit") or "",
            "standardUnit": g.get("standardUnit") or "",
            "goodsType": g.get("goodsType") or "",
            "firstCategoryUuid": fcu,
            "secondCategoryUuid": scu,
            "cat1": cat1,                        # 一级分类名
            "cat2": cat_map.get(scu, ""),         # 二级分类名
            "is_compare": True,                  # 食材，参与比价
            "price": g.get("price"),
            "salePrice": g.get("salePrice"),
            "refPrice": g.get("refPrice"),
            "status": g.get("status") or "",
        })

    snap = {
        "org": "XMJGST",
        "user": USER,
        "count": len(clean),
        "excluded_count": excluded,
        "fetched_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "categories": {k: v for k, v in cat_map.items() if v and v not in NON_FOOD_CATS},
        "goods": clean,
    }
    os.makedirs(os.path.dirname(BASE_LIB), exist_ok=True)
    with open(BASE_LIB, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    return snap


def load_goods():
    """读取已缓存的基准商品库；不存在则拉取。"""
    if not os.path.exists(BASE_LIB):
        return fetch_goods()
    return json.load(open(BASE_LIB, encoding="utf-8"))


def refresh_goods():
    """强制刷新基准商品库（重新登录并拉取）。"""
    return fetch_goods(force=True)


if __name__ == "__main__":
    snap = refresh_goods()
    print(f"基准商品库: {snap['count']} 条 | org={snap['org']} | {snap['fetched_at']}")
    for g in snap["goods"][:5]:
        print(" ", g["name"], "|", g["unit"], "|", g["firstCategoryUuid"][:8])
