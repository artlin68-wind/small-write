#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本機代理伺服器
================
同時做兩件事：
1. 提供資料夾內的靜態網頁檔案（例如「技術籌碼分析工具.html」）
2. 代替瀏覽器向 FinMind 公開 API 抓取資料，再回傳給網頁

為什麼需要這個代理？
FinMind 的公開 API 本身沒有開放瀏覽器端（JavaScript fetch）直接跨網域存取，
不論網頁是用 file:// 直接開啟，還是用 http://localhost 開啟，瀏覽器都會擋下
直接呼叫 FinMind 的請求（CORS 限制），導致「Failed to fetch」。

解法：改由這支「伺服器端」的 Python 程式代為呼叫 FinMind（伺服器對伺服器
之間不受瀏覽器 CORS 限制），再把資料原封不動回傳給網頁。網頁只需要呼叫
同網域的 /api/finmind，不再直接呼叫外部網址。

不需要安裝任何額外套件，只使用 Python 標準庫。
"""
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import os
import sys
import traceback

PORT = 8000
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"


class ProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/finmind":
            self.handle_finmind_proxy(parsed.query)
        else:
            super().do_GET()

    def handle_finmind_proxy(self, query_string):
        # 防呆：FinMind v4 用 data_id 帶股票代碼，舊參數名 stock_id 會被回 400。
        # 若網頁（例如瀏覽器快取到舊版）仍送 stock_id，這裡自動改成 data_id。
        params = urllib.parse.parse_qs(query_string, keep_blank_values=True)
        if "stock_id" in params and "data_id" not in params:
            params["data_id"] = params.pop("stock_id")
        query_string = urllib.parse.urlencode(params, doseq=True)

        target_url = f"{FINMIND_BASE}?{query_string}"
        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; FinMindProxy/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                status = resp.status
            sys.stderr.write(f"[proxy] {status} <- {target_url}\n")
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read() if e.fp else b'{"status":' + str(status).encode() + b',"data":[]}'
            sys.stderr.write(f"[proxy] HTTP {status} <- {target_url}\n{body[:300]!r}\n")
        except Exception as e:
            status = 502
            body = json.dumps(
                {"status": 502, "msg": f"proxy error: {e}", "data": []}
            ).encode("utf-8")
            sys.stderr.write(f"[proxy] EXCEPTION 連線 FinMind 失敗 <- {target_url}\n")
            traceback.print_exc()

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # 靜態網頁一律不快取，避免瀏覽器卡在改版前的舊 JS。
        if self.path.endswith(".html") or self.path == "/":
            self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        # 精簡 log，只顯示狀態碼跟路徑
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
    with socketserver.TCPServer(("", PORT), ProxyHandler) as httpd:
        print(f"伺服器已啟動：http://localhost:{PORT}/")
        print("（此視窗需保持開啟，關閉視窗會停止伺服器）")
        httpd.serve_forever()
