# -*- coding: utf-8 -*-
"""菜亿箩开放平台适配器（实时抓取）
数据源: http://openapi.caiyiluo.com/food.shop.openapi/
接口:
  POST /user/login.do           登录，返回 session
  GET  /Addr/getUserAddrList.do 当前用户地址/仓库
  GET  /product/getProductInWarByAddrId.do?addrId=  归属仓库全部产品+规格价
说明:
  - 账号为供应商账号，规格价 specPrice 单位与其 saleUnit 一致（多为「斤」）。
  - 接口限流 10 次/分钟，调用前需登录拿 session，且 session 放在请求头 session 字段。
  - 该接口为 HTTP，需绕过本地代理（trust_env=False 等效 --noproxy '*'）。
"""
import os
import requests

BASE = "http://openapi.caiyiluo.com/food.shop.openapi/"
PHONE = "15021036257"
# 密码不要明文写入版本库/公开仓库。
# 优先级：环境变量 CAIYILUO_PASSWORD > 本仓库 gitignore 的 secrets.local.json（{"password":"..."}）
def _load_password():
    import json
    pwd = os.environ.get("CAIYILUO_PASSWORD", "")
    if pwd:
        return pwd
    try:
        with open(os.path.join(os.path.dirname(__file__), "secrets.local.json"), encoding="utf-8") as _f:
            return json.load(_f).get("password", "")
    except Exception:
        return ""
PASSWORD = _load_password()
# 常州仓 addrId（实测：龙潜路99号恒立液压股份有限公司），调接口动态获取失败时的兜底
ADDR_FALLBACK = "9506c4fc648442878d3104e3cb657624"


def _session():
    s = requests.Session()
    s.trust_env = False  # 忽略系统代理，等效 curl --noproxy '*'
    return s


def login(sess=None):
    sess = sess or _session()
    r = sess.post(BASE + "user/login.do",
                  data={"username": PHONE, "password": PASSWORD, "rememberMe": "true"},
                  timeout=25)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise RuntimeError("菜亿箩登录失败: " + str(d.get("message", "")))
    return d["data"]  # session 字符串


def get_addr_id(session, sess=None):
    sess = sess or _session()
    r = sess.get(BASE + "Addr/getUserAddrList.do", headers={"session": session}, timeout=25)
    r.raise_for_status()
    data = r.json().get("data", [])
    if not data:
        raise RuntimeError("菜亿箩无可用地址")
    for a in data:
        if a.get("houseName", "") == "常州仓":
            return a["addrId"]
    return data[0]["addrId"]


def fetch_products():
    """实时登录并抓取常州仓全部产品（含规格价）。返回产品字典列表。"""
    sess = _session()
    session = login(sess)
    addr = get_addr_id(session, sess)
    r = sess.get(BASE + "product/getProductInWarByAddrId.do",
                 params={"addrId": addr}, headers={"session": session}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if not d.get("success"):
        raise RuntimeError("菜亿箩产品获取失败: " + str(d.get("message", "")))
    return d["data"]


if __name__ == "__main__":
    prods = fetch_products()
    print(f"菜亿箩实时产品: {len(prods)} 条")
    fresh = [p for p in prods if p.get("oneCategoryName") == "新鲜蔬果"]
    print(f"新鲜蔬果: {len(fresh)} 条")
    for p in fresh[:5]:
        s = p["specList"][0]
        print(f"  {p['productName']} | {s['specName']} | ¥{s['specPrice']}/{s.get('saleUnit')}")
