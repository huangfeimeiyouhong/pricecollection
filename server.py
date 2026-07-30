# -*- coding: utf-8 -*-
"""价格采集原型 · 本地后端（标准库，无额外依赖）
启动: python server.py  (默认 http://127.0.0.1:8000)
接口:
  GET  /                      提供 price-collector.html
  GET  /api/data              返回全量载荷 {cities, platforms, dates, snaps}
  POST /api/update?city=xxx   实时抓取该城市各平台当日数据并落盘，返回刷新后的载荷
说明:
  - 更新会真实调用各平台适配器（菜亿箩/厦门发改委/闽南果蔬），需联网。
  - 快照落盘于 data/<city>/<date>.json，前端按城市+日期读取。
"""
import os
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(ROOT, "price-collector.html")

import collect


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, ctype="text/html; charset=utf-8"):
        try:
            with open(path, "rb") as f:
                data = f.read()
        except FileNotFoundError:
            self._send(404, {"error": "文件不存在: " + path})
            return
        self._send(200, data, ctype)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/", "/index.html"):
            self._send_file(HTML_PATH)
            return
        # 根目录下的静态 HTML 页面（如 market-price.html）
        if path.endswith(".html"):
            fp = os.path.normpath(os.path.join(ROOT, path.lstrip("/")))
            if os.path.dirname(fp) == ROOT and os.path.exists(fp):
                self._send_file(fp, "text/html; charset=utf-8")
                return
        if path == "/api/data":
            try:
                self._send(200, collect.payload())
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        if path == "/api/houchu/goods":
            try:
                self._send(200, collect.benchmark_with_match())
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        if path == "/api/houchu/platforms":
            try:
                self._send(200, {"names": collect.platform_names()})
            except Exception as e:
                self._send(500, {"error": str(e)})
            return
        self._send(404, {"error": "not found: " + path})

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        # 读取请求体（JSON）
        length = int(self.headers.get("Content-Length") or 0)
        body = {}
        if length:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except Exception:
                body = {}

        if path == "/api/update":
            city = (urllib.parse.parse_qs(parsed.query).get("city") or [""])[0]
            try:
                collect.update(city)
                self._send(200, collect.payload())
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        if path == "/api/houchu/bind":
            try:
                uid = body.get("uuid", "")
                mk = body.get("match_key", "")
                if not uid:
                    self._send(400, {"error": "uuid 必填"})
                    return
                collect.save_binding(uid, mk)
                self._send(200, collect.benchmark_with_match())
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        if path == "/api/houchu/refresh":
            try:
                collect.houchu_adapter.refresh_goods()
                self._send(200, collect.benchmark_with_match())
            except Exception as e:
                self._send(500, {"error": str(e)})
            return

        self._send(404, {"error": "not found: " + path})

    def log_message(self, fmt, *args):
        pass  # 静默


def host_ip():
    """返回本机局域网 IP（用于局域网访问提示）。"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(2)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"价格采集服务已启动(局域网可访问): http://{host_ip()}:{port}  (本机: http://127.0.0.1:{port})")
    print("接口: GET /api/data  |  POST /api/update?city=xiamen")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
