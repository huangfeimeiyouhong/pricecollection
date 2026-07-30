# -*- coding: utf-8 -*-
"""触发天津全量抓取并落盘（T1-T6 共 6 市场）。
通过 collect.update('tianjin') 走适配器 → beijing_scraper.js 子进程。
beijing_scraper.js 现已改为有头模式：遇 21food.cn 图标点选验证码时，浏览器窗口
会直接弹在用户屏幕上，由用户亲自点选；脚本把要求写入 /tmp/CAPTCHA_WAITING.json
并轮询检测验证码是否消失，消失即自动继续。

collect.update 已支持「累加合并」：本次抓取为 0 但历史有数据的平台会沿用历史，
避免单次失败清空。本脚本在此基础上循环重试，直到 6 个市场全部齐全（或达到上限次数），
以应对个别市场当次抓取落空的偶发性。
"""
import time
from collections import Counter
import collect

TIANJIN_PIDS = ["T1", "T2", "T3", "T4", "T5", "T6"]

print("=== 开始天津更新（累加合并，直到 6 市场齐全）===", flush=True)
final_snap = None
for attempt in range(1, 5):
    snap, msg = collect.update('tianjin')
    final_snap = snap
    c = Counter()
    for item in snap.get('canonical', []):
        for p in item.get('prices', []):
            c[p.get('pid')] += 1
    per = {pid: c.get(pid, 0) for pid in TIANJIN_PIDS}
    missing = [pid for pid in TIANJIN_PIDS if c.get(pid, 0) == 0]
    print(f"attempt {attempt}: per-market={per} 缺失={missing}", flush=True)
    print(f"  msg={msg}", flush=True)
    if not missing:
        print("=== 全部市场齐全，更新完成 ===", flush=True)
        break
    print(f"  缺失 {missing}，3 秒后重试补齐…", flush=True)
    time.sleep(3)

if final_snap is not None:
    c = Counter()
    for item in final_snap.get('canonical', []):
        for p in item.get('prices', []):
            c[p.get('pid')] += 1
    print("最终 per-market:", {pid: c.get(pid, 0) for pid in TIANJIN_PIDS}, flush=True)
    print("canonical 总数:", len(final_snap.get('canonical', [])), flush=True)
print("=== 结束 ===", flush=True)
