# 技術線型解讀APP — 設計指南

適用平台：Python + Streamlit
定位：作為現有「台灣股票投資分析工具」(`stock_analyzer/app.py`) 的**技術面診斷模組**，兩者共用同一個 FinMind 資料層與快取機制，互相補強：

| 現有工具 | 本設計 |
|---|---|
| 基本面／財務／營收預估／九步驟評分 | K線型態、均線、量價、法人籌碼「技術面」判讀 |
| 回答「值不值得投資」 | 回答「現在是不是進場/出場時機」 |

以工程術語比喻：現有工具做的是「材料的可靠度分析」（長期體質），本模組做的是「即時應力監測」（短期訊號），兩者合併才是完整的設計驗證流程。

---

## 1. 系統架構（四層）

```
┌─────────────────────────────────────────┐
│ 呈現層 (Streamlit UI)                     │
│  - K線圖 (plotly candlestick)             │
│  - 型態標註 / 訊號燈號 / 文字解讀           │
├─────────────────────────────────────────┤
│ 判讀層 (Interpretation Engine)            │
│  - 規則引擎：把指標數值轉成「白話文結論」    │
│  - 例：「MA5上穿MA20 + 量增 → 短線偏多」    │
├─────────────────────────────────────────┤
│ 指標運算層 (Indicator Engine)              │
│  - 均線 / KD / MACD / RSI / 布林通道       │
│  - K線型態辨識 (candlestick patterns)      │
│  - 量價關係 (OBV、量比)                    │
│  - 法人籌碼彙總 (三大法人、投信、融資融券)   │
├─────────────────────────────────────────┤
│ 資料層 (FinMind API + 快取)                │
│  - 沿用現有 app.py 的 @st.cache_data 模式  │
└─────────────────────────────────────────┘
```

**設計原則**：指標運算層只算數字，判讀層負責把數字翻成「這代表什麼」。分開寫的好處是規則之後好調整，不用動到計算邏輯（跟你做可靠度設計時把「量測」和「判定標準」分開是同樣道理）。

---

## 2. 資料來源（FinMind，免費額度已在用）

| 用途 | Dataset | 備註 |
|---|---|---|
| OHLCV 日K | `TaiwanStockPrice` | 現有 app.py 已使用 |
| 三大法人買賣超 | `TaiwanStockInstitutionalInvestorsBuySell` | 欄位含 name（外資/投信/自營商）、buy、sell |
| 融資融券 | `TaiwanStockMarginPurchaseShortSale` | 判斷散戶籌碼 |
| 大戶持股分散表 | `TaiwanStockHoldingSharesPer` | 現有 app.py 已使用（STEP 6） |
| 分鐘K（選用） | `TaiwanStockPriceMinute` | 若要做當沖/短線功能才需要 |

官方文件：[FinMind 技術面](https://finmind.github.io/tutor/TaiwanMarket/Technical/)、[FinMind 籌碼面](https://finmind.github.io/tutor/TaiwanMarket/Chip/)

---

## 3. 四大分析模組

### 3.1 K線型態辨識
- **做法**：用 `pandas-ta`（純 Python，免編譯，比 TA-Lib 好裝在 Windows）內建的 candlestick pattern 函式，或自訂規則判斷常見型態：吞噬(engulfing)、十字星(doji)、鎚子線(hammer)、頭肩頂/底、三角收斂。
- **建議先做**：單根/雙根型態（doji、engulfing、hammer）— 規則簡單、誤判率低。
- **後做**：多根型態（頭肩頂、三角收斂）— 需要抓局部高低點，邏輯較複雜，建議 Phase 2 再上。
- **輸出**：型態名稱 + 出現位置（畫在K線圖上）+ 白話解讀（例如「量增吞噬棒，短線反轉訊號」）。

### 3.2 均線與趨勢判斷
延續你截圖上已有的均價5/10/20/120，額外計算：
- 均線多空排列：MA5 > MA10 > MA20 = 多頭排列
- 黃金交叉／死亡交叉：短天期均線上穿/下穿長天期
- 乖離率 BIAS = (股價 − MA20) ÷ MA20，過高代表短線過熱

### 3.3 成交量與量價關係
- 量增價漲／量縮價跌 = 健康；量增價跌／量縮價漲 = 背離警訊
- OBV（能量潮）判斷資金是否持續進場
- 均量比：今日量 ÷ 均量20，> 2 代表異常放量

### 3.4 法人籌碼／投信動向
截圖中「投信買賣超」「投信庫存」已是這個模組的雛形，建議擴充：
- 三大法人（外資/投信/自營商）合計買賣超連續天數
- 投信庫存趨勢（連增/連減週數）
- 融資餘額變化（融資大增後股價漲 = 散戶追價，需留意反轉風險）

---

## 4. 判讀規則引擎（範例）

```python
def interpret_technical(row):
    signals = []
    if row["ma5"] > row["ma10"] > row["ma20"]:
        signals.append(("均線多頭排列", "positive"))
    if row["volume"] > row["vol_ma20"] * 1.5 and row["close"] > row["open"]:
        signals.append(("價漲量增", "positive"))
    if row["trust_buy_streak"] >= 3:
        signals.append(("投信連3日買超", "positive"))
    if row["bias20"] > 8:
        signals.append(("乖離過大，短線過熱", "warning"))

    bullish = sum(1 for _, t in signals if t == "positive")
    verdict = "偏多" if bullish >= 3 else "中性偏多" if bullish >= 2 else "觀望"
    return signals, verdict
```

這種「訊號清單 + 計分 + 結論」的寫法，剛好可以沿用你現有 `stock_analyzer/app.py` 裡投資評分模組已經用過的 pattern（STEP 7 的技術面 2/3 判斷），不用重新發明架構。

---

## 5. 技術堆疊建議

| 項目 | 建議 | 原因 |
|---|---|---|
| 資料處理 | pandas | 已在用 |
| 技術指標 | pandas-ta | 免編譯，Windows 好裝；不用 TA-Lib（要裝C library，麻煩） |
| 圖表 | plotly (candlestick + subplot 量能) | 已在用，互動性好 |
| 介面 | Streamlit | 已在用，符合你的選擇 |
| 型態標註 | 用 plotly `add_annotation` 在圖上畫箭頭/文字 | 不需額外套件 |

---

## 6. 與現有工具整合方式

在 `stock_analyzer/app.py` 新增一個分頁（Streamlit `st.tabs`），例如：

```python
tab1, tab2 = st.tabs(["📊 基本面九步驟分析", "📈 技術面診斷"])
with tab2:
    render_technical_dashboard(stock_id)
```

好處：共用同一個 FinMind token、同一個股票搜尋輸入框、同一個 `2_啟動工具.bat` 啟動方式，使用者不用切換到另一個網址。

---

## 7. 開發路線圖

| 階段 | 內容 | 產出 |
|---|---|---|
| Phase 1（MVP） | 均線排列 + 量價關係 + 三大法人買賣超，規則引擎給結論 | 能跑的技術面分頁 |
| Phase 2 | 單根K線型態辨識（doji/engulfing/hammer）+ 圖上標註 | 型態自動標記 |
| Phase 3 | 多根K線型態（頭肩頂/三角收斂）+ 回測驗證規則準確度 | 進階型態辨識 |
| Phase 4（選用） | 訊號歷史回測（過去訊號出現後N天漲跌統計） | 幫你評估規則是否真的有效 |

**建議從 Phase 1 開始**：資料已經有（FinMind 已串接），規則最簡單，最快看到成果，也最容易验证是否有用。

---

## 下一步

1. 確認 Phase 1 範圍（均線＋量價＋法人）是否符合你要的第一版
2. 我可以直接在 `stock_analyzer/app.py` 新增技術面分頁的程式碼
3. 或先產出一份互動流程圖（用 design-flowchart skill）把上面架構視覺化，方便你檢視後再決定

Sources:
- [FinMind 技術面資料集](https://finmind.github.io/tutor/TaiwanMarket/Technical/)
- [FinMind 籌碼面資料集](https://finmind.github.io/tutor/TaiwanMarket/Chip/)
- [FinMind API 總覽](https://finmind.github.io/tutor/TaiwanMarket/DataList/)
