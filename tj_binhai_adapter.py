# -*- coding: utf-8 -*-
"""天津市滨海新区发改委「市场价格运行情况」适配器。

数据源: https://fgw.tjbh.gov.cn/channels/929.html
该频道按月发布「YYYY年M月份滨海新区市场价格运行情况」，正文含一张
「7月份农副产品集贸市场零售价格」表，为零售价（元/斤）。

本适配器负责：
1. fetch_latest()  —— 从列表页取【最新一期】报告链接与期号（如 2026年7月）。
2. fetch_rows()    —— 解析详情页表格，返回统一行格式（见下方 ROW 结构）。

行格式（与 collect.fetch_platform 对齐）:
    {
        "name":      商品名（品名；有具体规格时附 (规格)，如 "猪肉(带皮五花肉)"、"草鱼(每条1-1.5千克)"）,
        "category":  品名大类（如 "猪肉"）—— 供 collect.classify_bj 归并为粗类,
        "price_jin": 本月均价（元/斤，float）,
        "raw_kg":    本月均价 * 2（元/公斤，float）,
        "spec":      "斤",
        "period":    "2026年7月",
        "mom":       环比变化%（str，如 "+0.69%"）,
        "yoy":       同比变化%（str，如 "-12.37%"）,
    }

注意：走系统代理或直连均可（urllib 自动读取 http_proxy/https_proxy；
若被 collect 导入时清掉代理，则直连 .cn 政府站点同样 200 可用）。
"""
import re
import ssl
import json
import urllib.request
import urllib.error

BASE = "https://fgw.tjbh.gov.cn/channels/929.html"
LIST_RE = re.compile(
    r'<a href="(https://fgw\.tjbh\.gov\.cn/contents/929/\d+\.html)"[^>]*'
    r'title="([^"]*市场价格运行情况[^"]*)"', re.S)
# 规格中无意义的质量修饰词，出现时不并入商品名
_GENERIC_SPEC = {"鲜嫩", "鲜", "-", "—", ""}


def _get(url, timeout=40):
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    enc = "utf-8"
    try:
        ct = r.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            enc = m.group(1)
    except Exception:
        pass
    return raw.decode(enc, errors="replace")


def _clean(s):
    """去标签残留、折叠空白、去首尾空格。"""
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("　", " ")
    return re.sub(r"\s+", "", s).strip()


def fetch_latest():
    """返回 (url, period_label)。period_label 形如 '2026年7月'。取列表最新一期。"""
    html = _get(BASE)
    links = LIST_RE.findall(html)
    if not links:
        raise RuntimeError("未找到滨海新区市场价格运行情况链接")
    href, title = links[0]  # 列表默认按时间倒序，取第一条
    m = re.search(r"(\d{4}年\d{1,2}月)", title)
    period = m.group(1) if m else ""
    return href, period


def _parse_table(html):
    """解析详情页表格，返回 [(品名, 规格, 本月均价, 上月均价, 环比, 去年同期, 同比), ...]。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for r in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        if len(tds) < 3:
            continue
        cells = [_clean(t) for t in tds]
        pinming, guige, benyue = cells[0], cells[1], cells[2]
        if not pinming or not benyue:
            continue
        try:
            float(benyue.replace(",", ""))
        except ValueError:
            continue
        mom = cells[4] if len(cells) > 4 else ""
        yoy = cells[6] if len(cells) > 6 else ""
        out.append((pinming, guige, benyue, mom, yoy))
    return out


def fetch_rows(url=None):
    """解析最新一期（或指定 url）报告，返回统一行格式列表。"""
    if url is None:
        url, _period = fetch_latest()
    else:
        _period = ""
    html = _get(url)
    if not _period:
        m = re.search(r"(\d{4}年\d{1,2}月)", html)
        _period = m.group(1) if m else ""
    rows = []
    for pinming, guige, benyue, mom, yoy in _parse_table(html):
        avg_f = float(benyue.replace(",", ""))
        spec_clean = _clean(guige)
        # 有具体规格（非质量修饰词）时并入商品名，如 猪肉(带皮五花肉)、草鱼(每条1-1.5千克)
        if spec_clean and spec_clean not in _GENERIC_SPEC:
            name = f"{pinming}({spec_clean})"
        else:
            name = pinming
        rows.append({
            "name": name,
            "category": pinming,
            "price_jin": round(avg_f, 2),
            "raw_kg": round(avg_f * 2, 2),
            "spec": "斤",
            "period": _period,
            "mom": mom,
            "yoy": yoy,
        })
    return rows


if __name__ == "__main__":
    u, p = fetch_latest()
    print("最新报告:", p, u)
    rs = fetch_rows(u)
    print("解析条数:", len(rs))
    print(json.dumps(rs[:4], ensure_ascii=False, indent=2))
