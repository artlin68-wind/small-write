#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公司基本資料（主要經營業務）抓取程式
====================================
公開資訊觀測站（MOPS）「公司基本資料」有官方的「主要經營業務」，但不開放瀏覽器跨網域存取，
所以和千張大戶一樣由這支程式先抓好，存成 data/company/<代號>.json 給網頁同網域讀取。

  python fetch_company.py update             # 補沒抓過、或超過 REFRESH_DAYS 天的公司（每次最多 MAX_PER_RUN 家）
  python fetch_company.py all                # 同上但不限家數（第一次建資料用，約 1 小時）
  python fetch_company.py ids 2379 2330      # 立刻重抓指定公司

公司清單來自證交所／櫃買中心 OpenAPI（上市＋上櫃）。只使用 Python 標準庫。
"""
import datetime
import json
import re
import ssl
import sys
import time
import urllib.request
from pathlib import Path

MOPS_URL = "https://mops.twse.com.tw/mops/api/t05st03"
TWSE_LIST_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_LIST_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "company"
REFRESH_DAYS = 90       # 主要經營業務很少變，一季更新一次就夠
MAX_PER_RUN = 500
DELAY_SEC = 1.5         # MOPS 有防火牆，請求太密會被擋
MAX_FAILS = 5           # 連續失敗（多半是被擋）就停，下次再接著抓
UA = {"User-Agent": "Mozilla/5.0 (compatible; small-write-company/1.0; +https://github.com/artlin68-wind/small-write)"}

SSL_CTX = ssl.create_default_context()
SSL_CTX.verify_flags &= ~ssl.VERIFY_X509_STRICT


def get_json(url: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    headers = dict(UA, **({"Content-Type": "application/json"} if data else {}))
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        return json.loads(resp.read().decode("utf-8-sig"))


def company_ids() -> list[str]:
    ids = {r["公司代號"].strip() for r in get_json(TWSE_LIST_URL)}
    ids |= {r["SecuritiesCompanyCode"].strip() for r in get_json(TPEX_LIST_URL)}
    return sorted(i for i in ids if re.fullmatch(r"\d{4}", i))


def roc_date(s: str) -> str:
    """'76/10/21' → '1987-10-21'"""
    m = re.fullmatch(r"(\d{2,3})/(\d{1,2})/(\d{1,2})", (s or "").strip())
    return f"{int(m.group(1)) + 1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def fetch_one(stock_id: str) -> dict | None:
    res = get_json(MOPS_URL, {"companyId": stock_id})
    r = res.get("result") if res.get("code") == 200 else None
    if not r:
        return None
    v = lambda k: str((r.get(k) or {}).get("value") or "").strip()
    return {
        "id": stock_id,
        "name": v("companyName"),
        "market": v("marketName"),
        "industry": v("industryCategory"),
        "mainBusiness": v("mainBusiness"),
        "chairman": v("chairman"),
        "president": v("president"),
        "established": roc_date(v("establishDate")),
        "listed": roc_date(v("listingDate")) or roc_date(v("OTCDate")),
        "capital": v("capitalAmount"),
        "website": v("internetAddress"),
        "updated": datetime.date.today().isoformat(),
    }


def is_fresh(stock_id: str) -> bool:
    path = OUT_DIR / f"{stock_id}.json"
    if not path.exists():
        return False
    try:
        updated = datetime.date.fromisoformat(json.loads(path.read_text(encoding="utf-8"))["updated"])
    except (ValueError, KeyError):
        return False
    return (datetime.date.today() - updated).days < REFRESH_DAYS


def run(ids: list[str], limit: int | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = fails = 0
    for sid in ids:
        if limit is not None and done >= limit:
            break
        try:
            info = fetch_one(sid)
            fails = 0
        except Exception as e:  # 被防火牆擋時回的是 HTML，json 會解析失敗
            info = None
            fails += 1
            print(f"[company] {sid}：{type(e).__name__} {e}", file=sys.stderr)
            if fails >= MAX_FAILS:
                print("[company] 連續失敗，可能被暫時封鎖，先停止", file=sys.stderr)
                break
        if info:
            (OUT_DIR / f"{sid}.json").write_text(
                json.dumps(info, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            done += 1
        time.sleep(DELAY_SEC)
    print(f"[company] 更新 {done} 家")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode in ("update", "all"):
        todo = [i for i in company_ids() if not is_fresh(i)]
        print(f"[company] 需要更新 {len(todo)} 家")
        run(todo, MAX_PER_RUN if mode == "update" else None)
    elif mode == "ids":
        run([s for s in sys.argv[2:] if re.fullmatch(r"\d{4}", s)], None)
    else:
        sys.exit("用法：fetch_company.py update | all | ids <代號> [<代號> ...]")
