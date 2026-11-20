#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
首頁大盤資料抓取程式（大盤融資餘額、加權指數、美股指數、VIX、主動式 ETF、熱門股）
==========================================================================
網頁首頁先讀這裡存好的檔案，不必每次開頁都向 FinMind 要資料
（免費額度有限，公司網路也可能擋 api.finmindtrade.com）。

  python fetch_market_home.py          # 抓近 200 天，覆寫下列檔案

輸出（格式與 FinMind 回應相同，網頁直接讀 data 欄位）：
  data/margin/market_total_margin.json   全市場融資融券（TaiwanStockTotalMarginPurchaseShortSale）
  data/margin/taiex_price.json           加權指數日收盤（TaiwanStockPrice, TAIEX；首頁 RSI 也用這份）
  data/us_index/us_index.json            費城半導體 ^SOX、道瓊 ^DJI、那斯達克 ^IXIC、VIX 恐慌指數 ^VIX（USStockPrice）

另外存（自訂格式，見各函式說明）：
  data/hot/hot_stocks.json               最近交易日上市＋上櫃成交金額／成交量前 20 名個股（證交所、櫃買中心每日行情）
  data/etf/active_etf.json               主動式股票型 ETF（代號 00xxxA）各期間報酬率（歷史股價來自 FinMind）

各部分獨立執行，其中一部分失敗不影響其他部分的存檔。

FinMind Token（選用）：環境變數 FINMIND_TOKEN，或專案根目錄的 finmind_token.txt。只使用 Python 標準庫。
"""
import datetime
import json
import os
import re
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


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def taiwan_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))


# ──────────────────────────────────────────────────────────────
#  證交所＋櫃買中心每日行情（熱門股、主動式 ETF 當日報價共用）
# ──────────────────────────────────────────────────────────────
def daily_quotes() -> tuple[str, list[dict]]:
    """回傳 (交易日, 全部上市＋上櫃報價)。從今天往回找最近一個有資料的交易日。"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import fetch_inst_flow as fi   # 共用證交所／櫃買中心的抓取與解析函式（含重試）

    for back in range(8):
        day = taiwan_now().date() - datetime.timedelta(days=back)
        if day.weekday() >= 5:
            continue
        t = fi.find_table(fi.get_json(fi.TWSE_PRICE_URL.format(d=day.strftime("%Y%m%d"))), "證券代號", "收盤價")
        time.sleep(fi.DELAY_SEC)
        if not t:
            continue
        f = [x.strip() for x in t["fields"]]
        ix = {k: f.index(k) for k in ("證券代號", "證券名稱", "成交股數", "成交金額", "收盤價", "漲跌(+/-)", "漲跌價差")}
        rows = []
        for r in t["data"]:
            close = fi.num(r[ix["收盤價"]])
            if close <= 0:
                continue
            sign = -1 if "-" in re.sub(r"<[^>]+>", "", str(r[ix["漲跌(+/-)"]])) else 1
            rows.append({"id": r[ix["證券代號"]].strip(), "name": r[ix["證券名稱"]].strip(), "market": "上市", "close": close,
                         "chg": sign * fi.num(r[ix["漲跌價差"]]), "shares": fi.num(r[ix["成交股數"]]),
                         "value": fi.num(r[ix["成交金額"]])})
        try:
            d = fi.get_json(fi.TPEX_PRICE_URL.format(d=day.strftime("%Y/%m/%d")))
            pt = fi.find_table(d, "代號", "收盤")
            if pt and str(d.get("date")) == day.strftime("%Y%m%d"):
                f = [x.strip() for x in pt["fields"]]
                ic, ichg = f.index("收盤"), f.index("漲跌")
                ish = next(i for i, x in enumerate(f) if x.startswith("成交股數"))
                iv = next(i for i, x in enumerate(f) if x.startswith("成交金額"))
                for r in pt["data"]:
                    close = fi.num(r[ic])
                    if close > 0:
                        rows.append({"id": r[0].strip(), "name": r[1].strip(), "market": "上櫃", "close": close,
                                     "chg": fi.num(r[ichg]), "shares": fi.num(r[ish]), "value": fi.num(r[iv])})
            else:
                print(f"[home] {day} 上櫃行情抓不到，只用上市", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"[home] 上櫃行情抓取失敗：{e}", file=sys.stderr)
        return day.isoformat(), rows
    raise RuntimeError("近 8 天都找不到證交所行情")


def quote_row(q: dict, industry: str = "") -> dict:
    prev = q["close"] - q["chg"]
    return {"id": q["id"], "name": q["name"], "market": q["market"], "industry": industry,
            "close": q["close"], "chg": round(q["chg"], 2),
            "chg_pct": round(q["chg"] / prev * 100, 2) if prev > 0 else 0,
            "lots": round(q["shares"] / 1000), "value": round(q["value"] / 1e8, 2)}


HOT_N = 20


def save_hot_stocks(date: str, quotes: list[dict]) -> None:
    """熱門交易股：只取一般個股（4 碼、非 0 開頭，排除 ETF／ETN／權證），依成交金額、成交量各取前 HOT_N 名"""
    imap = {}
    try:
        imap = json.loads((ROOT / "data" / "inst_flow" / "industry_map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    stocks = [q for q in quotes if re.fullmatch(r"[1-9]\d{3}", q["id"])]
    by_value = sorted(stocks, key=lambda q: -q["value"])[:HOT_N]
    by_volume = sorted(stocks, key=lambda q: -q["shares"])[:HOT_N]
    write_json(ROOT / "data" / "hot" / "hot_stocks.json", {
        "date": date, "updated": taiwan_now().strftime("%Y-%m-%d %H:%M"),
        "by_value": [quote_row(q, imap.get(q["id"], "")) for q in by_value],
        "by_volume": [quote_row(q, imap.get(q["id"], "")) for q in by_volume],
    })
    print(f"已存 data/hot/hot_stocks.json：{date}，成交金額第 1 名 {by_value[0]['name']}")


# 期間（交易日數）；ytd＝今年以來、all＝上市以來
ETF_PERIODS = {"w1": 5, "m1": 21, "m3": 63, "m6": 126}
ETF_SPARK_N = 60


def save_active_etfs(date: str, quotes: list[dict]) -> None:
    """主動式股票型 ETF：代號 00 + 3 碼 + A。報酬率用收盤價計算，不含配息（還原股價需 FinMind 付費會員）。"""
    etfs = [q for q in quotes if re.fullmatch(r"00\d{3}A", q["id"])]
    if not etfs:
        raise RuntimeError("行情中找不到主動式 ETF")
    year_start = f"{date[:4]}-01-01"
    out = []
    for q in etfs:
        try:
            hist = finmind("TaiwanStockPrice", q["id"], "2025-01-01")["data"]
        except Exception as e:  # noqa: BLE001
            print(f"[home] {q['id']} 歷史股價抓取失敗：{e}", file=sys.stderr)
            hist = []
        time.sleep(0.4)
        closes = sorted((r["date"], float(r["close"])) for r in hist if float(r.get("close") or 0) > 0)
        if not closes or closes[-1][0] < date:
            closes.append((date, q["close"]))       # FinMind 還沒更新今天就補上官方收盤
        px = [c for _, c in closes]
        last = px[-1]
        ret = {k: (round((last / px[-1 - n] - 1) * 100, 2) if len(px) > n else None) for k, n in ETF_PERIODS.items()}
        prev_year = [c for d, c in closes if d < year_start]
        ret["ytd"] = round((last / prev_year[-1] - 1) * 100, 2) if prev_year else None
        ret["all"] = round((last / px[0] - 1) * 100, 2)
        row = quote_row(q)
        row.update({"listed": closes[0][0], "days": len(px), "ret": ret,
                    "spark": [round(c, 2) for c in px[-ETF_SPARK_N:]]})
        out.append(row)
    write_json(ROOT / "data" / "etf" / "active_etf.json", {
        "date": date, "updated": taiwan_now().strftime("%Y-%m-%d %H:%M"), "etfs": out})
    print(f"已存 data/etf/active_etf.json：{len(out)} 檔主動式 ETF，{date}")


def save_margin_and_index() -> None:
    start = (datetime.date.today() - datetime.timedelta(days=DAYS)).isoformat()
    margin = finmind("TaiwanStockTotalMarginPurchaseShortSale", "", start)
    taiex = finmind("TaiwanStockPrice", "TAIEX", start)
    save("market_total_margin.json", margin, 40)
    save("taiex_price.json", taiex, 20)


def save_us_index() -> None:
    us_start = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
    us_rows = []
    for sid in US_INDEXES:
        rows = finmind("USStockPrice", sid, us_start)["data"]
        if len(rows) < 20:
            raise RuntimeError(f"{sid} 只有 {len(rows)} 筆，不覆寫")
        us_rows += [{"date": r["date"], "stock_id": r["stock_id"], "close": r["Close"]} for r in rows]
    save("us_index.json", {"data": us_rows}, 60, ROOT / "data" / "us_index")


def main() -> int:
    failed = []

    def step(name, fn, *args):
        try:
            fn(*args)
        except Exception as e:  # noqa: BLE001  一部分失敗不影響其他部分
            failed.append(name)
            print(f"[home] {name} 失敗：{e}", file=sys.stderr)

    step("大盤融資＋加權指數", save_margin_and_index)
    step("美股指數", save_us_index)
    try:
        date, quotes = daily_quotes()
    except Exception as e:  # noqa: BLE001
        failed.append("每日行情")
        print(f"[home] 每日行情失敗：{e}", file=sys.stderr)
    else:
        step("熱門股", save_hot_stocks, date, quotes)
        step("主動式 ETF", save_active_etfs, date, quotes)
    if failed:
        print(f"[home] 以下部分失敗，保留舊檔：{'、'.join(failed)}", file=sys.stderr)
    # 全部失敗才回傳錯誤，讓排程標示失敗；部分成功仍照常 commit
    return 1 if len(failed) >= 3 else 0


if __name__ == "__main__":
    sys.exit(main())
