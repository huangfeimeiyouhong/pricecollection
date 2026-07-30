# -*- coding: utf-8 -*-
"""
闽南果蔬批发市场（福建厦门同安）价格适配器
============================================
数据源: 农业农村部全国农产品批发市场价格信息系统 (pfsc.agri.cn)
        → 由 21food.cn「食价搜」转发每日市场行情

接入方式:
  1. 通过官方接口 getMarketByProvinceCode 定位市场，取得 marketId / marketCode
     POST https://pfsc.agri.cn/api/priceQuotationController/getMarketByProvinceCode
     params={"provinceCode":"350000"}  → 在市场列表中查找 "闽南果蔬"
  2. 取每日行情：官方 getMarketReportPriceChart 返回的 data 为前端加密串，
     无法直接解析；因此采用「已发布的每日行情页」作为可用数据源：
     https://wap.21food.cn/price/market/1039.html
  3. 解析后统一归一为「元/斤」(元/公斤 ÷ 2)，便于跨平台比价。

说明: 这是原型阶段的轻量适配器，后续落库时建议改为定时任务 + 官方接口
      (待官方解密方案明确后替换 step2)。
"""
import json, re, os
import requests

MARKET_PAGE = "https://wap.21food.cn/price/market/1039.html"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1")

# 农业农村部官方接口定位市场（验证用，返回市场元数据）
PFSC_MARKET_API = "https://pfsc.agri.cn/api/priceQuotationController/getMarketByProvinceCode"


def locate_market():
    """通过官方接口确认市场元数据（marketId / marketCode）。"""
    try:
        r = requests.post(PFSC_MARKET_API, params={"provinceCode": "350000"},
                          headers={"User-Agent": UA, "Origin": "https://pfsc.agri.cn",
                                    "Referer": "https://pfsc.agri.cn/"}, timeout=20)
        for m in r.json().get("content", []):
            if "闽南" in m.get("marketName", "") or "同安" in m.get("address", ""):
                return {"marketName": m.get("marketName"), "marketId": m.get("id"),
                        "marketCode": m.get("marketCode"), "address": m.get("address")}
    except Exception as e:
        return {"error": str(e)}
    return None


def _parse_page(html):
    rows = []
    for tr in re.findall(r"<tr>.*?</tr>", html, re.S):
        nm = re.search(r'dre_xr1">([^<]+)</a>', tr)
        pr = re.search(r'dre_xr3">([\d.]+)元<em>/公斤</em>', tr)
        dt = re.search(r"(\d{4}-\d{2}-\d{2})", tr)
        if nm and pr:
            rows.append({
                "name": nm.group(1).strip(),
                "price_per_kg": float(pr.group(1)),
                "price_per_jin": round(float(pr.group(1)) / 2, 2),  # 1公斤=2斤
                "unit": "元/斤",
                "quote_date": dt.group(1) if dt else None,
            })
    return rows


def fetch_market_prices(use_cache_fallback=True):
    """实时抓取市场当日行情，失败则回退到本地存档。返回标准化行。"""
    try:
        r = requests.get(MARKET_PAGE, headers={"User-Agent": UA}, timeout=20)
        rows = _parse_page(r.text)
        if rows:
            return {"ok": True, "live": True, "count": len(rows), "rows": rows}
    except Exception as e:
        err = str(e)
    # 回退存档
    if use_cache_fallback:
        cache = os.path.join(os.path.dirname(__file__), "minnan_market_data.json")
        if os.path.exists(cache):
            data = json.load(open(cache, encoding="utf-8"))
            rows = [{"name": p["name"], "price_per_kg": p["price"],
                     "price_per_jin": round(p["price"] / 2, 2), "unit": "元/斤",
                     "quote_date": data["quote_date"]} for p in data["products"]]
            return {"ok": True, "live": False, "count": len(rows), "rows": rows,
                    "note": "实时抓取失败，使用本地存档", "error": err if 'err' in dir() else None}
    return {"ok": False, "error": err if 'err' in dir() else "无数据"}


if __name__ == "__main__":
    print("=== 市场定位(官方接口) ===")
    print(json.dumps(locate_market(), ensure_ascii=False))
    print("\n=== 实时行情 ===")
    res = fetch_market_prices()
    print("live =", res.get("live"), "| count =", res.get("count"))
    for x in res.get("rows", [])[:5]:
        print(f"  {x['name']:<6} {x['price_per_kg']}元/公斤 → {x['price_per_jin']}元/斤  ({x['quote_date']})")
