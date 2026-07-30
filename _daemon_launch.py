# -*- coding: utf-8 -*-
"""守护进程启动器（通用版）：双重 fork + setsid 脱离父进程组/会话，
使目标脚本不被 AI 工具在调用结束时按进程组回收，从而在 Mac 上常驻。
用法: python3 _daemon_launch.py <script.py> [logpath]
  script.py 在仓库根目录执行；stdout/stderr 重定向到 logpath（默认 /tmp/daemon.log）。
"""
import os
import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else "server.py"
LOG = sys.argv[2] if len(sys.argv) > 2 else "/tmp/daemon.log"

# 第一次 fork
pid = os.fork()
if pid > 0:
    sys.exit(0)

# 子进程：新建会话，脱离原进程组
os.setsid()

# 第二次 fork，避免重新获取控制终端
pid = os.fork()
if pid > 0:
    sys.exit(0)

# 重定向标准流，避免持有父进程的管道
sys.stdout.flush()
sys.stderr.flush()
devnull = os.open(os.devnull, os.O_RDWR)
os.dup2(devnull, 0)
with open(LOG, "w") as f:
    os.dup2(f.fileno(), 1)
    os.dup2(f.fileno(), 2)

# 执行目标脚本（保留后续参数）
os.execv(sys.executable, [sys.executable, TARGET] + sys.argv[3:])
