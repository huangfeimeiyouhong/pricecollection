# -*- coding: utf-8 -*-
"""采集核心：编排各平台适配器、合并为标准快照、落盘。
快照维度: data/<city>/<date>.json
快照结构: {canonical:[...], pending:[...], cats:[...], meta:{...}, demo:false, date, source:{pid:状态}}
前端 /api/data 与 /api/update 均消费本模块。
"""
import os
import re
import json
import copy
import datetime

ROOT = os.path.dirname(__file__)
DATA_DIR = os.path.join(ROOT, "data")

# 忽略系统代理，等效 curl --noproxy '*'（菜亿箩为 HTTP，代理会拦截）
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_k, None)

import xm_fgw_adapter
import minnan_adapter
import caiyiluo_adapter
import beijing_adapter
import tianjin_adapter
import tj_fgj_adapter
import tj_binhai_adapter
import houchu_adapter

# ---- 城市 → 平台配置（单一事实来源） ----
# role: base=作为基准商品底表；supplier=供应商价（同名挂接 + 名称差异进待映射）
CITY_PLATFORMS = {
    "xiamen": [
        {"id": "A", "name": "菜亿箩", "color": "#07c160", "src": "caiyiluo", "role": "supplier", "city": "xiamen"},
        {"id": "B", "name": "厦门市发改委", "color": "#1989fa", "src": "fgw", "role": "base", "city": "xiamen"},
        {"id": "C", "name": "闽南果蔬批发市场", "color": "#ff9f43", "src": "minnan", "role": "base", "city": "xiamen"},
    ],
    "beijing": [
        {"id": "B1", "name": "北京岳各庄", "color": "#e74c3c", "src": "beijing", "role": "base", "city": "beijing", "market_id": "850"},
        {"id": "B2", "name": "北京石门", "color": "#9b59b6", "src": "beijing", "role": "base", "city": "beijing", "market_id": "1004"},
        {"id": "B3", "name": "北京新发地", "color": "#16a085", "src": "beijing", "role": "base", "city": "beijing", "market_id": "1006"},
        {"id": "B4", "name": "北京大洋路", "color": "#f39c12", "src": "beijing", "role": "base", "city": "beijing", "market_id": "521"},
        {"id": "B5", "name": "北京水屯", "color": "#2980b9", "src": "beijing", "role": "base", "city": "beijing", "market_id": "822"},
        {"id": "B6", "name": "北京菜篮子", "color": "#d35400", "src": "beijing", "role": "base", "city": "beijing", "market_id": "1329"},
    ],
    "tianjin": [
        {"id": "T1", "name": "天津武清大沙河", "color": "#c0392b", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "388"},
        {"id": "T2", "name": "天津何庄子", "color": "#8e44ad", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "865"},
        {"id": "T3", "name": "天津碧城", "color": "#27ae60", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "1029"},
        {"id": "T4", "name": "天津韩家墅海吉星", "color": "#e67e22", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "1030"},
        {"id": "T5", "name": "天津红旗农贸", "color": "#2980b9", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "1031"},
        {"id": "T6", "name": "天津金钟河", "color": "#16a085", "src": "tianjin", "role": "base", "city": "tianjin", "market_id": "1190"},
        {"id": "T7", "name": "天津发改委(零售监测)", "color": "#34495e", "src": "tj_fgj", "role": "base", "city": "tianjin"},
        {"id": "T8", "name": "天津滨海新区(零售监测)", "color": "#7f8c8d", "src": "tj_binhai", "role": "base", "city": "tianjin"},
    ],
}
CITIES = [
    {"id": "xiamen", "name": "厦门市"},
    {"id": "beijing", "name": "北京市"},
    {"id": "tianjin", "name": "天津市"},
]


def norm(n):
    if not n:
        return ""
    n = n.replace("（", "(").replace("）", ")")
    for ch in ["/", "-", "－", "_", "~", "\\"]:
        n = n.replace(ch, "")
    n = re.sub(r"(优|精选|本地|普通)", "", n)
    return n.strip().lower()


SYN = {"上海青": "大青菜", "马铃薯": "土豆", "番茄": "西红柿",
       "菜椒": "青椒", "老姜": "生姜", "鲜鸡蛋": "鸡蛋"}


# 北京 21food 行轻量品类推断（按名称关键字粗分，未命中归为 农副产品）
def classify_bj(name):
    n = name or ""
    if any(k in n for k in ["猪", "牛", "羊", "鸡", "鸭", "鹅", "肉", "蛋", "乳", "奶",
                            "腿", "排", "里脊", "肝", "肚", "禽"]):
        return "肉禽蛋奶"
    if any(k in n for k in ["鱼", "虾", "蟹", "贝", "蚝", "鱿", "带鱼", "鲅", "鲈", "鲤",
                            "鲫", "鳝", "鳅", "鳖", "龟", "水产", "海参", "虾仁"]):
        return "水产品"
    if any(k in n for k in ["苹果", "梨", "橘", "桔", "橙", "柑", "桃", "李", "杏", "葡萄",
                            "香蕉", "西瓜", "芒果", "草莓", "枣", "柚", "柿", "火龙果",
                            "猕猴桃", "果", "瓜", "菠萝", "樱桃", "石榴", "蓝莓"]):
        return "水果"
    if any(k in n for k in ["米", "面", "油", "粮", "豆", "麦", "谷", "芝麻", "花生",
                            "玉米", "薯", "杂粮", "粉", "稻"]):
        return "粮油"
    return "蔬菜"


# ---------- 平台数据抓取（实时） ----------
def fetch_platform(plat):
    """返回统一行列表: {name, price_jin, spec, time, one_cat?, raw_kg?, cat1?, cat2?}"""
    src = plat["src"]
    if src == "caiyiluo":
        prods = caiyiluo_adapter.fetch_products()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        rows = []
        for p in prods:
            if not p.get("specList"):
                continue
            s = p["specList"][0]
            price = s.get("specPrice")
            if price is None:
                continue
            rows.append({
                "name": p["productName"],
                "price_jin": float(price),
                "spec": s.get("specName", ""),
                "time": now,
                "one_cat": p.get("oneCategoryName", ""),
            })
        return rows
    if src == "fgw":
        d = xm_fgw_adapter.fetch_all()
        rows = []
        for r in d["rows"]:
            rows.append({
                "name": r["name"], "price_jin": float(r["price"]), "spec": r.get("spec", ""),
                "time": (r.get("date") or "") + " 发布", "cat1": r.get("sub", "其他"), "cat2": r.get("spec", "—"),
            })
        return rows
    if src == "minnan":
        res = minnan_adapter.fetch_market_prices(use_cache_fallback=False)
        rows = []
        for r in res.get("rows", []):
            rows.append({
                "name": r["name"], "price_jin": float(r["price_per_jin"]), "spec": "斤",
                "time": (r.get("quote_date") or "") + " 11:00", "raw_kg": r.get("price_per_kg"),
                "cat1": "新鲜蔬果", "cat2": "蔬菜",
            })
        return rows
    if src in ("beijing", "tianjin"):
        mod = beijing_adapter if src == "beijing" else tianjin_adapter
        res = mod.fetch_market(plat.get("market_id"))
        rows = []
        for r in res:
            avg = r.get("avg")
            if avg is None:
                continue
            rows.append({
                "name": r["name"],
                "price_jin": round(float(avg) / 2, 2),  # 元/公斤 -> 元/斤，统一口径
                "spec": "斤",
                "time": (r.get("date") or "") + " 报价",
                "raw_kg": round(float(avg), 2),
                "cat1": classify_bj(r["name"]),
                "cat2": "—",
            })
        return rows
    if src == "tj_fgj":
        res = tj_fgj_adapter.fetch_rows()
        rows = []
        for r in res:
            rows.append({
                "name": r["name"],
                "price_jin": r["price_jin"],
                "spec": "斤",
                "time": (r.get("period") or "") + " 月均价",
                "raw_kg": r.get("raw_kg"),
                "cat1": classify_bj(r.get("category", "")),
                "cat2": "—",
            })
        return rows
    if src == "tj_binhai":
        res = tj_binhai_adapter.fetch_rows()
        rows = []
        for r in res:
            rows.append({
                "name": r["name"],
                "price_jin": r["price_jin"],
                "spec": "斤",
                "time": (r.get("period") or "") + " 月均价",
                "raw_kg": r.get("raw_kg"),
                "cat1": classify_bj(r.get("category", "")),
                "cat2": "—",
            })
        return rows
    raise RuntimeError("未知平台源: " + str(src))


def fetch_city(city):
    """抓取某城市全部平台实时数据，返回 {pid: rows}, 及来源状态。"""
    rows_by_pid = {}
    source = {}
    for p in CITY_PLATFORMS.get(city, []):
        try:
            rows = fetch_platform(p)
            rows_by_pid[p["id"]] = rows
            source[p["id"]] = {"name": p["name"], "ok": True, "count": len(rows)}
        except Exception as e:
            source[p["id"]] = {"name": p["name"], "ok": False, "error": str(e)}
            rows_by_pid[p["id"]] = []
    return rows_by_pid, source


# ---------- 合并为标准快照 ----------
def merge_snapshot(rows_by_pid, city, date, time_label_caiyiluo=None):
    plat = {p["id"]: p for p in CITY_PLATFORMS.get(city, [])}
    # 绑定桥接：平台商品名 → 基准商品（支持一对多）
    bind_map = platform_bind_map()
    base = houchu_adapter.load_goods()
    uuid2name = {g["uuid"]: g["name"] for g in base.get("goods", [])}

    def std_of(name):
        """返回 (canon_key, display_name)。已绑定基准则用基准名作标准名，
        从而让同城市不同平台、同名/同义（经绑定）的商品归并到同一行。"""
        k = norm(name)
        uus = bind_map.get(k)
        if uus:
            bn = uuid2name.get(uus[0]["uuid"])
            if bn:
                return norm(bn), bn
        return k, name

    canonical = {}
    pending = []

    # 1) 基准平台铺底（按标准名并表）
    for pid, p in plat.items():
        if p["role"] != "base":
            continue
        for r in rows_by_pid.get(pid, []):
            ck, dn = std_of(r["name"])
            if not ck:
                continue
            c = canonical.setdefault(ck, {"name": dn,
                                           "cat1": r.get("cat1", "其他"),
                                           "cat2": r.get("cat2", "—"), "prices": []})
            pr = {"pid": pid, "price": r["price_jin"], "spec": r.get("spec", ""),
                  "time": r.get("time", "")}
            if r.get("raw_kg"):
                pr["kg"] = r["raw_kg"]
            c["prices"].append(pr)

    canon_norm = {norm(c["name"]) for c in canonical.values()}

    # 2) 供应商平台：标准名挂接；蔬果名称差异进待映射
    for pid, p in plat.items():
        if p["role"] != "supplier":
            continue
        for r in rows_by_pid.get(pid, []):
            ck, dn = std_of(r["name"])
            if ck in canonical:
                canonical[ck]["prices"].append({"pid": pid, "price": r["price_jin"],
                                                 "spec": r.get("spec", ""), "time": r.get("time", "")})
                continue
            if r.get("one_cat") == "新鲜蔬果":
                target = None
                for k, v in SYN.items():
                    if ck == norm(k) and norm(v) in canon_norm:
                        target = v
                    elif ck == norm(v) and norm(k) in canon_norm:
                        target = k
                if target:
                    pending.append({"pname": r["name"], "pid": pid, "target": target,
                                    "price": r["price_jin"]})

    cats = sorted(set(c["cat1"] for c in canonical.values()))
    return {"canonical": [{"key": k, **v} for k, v in canonical.items()],
            "pending": pending, "cats": cats}


def build_snapshot(city, rows_by_pid, date, source):
    snap = merge_snapshot(rows_by_pid, city, date)
    snap["date"] = date
    snap["demo"] = False
    snap["meta"] = {"built_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": source}
    return snap


# ---------- 磁盘读写 ----------
def _city_dir(city):
    d = os.path.join(DATA_DIR, city)
    os.makedirs(d, exist_ok=True)
    return d


def save_snapshot(city, date, snap):
    _city_dir(city)
    path = os.path.join(DATA_DIR, city, date + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)
    return path


def load_snapshot(city, date):
    path = os.path.join(DATA_DIR, city, date + ".json")
    if not os.path.exists(path):
        return None
    return json.load(open(path, encoding="utf-8"))


def list_dates(city):
    d = os.path.join(DATA_DIR, city)
    if not os.path.isdir(d):
        return []
    ds = [f[:-5] for f in os.listdir(d) if f.endswith(".json")]
    return sorted(ds, reverse=True)


def payload(city=None):
    """返回前端所需全量载荷。"""
    snaps = {}
    dates = {}
    for c in CITY_PLATFORMS:
        ds = list_dates(c)
        dates[c] = ds
        snaps[c] = {d: load_snapshot(c, d) for d in ds}
    return {"cities": CITIES, "platforms": [p for plist in CITY_PLATFORMS.values() for p in plist],
            "dates": dates, "snaps": snaps, "bind_map": platform_bind_map()}


def dump_static(out_dir="public"):
    """导出静态前端所需全量 JSON 到 <out_dir>/data.json（供 Cloudflare Pages 等静态托管）。

    包含: payload() 的价格快照 + bind_map，以及基准商品库 benchmark_with_match()
    与平台名列表 platform_names()。前端改为只读该文件并缓存在 localStorage，
    不再依赖任何后端 /api/* 接口。
    """
    os.makedirs(out_dir, exist_ok=True)
    bundle = payload()
    bundle["houchu"] = benchmark_with_match()
    bundle["houchu_platforms"] = platform_names()
    bundle["generated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path = os.path.join(out_dir, "data.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)
    size = os.path.getsize(path)
    print(f"静态包已生成: {path} ({size // 1024} KB) | 城市 {len(bundle['cities'])} "
          f"| 基准 {bundle['houchu']['count']} 条 | 生成于 {bundle['generated_at']}")
    return path



# ---------- seed（用缓存真实数据生成初始快照） ----------
def seed():
    """用已缓存的真实数据生成厦门 2026-07-24 快照（无需联网）。已存在则跳过。"""
    city = "xiamen"
    date = "2026-07-24"
    if load_snapshot(city, date):
        print(f"seed 跳过：{city}/{date} 已存在（如需重置请删除 data/{city}/{date}.json）")
        return load_snapshot(city, date)
    products = json.load(open(os.path.join(ROOT, "products_raw.json"), encoding="utf-8"))["data"]
    fgw = json.load(open(os.path.join(ROOT, "xm_fgw_data.json"), encoding="utf-8"))
    minnan = json.load(open(os.path.join(ROOT, "minnan_market_data.json"), encoding="utf-8"))

    rows_by_pid = {
        "A": [{"name": p["productName"], "price_jin": float(p["specList"][0]["specPrice"]),
               "spec": p["specList"][0].get("specName", ""), "time": "2026-07-24 13:58",
               "one_cat": p.get("oneCategoryName", "")}
              for p in products if p.get("specList")],
        "B": [{"name": r["name"], "price_jin": float(r["price"]), "spec": r.get("spec", ""),
               "time": (r.get("date") or "") + " 发布", "cat1": r.get("sub", "其他"), "cat2": r.get("spec", "—")}
              for r in fgw["rows"]],
        "C": [{"name": p["name"], "price_jin": round(p["price"] / 2, 2), "spec": "斤",
               "time": minnan["quote_date"] + " 11:00", "raw_kg": p["price"],
               "cat1": "新鲜蔬果", "cat2": "蔬菜"} for p in minnan["products"]],
    }
    source = {"A": {"name": "菜亿箩", "ok": True, "count": len(rows_by_pid["A"]), "cached": True},
              "B": {"name": "厦门市发改委", "ok": True, "count": len(rows_by_pid["B"]), "cached": True},
              "C": {"name": "闽南果蔬批发市场", "ok": True, "count": len(rows_by_pid["C"]), "cached": True}}
    snap = build_snapshot(city, rows_by_pid, date, source)
    path = save_snapshot(city, date, snap)
    print(f"seed 完成: {path} | 基准 {len(snap['canonical'])} | 待映射 {len(snap['pending'])}")
    return snap


# ---------- update（实时抓取当日数据） ----------
def update(city):
    if not CITY_PLATFORMS.get(city):
        raise RuntimeError("城市无配置平台: " + city)
    if not CITY_PLATFORMS[city]:
        raise RuntimeError("城市暂未接入平台: " + city)
    beijing_adapter.invalidate_cache()  # 更新时强制重新抓取北京最新数据
    tianjin_adapter.invalidate_cache()  # 更新时强制重新抓取天津最新数据
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    rows_by_pid, source = fetch_city(city)
    # 累加合并：某平台「本次抓取为 0 条」但历史快照有数据，则沿用历史，
    # 避免单次抓取失败（如验证码超时、页面重载瞬间读取失败）把该市场数据清空。
    # 多次运行可逐步补齐，最终所有平台均有数据。
    existing = load_snapshot(city, date)
    if existing:
        hist_by_pid = {}
        for item in existing.get("canonical", []):
            for pr in item.get("prices", []):
                pid = pr.get("pid")
                if not pid:
                    continue
                hist_by_pid.setdefault(pid, []).append({
                    "name": item.get("name", ""),
                    "price_jin": pr.get("price"),
                    "spec": pr.get("spec", ""),
                    "time": pr.get("time", ""),
                    "raw_kg": pr.get("kg"),
                    "cat1": item.get("cat1", "其他"),
                    "cat2": item.get("cat2", "—"),
                })
        for p in CITY_PLATFORMS.get(city, []):
            pid = p["id"]
            if not rows_by_pid.get(pid) and hist_by_pid.get(pid):
                rows_by_pid[pid] = hist_by_pid[pid]
                source[pid] = {"name": p["name"], "ok": True,
                               "count": len(rows_by_pid[pid]), "cached_fallback": True}
    snap = build_snapshot(city, rows_by_pid, date, source)
    ok = [f"{v['name']}({v['count']}条)" for v in source.values() if v.get("ok")]
    fail = [f"{v['name']}:{v.get('error','')}" for v in source.values() if not v.get("ok")]
    msg = f"{city} 更新完成：{'、'.join(ok)}"
    if fail:
        msg += "；失败：" + "；".join(fail)
    snap["_msg"] = msg
    save_snapshot(city, date, snap)
    # 更新后同步重新生成静态前端包（public/data.json），便于推送到 Cloudflare。
    try:
        dump_static()
    except Exception as e:
        print(f"警告: 静态包重新生成失败 -> {e}")
    return snap, msg


# ---------- 后厨管家基准商品库 + 映射绑定 ----------
BINDINGS_FILE = os.path.join(DATA_DIR, "houchu_bindings.json")


def platform_pool():
    """聚合所有城市最新快照的 canonical 商品，构建 {norm_key: display_name} 匹配池。"""
    pool = {}
    for c in CITY_PLATFORMS:
        ds = list_dates(c)
        if not ds:
            continue
        snap = load_snapshot(c, ds[0])
        if not snap:
            continue
        for item in snap.get("canonical", []):
            k = norm(item["name"])
            if k and k not in pool:
                pool[k] = item["name"]
    return pool


def platform_names():
    """所有城市 canonical 商品去重列表，供前端绑定下拉。返回 [{name, key}]。"""
    seen = {}
    for c in CITY_PLATFORMS:
        ds = list_dates(c)
        if not ds:
            continue
        snap = load_snapshot(c, ds[0])
        if not snap:
            continue
        for item in snap.get("canonical", []):
            k = norm(item["name"])
            if k and k not in seen:
                seen[k] = item["name"]
    return [{"name": v, "key": k} for k, v in seen.items()]


def auto_match(houchu_name, pool):
    """后厨管家商品名 → 平台 canonical 归一化 key（匹配不上返回 None）。"""
    k = norm(houchu_name)
    if k in pool:
        return k
    for sk, sv in SYN.items():
        if k == norm(sk) and norm(sv) in pool:
            return norm(sv)
        if k == norm(sv) and norm(sk) in pool:
            return norm(sk)
    return None


def load_bindings():
    if os.path.exists(BINDINGS_FILE):
        return json.load(open(BINDINGS_FILE, encoding="utf-8"))
    return {"bindings": {}, "updated_at": ""}


def save_bindings(b):
    b["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(BINDINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(b, f, ensure_ascii=False, indent=2)


def benchmark_with_match():
    """返回基准商品库 + 每个商品的自动匹配/已绑定状态。绑定持久化在 bindings.json。"""
    base = houchu_adapter.load_goods()
    pool = platform_pool()
    binds = load_bindings().get("bindings", {})
    out = []
    for g in base["goods"]:
        uid = g["uuid"]
        b = binds.get(uid)
        if b and b.get("match_key"):
            match_key = b["match_key"]
            confirmed = b.get("confirmed", True)
            auto = False
        else:
            match_key = auto_match(g["name"], pool)
            confirmed = False
            auto = match_key is not None
        out.append({
            "uuid": uid, "name": g["name"], "unit": g.get("unit", ""),
            "spec": g.get("spec", ""),
            "cat1": g.get("cat1", ""),      # 一级分类名
            "cat2": g.get("cat2", ""),       # 二级分类名
            "match_key": match_key, "match_name": pool.get(match_key, ""),
            "confirmed": confirmed, "auto": auto,
        })
    cats = sorted({g["cat1"] for g in out if g["cat1"]})
    return {"org": base["org"], "count": base["count"],
            "excluded_count": base.get("excluded_count", 0),
            "fetched_at": base["fetched_at"], "pool_size": len(pool),
            "categories": cats,
            "confirmed_count": sum(1 for o in out if o["confirmed"]),
            "goods": out}


def save_binding(uuid, match_key):
    """保存/更新某后厨管家商品的绑定（confirmed=True，持久化）。"""
    b = load_bindings()
    b.setdefault("bindings", {})[uuid] = {
        "match_key": match_key,
        "confirmed": True,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    save_bindings(b)
    return b


# ---------- 反向映射：平台商品 → 基准库绑定状态（供价格对比列表使用） ----------
def platform_bind_map():
    """返回 {platform_norm_key: [{uuid, houchu_name}]} 反向索引（支持一对多）。
    仅包含 confirmed=True 的绑定，且基准 uuid 必须仍在基准库中（非食材已过滤）。
    价格对比列表用它判断每条商品是否已匹配基准库、以及匹配到的基准名列表。"""
    binds = load_bindings().get("bindings", {})
    base = houchu_adapter.load_goods()
    # 建 uuid→name 查找表
    uuid2name = {g["uuid"]: g["name"] for g in base.get("goods", [])}
    rev = {}
    for uid, info in binds.items():
        if not info.get("match_key") or not info.get("confirmed"):
            continue
        mk = info["match_key"]
        if uid not in uuid2name:   # 该基准商品已被过滤（如非食材），跳过
            continue
        rev.setdefault(mk, []).append({"uuid": uid, "houchu_name": uuid2name[uid]})
    return rev


if __name__ == "__main__":
    seed()
