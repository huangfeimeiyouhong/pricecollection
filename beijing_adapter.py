# -*- coding: utf-8 -*-
"""北京 6 大农批市场价格适配器（数据源：食价搜 21food.cn）。
该站对部分市场使用 JS 反爬验证页，故由 beijing_scraper.js 用无头 Edge 渲染抓取。
本模块以子进程调用 scraper，输出 {market_id: [ {name,max,min,avg,date,unit}, ... ]}。
"""
import os
import json
import subprocess

ROOT = os.path.dirname(__file__)
NODE = "/Users/phil/.workbuddy/binaries/node/versions/22.22.2/bin/node"
NODE_PATH = "/Users/phil/.workbuddy/binaries/node/workspace/node_modules"
SCRAPER = os.path.join(ROOT, "beijing_scraper.js")

# 北京 6 大市场（id 取自 price.21food.cn/market/beijing/ 列表）
MARKETS = [
    ("850", "北京京丰岳各庄农副产品批发市场"),
    ("1004", "北京顺鑫石门国际农产品批发市场集团有限公司"),
    ("1006", "北京新发地农副产品批发市场信息中心"),
    ("521", "北京朝阳区大洋路综合市场"),
    ("822", "北京水屯农副产品批发市场中心"),
    ("1329", "北京菜篮子鲜活农产品批发市场有限公司"),
]

_cache = None


def fetch_all(refresh=False):
    """抓取全部 6 个市场，返回 {market_id: rows}。进程内缓存避免重复抓取。"""
    global _cache
    if not refresh and _cache is not None:
        return _cache
    ids = [m[0] for m in MARKETS]
    env = dict(os.environ, NODE_PATH=NODE_PATH,
               FOOD_MAX_PAGES=os.environ.get("FOOD_MAX_PAGES", "3"),
               BJ_MAX_PAGES=os.environ.get("BJ_MAX_PAGES", "3"))
    out = subprocess.run([NODE, SCRAPER, *ids], capture_output=True, text=True,
                         env=env, timeout=600)
    if out.returncode != 0:
        raise RuntimeError("北京抓取失败: " + (out.stderr or "")[:500])
    _cache = json.loads(out.stdout)
    return _cache


def invalidate_cache():
    global _cache
    _cache = None


def fetch_market(market_id, refresh=False):
    return fetch_all(refresh).get(market_id, [])
