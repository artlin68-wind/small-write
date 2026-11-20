#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首頁大盤資料抓取程式（大盤融資餘額、加權指數、美股三大指數、VIX）
==========================================================
網頁首頁先讀這裡存好的檔案，不必每次開頁都向 FinMind 要資料
（免費額度有限，公司網路也可能擋 api.finmindtrade.com）。

  python fetch_market_home.py          # 抓近 200 天，覆寫下列檔案

輸出（格式與 FinMind 回應相同，網頁直接讀 data 欄位）：
  data/margin/market_total_margin.json   全市場融資融券（TaiwanStockTotalMarginPurchaseShortSale）
  data/margin/taiex_price.json           加權指數日收盤（TaiwanStockPrice, TAIEX；首頁 RSI 也用這份）
  data/us_index/us_index.json            費城半導體 ^SOX、道瓊 ^DJI、那斯達克 ^IXIC、VIX 恐慌指數 ^VIX（USStockPrice）

FinMind Token（選用）：環境變數 FINMIND_TOKEN，或專案根目錄的 finmind_token.txt。只使用 Python 標準庫。
"""
import datetime
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.finmindtrade.com/api/v4/data"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "margin"
DAYS = 200
UA = {"User-Agent": "Mozilla/5.0 (compatible; taiwan-stock-tool/1.0)"}


def token() -> str:
    t = os.environ.get("FINMIND_TOKEN", "").strip()
    if t:
        return t
    # 與 finmind_proxy_server.py 相同：忽略 # 註解行與尚未填寫的範例文字
    f = ROOT / "finmind_token.txt"
    if f.exists():
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line != "在這裡貼上Token":
                return line
    return ""


def finmind(dataset: str, data_id: str, start: str) -> dict:
    q = {"dataset": dataset, "data_id": data_id, "start_date": start}
    t = token()
    if t:
        q["token"] = t
    url = f"{API}?{urllib.parse.urlencode(q)}"
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as resp:
                js = json.loads(resp.read().decode("utf-8"))
            if js.get("status") != 200 or not isinstance(js.get("data"), list):
                raise RuntimeError(f"{dataset}: {js.get('msg')}")
            return js
        except Exception as e:  # noqa: BLE001  網路逾時、額度用完都重試幾次
            last_err = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"抓取 {dataset} 失敗：{last_err}")


US_INDEXES = ["^SOX", "^DJI", "^IXIC", "^VIX"]


def save(name: str, js: dict, min_rows: int, out_dir: Path = OUT_DIR) -> None:
    rows = js["data"]
    if len(rows) < min_rows:
        # 資料異常少時不覆寫，避免把好的舊檔換成空檔
        raise RuntimeError(f"{name} 只有 {len(rows)} 筆，不覆寫")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(json.dumps({"msg": js.get("msg", "success"), "status": 200, "data": rows},
                               ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"已存 {path.relative_to(ROOT)}：{len(rows)} 筆，最新 {rows[-1]['date']}")


def main() -> int:
    start = (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()
    margin = finmind("TaiwanStockTotalMarginPurchaseShortSale", "", start)
    taiex = finmind("TaiwanStockPrice", "TAIEX", start)
    save("market_total_margin.json", margin, 40)
    save("taiex_price.json", taiex, 20)
    us_start = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
    us_rows = []
    for sid in US_INDEXES:
        rows = finmind("USStockPrice", sid, us_start)["data"]
        if len(rows) < 20:
            raise RuntimeError(f"{sid} 只有 {len(rows)} 筆，不覆寫")
        us_rows += [{"date": r["date"], "stock_id": r["stock_id"], "close": r["Close"]} for r in rows]
    save("us_index.json", {"data": us_rows}, 60, ROOT / "data" / "us_index")
    return 0


if __name__ == "__main__":
    sys.exit(main())
