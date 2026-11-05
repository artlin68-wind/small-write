#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
投信買賣資金產業分布抓取程式
==============================
FinMind 的「全市場某日法人買賣超」需要付費等級，所以改向證交所／櫃買中心免費公開資料抓取：

  - 投信買進／賣出股數：證交所 T86（三大法人買賣超日報）、櫃買中心三大法人買賣明細
  - 收盤價：證交所 MI_INDEX、櫃買中心上櫃收盤行情
  - 產業別：證交所／櫃買中心 OpenAPI 公司基本資料（官方產業別代碼）

買進金額、賣出金額＝股數 × 當日收盤價（官方只公布股數，屬估算值），再依產業加總。

輸出（放在 GitHub Pages 上給網頁同網域讀取，桌面版 Streamlit 也讀同一份）：
  data/trust_flow/summary.json          近 KEEP_DAYS 個交易日、各產業每日買進／賣出金額（億元）
  data/trust_flow/days/<YYYY-MM-DD>.json 當日每檔股票的投信買進／賣出金額（萬元），給「產業內個股」明細用
  data/trust_flow/industry_map.json     代號 → 產業別（官方資料抓不到時的備援）

  python fetch_trust_flow.py daily        # 補最近幾天還沒抓的交易日（排程用）
  python fetch_trust_flow.py backfill 40  # 補最近 40 個交易日

只使用 Python 標準庫。
"""
import datetime
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date={d}&selectType=ALLBUT0999&response=json"
TWSE_PRICE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d}&type=ALLBUT0999&response=json"
TPEX_INST_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={d}&response=json"
TPEX_PRICE_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date={d}&type=EW&response=json"
TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_LIST_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "trust_flow"
DAY_DIR = OUT_DIR / "days"
KEEP_DAYS = 60
DELAY_SEC = 3.0         # 證交所每 5 秒超過 3 次請求會暫時封鎖 IP
UA = {"User-Agent": "Mozilla/5.0 (compatible; small-write-trustflow/1.0; +https://github.com/artlin68-wind/small-write)"}

SSL_CTX = ssl.create_default_context()
SSL_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT

# 證交所／櫃買中心官方產業別代碼
INDUSTRY = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
    "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙工業", "10": "鋼鐵工業", "11": "橡膠工業",
    "12": "汽車工業", "14": "建材營造", "15": "航運業", "16": "觀光餐旅", "17": "金融保險",
    "18": "貿易百貨", "19": "綜合", "20": "其他", "21": "化學工業", "22": "生技醫療業",
    "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業",
    "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "32": "文化創意業", "33": "農業科技業", "34": "電子商務",
    "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "存託憑證",
}
ETF = "ETF／ETN"        # 代號 00 開頭：不屬於任何產業，網頁上另外列、不列入產業排名


def get_json(url: str):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def num(s) -> float:
    s = re.sub(r"<[^>]+>", "", str(s)).replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def find_table(d: dict, *need: str) -> dict | None:
    """證交所／櫃買中心回傳多個表格，找欄位名稱同時包含 need 的那個"""
    for t in d.get("tables", []):
        fields = [str(f).strip() for f in t.get("fields") or []]
        if t.get("data") and all(any(n in f for f in fields) for n in need):
            return t
    return None


# ──────────────────────────────────────────────────────────────
#  產業別
# ──────────────────────────────────────────────────────────────
def load_industry_map() -> dict[str, str]:
    path = OUT_DIR / "industry_map.json"
    try:
        m = {r["公司代號"].strip(): INDUSTRY.get(r["產業別"].strip(), "其他") for r in get_json(TWSE_LIST_URL)}
        m.update({r["SecuritiesCompanyCode"].strip(): INDUSTRY.get(str(r["SecuritiesIndustryCode"]).strip(), "其他")
                  for r in get_json(TPEX_LIST_URL)})
        if len(m) > 1000:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(m, ensure_ascii=False, separators=(",", ":"), sort_keys=True), encoding="utf-8")
            return m
    except Exception as e:
        print(f"[trust] 產業別清單抓取失敗，改用上次存檔：{type(e).__name__} {e}", file=sys.stderr)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def industry_of(sid: str, imap: dict[str, str]) -> str:
    if sid.startswith("00"):
        return ETF
    return imap.get(sid) or imap.get(sid[:4]) or "其他"


# ──────────────────────────────────────────────────────────────
#  單日資料
# ──────────────────────────────────────────────────────────────
def twse_day(day: datetime.date) -> tuple[dict, dict]:
    """回傳 ({代號: (名稱, 投信買股數, 投信賣股數)}, {代號: 收盤價})；非交易日回傳空"""
    d = day.strftime("%Y%m%d")
    inst = get_json(T86_URL.format(d=d))
    if inst.get("stat") != "OK" or not inst.get("data"):
        return {}, {}
    f = [x.strip() for x in inst["fields"]]
    ib, isl = f.index("投信買進股數"), f.index("投信賣出股數")
    trades = {r[0].strip(): (r[1].strip(), num(r[ib]), num(r[isl])) for r in inst["data"]}
    time.sleep(DELAY_SEC)
    t = find_table(get_json(TWSE_PRICE_URL.format(d=d)), "證券代號", "收盤價")
    prices = {}
    if t:
        f = [x.strip() for x in t["fields"]]
        ic = f.index("收盤價")
        prices = {r[0].strip(): num(r[ic]) for r in t["data"]}
    return trades, prices


def tpex_day(day: datetime.date) -> tuple[dict, dict]:
    d = day.strftime("%Y/%m/%d")
    inst = get_json(TPEX_INST_URL.format(d=d))
    t = (inst.get("tables") or [{}])[0]
    # 回傳的日期不是要求的那天＝非交易日（櫃買中心會回最近一個交易日）
    if not t.get("data") or str(inst.get("date")) != day.strftime("%Y%m%d"):
        return {}, {}
    # 欄位依序為：外資(不含外資自營) 3 欄、外資自營 3 欄、外資合計 3 欄、投信 3 欄（買進、賣出、買賣超）…
    # 已用 FinMind 的 Investment_Trust 逐筆核對過，投信買進／賣出在第 11、12 欄
    trades = {r[0].strip(): (r[1].strip(), num(r[11]), num(r[12])) for r in t["data"] if len(r) > 12}
    time.sleep(DELAY_SEC)
    pt = find_table(get_json(TPEX_PRICE_URL.format(d=d)), "代號", "收盤")
    prices = {}
    if pt:
        f = [x.strip() for x in pt["fields"]]
        ic = f.index("收盤")
        prices = {r[0].strip(): num(r[ic]) for r in pt["data"]}
    return trades, prices


def fetch_day(day: datetime.date, imap: dict[str, str]) -> dict | None:
    rows = []
    for market, fn in (("上市", twse_day), ("上櫃", tpex_day)):
        trades, prices = fn(day)
        time.sleep(DELAY_SEC)
        if not trades:
            if market == "上市":
                return None          # 證交所沒資料＝非交易日（或還沒公布）
            print(f"[trust] {day} 上櫃資料抓不到，只存上市", file=sys.stderr)
            continue
        for sid, (name, buy, sell) in trades.items():
            if buy <= 0 and sell <= 0:
                continue
            px = prices.get(sid, 0)
            if px <= 0:
                continue
            # 金額存「萬元」，取到小數 1 位，檔案小一點
            rows.append([sid, name, industry_of(sid, imap), round(buy * px / 1e4, 1), round(sell * px / 1e4, 1)])
    rows.sort(key=lambda r: -(r[3] + r[4]))
    return {"date": day.isoformat(), "fields": ["代號", "名稱", "產業", "買進萬元", "賣出萬元"], "stocks": rows}


# ──────────────────────────────────────────────────────────────
#  彙總
# ──────────────────────────────────────────────────────────────
def saved_days() -> list[str]:
    return sorted(p.stem for p in DAY_DIR.glob("*.json"))


def rebuild_summary() -> None:
    days = saved_days()
    for old in days[:-KEEP_DAYS]:
        (DAY_DIR / f"{old}.json").unlink()
    days = days[-KEEP_DAYS:]
    ind: dict[str, list] = {}
    for i, d in enumerate(days):
        for sid, _, cat, buy, sell in json.loads((DAY_DIR / f"{d}.json").read_text(encoding="utf-8"))["stocks"]:
            v = ind.setdefault(cat, [[0.0, 0.0] for _ in days])[i]
            v[0] += buy
            v[1] += sell
    # 萬元 → 億元
    ind = {k: [[round(b / 1e4, 2), round(s / 1e4, 2)] for b, s in v] for k, v in sorted(ind.items())}
    (OUT_DIR / "summary.json").write_text(json.dumps({
        "updated": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
        "unit": "億元（投信買進／賣出股數 × 當日收盤價，估算）",
        "etf": ETF,
        "dates": days,
        "industries": ind,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[trust] summary：{len(days)} 個交易日、{len(ind)} 個產業")


def run(candidates: list[datetime.date], want: int | None = None) -> int:
    DAY_DIR.mkdir(parents=True, exist_ok=True)
    have = set(saved_days())
    imap = load_industry_map()
    got = 0
    for day in candidates:
        if want is not None and got >= want:
            break
        if day.weekday() >= 5:
            continue
        if day.isoformat() in have:
            got += 1
            continue
        try:
            data = fetch_day(day, imap)
        except Exception as e:
            print(f"[trust] {day}：{type(e).__name__} {e}", file=sys.stderr)
            continue
        if not data:
            print(f"[trust] {day}：非交易日或尚未公布")
            continue
        (DAY_DIR / f"{day.isoformat()}.json").write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        got += 1
        print(f"[trust] {day}：{len(data['stocks'])} 檔")
    rebuild_summary()
    return got


def taiwan_today() -> datetime.date:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date()


def recent_days(n_calendar: int) -> list[datetime.date]:
    today = taiwan_today()
    return [today - datetime.timedelta(days=i) for i in range(n_calendar)]


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "daily":
        run(recent_days(7))
    elif mode == "backfill":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
        run(recent_days(int(n * 1.6) + 10), want=n)
    else:
        sys.exit("用法：fetch_trust_flow.py daily | backfill <交易日數>")
