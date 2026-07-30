# -*- coding: utf-8 -*-
"""
厦门市发改委「今日民生」价格适配器
================================
数据源: 厦门市发展和改革委员会官网「便民专栏 › 今日民生」
        https://dpc.xm.gov.cn/bmzl/jrms/
栏目（民生商品价格，单位均为 元/500克 = 元/斤）:
  ly    -> 粮油
  sc    -> 果蔬（蔬菜+水果）
  rqd   -> 肉禽蛋奶
  79647 -> 水产品
  yj    -> 工业生产资料（钢材等，非菜篮子，已排除）

接入方式:
  1. 抓各子栏目列表页，取第一条（最新一期）详情页链接
  2. 解析 Excel 导出的 HTML 表格（品名/规格/计量单位/农超平均价）
  3. 单位已是「元/500克」=「元/斤」，与菜亿箩一致，无需换算
  4. 输出标准化行：{name, spec, unit, price, sub, date}

说明: 原型阶段轻量适配器；落库时建议改为定时任务（每日抓取最新一期）。
"""

import os
import re
import json
from urllib.parse import urljoin

import requests

BASE = "https://dpc.xm.gov.cn/bmzl/jrms/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 民生子栏目（排除 yj 工业生产资料）
SUBS = {
    "ly": "粮油",
    "sc": "果蔬",
    "rqd": "肉禽蛋奶",
    "79647": "水产品",
}


def _get(url, timeout=20):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r


def _parse_detail(html):
    """解析 Excel 导出 HTML 表格，返回 {name, spec, unit, price} 列表。"""
    tds = re.findall(r"<td[^>]*>(.*?)</td>", html, re.S)
    cells = [re.sub(r"<[^>]+>", "", t).strip() for t in tds]
    cells = ["" if c == " " else c for c in cells]

    if "品名" not in cells:
        return []
    start = cells.index("品名")

    # 判断列数：表头 [品名,规格,计量单位,农超平均价] 默认4列；
    # 若农超价后紧跟「农贸平均价」则为5列。价格始终取第4列（农超平均价）。
    col_n = 4
    if start + 4 < len(cells) and "农贸" in cells[start + 4]:
        col_n = 5

    price_off = 3  # 农超平均价在表头偏移 3
    rows = []
    i = start + col_n
    while i + price_off < len(cells):
        name = cells[i]
        if not name:
            break
        price = cells[i + price_off]
        if re.match(r"^\d+(\.\d+)?$", price):
            rows.append({
                "name": name,
                "spec": cells[i + 1],
                "unit": cells[i + 2],
                "price": float(price),
            })
        i += col_n
    return rows


def fetch_sub(code, sub_name):
    """抓取单个子栏目最新一期，返回 {sub, date, rows}。"""
    list_url = urljoin(BASE, code + "/")
    r = _get(list_url)
    m = re.search(r'href="(\./\d{6}/t20\d{6}_\d+\.htm)"', r.text)
    if not m:
        return {"sub": sub_name, "code": code, "date": None, "rows": [], "error": "无文章"}
    detail_url = urljoin(list_url, m.group(1))
    # 从文件名取日期 t20260724_xxxx.htm -> 2026-07-24
    dm = re.search(r"t(20\d{2})(\d{2})(\d{2})_", m.group(1))
    date = f"{dm.group(1)}-{dm.group(2)}-{dm.group(3)}" if dm else None
    r2 = _get(detail_url)
    rows = _parse_detail(r2.text)
    return {"sub": sub_name, "code": code, "date": date, "url": detail_url, "rows": rows}


def fetch_all():
    """抓取全部民生子栏目，返回标准化结果。"""
    result = {"source": "厦门市发展和改革委员会-今日民生", "base": BASE,
              "subs": [], "rows": [], "total": 0}
    for code, name in SUBS.items():
        sub = fetch_sub(code, name)
        result["subs"].append(sub)
        for row in sub["rows"]:
            row["sub"] = name
            row["date"] = sub["date"]
            result["rows"].append(row)
        result["total"] += len(sub["rows"])
    return result


if __name__ == "__main__":
    data = fetch_all()
    print(f"数据源: {data['source']}")
    for s in data["subs"]:
        print(f"  [{s['sub']}] 日期 {s.get('date')} 价格 {len(s['rows'])} 条")
        for r in s["rows"][:3]:
            print(f"      {r['name']:<8} {r['price']}元/斤 ({r['spec']})")
    print(f"\n合计: {data['total']} 条真实价格")
    # 存档
    out = os.path.join(os.path.dirname(__file__), "xm_fgw_data.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已存档: {out}")
