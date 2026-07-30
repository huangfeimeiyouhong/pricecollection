# -*- coding: utf-8 -*-
"""临时验证：后厨管家账号 xmszf001 能否登录菜亿箩 OpenAPI 并拉取商品。"""
import requests

BASE = "http://openapi.caiyiluo.com/food.shop.openapi/"
USER = "xmszf001"
PWD = "xmszf123#"

s = requests.Session()
s.trust_env = False
try:
    r = s.post(BASE + "user/login.do",
               data={"username": USER, "password": PWD, "rememberMe": "true"}, timeout=25)
    print("login http", r.status_code)
    print("login body", r.text[:500])
    d = r.json()
    if not d.get("success"):
        print("LOGIN FAIL:", d.get("message"))
        raise SystemExit
    sess = d["data"]
    ra = s.get(BASE + "Addr/getUserAddrList.do", headers={"session": sess}, timeout=25)
    print("addr body", ra.text[:500])
    addrs = ra.json().get("data", [])
    if not addrs:
        print("NO ADDR"); raise SystemExit
    addr = addrs[0]["addrId"]
    print("addrId", addr, "houseName", addrs[0].get("houseName"))
    rp = s.get(BASE + "product/getProductInWarByAddrId.do",
               params={"addrId": addr}, headers={"session": sess}, timeout=30)
    dd = rp.json()
    prods = dd.get("data", [])
    print("products success", dd.get("success"), "count", len(prods))
    cats = {}
    for p in prods:
        c = p.get("oneCategoryName", "?")
        cats[c] = cats.get(c, 0) + 1
    print("categories", cats)
    for p in prods[:8]:
        sl = p.get("specList") or [{}]
        print("  ", p.get("productName"), "|", p.get("oneCategoryName"),
              "| 规格数", len(sl), "| 示例价", sl[0].get("specPrice"))
except Exception as e:
    print("ERR", type(e).__name__, e)
