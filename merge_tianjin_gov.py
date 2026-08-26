# -*- coding: utf-8 -*-
"""将天津市政府零售监测数据（T7 天津发改委 / T8 滨海新区）并入【现有】天津快照。

设计：天津 T1–T6 来自 21food 批发市场（需弹验证码人工点选，由 update_tianjin.py
驱动）。本脚本只负责把无需验证码的政府零售监测数据合并进【已有的最新快照】，
不触碰 T1–T6，避免重复验证码。

- 载入 data/tianjin/ 下最新日期快照（保留 T1–T6 等已有平台）
- 对每个政府平台：抓取最新一期 → 按 norm(name) 并入 canonical（已存在则追加价、
  不存在则新建行）→ 重算 cats、补 source 元信息
- 覆盖保存快照并重新生成 public/data.json 静态包
- 幂等：若某平台 pid 已在 source 中则跳过，可重复运行
"""
import collect
import tj_fgj_adapter
import tj_binhai_adapter

GOV = [
    {"pid": "T7", "adapter": tj_fgj_adapter,    "name": "天津发改委(零售监测)"},
    {"pid": "T8", "adapter": tj_binhai_adapter, "name": "天津滨海新区(零售监测)"},
]


def merge_one(snap, g):
    pid = g["pid"]
    source = snap.get("meta", {}).get("source", {})
    if pid in source and source[pid].get("ok"):
        print(f"[skip] {pid} {g['name']} 已存在快照中，跳过")
        return 0, 0

    url, period = g["adapter"].fetch_latest()
    rows = g["adapter"].fetch_rows(url)
    print(f"[{pid}] {g['name']} 抓取: {period} | {len(rows)} 条 | {url}")

    canonical = snap["canonical"]
    idx = {collect.norm(c["name"]): c for c in canonical}
    added, created = 0, 0
    for r in rows:
        ck = collect.norm(r["name"])
        pr = {"pid": pid, "price": r["price_jin"], "spec": "斤",
              "time": (period or r.get("period", "")) + " 月均价"}
        if r.get("raw_kg"):
            pr["kg"] = r["raw_kg"]
        if ck in idx:
            c = idx[ck]
            if any(p["pid"] == pid for p in c["prices"]):
                continue
            c["prices"].append(pr)
            added += 1
        else:
            c = {"key": ck, "name": r["name"],
                 "cat1": collect.classify_bj(r.get("category", r["name"])),
                 "cat2": "—", "prices": [pr]}
            canonical.append(c)
            idx[ck] = c
            created += 1

    snap.setdefault("meta", {})["source"][pid] = {
        "name": g["name"], "ok": True, "count": len(rows)}
    print(f"      → 追加到已有 {added} 行，新建 {created} 行")
    return added, created


def main():
    city = "tianjin"
    ds = collect.list_dates(city)
    if not ds:
        print("未找到天津快照，请先运行 update_tianjin.py")
        return
    date = ds[0]
    print(f"载入天津最新快照: {date}")
    snap = collect.load_snapshot(city, date)

    total_added = total_created = 0
    for g in GOV:
        a, c = merge_one(snap, g)
        total_added += a
        total_created += c

    snap["cats"] = sorted({c["cat1"] for c in snap["canonical"]})
    snap["meta"]["built_at"] = collect.datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    collect.save_snapshot(city, date, snap)
    collect.dump_static("public")
    print(f"\n完成: 快照 {date} 已保存 | 本次新增 {total_created} 行、追加 {total_added} 价 | "
          f"静态包已重新生成")


if __name__ == "__main__":
    main()
