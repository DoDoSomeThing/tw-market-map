# tw-market-map — 自用台股產業地圖

仿 aistockmap.com 的自用台股儀表板。GitHub Actions 每交易日 17:30 後抓免費公開資料，產靜態 JSON + 單頁 HTML，掛 GitHub Pages。

**定位：只做現況呈現，不做預測。** 省看盤時間，不是找明牌。

## P1 內容（已完成）

- **國際指數卡**：加權 / 費半 / S&P500 / 台積 ADR / 日經 / VIX / NVDA（yfinance）
- **三大法人**：上市 BFI82U + 上櫃 TPEx 彙總（買/賣/買賣超，億元）
- **資券**：上市融資金額 / 融券張數餘額變化（MI_MARGN）
- **產業熱力圖**：上市+上櫃全市場，TWSE 產業分類聚合，格子大小=成交值、顏色=漲跌%（紅漲綠跌），手刻 squarified treemap 無框架
- **強弱排行**:日 / 週 Top 20（門檻：日成交值 ≥ 1 億；週=近 5 交易日快照累積）

## 架構

```
scripts/
  tw_common.py       共用：HTTP 節流、民國日期、freshness 守門（移植自 tw-stock-bot）
  fetch_indices.py   yfinance 指數
  fetch_market.py    TWSE BFI82U + MI_MARGN + TPEx insti/summary
  fetch_daily_all.py TWSE STOCK_DAY_ALL + TPEx quotes + 產業分類(t187ap03)
  build_heatmap.py   產業聚合 treemap 資料
  build_rank.py      日/週排行 + data/history 日快照
  render.py          產 docs/index.html（dark 單頁 RWD，資料內嵌）
  run_all.py         管線入口（單模組失敗不擋全局）
data/                JSON 輸出（信封格式：ok/data_date/fetched_at/source/error/data）
docs/index.html      GitHub Pages 入口
.github/workflows/daily.yml  平日 09:30 UTC（台北 17:30）
```

## 資料新鮮度鐵則

- 每個資料檔帶 `data_date`，**瀏覽端** JS 算交易日齡（頁面可能隔天才開，伺服端算會裝新鮮）
- 逾 2 交易日 → 區塊標 ⚠️；抓取失敗 → 顯示錯誤，**絕不拿舊資料裝新**
- 漲跌% 超過 ±10%（漲跌停）視為欄位錯，該筆剔除

## 本機跑

```bash
pip install -r requirements.txt
python scripts/run_all.py
open docs/index.html
```

Windows 需 `PYTHONUTF8=1`。

## 部署（一次性手動步驟）

1. GitHub 建 repo `tw-market-map`（建議 DoDoSomeThing 帳號），push 本目錄
2. Settings → Pages → Deploy from branch → `main` / `docs/`
3. Actions 需 workflow 寫入權限：Settings → Actions → General → Workflow permissions → Read and write

## 後續階段

- P2 題材頁（20 題材 + 個股對照，Claude 初稿 + 人工校）
- P3 觀測站（MOPS 重大訊息 + TDCC 大戶持股）
- P4 價值鏈 + kanpan 連結 + TG 推播

SPEC：`AI_agent/100_Todo/2026-07-06_tw-market-map自用產業地圖_SPEC.md`
