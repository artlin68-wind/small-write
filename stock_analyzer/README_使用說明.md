# 台灣股票投資分析工具 v2.1（v5框架＋籌碼技術模組）— 使用說明

## 功能概覽
輸入股票代碼，自動走完 9 步驟分析流程，並在各紅旗節點做出投資判斷，最終輸出可下載的 HTML 分析報告。

v2.0 新增：ROE門檻升至15%、負債比改同業比較、6週籌碼追蹤、技術面進場評估、總經/利率環境、基本面停損、**投資評分模組（短期1-2月 ／ 長期6月-2年）**

v2.1 新增（籌碼／技術面深化）：
- 🔬 **籌碼面技術評分**：融資增減、三大法人買賣超、投信買賣超、信用當沖比例，四構面各25分，固定門檻規則式評分（可解釋、可重現，非AI主觀判斷）
- 🌊 **波浪理論輔助判讀**：ZigZag演算法客觀標記股價轉折高低點，輔助簡化波浪計數（僅供參考，非嚴謹艾略特波浪定論）
- 📸 **技術線型截圖 AI 解讀**：可上傳看盤軟體截圖，呼叫 Claude Vision 解讀畫面上的數據，並與 FinMind 自動抓取的數據交叉比對，避免主觀臆測（此功能為選用，需自行申請 Anthropic API Key，用量計費）

## 一次性安裝（只需做一次）

### 步驟 1：安裝 Python
前往 https://www.python.org/downloads/ 下載 Python 3.10 以上版本，安裝時勾選「Add Python to PATH」。

### 步驟 2：開啟命令提示字元（cmd）
按 `Win + R` → 輸入 `cmd` → 按 Enter

### 步驟 3：安裝所需套件
```
cd "D:\Art_Project\AI Project\Claude Code\投資小白\stock_analyzer"
pip install -r requirements.txt
```

---

## 每次啟動

```
cd "D:\Art_Project\AI Project\Claude Code\投資小白\stock_analyzer"
streamlit run app.py
```

瀏覽器會自動開啟 http://localhost:8501

---

## 使用方式

| 步驟 | 操作 |
|------|------|
| 1 | 在左側輸入股票代碼（如 `2317`）或公司名稱（如 `鴻海`） |
| 2 | 點擊「🔍 開始分析」 |
| 3 | 系統自動抓取 FinMind 公開資料 |
| 4 | 依序閱讀每個 STEP，確認紅旗節點判斷 |
| 5 | 通過所有節點後，點擊「📥 產生並下載 HTML 報告」 |

---

## 分析流程對應

| 節點 | 內容 | 資料來源 |
|------|------|---------|
| STEP 1–2 | 基本資料（代號、名稱、產業、股價） | FinMind 自動 |
| STEP 3 | EPS / ROE / 負債比率 + 財務紅旗 | FinMind 自動 |
| STEP 4 | 產業景氣 / 護城河 / 政策風險 | 手動填入 |
| STEP 5 | 投資可行性綜合判斷 | 手動確認 |
| ①②③ | 月營收年增率 → 預估全年營收 | FinMind 自動 |
| ④–⑧ | 稅後淨利率 → EPS → 股利預估 | 半自動（可調整） |
| STEP 6 | 近6週千張大戶 / 外資持股變化（趨勢判斷） | FinMind 或手動填入 |
| STEP 6b | 籌碼面技術評分（融資／法人／投信／當沖） | FinMind 自動 |
| STEP 6c | 波浪理論輔助判讀（ZigZag轉折點） | 自動計算（依股價） |
| STEP 6d | 技術線型截圖 AI 解讀＋交叉比對 | 選用，需自行提供 Anthropic API Key |
| STEP 7–8 | 投資策略 / 資金配置建議 | 手動確認 |
| STEP 9 | 輸出 HTML 完整分析報告 | 自動生成 |

---

## 資料來源

- **FinMind 免費 API**：https://finmindtrade.com（不需要帳號，有速率限制；彙整自台灣證交所／櫃買中心公開交易資訊）
- **集保戶股權分散表**（籌碼面）：https://www.tdcc.com.tw 或 https://www.wantgoo.com
- **Anthropic Claude API**（STEP 6d 截圖解讀用，選用）：https://console.anthropic.com

## STEP 6d 截圖解讀設定方式

1. 至 https://console.anthropic.com 註冊帳號並取得 API Key（格式 `sk-ant-...`）
2. 在 STEP 6d 區塊的欄位貼上 API Key（僅在當次瀏覽器 session 使用，不會被寫入檔案）
3. 上傳看盤軟體截圖（K線圖、法人買賣超畫面等），點擊「開始 AI 解讀截圖」
4. AI 只會回報畫面上『實際看得到』的數據，並自動與 FinMind 抓到的數據比對方向是否一致
5. 每次解讀會依 Anthropic 用量計費（Claude Sonnet 影像輸入，約數美分/次），非免費功能

---

## 常見問題

**Q：資料顯示「無法自動取得」**
A：FinMind 有每日免費請求次數限制。若超過限制，部分資料需手動填入，或隔日再使用。申請免費帳號可提高額度：https://finmindtrade.com

**Q：如何分享給同事使用？**
A：將整個 `stock_analyzer` 資料夾複製給同事，同事依相同步驟安裝即可。或在公司內網部署後，提供 IP + Port 讓同事直接用瀏覽器開啟（不需各自安裝）。

**Q：EPS 和月營收的資料是否即時？**
A：月營收通常在每月10日之前公布，FinMind 更新頻率約1天內。股價資料為延遲約15分鐘。

---

## 免責聲明
本工具分析結果僅供參考，不構成任何投資建議。投資有風險，請依個人財務狀況與風險承受度謹慎判斷。
