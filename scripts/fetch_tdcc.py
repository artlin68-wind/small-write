#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集保股權分散表（千張大戶）抓取程式
====================================
FinMind 的 TaiwanStockHoldingSharesPer 需要付費等級，這支程式改向集保結算所（TDCC）
免費公開資料抓取，整理成每檔股票一個小 JSON（data/tdcc/<代號>.json），
放在 GitHub Pages 上給網頁同網域讀取（TDCC 不開放瀏覽器跨網域存取）。

兩種模式：
  python fetch_tdcc.py weekly                # 下載最新一週全市場 CSV，更新所有股票
  python fetch_tdcc.py backfill 2379 2330    # 用查詢頁補指定股票過去幾週的歷史

只使用 Python 標準庫。
"""
import csv
import io
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

OPEN_DATA_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
QUERY_URL = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "tdcc"
KEEP_WEEKS = 52
BACKFILL_WEEKS = 8
UA = {"User-Agent": "Mozilla/5.0 (compatible; small-write-tdcc/1.0; +https://github.com/artlin68-wind/small-write)"}

# 持股分級：12=400,001-600,000 … 15=1,000,001以上（千張大戶）
LEVEL_400 = (12, 13, 14, 15)
LEVEL_1000 = 15

# TDCC 的憑證缺少 Subject Key Identifier，Python 3.13+ 預設的嚴格模式會拒絕；
# 只關掉 X509_STRICT，憑證鏈與主機名稱照常驗證。
SSL_CTX = ssl.create_default_context()
SSL_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


def num(s: str) -> float:
    return float(s.replace(",", "").strip() or 0)


def week_record(date: str, levels: dict, total_holders: int) -> dict:
    """levels: {分級: (人數, 股數, 比例%)}"""
    h1000, _, p1000 = levels.get(LEVEL_1000, (0, 0, 0.0))
    return {
        "date": date,
        "holders1000": int(h1000),
        "pct1000": round(p1000, 2),
        "holders400": int(sum(levels.get(l, (0, 0, 0))[0] for l in LEVEL_400)),
        "pct400": round(sum(levels.get(l, (0, 0, 0.0))[2] for l in LEVEL_400), 2),
        "totalHolders": int(total_holders),
    }


def merge_and_save(stock_id: str, records: list[dict]) -> None:
    path = OUT_DIR / f"{stock_id}.json"
    weeks = {}
    if path.exists():
        for w in json.loads(path.read_text(encoding="utf-8")).get("weeks", []):
            weeks[w["date"]] = w
    for r in records:
        weeks[r["date"]] = r
    ordered = sorted(weeks.values(), key=lambda w: w["date"])[-KEEP_WEEKS:]
    path.write_text(
        json.dumps({"id": stock_id, "weeks": ordered}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


# ──────────────────────────────────────────────────────────────
#  每週：全市場最新一週 CSV
# ──────────────────────────────────────────────────────────────
def run_weekly() -> None:
    req = urllib.request.Request(OPEN_DATA_URL, headers=UA)
    with urllib.request.urlopen(req, timeout=120, context=SSL_CTX) as resp:
        text = resp.read().decode("utf-8-sig")

    # 欄位：資料日期,證券代號,持股分級,人數,股數,占集保庫存數比例%
    # CSV 的分級 16 是「差異數調整」、17 是「合計」
    by_stock: dict[str, dict] = {}
    date = None
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 6 or not row[0].isdigit():
            continue
        date = row[0]
        sid = row[1].strip()
        # 只保留一般股票（4 碼數字），排除權證、ETN 等
        if not re.fullmatch(r"\d{4}", sid):
            continue
        s = by_stock.setdefault(sid, {"levels": {}, "total": 0})
        level = int(row[2])
        if level == 17:
            s["total"] = num(row[3])
        else:
            s["levels"][level] = (num(row[3]), num(row[4]), num(row[5]))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for sid, s in by_stock.items():
        merge_and_save(sid, [week_record(date, s["levels"], s["total"])])
    print(f"[weekly] {date}：更新 {len(by_stock)} 檔股票")


# ──────────────────────────────────────────────────────────────
#  補歷史：查詢頁（每檔每週一次請求，刻意放慢）
# ──────────────────────────────────────────────────────────────
def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def backfill(stock_ids: list[str]) -> None:
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=SSL_CTX)
    )
    opener.addheaders = list(UA.items())

    def get_form() -> tuple[str, list[str]]:
        html = opener.open(QUERY_URL, timeout=30).read().decode("utf-8")
        token = re.search(r'name="SYNCHRONIZER_TOKEN" value="([^"]+)"', html).group(1)
        dates = re.findall(r'<option value="(\d{8})"', html)
        return token, dates

    token, dates = get_form()
    dates = dates[:BACKFILL_WEEKS]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for sid in stock_ids:
        records = []
        for d in dates:
            body = urllib.parse.urlencode({
                "SYNCHRONIZER_TOKEN": token,
                "SYNCHRONIZER_URI": "/portal/zh/smWeb/qryStock",
                "method": "submit",
                "firDate": dates[0],
                "scaDate": d,
                "sqlMethod": "StockNo",
                "stockNo": sid,
                "stockName": "",
            }).encode()
            html = opener.open(QUERY_URL, data=body, timeout=30).read().decode("utf-8")
            # 每次送出後 token 會換新，下一次要用新的
            m = re.search(r'name="SYNCHRONIZER_TOKEN" value="([^"]+)"', html)
            if m:
                token = m.group(1)

            levels, total = {}, 0
            for tr in re.findall(r"<tr>(.*?)</tr>", html, re.S):
                cells = [strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
                if len(cells) != 5 or not cells[0].isdigit():
                    continue
                if "合" in cells[1] and "計" in cells[1]:
                    total = num(cells[2])
                elif "差異數" not in cells[1]:
                    levels[int(cells[0])] = (num(cells[2]), num(cells[3]), num(cells[4]))
            if LEVEL_1000 in levels:
                records.append(week_record(d, levels, total))
            else:
                print(f"[backfill] {sid} {d}：查無資料", file=sys.stderr)
            time.sleep(1.0)

        merge_and_save(sid, records)
        print(f"[backfill] {sid}：補入 {len(records)} 週")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("weekly", "backfill"):
        sys.exit("用法：fetch_tdcc.py weekly | backfill <代號> [<代號> ...]")
    if sys.argv[1] == "weekly":
        run_weekly()
    else:
        backfill([s for s in sys.argv[2:] if re.fullmatch(r"\d{4,6}", s)])
