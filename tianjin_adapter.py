# -*- coding: utf-8 -*-
"""天津 6 大农批市场价格适配器（数据源：食价搜 21food.cn）。
与北京同源同结构，复用 beijing_scraper.js（无头 Edge 渲染绕过 JS 反爬）。
本模块以子进程调用 scraper，输出 {market_id: [ {name,max,min,avg,date,unit}, ... ]}。
仅采集前 2 页（FOOD_MAX_PAGES 默认 2）。
"""
import os
import json
import subprocess

ROOT = os.path.dirname(__file__)
NODE = "/Users/phil/.workbuddy/binaries/node/versions/22.22.2/bin/node"
NODE_PATH = "/Users/phil/.workbuddy/binaries/node/workspace/node_modules"
SCRAPER = os.path.join(ROOT, "beijing_scraper.js")

# 天津 6 大市场（id 取自 price.21food.cn/market/tianjin/ 列表）
MARKETS = [
    ("388", "天津武清大沙河批发市场"),
    ("865", "天津何庄子农产品批发市场"),
    ("1029", "天津碧城农产品批发市场"),
    ("1030", "天津韩家墅海吉星农产品物流有限公司"),
    ("1031", "天津市红旗农贸综合批发市场有限公司"),
    ("1190", "天津市金钟河蔬菜贸易中心"),
]

_cache = None


def fetch_all(refresh=False):
    """抓取全部 6 个市场，返回 {market_id: rows}。进程内缓存避免重复抓取。"""
    global _cache
    if not refresh and _cache is not None:
        return _cache
    ids = [m[0] for m in MARKETS]
    env = dict(os.environ, NODE_PATH=NODE_PATH,
               FOOD_MAX_PAGES=os.environ.get("FOOD_MAX_PAGES", "2"),
               BJ_MAX_PAGES=os.environ.get("BJ_MAX_PAGES", "2"))
    out = subprocess.run([NODE, SCRAPER, *ids], capture_output=True, text=True,
                         env=env, timeout=1200)
    if out.returncode != 0:
        raise RuntimeError("天津抓取失败: " + (out.stderr or "")[:500])
    _cache = json.loads(out.stdout)
    return _cache


def invalidate_cache():
    global _cache
    _cache = None


def fetch_market(market_id, refresh=False):
    return fetch_all(refresh).get(market_id, [])
