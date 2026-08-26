# -*- coding: utf-8 -*-
"""天津市发改委「菜篮子」农副产品零售价格监测表 适配器。

数据源: https://fzgg.tj.gov.cn/zwgk_47325/zfxxgk1/fdzdgknr1/tjxx/
该页面按月发布「天津市"菜篮子"工程主要农副产品零售价格监测表」，为零售价（元/500克）。

本适配器负责：
1. fetch_latest()  —— 从列表页取【最新一期】监测表链接与期号（如 2026年7月）。
2. fetch_rows()    —— 解析详情页表格，返回统一行格式（见下方 ROW 结构）。

行格式（与 collect.fetch_platform 对齐）:
    {
        "name":      规格（具体品名，如 "集贸带皮五花肉"）,
        "category":  品名（大类，如 "猪肉"）—— 供 collect.classify_bj 归并为粗类,
        "price_jin": 月均价（元/500克 = 元/斤，float）,
        "raw_kg":    月均价 * 2（元/公斤，float）,
        "max":       最高价（float）,
        "min":       最低价（float）,
        "unit":      "元/500克",
        "period":    "2026年7月",
    }

注意：走系统代理（urllib 自动读取 http_proxy/https_proxy 环境变量）。
"""
import re
import ssl
import json
import urllib.request
import urllib.error

BASE = "https://fzgg.tj.gov.cn/zwgk_47325/zfxxgk1/fdzdgknr1/tjxx/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 汇总/无效行特征（规格为空，或规格==品名，或含"均价"汇总字样）
_SUMMARY_RE = re.compile(r"均价|平均|合计|总计", re.S)

# 规格中无意义的质量修饰词，出现时不并入商品名（避免 24 种蔬菜都叫「集贸新鲜」撞名）
_GENERIC_SPEC = {"集贸新鲜", "集贸", "集贸普通", "—", "-", ""}


def _make_name(cat, spec):
    """由 品名+规格 生成唯一可读的商品名。

    天津发改委监测表的「规格」列实为具体品名/部位（集贸带皮五花肉、集贸去骨净肉、
    集贸新鲜…），仅用规格会撞名（牛肉/羊肉都叫「集贸去骨净肉」、24 种蔬菜都叫
    「集贸新鲜」）。故以 品名 为主、规格有意义时括注，保证 40 行各自唯一。
    """
    spec_clean = re.sub(r"\s+", "", spec.replace("&nbsp;", " ")).strip()
    if spec_clean and spec_clean not in _GENERIC_SPEC:
        return f"{cat}({spec_clean})"
    return cat


def _get(url, timeout=40):
    """带 UA 的 GET，返回解码后的文本。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        raw = r.read()
    # 尝试从 Content-Type 推断编码，默认 utf-8
    enc = "utf-8"
    try:
        ct = r.headers.get("Content-Type", "")
        m = re.search(r"charset=([\w-]+)", ct)
        if m:
            enc = m.group(1)
    except Exception:
        pass
    return raw.decode(enc, errors="replace")


def _abs(href, base=BASE):
    if href.startswith("http"):
        return href
    if href.startswith("./"):
        return base + href[2:]
    if href.startswith("/"):
        return "https://fzgg.tj.gov.cn" + href
    return base + href


def fetch_latest():
    """返回 (url, period_label)。period_label 形如 '2026年7月'。取列表最新一期。"""
    html = _get(BASE)
    # 匹配带 title 的链接，title 含「价格监测表」
    links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*title="([^"]*价格监测表[^"]*)"',
                       html, re.S)
    if not links:
        # 兜底：匹配可见文本含价格监测表的链接
        links = re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*价格监测表[^<]*)</a>',
                           html, re.S)
    if not links:
        raise RuntimeError("未找到天津发改委价格监测表链接")
    # 列表默认按时间倒序，取第一条
    href, title = links[0]
    url = _abs(href)
    m = re.search(r"(\d{4}年\d{1,2}月)", title)
    period = m.group(1) if m else ""
    return url, period


def _parse_table(html):
    """解析详情页表格，返回原始行列表 [(cat, name, unit, hi, lo, avg), ...]。"""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    out = []
    for r in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        tds = [re.sub(r"<[^>]+>", "", t).replace("&nbsp;", " ")
               .replace("　", " ").strip() for t in tds]
        if len(tds) < 6:
            continue
        cat, name, unit, hi, lo, avg = tds[0], tds[1], tds[2], tds[3], tds[4], tds[5]
        # 必须有具体品名，且 avg 可解析为数字
        if not name or name in ("—", "-", ""):
            continue
        if _SUMMARY_RE.search(name) or _SUMMARY_RE.search(cat):
            continue
        try:
            float(avg.replace(",", ""))
        except ValueError:
            continue
        out.append((cat, name, unit, hi, lo, avg))
    return out


def fetch_rows(url=None):
    """解析最新一期（或指定 url）监测表，返回统一行格式列表。"""
    if url is None:
        url, _period = fetch_latest()
    else:
        _period = ""
    html = _get(url)
    if not _period:
        # 从页面标题/文件名尝试提取期号
        m = re.search(r"(\d{4}年\d{1,2}月)", html)
        _period = m.group(1) if m else ""
    rows = []
    for cat, name, unit, hi, lo, avg in _parse_table(html):
        avg_f = float(avg.replace(",", ""))
        rows.append({
            "name": _make_name(cat, name),
            "category": cat,
            "price_jin": round(avg_f, 2),
            "raw_kg": round(avg_f * 2, 2),
            "max": float(hi.replace(",", "")) if hi else None,
            "min": float(lo.replace(",", "")) if lo else None,
            "unit": unit or "元/500克",
            "period": _period,
        })
    return rows


if __name__ == "__main__":
    u, p = fetch_latest()
    print("最新监测表:", p, u)
    rs = fetch_rows(u)
    print("解析条数:", len(rs))
    print(json.dumps(rs[:3], ensure_ascii=False, indent=2))
