"""
台灣股票投資分析工具 v2.0 (v5框架)
============================
執行方式：streamlit run app.py
資料來源：FinMind（免費公開 API）、台灣證交所
v2.0 更新：ROE門檻15%、6週籌碼、基本面停損、投資評分模組
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import base64
import math
import json

# ══════════════════════════════════════════════════════════════════
#  PAGE CONFIG
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="台灣股票投資分析工具",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════
#  GLOBAL CONSTANTS
# ══════════════════════════════════════════════════════════════════
FINMIND_BASE = "https://api.finmindtrade.com/api/v4/data"
BUDGET = 1_000_000  # 100萬台幣

# ══════════════════════════════════════════════════════════════════
#  CSS
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
  .title-banner {
    background: linear-gradient(135deg,#1a3a6b,#2d6abf);
    color:white; padding:20px 24px; border-radius:12px; margin-bottom:16px;
  }
  .step-box {
    background:#f0f4ff; border-left:4px solid #2d6abf;
    padding:12px 16px; border-radius:0 8px 8px 0; margin:8px 0;
  }
  .red-check {
    background:#fff5f5; border:1.5px dashed #e05252;
    padding:14px; border-radius:8px; margin:8px 0;
  }
  .not-rec {
    background:#fde8e8; border:2px solid #c02020;
    padding:14px; border-radius:8px; color:#c02020;
  }
  .ok-pass {
    background:#e8f5e9; border:2px solid #27ae60;
    padding:14px; border-radius:8px; color:#155724;
  }
  .neutral-box {
    background:white; border:1px solid #dde2f0;
    padding:14px; border-radius:8px;
  }
  .chip-box {
    background:#f5f0ff; border:1.5px solid #7c3aed;
    padding:14px; border-radius:8px;
  }
  .forecast-box {
    background:#fff8f0; border:1.5px solid #e67e22;
    padding:14px; border-radius:8px;
  }
  .rev-box {
    background:#eef3ff; border:1.5px solid #2d6abf;
    padding:14px; border-radius:8px;
  }
  div[data-testid="stMetric"] {
    background:white; border:1px solid #eee;
    padding:12px; border-radius:8px;
  }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
#  DATA FETCH — all cached to minimise API calls
# ══════════════════════════════════════════════════════════════════

@st.cache_data(ttl=86_400, show_spinner=False)
def fetch_stock_list() -> pd.DataFrame:
    try:
        r = requests.get(f"{FINMIND_BASE}?dataset=TaiwanStockInfo", timeout=20)
        d = r.json()
        if d.get("status") == 200:
            df = pd.DataFrame(d["data"])
            return df[df["type"].isin(["twse", "tpex"])][
                ["stock_id", "stock_name", "type", "industry_category"]
            ]
    except Exception:
        pass
    return pd.DataFrame(columns=["stock_id", "stock_name", "type", "industry_category"])


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_monthly_revenue(stock_id: str, start: str = "2023-01-01") -> pd.DataFrame:
    try:
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockMonthRevenue"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_financial_statements(stock_id: str, start: str = "2020-01-01") -> pd.DataFrame:
    try:
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockFinancialStatements"
            f"&data_id={stock_id}&start_date={start}",
            timeout=25,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_balance_sheet(stock_id: str, start: str = "2020-01-01") -> pd.DataFrame:
    try:
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockBalanceSheet"
            f"&data_id={stock_id}&start_date={start}",
            timeout=25,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            return df
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=1_800, show_spinner=False)
def fetch_latest_price(stock_id: str) -> float | None:
    try:
        start = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        end = datetime.now().strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockPrice"
            f"&data_id={stock_id}&start_date={start}&end_date={end}",
            timeout=15,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            return float(df.sort_values("date").iloc[-1]["close"])
    except Exception:
        pass
    return None


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_dividend(stock_id: str, start: str = "2019-01-01") -> pd.DataFrame:
    try:
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockDividend"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            return pd.DataFrame(d["data"])
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=7_200, show_spinner=False)
def fetch_chip_data(stock_id: str) -> pd.DataFrame:
    """嘗試從 FinMind 取得集保戶股權分散表"""
    try:
        start = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockHoldingSharesPer"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=1_800, show_spinner=False)
def fetch_price_history(stock_id: str, days: int = 40) -> pd.DataFrame:
    """日K OHLCV，含成交量（Trading_Volume），來源：台灣證交所公開交易資訊（經 FinMind 彙整）"""
    try:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockPrice"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            for c in ["close", "open", "max", "min", "Trading_Volume"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_margin_data(stock_id: str, days: int = 40) -> pd.DataFrame:
    """融資融券餘額，來源：台灣證交所／櫃買中心公開交易資訊（經 FinMind 彙整）"""
    try:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockMarginPurchaseShortSale"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            for c in df.columns:
                if c not in ("date", "stock_id"):
                    df[c] = pd.to_numeric(df[c], errors="coerce")
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_institutional_data(stock_id: str, days: int = 40) -> pd.DataFrame:
    """三大法人（外資／投信／自營商）買賣超，來源：台灣證交所公開交易資訊（經 FinMind 彙整）"""
    try:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockInstitutionalInvestorsBuySell"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            df["buy"] = pd.to_numeric(df["buy"], errors="coerce")
            df["sell"] = pd.to_numeric(df["sell"], errors="coerce")
            df["net"] = df["buy"] - df["sell"]
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3_600, show_spinner=False)
def fetch_day_trading(stock_id: str, days: int = 40) -> pd.DataFrame:
    """信用當沖成交量，來源：台灣證交所公開交易資訊（經 FinMind 彙整）"""
    try:
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        r = requests.get(
            f"{FINMIND_BASE}?dataset=TaiwanStockDayTrading"
            f"&data_id={stock_id}&start_date={start}",
            timeout=20,
        )
        d = r.json()
        if d.get("status") == 200 and d["data"]:
            df = pd.DataFrame(d["data"])
            df["date"] = pd.to_datetime(df["date"])
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
            return df.sort_values("date").reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


# ══════════════════════════════════════════════════════════════════
#  ANALYSIS HELPERS
# ══════════════════════════════════════════════════════════════════

def extract_metric(df: pd.DataFrame, keywords: list[str]) -> dict:
    """從 FinMind financial statement 中抽取特定指標的年度值"""
    if df.empty:
        return {}
    pat = "|".join(keywords)
    sub = df[df["type"].str.contains(pat, case=False, na=False)].copy()
    if sub.empty:
        return {}
    sub["date"] = pd.to_datetime(sub["date"])
    sub["year"] = sub["date"].dt.year
    # quarterly EPS → sum per year; other ratios → mean per year
    agg = "sum" if any(k in pat.lower() for k in ["eps", "每股盈餘"]) else "mean"
    return sub.groupby("year")["value"].agg(agg).to_dict()


def calc_revenue_yoy(rev_df: pd.DataFrame):
    """回傳 (去年全年, 累計年增率%, 今年累計, 最新月份)"""
    if rev_df.empty:
        return None, None, None, None
    cy = datetime.now().year
    ly = cy - 1
    ly_df = rev_df[rev_df["date"].dt.year == ly]
    cy_df = rev_df[rev_df["date"].dt.year == cy]
    last_year_total = ly_df["revenue"].sum() if not ly_df.empty else None
    if cy_df.empty:
        return last_year_total, None, None, None
    months = cy_df["date"].dt.month.tolist()
    latest_month = max(months)
    cy_ytd = cy_df["revenue"].sum()
    ly_same = ly_df[ly_df["date"].dt.month.isin(months)]["revenue"].sum()
    yoy = (cy_ytd - ly_same) / ly_same * 100 if ly_same > 0 else None
    return last_year_total, yoy, cy_ytd, latest_month


def red_flag_check(items: list[str], title: str) -> bool:
    """Render red-flag box. Returns True if user chooses to continue."""
    if not items:
        return True
    st.markdown(
        f'<div class="red-check"><b>⚠️ {title}</b><br>' + "<br>".join(items) + "</div>",
        unsafe_allow_html=True,
    )
    choice = st.radio(
        "您的判斷：",
        ["✅ 風險可控，繼續分析", "⛔ 問題嚴重，不建議投資"],
        key=f"rf_{title[:6]}",
    )
    return "不建議" not in choice


def grade_score(s: float):
    """共用評級對照：A+/A/B+/B/C/D"""
    if s >= 85: return "A+", "#27ae60"
    if s >= 70: return "A",  "#2d9e60"
    if s >= 55: return "B+", "#e67e22"
    if s >= 40: return "B",  "#c47800"
    if s >= 25: return "C",  "#e05252"
    return "D", "#c02020"


# ── 籌碼／技術訊號：資料整理 ─────────────────────────────────────────

def calc_institutional_signal(inst_df: pd.DataFrame) -> dict | None:
    """三大法人合計買賣超（近5/10日）＋ 投信買賣超趨勢（連續天數）"""
    if inst_df.empty or "net" not in inst_df.columns:
        return None
    daily_net = inst_df.groupby("date")["net"].sum().sort_index()
    if daily_net.empty:
        return None

    trust_df = inst_df[inst_df["name"].astype(str).str.contains("Investment_Trust", na=False)]
    trust_net = trust_df.groupby("date")["net"].sum().sort_index()

    net5 = float(daily_net.tail(5).sum())
    net10 = float(daily_net.tail(10).sum())
    t_net5 = float(trust_net.tail(5).sum()) if not trust_net.empty else 0.0

    t_series = trust_net.tail(10).tolist()
    buy_streak = 0
    for v in reversed(t_series):
        if v > 0: buy_streak += 1
        else: break
    sell_streak = 0
    for v in reversed(t_series):
        if v < 0: sell_streak += 1
        else: break
    last5 = trust_net.tail(5).tolist()
    buy_days5 = sum(1 for v in last5 if v > 0)
    sell_days5 = sum(1 for v in last5 if v < 0)

    return {
        "inst_net5": net5, "inst_net10": net10, "trust_net5": t_net5,
        "trust_buy_streak": buy_streak, "trust_sell_streak": sell_streak,
        "trust_buy_days5": buy_days5, "trust_sell_days5": sell_days5,
    }


def calc_margin_signal(margin_df: pd.DataFrame, price_df: pd.DataFrame) -> dict | None:
    """融資餘額5日變化率 vs 股價5日變化率，判斷籌碼安定度"""
    if margin_df.empty or "MarginPurchaseTodayBalance" not in margin_df.columns:
        return None
    m = margin_df.sort_values("date").dropna(subset=["MarginPurchaseTodayBalance"])
    if len(m) < 2:
        return None
    bal_now = float(m.iloc[-1]["MarginPurchaseTodayBalance"])
    bal_ref = float(m.iloc[max(0, len(m) - 6)]["MarginPurchaseTodayBalance"])
    margin_chg_pct = (bal_now - bal_ref) / bal_ref * 100 if bal_ref else 0.0

    price_chg_pct = None
    if not price_df.empty and len(price_df) >= 2 and "close" in price_df.columns:
        p = price_df.sort_values("date").dropna(subset=["close"])
        if len(p) >= 2:
            p_now = float(p.iloc[-1]["close"])
            p_ref = float(p.iloc[max(0, len(p) - 6)]["close"])
            price_chg_pct = (p_now - p_ref) / p_ref * 100 if p_ref else None

    return {"margin_chg_pct": margin_chg_pct, "price_chg_pct": price_chg_pct,
            "margin_balance": bal_now}


def calc_day_trading_signal(dt_df: pd.DataFrame, price_df: pd.DataFrame) -> dict | None:
    """近5日：信用當沖成交量 ÷ 當日總成交量，取平均比例"""
    if dt_df.empty or price_df.empty or "Trading_Volume" not in price_df.columns:
        return None
    pv = price_df.dropna(subset=["Trading_Volume"]).set_index("date")["Trading_Volume"]
    ratios = []
    for _, row in dt_df.sort_values("date").tail(5).iterrows():
        d = row["date"]
        if d in pv.index and pv[d] and pv[d] > 0 and pd.notna(row["Volume"]):
            ratios.append(row["Volume"] / pv[d] * 100)
    if not ratios:
        return None
    return {"day_trading_ratio_avg": sum(ratios) / len(ratios), "sample_days": len(ratios)}


def calc_chip_tech_score(inst_sig: dict | None, margin_sig: dict | None,
                          dt_sig: dict | None) -> tuple[int, list]:
    """
    籌碼面技術評分（100分，四構面各25分）：三大法人買賣超／投信買賣超／融資餘額變化／信用當沖比例
    評分規則為固定門檻的規則式評分（非AI主觀判斷），門檻依據台股籌碼分析常見經驗法則設定，
    僅供參考，非保證有效的投資訊號。
    """
    items = []
    score = 0

    if inst_sig:
        n5, n10 = inst_sig["inst_net5"], inst_sig["inst_net10"]
        if n5 > 0 and n10 > 0:
            score += 25; items.append(("✅", f"三大法人近5日＋10日均為買超（5日淨買 {n5:,.0f} 張）", 25))
        elif n5 > 0:
            score += 18; items.append(("✅", f"三大法人近5日買超（{n5:,.0f} 張），10日尚未轉正", 18))
        elif abs(n5) < 1:
            score += 10; items.append(("➡️", "三大法人買賣力道接近持平", 10))
        elif n5 < 0 and n10 > 0:
            score += 5; items.append(("⚠️", "三大法人近5日轉賣，10日仍為買超，動能可能減弱", 5))
        else:
            score += 0; items.append(("🔴", f"三大法人近5日＋10日均為賣超（5日淨賣 {abs(n5):,.0f} 張）", 0))
    else:
        items.append(("❔", "三大法人資料不足，無法評分", 0))

    if inst_sig:
        bs, ss = inst_sig["trust_buy_streak"], inst_sig["trust_sell_streak"]
        bd5, sd5 = inst_sig["trust_buy_days5"], inst_sig["trust_sell_days5"]
        if bs >= 5:
            score += 25; items.append(("✅", f"投信連續 {bs} 日買超，籌碼集中度高", 25))
        elif bd5 >= 3:
            score += 18; items.append(("✅", f"投信近5日有 {bd5} 天買超", 18))
        elif sd5 >= 3:
            score += 5; items.append(("⚠️", f"投信近5日有 {sd5} 天賣超", 5))
        elif ss >= 5:
            score += 0; items.append(("🔴", f"投信連續 {ss} 日賣超，籌碼流失", 0))
        else:
            score += 10; items.append(("➡️", "投信買賣互見，無明顯方向", 10))
    else:
        items.append(("❔", "投信資料不足，無法評分", 0))

    if margin_sig and margin_sig.get("price_chg_pct") is not None:
        mc, pc = margin_sig["margin_chg_pct"], margin_sig["price_chg_pct"]
        if mc < 0 and pc > 0:
            score += 25; items.append(("✅", f"融資減少 {mc:.1f}% 同時股價上漲 {pc:.1f}%，籌碼安定型上漲", 25))
        elif abs(mc) < 2 and pc > 0:
            score += 18; items.append(("✅", f"融資變化不大（{mc:+.1f}%），股價上漲 {pc:.1f}%", 18))
        elif mc > 0 and pc > mc:
            score += 10; items.append(("➡️", f"融資增加 {mc:.1f}%，但漲幅 {pc:.1f}% 仍大於融資增幅", 10))
        elif mc > 5 and pc <= mc:
            score += 0; items.append(("🔴", f"融資大增 {mc:.1f}% 但漲幅僅 {pc:.1f}%，散戶追價風險偏高", 0))
        else:
            score += 5; items.append(("⚠️", f"融資變化 {mc:+.1f}%、股價變化 {pc:+.1f}%，訊號不明確", 5))
    else:
        items.append(("❔", "融資資料不足，無法評分", 0))

    if dt_sig:
        r = dt_sig["day_trading_ratio_avg"]
        if r < 15:
            score += 25; items.append(("✅", f"近5日當沖比例平均 {r:.1f}%，籌碼相對穩定", 25))
        elif r < 25:
            score += 18; items.append(("➡️", f"當沖比例 {r:.1f}%，屬正常範圍", 18))
        elif r < 40:
            score += 10; items.append(("⚠️", f"當沖比例 {r:.1f}%，投機味漸濃，留意隔日沖賣壓", 10))
        else:
            score += 0; items.append(("🔴", f"當沖比例高達 {r:.1f}%，短線投機盛行，波動風險大", 0))
    else:
        items.append(("❔", "當沖資料不足，無法評分", 0))

    return score, items


# ── 波浪理論輔助判讀（ZigZag 轉折點，規則式、可重現）──────────────────

def zigzag_pivots(price_df: pd.DataFrame, pct_threshold: float = 5.0) -> pd.DataFrame:
    """
    簡化版 ZigZag 演算法：股價自前一轉折點反向變動達 pct_threshold% 才標記新轉折點。
    這是固定規則、可重現的演算法，用來客觀標記出「相對高點／低點」，作為波浪計數的依據，
    避免用肉眼主觀畫線。
    """
    if price_df.empty or len(price_df) < 5 or "close" not in price_df.columns:
        return pd.DataFrame()
    df = price_df.sort_values("date").dropna(subset=["close"]).reset_index(drop=True)
    if len(df) < 5:
        return pd.DataFrame()

    pivots = []
    last_idx, last_price = 0, float(df.loc[0, "close"])
    direction = None

    for i in range(1, len(df)):
        price = float(df.loc[i, "close"])
        chg_pct = (price - last_price) / last_price * 100 if last_price else 0

        if direction is None:
            if abs(chg_pct) >= pct_threshold:
                pivots.append((last_idx, last_price, "起"))
                direction = "up" if chg_pct > 0 else "down"
                last_idx, last_price = i, price
        elif direction == "up":
            if price >= last_price:
                last_idx, last_price = i, price
            elif last_price and (last_price - price) / last_price * 100 >= pct_threshold:
                pivots.append((last_idx, last_price, "高點"))
                direction, last_idx, last_price = "down", i, price
        else:  # down
            if price <= last_price:
                last_idx, last_price = i, price
            elif last_price and (price - last_price) / last_price * 100 >= pct_threshold:
                pivots.append((last_idx, last_price, "低點"))
                direction, last_idx, last_price = "up", i, price

    pivots.append((last_idx, last_price,
                    "高點" if direction == "up" else "低點" if direction == "down" else "目前"))

    return pd.DataFrame([
        {"date": df.loc[idx, "date"], "price": price, "type": kind}
        for idx, price, kind in pivots
    ])


def simple_wave_count(pivot_df: pd.DataFrame) -> dict:
    """
    以 ZigZag 轉折點做簡化波浪標記（輔助判讀，非嚴謹艾略特波浪理論定論——
    正式波浪計數需搭配型態、成交量、費波那契比率等多重確認，仍具主觀判斷成分）。
    """
    if pivot_df.empty or len(pivot_df) < 2:
        return {"available": False}

    recent = pivot_df.tail(6).reset_index(drop=True)
    n = len(recent)
    wave_names = ["起", "1", "2", "3", "4", "5"]
    recent["wave_label"] = [wave_names[i] if i < len(wave_names) else str(i) for i in range(n)]

    last_leg_pct = None
    if n >= 2:
        p0, p1 = float(recent.iloc[-2]["price"]), float(recent.iloc[-1]["price"])
        last_leg_pct = (p1 - p0) / p0 * 100 if p0 else None

    if n >= 6:
        stage_note = "近期已出現5段以上轉折，型態上可能完成一組推動浪（1-5），留意是否轉入修正浪（A-B-C），僅供參考"
    elif n >= 4:
        stage_note = "出現3-4段轉折，可能處於推動浪中段，趨勢仍在發展，尚未完整成形"
    else:
        stage_note = "轉折段數不足，僅能判斷目前處於上升段或下降段，無法完整計數"

    return {
        "available": True, "pivots": recent,
        "current_leg": recent.iloc[-1]["type"],
        "current_leg_chg_pct": last_leg_pct,
        "stage_note": stage_note,
    }


# ── 技術線型截圖：AI 解讀＋與自動數據交叉比對 ─────────────────────────

def analyze_chart_screenshot(image_bytes: bytes, api_key: str) -> dict:
    """
    呼叫 Claude Vision 解讀使用者上傳的技術線型截圖。
    規則：AI 只能回報畫面上『實際可辨識』的文字／數值，不得臆測畫面沒有的資訊，
    輸出結構化 JSON，以便後續與 FinMind 自動抓取的量化數據做交叉比對，
    避免整個判讀流於主觀。
    """
    try:
        import anthropic
    except ImportError:
        return {"error": "尚未安裝 anthropic 套件，請先在終端機執行：pip install anthropic"}

    media_type = "image/png"
    try:
        from PIL import Image
        import io as _io
        img = Image.open(_io.BytesIO(image_bytes))
        if img.format == "JPEG":
            media_type = "image/jpeg"
    except Exception:
        pass

    b64_img = base64.b64encode(image_bytes).decode()

    prompt = """你是一位嚴謹的股市技術分析助手。請只根據這張截圖「畫面上實際顯示」的文字與圖形做判讀，
不要臆測或編造畫面沒有出現的資訊。若某個欄位畫面沒有顯示，請填「未顯示」。

請以「純JSON」格式回覆（不要加任何說明文字、不要用markdown code block包住），欄位如下：
{
  "chart_type": "這張截圖是什麼類型的畫面（K線圖／法人買賣超／融資融券／當沖統計／其他）",
  "stock_name_or_id": "畫面上顯示的股票代碼或名稱，若無則填未顯示",
  "date_or_range": "畫面上顯示的日期或期間，若無則填未顯示",
  "ma_alignment": "均線排列狀態（多頭排列／空頭排列／糾結不明／未顯示），需依畫面上實際均線數值判斷",
  "candlestick_pattern": "畫面上可辨識的K線型態描述，若無明顯型態或看不清楚請填未顯示",
  "volume_signal": "成交量與價格的關係（量增價漲／量縮價跌／背離／未顯示）",
  "institutional_net": "畫面上顯示的法人買賣超數字或文字，若無則填未顯示",
  "trust_net": "畫面上顯示的投信買賣超或投信庫存數字，若無則填未顯示",
  "margin_change": "畫面上顯示的融資增減資訊，若無則填未顯示",
  "day_trading_ratio": "畫面上顯示的當沖比例或當沖量，若無則填未顯示",
  "overall_signal": "綜合畫面上可辨識的數據給出的方向判斷（偏多／中性／偏空），必須註明是根據哪些具體畫面數據得出",
  "confidence_note": "誠實說明這個判讀的把握程度，畫面資訊不足時要明確說明，不要給過度自信的結論"
}"""

    text = ""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64_img}},
                    {"type": "text", "text": prompt},
                ],
            }],
        )
        text = msg.content[0].text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
            if text.lower().startswith("json"):
                text = text[4:]
        extracted = json.loads(text)
        return {
            "extracted": extracted,
            "signal_reading": f"{extracted.get('overall_signal', 'N/A')}｜{extracted.get('confidence_note', '')}",
        }
    except json.JSONDecodeError:
        return {"error": "AI 回覆非標準JSON格式，請重試一次", "raw": text}
    except Exception as e:
        return {"error": str(e)}


def cross_check_vision_vs_data(vr: dict, inst_sig: dict | None,
                                margin_sig: dict | None, dt_sig: dict | None) -> list[str]:
    """比對AI從截圖讀到的方向性描述，與FinMind自動抓取數據的方向是否一致"""
    notes = []
    ext = vr.get("extracted", {})

    def has(v, *kws):
        return isinstance(v, str) and any(k in v for k in kws)

    trust_txt = ext.get("trust_net", "")
    if inst_sig and trust_txt and "未顯示" not in trust_txt:
        auto_buy = inst_sig["trust_net5"] > 0
        shot_buy, shot_sell = has(trust_txt, "買超", "買進", "增"), has(trust_txt, "賣超", "賣出", "減")
        if (shot_buy and auto_buy) or (shot_sell and not auto_buy):
            notes.append(f"✅ 投信方向一致：截圖顯示「{trust_txt}」，自動數據近5日淨{'買' if auto_buy else '賣'} {abs(inst_sig['trust_net5']):,.0f} 張")
        elif shot_buy or shot_sell:
            notes.append(f"⚠️ 投信方向可能不一致：截圖顯示「{trust_txt}」，自動數據近5日淨{'買' if auto_buy else '賣'} {abs(inst_sig['trust_net5']):,.0f} 張 —— 請確認兩者時間區間是否相同")

    margin_txt = ext.get("margin_change", "")
    if margin_sig and margin_sig.get("margin_chg_pct") is not None and margin_txt and "未顯示" not in margin_txt:
        auto_up = margin_sig["margin_chg_pct"] > 0
        shot_up, shot_down = has(margin_txt, "增", "上升", "增加"), has(margin_txt, "減", "下降", "減少")
        if (shot_up and auto_up) or (shot_down and not auto_up):
            notes.append(f"✅ 融資方向一致：截圖顯示「{margin_txt}」，自動數據5日變化 {margin_sig['margin_chg_pct']:+.1f}%")
        elif shot_up or shot_down:
            notes.append(f"⚠️ 融資方向可能不一致：截圖顯示「{margin_txt}」，自動數據5日變化為 {margin_sig['margin_chg_pct']:+.1f}% —— 請確認兩者時間區間是否相同")

    if not notes:
        notes.append("ℹ️ 截圖未包含可與自動數據直接比對的具體法人／融資數字，此截圖僅作為圖形輔助參考，實際評分仍以上方「籌碼面技術評分」的量化數據為準")
    return notes


# ══════════════════════════════════════════════════════════════════
#  HTML REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════

def build_html_report(rd: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    stock_id = rd.get("stock_id", "")
    name = rd.get("company_name", "")
    verdict = rd.get("verdict", "待評估")
    vc = "#27ae60" if "不" not in verdict else "#c02020"

    eps_rows = "".join(
        f"<tr><td>{y}</td><td style='text-align:right'>{v:.2f}</td></tr>"
        for y, v in sorted(rd.get("eps_history", {}).items())
    )

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}({stock_id}) 投資分析報告</title>
<style>
  body{{font-family:'Microsoft JhengHei',Arial,sans-serif;max-width:900px;margin:0 auto;padding:24px;color:#333;background:#f5f7fb}}
  h1{{background:linear-gradient(135deg,#1a3a6b,#2d6abf);color:white;padding:20px;border-radius:10px;margin:0 0 16px}}
  h2{{color:#1a3a6b;border-bottom:2px solid #2d6abf;padding-bottom:6px;margin-top:24px}}
  .verdict{{background:{vc}22;border:2px solid {vc};padding:16px;border-radius:8px;margin:16px 0}}
  .verdict h2{{color:{vc};border-color:{vc}}}
  .section{{background:white;border:1px solid #dde2f0;border-radius:8px;padding:18px;margin:16px 0;box-shadow:0 1px 4px rgba(0,0,0,0.06)}}
  table{{width:100%;border-collapse:collapse;margin:10px 0}}
  th{{background:#2d6abf;color:white;padding:9px 12px;text-align:left;font-size:13px}}
  td{{padding:9px 12px;border-bottom:1px solid #eee;font-size:13px}}
  tr:nth-child(even){{background:#f8f9ff}}
  .highlight{{background:#fffbe6;font-weight:bold}}
  footer{{text-align:center;color:#aaa;font-size:11px;margin-top:40px;padding:20px;border-top:1px solid #eee}}
</style>
</head>
<body>
<h1>📊 {name}（{stock_id}）投資分析報告</h1>
<p style="color:#888;font-size:13px;margin:0 0 12px">分析日期：{now}　｜　投資預算：100萬台幣</p>

<div class="verdict">
  <h2>{'✅ 建議考慮投資' if '不' not in verdict else '⛔ 不建議投資'}</h2>
  <p style="margin:0">{verdict}</p>
</div>

<div class="section">
  <h2>基本資料</h2>
  <table>
    <tr><th>項目</th><th>數值</th></tr>
    <tr><td>股票代號</td><td><b>{stock_id}</b></td></tr>
    <tr><td>公司名稱</td><td><b>{name}</b></td></tr>
    <tr><td>產業別</td><td>{rd.get("industry","N/A")}</td></tr>
    <tr><td>目前股價</td><td>{rd.get("price","N/A")} 元</td></tr>
  </table>
</div>

<div class="section">
  <h2>EPS 歷年趨勢</h2>
  <table>
    <tr><th>年度</th><th>EPS（元）</th></tr>
    {eps_rows if eps_rows else "<tr><td colspan='2'>無資料</td></tr>"}
  </table>
</div>

<div class="section">
  <h2>營收預估模組（①②③）</h2>
  <table>
    <tr><th>項目</th><th>數值</th></tr>
    <tr><td>① 上年度全年營收（A）</td><td>{rd.get("last_year_rev","N/A")}</td></tr>
    <tr><td>② 最新累計年增率（B）</td><td>{rd.get("ytd_yoy","N/A")}</td></tr>
    <tr class="highlight"><td>③ 今年預估全年營收（C = A×(1+B)）</td><td><b>{rd.get("est_annual_rev","N/A")}</b></td></tr>
  </table>
</div>

<div class="section">
  <h2>EPS / 股利預估（④–⑧）</h2>
  <table>
    <tr><th>情境</th><th>稅後淨利率</th><th>預估 EPS</th><th>預估現金股利</th></tr>
    <tr><td>保守</td><td>{rd.get("m_cons","N/A")}%</td><td>{rd.get("eps_cons","N/A")} 元</td><td>{rd.get("div_cons","N/A")} 元</td></tr>
    <tr class="highlight"><td>合理 ★</td><td>{rd.get("m_base","N/A")}%</td><td><b>{rd.get("eps_base","N/A")} 元</b></td><td><b>{rd.get("div_base","N/A")} 元</b></td></tr>
    <tr><td>樂觀</td><td>{rd.get("m_opt","N/A")}%</td><td>{rd.get("eps_opt","N/A")} 元</td><td>{rd.get("div_opt","N/A")} 元</td></tr>
  </table>
  {"<p>股息殖利率（合理情境）：<b>" + rd.get("yield_base","N/A") + "</b></p>" if rd.get("yield_base") else ""}
</div>

<div class="section">
  <h2>投資評分</h2>
  <table>
    <tr><th>期間</th><th>評級</th><th>分數（/100）</th></tr>
    <tr class="highlight"><td>短期（1-2個月）</td><td style="font-size:20px;font-weight:800">{rd.get("st_grade","N/A")}</td><td>{rd.get("st_score","N/A")} 分</td></tr>
    <tr class="highlight"><td>長期（6個月-2年）</td><td style="font-size:20px;font-weight:800">{rd.get("lt_grade","N/A")}</td><td>{rd.get("lt_score","N/A")} 分</td></tr>
  </table>
  <p style="font-size:12px;color:#888">評分維度：營收動能・大戶籌碼・ROE品質・EPS趨勢・股息殖利率・護城河・技術面</p>
</div>

<div class="section">
  <h2>籌碼面（千張大戶 6週趨勢）</h2>
  <table>
    <tr><th>項目</th><th>數值</th></tr>
    <tr><td>大戶6週合計變化</td><td>{rd.get("chip_big_delta","N/A")}</td></tr>
    <tr><td>外資6週合計變化</td><td>{rd.get("chip_foreign_delta","N/A")}</td></tr>
    <tr><td>技術面信號</td><td>{rd.get("tech_signals","N/A")}</td></tr>
    <tr><td>籌碼信號</td><td>{rd.get("chip_signal","N/A")}</td></tr>
  </table>
</div>

<div class="section">
  <h2>籌碼面技術評分（融資／三大法人／投信／當沖）</h2>
  <table>
    <tr><th>項目</th><th>數值</th></tr>
    <tr class="highlight"><td>籌碼面技術評分</td><td>{rd.get("chip_tech_grade","N/A")}（{rd.get("chip_tech_score","N/A")} / 100）</td></tr>
    <tr><td>評分細項</td><td>{rd.get("chip_tech_summary","N/A")}</td></tr>
    <tr><td>波浪理論輔助判讀</td><td>{rd.get("wave_note","未評估")}</td></tr>
  </table>
  <p style="font-size:12px;color:#888">資料來源：台灣證交所公開交易資訊（經FinMind彙整），固定門檻規則式評分，非AI主觀判斷</p>
</div>

<div class="section">
  <h2>投資策略與資金配置（v5 基本面停損）</h2>
  <table>
    <tr><th>項目</th><th>建議</th></tr>
    <tr><td>投資期限</td><td>{rd.get("strategy","N/A")}</td></tr>
    <tr><td>單檔配置上限</td><td>20 萬元（20%）</td></tr>
    <tr><td>分批進場</td><td>3 批，每批約 6~7 萬元</td></tr>
    <tr><td>長期停損條件</td><td>EPS預估下修 &gt;20%，或連2季衰退</td></tr>
    <tr><td>短期停損條件</td><td>跌破關鍵支撐位（非固定%）</td></tr>
    <tr><td>其餘資金</td><td>分散 4~5 支股票或現金/ETF</td></tr>
  </table>
</div>

<footer>
  ⚠️ 本報告由「台灣股票投資分析工具」自動生成，僅供參考，不構成投資建議。<br>
  投資有風險，請依個人財務狀況與風險承受度謹慎判斷。
</footer>
</body>
</html>"""
    return html


# ══════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════

def sidebar() -> tuple[str, bool]:
    with st.sidebar:
        st.markdown("## 📊 台灣股票分析工具")
        st.markdown("---")
        stock_input = st.text_input(
            "輸入股票代碼或公司名稱",
            placeholder="例：2317 或 鴻海",
        ).strip()
        clicked = st.button("🔍 開始分析", type="primary", width="stretch")
        st.markdown("---")
        st.markdown("**流程概覽**")
        st.markdown("""
📋 STEP 1–2　基本資料
📈 STEP 3　財務基本面
🏭 STEP 4　產業護城河
💎 STEP 5　可行性判斷
📊 ①②③　營收預估
📐 ④–⑧　EPS/股利預估
🐋 STEP 6　大戶籌碼
🔬 STEP 6b　籌碼技術評分
🌊 STEP 6c　波浪輔助判讀
📸 STEP 6d　截圖AI解讀
📅 STEP 7　投資策略
💰 STEP 8　資金配置
📋 STEP 9　輸出報告
        """)
        st.markdown("---")
        st.caption("資料來源：FinMind、台灣證交所\n⚠️ 僅供參考，非投資建議")
    return stock_input, clicked


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    # Session state init
    for key in ["started", "stock_id", "company_name", "rpt"]:
        if key not in st.session_state:
            st.session_state[key] = None if key != "started" else False
            if key == "rpt":
                st.session_state["rpt"] = {}

    stock_input, clicked = sidebar()

    if clicked and stock_input:
        st.session_state.started = True
        st.session_state.stock_input = stock_input
        st.session_state.rpt = {}
        st.cache_data.clear()

    # ── Welcome screen ───────────────────────────────────────────
    if not st.session_state.started:
        st.markdown("""
        <div style="text-align:center;padding:40px 0">
          <h1>📊 台灣股票投資分析工具</h1>
          <p style="font-size:17px;color:#555">
            輸入股票代碼，自動走完 9 步驟分析流程，產出完整 HTML 報告
          </p>
          <p style="color:#aaa;margin-top:24px">← 左側輸入股票代碼後點擊「開始分析」</p>
        </div>
        """, unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.info("🔢 **9步驟完整流程**\n\n基本面→財務→產業→籌碼→策略")
        c2.info("📡 **自動抓取公開資料**\n\nFinMind 免費 API，月營收/EPS/ROE")
        c3.info("📋 **輸出 HTML 報告**\n\n可下載留存，一鍵分享")
        return

    raw = st.session_state.stock_input

    # ── Resolve stock ID / name ──────────────────────────────────
    with st.spinner("載入股票清單…"):
        sl = fetch_stock_list()

    sid, sname, industry = raw, raw, "N/A"
    if not sl.empty:
        if raw.isdigit():
            m = sl[sl["stock_id"] == raw]
        else:
            m = sl[sl["stock_name"].str.contains(raw, na=False)]
        if not m.empty:
            sid = m.iloc[0]["stock_id"]
            sname = m.iloc[0]["stock_name"]
            industry = m.iloc[0].get("industry_category", "N/A")

    rpt = st.session_state.rpt
    rpt.update({"stock_id": sid, "company_name": sname, "industry": industry})

    st.markdown(f"""
    <div class="title-banner">
      <h2 style="margin:0;color:white">📊 {sname}（{sid}）投資分析</h2>
      <p style="margin:4px 0 0;color:rgba(255,255,255,.8);font-size:13px">
        分析時間：{datetime.now().strftime("%Y-%m-%d %H:%M")} ｜ 預算：100 萬台幣
      </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Bulk data fetch ──────────────────────────────────────────
    with st.spinner(f"正在抓取 {sname} 資料，請稍候…"):
        rev_df   = fetch_monthly_revenue(sid)
        fin_df   = fetch_financial_statements(sid)
        bal_df   = fetch_balance_sheet(sid)
        price    = fetch_latest_price(sid)
        div_df   = fetch_dividend(sid)
        chip_df  = fetch_chip_data(sid)
        price_hist_df = fetch_price_history(sid)
        margin_df     = fetch_margin_data(sid)
        inst_df       = fetch_institutional_data(sid)
        dt_df         = fetch_day_trading(sid)
    rpt["price"] = f"{price:.1f}" if price else "N/A"

    # ════════════════════════════════════════════════════════════
    #  STEP 1–2 基本資料
    # ════════════════════════════════════════════════════════════
    with st.expander("📋 STEP 1–2 ｜ 基本資料", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("股票代號", sid)
        c2.metric("公司名稱", sname)
        c3.metric("產業別", industry or "N/A")
        c4.metric("目前股價", f"{price:.1f} 元" if price else "N/A")

    # ════════════════════════════════════════════════════════════
    #  STEP 3 財務基本面
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📈 STEP 3 ｜ 財務基本面分析", expanded=True):

        eps_dict = extract_metric(fin_df, ["EPS", "每股盈餘"])
        roe_dict = extract_metric(fin_df, ["ROE", "股東權益報酬率"])
        nm_dict  = extract_metric(fin_df, ["稅後淨利率", "NetProfitMargin"])

        # Debt ratio from balance sheet
        debt_ratio = None
        if not bal_df.empty:
            dr = bal_df[bal_df["type"].str.contains("負債比率|DebtRatio", na=False)]
            if not dr.empty:
                debt_ratio = float(dr.sort_values("date").iloc[-1]["value"])

        # EPS chart
        if eps_dict:
            years = sorted(eps_dict.keys())
            vals  = [eps_dict[y] for y in years]
            fig = go.Figure(go.Bar(
                x=[str(y) for y in years], y=vals,
                marker_color=["#27ae60" if v > 0 else "#c02020" for v in vals],
                text=[f"{v:.2f}" for v in vals], textposition="outside",
            ))
            fig.update_layout(
                title=f"{sname} 年度 EPS（元）",
                height=300, yaxis_title="EPS（元）",
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(t=40, b=20),
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.warning("⚠️ 無法自動取得 EPS，請手動填入：")
            cy = datetime.now().year
            c1, c2, c3 = st.columns(3)
            v1 = c1.number_input(f"{cy-3}年EPS", value=0.0, step=0.1, key="eps1")
            v2 = c2.number_input(f"{cy-2}年EPS", value=0.0, step=0.1, key="eps2")
            v3 = c3.number_input(f"{cy-1}年EPS", value=0.0, step=0.1, key="eps3")
            eps_dict = {cy-3: v1, cy-2: v2, cy-1: v3}

        rpt["eps_history"] = eps_dict

        # ROE & Debt
        c1, c2 = st.columns(2)
        with c1:
            if roe_dict:
                lv = list(roe_dict.values())[-1]
                c1.metric("最新 ROE", f"{lv:.1f}%",
                          delta="健全 ✅" if lv >= 15 else ("偏低 ⚠️" if lv < 15 else "尚可"))
            else:
                man_roe = st.number_input("ROE % (手動)", value=15.0, step=0.5, key="man_roe")
                roe_dict = {datetime.now().year-1: man_roe}
        with c2:
            if debt_ratio is not None:
                c2.metric("負債比率", f"{debt_ratio:.1f}%",
                          delta="正常 ✅" if debt_ratio < 60 else "偏高 ⚠️")
            else:
                debt_ratio = st.number_input("負債比率 % (手動)", value=40.0, step=1.0, key="man_debt")

        # Red Check A
        st.markdown("---")
        flags_a = []
        if eps_dict:
            yrs = sorted(eps_dict.keys())
            if len(yrs) >= 2 and eps_dict[yrs[-1]] < eps_dict[yrs[-2]]:
                flags_a.append("EPS 年度衰退")
            if len(yrs) >= 1 and eps_dict[yrs[-1]] <= 0:
                flags_a.append("EPS 為負（虧損）")
            if len(yrs) >= 3:
                trd = [eps_dict[y] for y in yrs[-3:]]
                if all(trd[i] < trd[i-1] for i in range(1, 3)):
                    flags_a.append("EPS 連續 3 年衰退")
        if roe_dict and list(roe_dict.values())[-1] < 15:
            flags_a.append(f"ROE 低於 15%（現 {list(roe_dict.values())[-1]:.1f}%）—— 非金融股品質門檻")
        if debt_ratio and debt_ratio > 70:
            flags_a.append(f"負債比率明顯偏高（{debt_ratio:.1f}%）—— 請與同產業均值比較")

        if flags_a:
            if not red_flag_check(flags_a, "財務紅旗確認（任一成立→不建議）"):
                st.markdown('<div class="not-rec">⛔ 不建議投資：財務基本面不健全，建議重新選股</div>',
                            unsafe_allow_html=True)
                return
        else:
            st.markdown('<div class="ok-pass">✅ 財務紅旗確認通過：無明顯財務異常</div>',
                        unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    #  STEP 4 產業分析
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🏭 STEP 4 ｜ 產業、護城河與總經分析", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            cyc   = st.selectbox("產業景氣位置", ["上行期（利多）","高峰期（中性）","下行期（警示）","底部期（等待）"])
            moat  = st.selectbox("競爭護城河",    ["強（技術/規模壁壘高）","中（有一定優勢）","弱（易被取代）"])
        with c2:
            pol   = st.selectbox("政策/地緣風險", ["低風險","中等風險","高風險（制裁/貿易戰）"])
            mshare= st.selectbox("市占率趨勢",    ["持續增加","穩定","緩慢下滑","快速流失"])

        st.markdown("**🌐 總體經濟環境（影響估值折現率）**")
        c3, c4 = st.columns(2)
        with c3:
            rate_env = st.selectbox("利率環境", ["降息週期（股市有利）","利率高檔平穩","升息週期（高P/E承壓）"])
        with c4:
            macro_sig = st.selectbox("景氣燈號", ["綠燈（穩定擴張）","黃藍燈（注意）","藍燈（收縮）","紅燈（過熱）"])

        flags_b = []
        if "下行期"  in cyc:    flags_b.append("產業處於下行週期")
        if "高風險"  in pol:    flags_b.append("政策/地緣風險高")
        if "快速流失" in mshare: flags_b.append("市占率快速流失")
        if "弱"      in moat:   flags_b.append("護城河薄弱，易被競爭者取代")
        if "升息" in rate_env:  flags_b.append("升息週期，高P/E股估值受壓，需更大安全邊際")

        if flags_b:
            if not red_flag_check(flags_b, "產業紅旗確認（任一成立→不建議）"):
                st.markdown('<div class="not-rec">⛔ 不建議投資：產業前景不樂觀，等待轉機確認</div>',
                            unsafe_allow_html=True)
                return
        else:
            st.markdown('<div class="ok-pass">✅ 產業紅旗確認通過：產業趨勢正向</div>',
                        unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    #  STEP 5 投資可行性
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("💎 STEP 5 ｜ 投資可行性綜合判斷", expanded=True):
        dec5 = st.radio("綜合 STEP 3–4 結果：",
                        ["✅ 財務健全、前景明確，值得進一步分析",
                         "⛔ 綜合評估不適合投資"],
                        key="step5")
        if "不適合" in dec5:
            st.markdown('<div class="not-rec">⛔ 不適合投資：STEP 5 綜合判斷不通過</div>',
                        unsafe_allow_html=True)
            return
        st.markdown('<div class="ok-pass">✅ STEP 5 通過 → 進入預估模組</div>',
                    unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    #  ①②③ 營收預估
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📊 營收預估模組（①②③）", expanded=True):
        ly_rev, yoy, cy_ytd, lm = calc_revenue_yoy(rev_df)
        cy = datetime.now().year

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**① 上年度（{cy-1}）全年營收 A（億元）**")
            A_def = round(ly_rev / 1e8, 2) if ly_rev else 0.0
            A = st.number_input("億元", value=A_def, step=10.0, key="A",
                                label_visibility="collapsed")
            if ly_rev:
                st.caption(f"自動取得：{A_def:,.1f} 億元")
            else:
                st.caption("⚠️ 無法自動取得，請手動填入")

        with c2:
            st.markdown(f"**② 最新累計年增率 B（%）— 截至 {cy}年{lm or '?'}月**")
            B_def = round(yoy, 2) if yoy is not None else 0.0
            B = st.number_input("%", value=B_def, step=0.1, key="B",
                                label_visibility="collapsed")
            if yoy is not None:
                st.caption(f"自動計算：{B_def:+.2f}%")
            else:
                st.caption("⚠️ 無法自動計算，請手動填入")

        # Monthly chart
        if not rev_df.empty:
            plot_df = rev_df.tail(24).copy()
            plot_df["月份"] = plot_df["date"].dt.strftime("%Y-%m")
            fig = px.bar(plot_df, x="月份", y="revenue",
                         title=f"{sname} 近24個月月營收",
                         color_discrete_sequence=["#2d6abf"],
                         labels={"revenue": "營收（元）"})
            fig.update_layout(height=260, plot_bgcolor="white",
                              paper_bgcolor="white", margin=dict(t=36,b=10))
            st.plotly_chart(fig, width="stretch")

        if A > 0:
            C = A * (1 + B / 100)
            st.markdown(
                f'<div class="rev-box">'
                f'<b>③ 今年預估全年營收 C = A × (1 + B)</b><br>'
                f'<span style="font-size:22px;font-weight:700;color:#1a3a6b">'
                f'{A:,.1f} 億 × (1 + {B:.1f}%) = '
                f'<span style="color:#2d6abf">{C:,.1f} 億元</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            C = 0.0
            st.warning("請填入上年度營收以計算預估值")

        rpt.update({
            "last_year_rev": f"{A:,.1f} 億元",
            "ytd_yoy": f"{B:+.2f}%",
            "est_annual_rev": f"{C:,.1f} 億元",
        })

        # Red Check C
        st.markdown("---")
        flags_c = []
        if B < 0:
            flags_c.append(f"累計年增率 {B:.1f}% < 0%，當年營收萎縮")
        if A > 0 and C < A:
            flags_c.append(f"預估全年（{C:,.1f}億）< 上年度（{A:,.1f}億）")
        if flags_c:
            if not red_flag_check(flags_c, "營收衰退確認（③出口）"):
                st.markdown('<div class="not-rec">⛔ 不建議投資：當年營收衰退，等待回升確認</div>',
                            unsafe_allow_html=True)
                return
        elif B > 0:
            st.markdown(f'<div class="ok-pass">✅ 營收確認通過：年增率 {B:+.1f}%，正成長</div>',
                        unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    #  ④–⑧ EPS / 股利預估
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📐 EPS / 股利預估模組（④–⑧）", expanded=True):

        # Shares outstanding
        shares_default = 10.0
        if not fin_df.empty:
            sc = fin_df[fin_df["type"].str.contains("發行股數|OutstandingShares", na=False, case=False)]
            if not sc.empty:
                shares_default = float(sc.sort_values("date").iloc[-1]["value"]) / 1e8

        c1, c2 = st.columns(2)
        with c1:
            shares = st.number_input("發行股數（億股）", value=shares_default, step=0.1, key="shares")
        with c2:
            ref_margin = round(list(nm_dict.values())[-1], 2) if nm_dict else 2.5
            st.markdown(f"**稅後淨利率參考（歷年均值）：約 {ref_margin:.1f}%**")

        c1, c2, c3 = st.columns(3)
        m_c = c1.number_input("保守淨利率 %", value=round(ref_margin * 0.88, 2), step=0.1, key="mc")
        m_b = c2.number_input("合理淨利率 % ★", value=ref_margin, step=0.1, key="mb")
        m_o = c3.number_input("樂觀淨利率 %", value=round(ref_margin * 1.12, 2), step=0.1, key="mo")

        # Payout ratio from dividend history
        payout_default = 52
        if not div_df.empty:
            try:
                cash = div_df[div_df["CashEarningsDistribution"] > 0]["CashEarningsDistribution"]
                eps_vals = list(eps_dict.values())
                if len(eps_vals) >= 2 and len(cash) >= 2:
                    ratios = [cash.iloc[i] / abs(eps_vals[-2+i]) * 100
                              for i in range(2) if abs(eps_vals[-2+i]) > 0]
                    if ratios:
                        payout_default = int(round(sum(ratios) / len(ratios)))
            except Exception:
                pass

        payout = st.slider("⑦ 盈餘分配率 %（歷年平均）", 20, 100, payout_default, key="payout")

        if C > 0 and shares > 0:
            C_yuan = C * 1e8        # 億 → 元
            shares_total = shares * 1e8

            def calc(m):
                eps = (C_yuan * m / 100) / shares_total
                div = eps * payout / 100
                return eps, div

            eps_c, div_c = calc(m_c)
            eps_b, div_b = calc(m_b)
            eps_o, div_o = calc(m_o)

            table = pd.DataFrame({
                "情境":          ["保守", "合理 ★", "樂觀"],
                "稅後淨利率":    [f"{m_c:.1f}%", f"{m_b:.1f}%", f"{m_o:.1f}%"],
                "⑤ 預估稅後淨利（億）": [f"{C*m_c/100:,.0f}", f"{C*m_b/100:,.0f}", f"{C*m_o/100:,.0f}"],
                "⑥ 預估 EPS（元）":     [f"{eps_c:.2f}", f"{eps_b:.2f}", f"{eps_o:.2f}"],
                "⑧ 預估現金股利（元）": [f"{div_c:.2f}", f"{div_b:.2f}", f"{div_o:.2f}"],
            })
            st.dataframe(table, hide_index=True, width="stretch")

            # Yield
            if price:
                yield_b = div_b / price * 100
                st.markdown(
                    f'<div class="forecast-box">'
                    f'<b>股息殖利率（合理情境，以目前股價 {price:.1f} 元）：{yield_b:.2f}%</b>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                rpt["yield_base"] = f"{yield_b:.2f}%"

            rpt.update({
                "m_cons": f"{m_c:.1f}", "m_base": f"{m_b:.1f}", "m_opt": f"{m_o:.1f}",
                "eps_cons": f"{eps_c:.2f}", "eps_base": f"{eps_b:.2f}", "eps_opt": f"{eps_o:.2f}",
                "div_cons": f"{div_c:.2f}", "div_base": f"{div_b:.2f}", "div_opt": f"{div_o:.2f}",
            })

            # Red Check D
            st.markdown("---")
            flags_d = []
            if eps_dict:
                last_eps = list(eps_dict.values())[-1]
                if eps_b < last_eps:
                    flags_d.append(f"合理EPS（{eps_b:.2f}元）< 上年度EPS（{last_eps:.2f}元）")
            if m_b < 1.5:
                flags_d.append(f"稅後淨利率偏低（{m_b:.1f}% < 1.5%）")
            if not div_df.empty:
                try:
                    prev_div = float(
                        div_df[div_df["CashEarningsDistribution"] > 0]
                        .sort_values("ExDividendTradingDate").iloc[-1]["CashEarningsDistribution"]
                    )
                    if div_b < prev_div:
                        flags_d.append(f"預估股利（{div_b:.2f}元）< 前年發放（{prev_div:.2f}元）")
                except Exception:
                    pass

            if flags_d:
                if not red_flag_check(flags_d, "獲利衰退確認（⑧出口）"):
                    st.markdown('<div class="not-rec">⛔ 不建議投資：獲利衰退，股利恐遭削減</div>',
                                unsafe_allow_html=True)
                    return
            else:
                st.markdown('<div class="ok-pass">✅ 獲利確認通過：EPS 與股利預估維持正成長</div>',
                            unsafe_allow_html=True)
        else:
            st.warning("請先填入營收與發行股數")

    # ════════════════════════════════════════════════════════════
    #  STEP 6 籌碼面
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🐋 STEP 6 ｜ 近6週千張大戶持股變化（趨勢比單週更可靠）", expanded=True):

        if not chip_df.empty:
            show_cols = [c for c in chip_df.columns
                         if any(k in c for k in ["date","HoldingSharesLevel","percent","400","foreign"])]
            st.dataframe(chip_df.tail(18)[show_cols or chip_df.columns.tolist()],
                         width="stretch")
            rpt["chip_signal"] = "自動取得資料，請依表格研判"
        else:
            st.info("💡 自動取得失敗，請手動填入近6週數據（來源：集保戶股權分散表 / wantgoo.com）")

            cols6 = st.columns(6)
            labels6 = ["W1（最舊）","W2","W3","W4","W5","W6（最新）🆕"]
            w_big, w_for = [], []
            for i, (col, lbl) in enumerate(zip(cols6, labels6)):
                with col:
                    st.markdown(f"**{lbl}**")
                    st.text_input("日期", placeholder="2026/05/01", key=f"wd{i}")
                    w_big.append(st.number_input("400張%", value=0.0, step=0.01, key=f"wb{i}"))
                    w_for.append(st.number_input("外資%",  value=0.0, step=0.01, key=f"wf{i}"))

            if w_big[0] > 0 and w_big[5] > 0:
                delta_big = w_big[5] - w_big[0]
                delta_for = w_for[5] - w_for[0]
                c1, c2 = st.columns(2)
                c1.metric("大戶6週合計變化", f"{delta_big:+.2f}%")
                c2.metric("外資6週合計變化", f"{delta_for:+.2f}%")
                rpt.update({
                    "chip_big_delta":     f"{delta_big:+.2f}%",
                    "chip_foreign_delta": f"{delta_for:+.2f}%",
                })

                # 6-week trend: count consecutive declining weeks
                big_diffs = [w_big[i+1] - w_big[i] for i in range(5)]
                consec_down = sum(1 for d in big_diffs[-4:] if d < -0.3)

                flags_e = []
                if consec_down >= 4:
                    flags_e.append(f"大戶連4週以上持續減持（6週趨勢向下）")
                elif consec_down >= 3:
                    flags_e.append(f"大戶近3-4週減持，趨勢偏弱，需觀察")
                if delta_for < -5:
                    flags_e.append(f"外資6週快速撤出 {delta_for:+.2f}%")
                if delta_big < -3 and delta_for < -2:
                    flags_e.append("大戶與外資同步撤出，籌碼惡化明顯")

                if flags_e:
                    if not red_flag_check(flags_e, "籌碼出走確認（STEP 6出口）"):
                        st.markdown('<div class="not-rec">⛔ 不建議投資：6週籌碼持續流失，暫緩進場</div>',
                                    unsafe_allow_html=True)
                        return
                    rpt["chip_signal"] = "⚠️ 籌碼出現異常，已確認繼續"
                else:
                    consec_up = sum(1 for d in big_diffs[-4:] if d > 0.1)
                    if consec_up >= 3:
                        signal = "✅ 大戶連3週以上增持，籌碼趨勢正向"
                    elif delta_big > 0:
                        signal = "✅ 6週大戶合計增持，籌碼偏正向"
                    else:
                        signal = "➡️ 籌碼穩定，無明顯異常（建議持續觀察）"
                    st.markdown(f'<div class="ok-pass">{signal}</div>', unsafe_allow_html=True)
                    rpt["chip_signal"] = signal

    # ════════════════════════════════════════════════════════════
    #  STEP 6b 籌碼面技術評分（融資／三大法人／投信／當沖）
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🔬 STEP 6b ｜ 籌碼面技術評分（融資增減／法人買賣超／投信買賣超／信用當沖）", expanded=True):
        st.caption("資料來源：台灣證交所公開交易資訊（經 FinMind API 彙整），採固定門檻規則式評分，非AI主觀判斷")

        inst_sig   = calc_institutional_signal(inst_df)
        margin_sig = calc_margin_signal(margin_df, price_hist_df)
        dt_sig     = calc_day_trading_signal(dt_df, price_hist_df)
        chip_tech_score, chip_tech_items = calc_chip_tech_score(inst_sig, margin_sig, dt_sig)
        ctg, ctc = grade_score(chip_tech_score)

        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"""
            <div style="background:white;border:2px solid {ctc};border-radius:12px;padding:18px;text-align:center">
              <div style="font-size:13px;color:#555;font-weight:600">籌碼面技術評分</div>
              <div style="font-size:44px;font-weight:800;color:{ctc};line-height:1.1">{ctg}</div>
              <div style="font-size:22px;font-weight:700;color:{ctc}">{chip_tech_score} / 100</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown("**📋 評分細項（四構面各25分）**")
            for icon, desc, pts in chip_tech_items:
                st.markdown(f"{icon} {desc} **({pts}分)**")

        # 原始數據呈現（可攤開檢視）
        with st.expander("查看原始數據", expanded=False):
            cc1, cc2 = st.columns(2)
            with cc1:
                if inst_sig:
                    st.markdown(f"- 三大法人 5日淨買賣：**{inst_sig['inst_net5']:+,.0f}** 張")
                    st.markdown(f"- 三大法人 10日淨買賣：**{inst_sig['inst_net10']:+,.0f}** 張")
                    st.markdown(f"- 投信 5日淨買賣：**{inst_sig['trust_net5']:+,.0f}** 張")
                    st.markdown(f"- 投信連續買超：**{inst_sig['trust_buy_streak']}** 日／連續賣超：**{inst_sig['trust_sell_streak']}** 日")
                else:
                    st.caption("三大法人／投信資料不足")
            with cc2:
                if margin_sig:
                    st.markdown(f"- 融資餘額5日變化：**{margin_sig['margin_chg_pct']:+.1f}%**")
                    if margin_sig.get("price_chg_pct") is not None:
                        st.markdown(f"- 股價同期變化：**{margin_sig['price_chg_pct']:+.1f}%**")
                else:
                    st.caption("融資資料不足")
                if dt_sig:
                    st.markdown(f"- 近5日信用當沖比例平均：**{dt_sig['day_trading_ratio_avg']:.1f}%**")
                else:
                    st.caption("當沖資料不足")

        rpt.update({
            "chip_tech_score": chip_tech_score, "chip_tech_grade": ctg,
            "chip_tech_summary": "；".join(f"{i[0]}{i[1]}" for i in chip_tech_items),
        })

    # ════════════════════════════════════════════════════════════
    #  STEP 6c 波浪理論輔助判讀（ZigZag，輔助非定論）
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🌊 STEP 6c ｜ 波浪理論輔助判讀（ZigZag 轉折點，輔助判讀非定論）", expanded=False):
        st.caption("以固定規則的 ZigZag 演算法客觀標記轉折高低點，輔助波浪計數；正式艾略特波浪理論仍需搭配型態、量能、費波那契比率等多重確認，本模組僅供參考")

        zz_pct = st.slider("轉折敏感度（反向變動幅度%才視為新轉折點）", 2.0, 10.0, 5.0, 0.5, key="zz_pct")
        pivots = zigzag_pivots(price_hist_df, pct_threshold=zz_pct)
        wave = simple_wave_count(pivots)

        if wave.get("available") and not price_hist_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=price_hist_df["date"], y=price_hist_df["close"],
                mode="lines", name="收盤價", line=dict(color="#c7c7c7", width=1),
            ))
            pv = wave["pivots"]
            fig.add_trace(go.Scatter(
                x=pv["date"], y=pv["price"], mode="lines+markers+text",
                text=pv["wave_label"], textposition="top center",
                name="ZigZag轉折", line=dict(color="#7c3aed", width=2),
                marker=dict(size=8),
            ))
            fig.update_layout(height=320, plot_bgcolor="white", paper_bgcolor="white",
                              margin=dict(t=20, b=20), title=f"{sname} 近期轉折點與簡化波浪標記")
            st.plotly_chart(fig, width="stretch")

            st.markdown(f'<div class="chip-box">📍 目前所處：<b>{wave["current_leg"]}</b>'
                        + (f"（波段變動 {wave['current_leg_chg_pct']:+.1f}%）" if wave["current_leg_chg_pct"] is not None else "")
                        + f"<br>{wave['stage_note']}</div>", unsafe_allow_html=True)
            rpt["wave_note"] = wave["stage_note"]
        else:
            st.info("近期股價轉折段數不足或資料不足，暫無法標記波浪，可調降敏感度門檻試試")

    # ════════════════════════════════════════════════════════════
    #  STEP 6d 技術線型截圖 AI 解讀＋自動數據交叉比對
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📸 STEP 6d ｜ 技術線型截圖 AI 解讀＋自動數據交叉比對（選用）", expanded=False):
        st.caption("上傳看盤軟體截圖（如K線圖、法人買賣超畫面），AI 僅會回報畫面上實際可辨識的數據，並與上方 FinMind 自動抓取的數據交叉比對，避免主觀臆測")

        api_key = st.text_input(
            "Anthropic API Key（僅本次session使用，不會被儲存）",
            type="password", key="anthropic_key",
            help="至 https://console.anthropic.com 申請，用量計費，每次解讀約數美分",
        )
        uploaded = st.file_uploader("上傳或貼上技術線型截圖", type=["png", "jpg", "jpeg"], key="chart_upload")

        if uploaded and api_key:
            if st.button("🔍 開始 AI 解讀截圖", key="run_vision"):
                with st.spinner("AI 正在解讀截圖…"):
                    result = analyze_chart_screenshot(uploaded.getvalue(), api_key)
                if result.get("error"):
                    st.error(f"解讀失敗：{result['error']}")
                else:
                    st.session_state["vision_result"] = result

        if st.session_state.get("vision_result"):
            vr = st.session_state["vision_result"]
            st.markdown("**📄 AI 從截圖中辨識到的數據**")
            st.json(vr.get("extracted", {}))
            st.markdown(f"**AI 訊號判讀：** {vr.get('signal_reading', 'N/A')}")

            # 交叉比對：AI從截圖讀到的方向 vs 自動抓取數據方向
            cross_notes = cross_check_vision_vs_data(vr, inst_sig, margin_sig, dt_sig)
            if cross_notes:
                st.markdown("**🔄 與自動抓取數據交叉比對**")
                for note in cross_notes:
                    st.markdown(f"- {note}")
        elif uploaded and not api_key:
            st.warning("請先輸入 Anthropic API Key 才能進行 AI 解讀")

    # ════════════════════════════════════════════════════════════
    #  STEP 7 策略
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("📅 STEP 7 ｜ 投資策略 ＆ 技術面進場時機", expanded=True):
        strat = st.radio("建議策略：", [
            "📅 長期投資（殖利率佳，護城河強，持有2年以上）",
            "⚡ 短期交易（題材驅動，技術面追蹤，嚴格停損）",
            "📅+⚡ 核心衛星（60% 長期 + 40% 短期）",
        ], key="strat")
        rpt["strategy"] = strat.split("（")[0]

        st.markdown("**📐 技術面進場判斷（選填）**")
        c1, c2, c3 = st.columns(3)
        with c1:
            ma20_pos = st.selectbox("股價 vs MA20", ["站上 MA20 ✅","接近 MA20 ➡️","跌破 MA20 ⚠️"], key="ma20")
        with c2:
            trend_confirm = st.selectbox("趨勢確認", ["MACD 黃金交叉 ✅","MACD 橫盤整理 ➡️","MACD 死亡交叉 ⚠️"], key="macd")
        with c3:
            support = st.selectbox("支撐位狀態", ["站穩關鍵支撐 ✅","靠近支撐待確認 ➡️","跌破支撐 ⚠️"], key="sup")

        tech_signals = []
        if "站上" in ma20_pos: tech_signals.append("站上MA20")
        if "黃金" in trend_confirm: tech_signals.append("MACD黃金交叉")
        if "站穩" in support: tech_signals.append("站穩支撐")
        tech_count = len(tech_signals)
        if tech_count >= 2:
            st.markdown(f'<div class="ok-pass">✅ 技術面 {tech_count}/3 項正向：{", ".join(tech_signals)}，進場時機偏好</div>', unsafe_allow_html=True)
        elif "跌破" in ma20_pos or "跌破" in support:
            st.markdown('<div class="red-check">⚠️ 技術面偏弱，建議等待支撐確認後再進場</div>', unsafe_allow_html=True)
        rpt["tech_signals"] = ", ".join(tech_signals) if tech_signals else "未評估"

    # ════════════════════════════════════════════════════════════
    #  STEP 8 資金配置
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("💰 STEP 8 ｜ 資金配置（100萬台幣）", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("總預算", "100 萬元")
        c2.metric("單檔上限 20%", "20 萬元")
        c3.metric("分3批，每批約", "6~7 萬元")
        st.markdown("""
        <div class="neutral-box">
        📌 <b>配置建議（v5 基本面停損）</b><br>
        第1批 6 萬：建立基本部位（確認趨勢前）<br>
        第2批 7 萬：趨勢確認後加碼<br>
        第3批 7 萬：突破關鍵阻力後<br><br>
        🛑 <b>停損原則（非固定 -10%）：</b><br>
        &nbsp;&nbsp;• <b>長期投資：</b>EPS預估下修 &gt; 20% → 檢討出場；連續2季EPS衰退 → 減碼<br>
        &nbsp;&nbsp;• <b>短期交易：</b>跌破關鍵支撐位 → 出場，不以固定%機械停損<br>
        &nbsp;&nbsp;• <b>估值過高：</b>股價 &gt; 目標價 × 1.3 時縮減部位至 10%<br><br>
        其餘 80 萬：分散 4~5 支股票或現金/ETF
        </div>
        """, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════
    #  INVESTMENT SCORE MODULE
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    with st.expander("🏆 投資評分總結（短期 1-2月 ／ 長期 6月-2年）", expanded=True):

        # ── Collect signals ─────────────────────────────────────
        latest_roe = list(roe_dict.values())[-1] if roe_dict else 0
        eps_vals   = [eps_dict[k] for k in sorted(eps_dict.keys())] if eps_dict else []
        eps_trend  = len(eps_vals) >= 2 and eps_vals[-1] > eps_vals[-2]
        eps_trend3 = len(eps_vals) >= 3 and all(eps_vals[i] < eps_vals[i+1] for i in range(len(eps_vals)-3, len(eps_vals)-1))

        # Revenue growth B from session state
        try:
            B_val = float(st.session_state.get("B", 0))
        except Exception:
            B_val = 0.0

        # Yield
        try:
            yld = float(rpt.get("yield_base", "0").replace("%", ""))
        except Exception:
            yld = 0.0

        # Chip delta
        try:
            chip_big_d = float(rpt.get("chip_big_delta", "0").replace("%","").replace("+",""))
        except Exception:
            chip_big_d = 0.0

        # ── SHORT-TERM SCORE (1–2 months) ───────────────────────
        st_score = 0
        st_items = []

        # 1. Revenue momentum (25 pts)
        if B_val >= 15:
            st_score += 25; st_items.append(("✅", f"營收高速成長 +{B_val:.1f}%", 25))
        elif B_val >= 8:
            st_score += 18; st_items.append(("✅", f"營收穩健成長 +{B_val:.1f}%", 18))
        elif B_val >= 0:
            st_score += 10; st_items.append(("➡️", f"營收微幅成長 +{B_val:.1f}%", 10))
        else:
            st_score +=  0; st_items.append(("⚠️", f"營收衰退 {B_val:.1f}%", 0))

        # 2. Chip trend (25 pts)
        if chip_big_d >= 1:
            st_score += 25; st_items.append(("✅", f"大戶持續增持 +{chip_big_d:.2f}%", 25))
        elif chip_big_d >= 0:
            st_score += 15; st_items.append(("➡️", "大戶小幅增持/持平", 15))
        elif chip_big_d >= -1:
            st_score += 5;  st_items.append(("⚠️", f"大戶小幅減持 {chip_big_d:.2f}%", 5))
        else:
            st_score += 0;  st_items.append(("🔴", f"大戶明顯減持 {chip_big_d:.2f}%", 0))

        # 3. Industry cycle (20 pts)
        cyc_v = st.session_state.get("産業景氣位置", "")
        if "上行" in str(rpt.get("industry", "")) or "上行期" in cyc:
            st_score += 20; st_items.append(("✅", "產業上行期", 20))
        elif "高峰" in cyc:
            st_score += 12; st_items.append(("➡️", "產業高峰期（中性）", 12))
        elif "底部" in cyc:
            st_score += 8;  st_items.append(("➡️", "產業底部，等待轉機", 8))
        else:
            st_score += 0;  st_items.append(("⚠️", "產業下行期，短期風險高", 0))

        # 4. EPS momentum (15 pts)
        if eps_trend:
            st_score += 15; st_items.append(("✅", "EPS 年增，獲利動能正向", 15))
        elif len(eps_vals) >= 1 and eps_vals[-1] > 0:
            st_score += 8;  st_items.append(("➡️", "EPS 正值但未見成長", 8))
        else:
            st_score += 0;  st_items.append(("⚠️", "EPS 衰退或虧損", 0))

        # 5. Technical (15 pts)
        tech_sig = rpt.get("tech_signals", "")
        tc = tech_sig.count("MA20") + tech_sig.count("黃金") + tech_sig.count("支撐")
        if tc >= 2:
            st_score += 15; st_items.append(("✅", f"技術面 {tc}/3 正向信號", 15))
        elif tc == 1:
            st_score += 8;  st_items.append(("➡️", "技術面 1 項正向信號", 8))
        else:
            st_score += 0;  st_items.append(("⚠️", "技術面信號不明確", 0))

        # ── LONG-TERM SCORE (6 months – 2 years) ───────────────
        lt_score = 0
        lt_items = []

        # 1. ROE quality (25 pts)
        if latest_roe >= 20:
            lt_score += 25; lt_items.append(("✅", f"ROE 優秀 {latest_roe:.1f}% ≥ 20%", 25))
        elif latest_roe >= 15:
            lt_score += 18; lt_items.append(("✅", f"ROE 健全 {latest_roe:.1f}% ≥ 15%", 18))
        elif latest_roe >= 10:
            lt_score += 10; lt_items.append(("➡️", f"ROE 尚可 {latest_roe:.1f}%（< 15% 門檻）", 10))
        else:
            lt_score += 0;  lt_items.append(("⚠️", f"ROE 偏低 {latest_roe:.1f}%", 0))

        # 2. EPS growth trend (25 pts)
        if eps_trend3:
            lt_score += 25; lt_items.append(("✅", "EPS 連續3年成長，品質佳", 25))
        elif eps_trend:
            lt_score += 15; lt_items.append(("✅", "EPS 近1年成長", 15))
        elif len(eps_vals) >= 1 and eps_vals[-1] > 0:
            lt_score += 8;  lt_items.append(("➡️", "EPS 正值但趨勢平緩", 8))
        else:
            lt_score += 0;  lt_items.append(("⚠️", "EPS 衰退，長期動能不足", 0))

        # 3. Dividend yield (20 pts)
        if yld >= 5:
            lt_score += 20; lt_items.append(("✅", f"殖利率優異 {yld:.1f}% ≥ 5%", 20))
        elif yld >= 3:
            lt_score += 15; lt_items.append(("✅", f"殖利率良好 {yld:.1f}% ≥ 3%", 15))
        elif yld >= 2:
            lt_score += 8;  lt_items.append(("➡️", f"殖利率一般 {yld:.1f}%", 8))
        else:
            lt_score += 0;  lt_items.append(("⚠️", f"殖利率偏低 {yld:.1f}%（或未取得）", 0))

        # 4. Moat / Industry (15 pts)
        if "強" in moat:
            lt_score += 15; lt_items.append(("✅", "護城河強，競爭壁壘高", 15))
        elif "中" in moat:
            lt_score += 8;  lt_items.append(("➡️", "護城河中等", 8))
        else:
            lt_score += 0;  lt_items.append(("⚠️", "護城河弱，易被取代", 0))

        # 5. Revenue growth – structural (15 pts)
        if B_val >= 10:
            lt_score += 15; lt_items.append(("✅", "營收高速成長，業務擴張", 15))
        elif B_val >= 5:
            lt_score += 10; lt_items.append(("✅", "營收穩健成長", 10))
        elif B_val >= 0:
            lt_score += 5;  lt_items.append(("➡️", "營收正成長但偏低", 5))
        else:
            lt_score += 0;  lt_items.append(("⚠️", "營收負成長，結構性壓力", 0))

        # ── Grade helper ─────────────────────────────────────────
        def grade(s):
            if s >= 85: return "A+", "#27ae60"
            if s >= 70: return "A",  "#2d9e60"
            if s >= 55: return "B+", "#e67e22"
            if s >= 40: return "B",  "#c47800"
            if s >= 25: return "C",  "#e05252"
            return "D", "#c02020"

        st_grade, st_color = grade(st_score)
        lt_grade, lt_color = grade(lt_score)

        # ── Render ───────────────────────────────────────────────
        col1, col2 = st.columns(2)

        with col1:
            st.markdown(f"""
            <div style="background:white;border:2px solid {st_color};border-radius:12px;padding:20px;text-align:center">
              <div style="font-size:13px;color:#555;font-weight:600">短期 1-2個月 評分</div>
              <div style="font-size:52px;font-weight:800;color:{st_color};line-height:1.1">{st_grade}</div>
              <div style="font-size:28px;font-weight:700;color:{st_color}">{st_score} / 100</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**📋 短期評分細項**")
            for icon, desc, pts in st_items:
                st.markdown(f"{icon} {desc} **({pts}分)**")

        with col2:
            st.markdown(f"""
            <div style="background:white;border:2px solid {lt_color};border-radius:12px;padding:20px;text-align:center">
              <div style="font-size:13px;color:#555;font-weight:600">長期 6個月-2年 評分</div>
              <div style="font-size:52px;font-weight:800;color:{lt_color};line-height:1.1">{lt_grade}</div>
              <div style="font-size:28px;font-weight:700;color:{lt_color}">{lt_score} / 100</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("**📋 長期評分細項**")
            for icon, desc, pts in lt_items:
                st.markdown(f"{icon} {desc} **({pts}分)**")

        # ── Summary verdict ──────────────────────────────────────
        st.markdown("---")
        if lt_score >= 70 and st_score >= 55:
            verdict_text = f"📈 長短期皆強（長期{lt_grade} {lt_score}分 / 短期{st_grade} {st_score}分）→ 可考慮積極建立部位"
            verdict_color = "#27ae60"
        elif lt_score >= 70:
            verdict_text = f"📅 長期佳但短期動能不足（長期{lt_grade} {lt_score}分 / 短期{st_grade} {st_score}分）→ 建議長期持有，分批進場"
            verdict_color = "#2d6abf"
        elif st_score >= 55:
            verdict_text = f"⚡ 短期動能強但長期品質待確認（短期{st_grade} {st_score}分）→ 小部位短線操作"
            verdict_color = "#e67e22"
        else:
            verdict_text = f"⚠️ 長短期評分均偏低（長期{lt_grade} {lt_score}分 / 短期{st_grade} {st_score}分）→ 建議觀望等待訊號改善"
            verdict_color = "#c02020"

        st.markdown(f"""
        <div style="background:{verdict_color}22;border:2px solid {verdict_color};
             border-radius:10px;padding:16px;font-size:15px;font-weight:600;color:{verdict_color}">
        {verdict_text}
        </div>
        """, unsafe_allow_html=True)

        rpt.update({
            "st_score": st_score, "st_grade": st_grade,
            "lt_score": lt_score, "lt_grade": lt_grade,
        })

    # ════════════════════════════════════════════════════════════
    #  STEP 9 報告輸出
    # ════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown("### 📋 STEP 9 ｜ 輸出完整分析報告")
    st.markdown("""
    <div class="ok-pass">
    <b>✅ 分析完成！所有節點均通過</b><br>
    依據財務、產業、營收、獲利、籌碼五大面向評估，目前條件符合投資參考標準。<br>
    ⚠️ 本工具僅供參考，最終決策請自行判斷。
    </div>
    """, unsafe_allow_html=True)

    rpt["verdict"] = "通過所有分析節點，建議依個人風險承受度考慮投資"

    if st.button("📥 產生並下載 HTML 分析報告", type="primary"):
        html = build_html_report(rpt)
        b64 = base64.b64encode(html.encode("utf-8")).decode()
        fname = f"{sid}_{sname}_{datetime.now().strftime('%Y%m%d')}_投資分析報告.html"
        st.markdown(
            f'<a href="data:text/html;base64,{b64}" download="{fname}">'
            f'📄 點擊此處下載：{fname}</a>',
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
