# -*- coding: utf-8 -*-
"""北京空市场补齐：只抓取当前为 0 条的市场，已抓到的 B1/B2 从快照还原不重复抓取。
循环重试，直到所有配置市场都有数据或达到最大轮次。
用法: python3 update_beijing.py
日志: /tmp/update_beijing.log
"""
import os
import sys
import json
import datetime
import subprocess

import collect
import beijing_adapter

ROOT = os.path.dirname(__file__)
NODE = beijing_adapter.NODE
NODE_PATH = beijing_adapter.NODE_PATH
SCRAPER = beijing_adapter.SCRAPER

CITY = "beijing"
MAX_ITER = 1  # 单轮跑完即停，不再死循环重抓（避免同一 IP 短时间狂刷触发更频繁验证码）


def rows_from_snap_for_pid(snap, pid):
    """从已有快照还原某平台的原始行，避免重复抓取。"""
    out = []
    if not snap:
        return out
    for item in snap.get("canonical", []):
        for pr in item.get("prices", []):
            if pr.get("pid") == pid:
                out.append({
                    "name": item["name"],
                    "price_jin": pr["price"],
                    "spec": pr.get("spec", ""),
                    "time": pr.get("time", ""),
                    "raw_kg": pr.get("kg"),
                    "cat1": item.get("cat1", "其他"),
                    "cat2": item.get("cat2", "—"),
                })
    return out


def scraped_to_platform(mid, rows, date):
    """把 scraper 输出的 {name,max,min,avg,date,unit} 转成 merge_snapshot 需要的行。"""
    out = []
    for r in rows:
        avg = r.get("avg")
        if avg is None:
            continue
        out.append({
            "name": r["name"],
            "price_jin": round(float(avg) / 2, 2),   # 元/公斤 -> 元/斤
            "spec": "斤",
            "time": (r.get("date") or date) + " 报价",
            "raw_kg": round(float(avg), 2),
            "cat1": collect.classify_bj(r["name"]),
            "cat2": "—",
        })
    return out


def main():
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    plats = collect.CITY_PLATFORMS[CITY]
    pid2mid = {p["id"]: p["market_id"] for p in plats}
    mid2pid = {p["market_id"]: p["id"] for p in plats}
    pid2name = {p["id"]: p["name"] for p in plats}

    # 优先用今日快照；没有则用最近一日（把已有 B1/B2 数据继承过来）
    dates = collect.list_dates(CITY)
    snap = collect.load_snapshot(CITY, date) if date in dates else (
        collect.load_snapshot(CITY, dates[0]) if dates else None)

    rows_by_pid = {}
    source = {}
    for p in plats:
        pid = p["id"]
        rows_by_pid[pid] = rows_from_snap_for_pid(snap, pid)
        source[pid] = {"name": pid2name[pid], "ok": True,
                       "count": len(rows_by_pid[pid]), "from": "snapshot"}

    def empty_pids():
        return [p["id"] for p in plats if not rows_by_pid[p["id"]]]

    for it in range(MAX_ITER):
        empty = empty_pids()
        if not empty:
            break
        print(f"\n[第 {it+1} 轮] 待补市场: " + ", ".join(
            f"{pid}({pid2mid[pid]})" for pid in empty), flush=True)
        ids = [pid2mid[pid] for pid in empty]
        env = dict(os.environ, NODE_PATH=NODE_PATH,
                   FOOD_MAX_PAGES=os.environ.get("FOOD_MAX_PAGES", "3"),
                   BJ_MAX_PAGES=os.environ.get("BJ_MAX_PAGES", "3"))
        for _k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                   "all_proxy", "ALL_PROXY"):
            env.pop(_k, None)
        try:
            out = subprocess.run([NODE, SCRAPER, *ids], capture_output=True,
                                 text=True, env=env, timeout=1800)
        except subprocess.TimeoutExpired:
            print("  scraper 超时（30分钟），本轮结束", flush=True)
            break
        if out.returncode != 0:
            print("  scraper 失败: " + (out.stderr or "")[:600], flush=True)
            continue
        try:
            res = json.loads(out.stdout)
        except Exception as e:
            print("  scraper 输出解析失败: " + str(e), flush=True)
            continue
        for pid in empty:
            mid = pid2mid[pid]
            scraped = res.get(mid, [])
            rows = scraped_to_platform(mid, scraped, date)
            if rows:
                rows_by_pid[pid] = rows
                source[pid] = {"name": pid2name[pid], "ok": True, "count": len(rows)}
                print(f"  ✓ {pid}({mid}) {pid2name[pid]}: {len(rows)} 条", flush=True)
            else:
                print(f"  ✗ {pid}({mid}) {pid2name[pid]}: 0 条（可能验证码未过）", flush=True)

        # 用累计的 rows_by_pid 重建并落盘（含已抓 B1/B2 + 本轮新抓）
        snap = collect.build_snapshot(CITY, rows_by_pid, date, source)
        snap["_msg"] = "beijing 补齐：" + "、".join(
            f"{v['name']}({v['count']}条)" for v in source.values())
        collect.save_snapshot(CITY, date, snap)
        print(f"  已落盘 data/{CITY}/{date}.json", flush=True)

    final = {pid: len(rows_by_pid[pid]) for pid in pid2mid}
    still = [pid for pid, c in final.items() if c == 0]
    print("\n==== 完成 ====", flush=True)
    print("各市场条数: " + json.dumps(final, ensure_ascii=False), flush=True)
    if still:
        print("仍未补齐: " + ", ".join(f"{pid}({pid2mid[pid]})" for pid in still), flush=True)
        print("可再次运行本脚本继续补齐。", flush=True)
    else:
        print("北京全部市场均已补齐 ✅", flush=True)


if __name__ == "__main__":
    main()
