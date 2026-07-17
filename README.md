# tw-market-map — 自用台股產業地圖

仿 aistockmap.com 的自用台股儀表板。GitHub Actions 每交易日收盤後抓免費公開資料，產靜態 JSON + 單頁 HTML，掛 GitHub Pages。（排程設 17:30，但 Actions 免費排程實測平均遲到 ~134 分 → 實際更新約 19:00–20:30。）

**定位：只做現況呈現，不做預測。** 省看盤時間，不是找明牌。

## 功能（P1–P7 全上線，分頁式版型）

- **P1 核心盤面**：國際指數卡（加權/費半/S&P500/台積 ADR/日經/VIX/NVDA）、三大法人（上市 BFI82U＋上櫃 TPEx）、資券（MI_MARGN）、產業熱力圖（手刻 squarified treemap）、日/週強弱排行 Top20
- **P2 題材頁**：20 題材＋個股對照（已人工校對）；法人個股動向（T86/TPEx 買賣超、連買天數）
- **P3 觀測站**：MOPS 重大訊息＋TDCC 大戶持股週動向
- **P4 價值鏈**：產業價值鏈（3 鏈）＋個股直連 kanpan 面板（`?sid=`）
- **法人資金流**：法人買賣超聚合到產業/題材
- **P5 基本面深度＋市場新聞聚合**
- **P6 分頁式改版**：仿 aistockmap 版型（vanilla 重刻，未搬其程式碼）
- **P7 市場寬度＋營收亮點＋日期回看＋全站搜尋**
- 個股點擊開 Yahoo 股市頁；MOPS 資料有防倒退守門

## 架構

```
scripts/
  tw_common.py         共用：HTTP 節流、民國日期、freshness 守門（移植自 tw-stock-bot）
  fetch_indices.py     yfinance 指數
  fetch_market.py      TWSE BFI82U + MI_MARGN + TPEx insti/summary
  fetch_daily_all.py   TWSE rwd MI_INDEX + TPEx quotes + 產業分類(t187ap03)
  fetch_t86.py         法人個股買賣超（T86 / TPEx）
  fetch_mops.py        MOPS 重大訊息
  fetch_tdcc.py        TDCC 大戶持股週動向
  fetch_fundamentals.py / fetch_revenue.py / fetch_news.py   基本面 / 營收 / 新聞
  build_heatmap.py     產業聚合 treemap 資料
  build_rank.py        日/週排行 + data/history 日快照
  build_topics.py      題材對照（topics/topics.json）
  build_chains.py      價值鏈（chains/chains.json）
  build_inst_rank.py / build_flow.py / build_breadth.py   法人排行 / 資金流 / 市場寬度
  render.py            產 docs/index.html（dark 分頁式 RWD，資料內嵌）
  run_all.py           管線入口（單模組失敗不擋全局）
data/                  JSON 輸出（信封格式：ok/data_date/fetched_at/source/error/data）
docs/index.html        GitHub Pages 入口
.github/workflows/daily.yml  平日 09:30 UTC（台北 17:30 排程；實際觸發約 19:00–20:30，Actions 排隊延遲）
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

## 待辦（選配）

- TG 推播（SPEC P4 的選配項，未做）

SPEC：`AI_agent/100_Todo/2026-07-06_tw-market-map自用產業地圖_SPEC.md`

## 資料源踩坑（除錯前先看）

- TWSE openapi `STOCK_DAY_ALL` 隔日早上才更新 → 當晚要用 rwd `MI_INDEX?type=ALLBUT0999`
- 上櫃法人**金額**用 `tpex.org.tw/www/zh-tw/insti/summary`（3insti 個股端點給的是**股數**）
- Mac LibreSSL 對 TPEx SSL 挑剔 → 已加 curl 備援
- T86 有短列 → 已加 guard
- MI_MARGN 會逾時 → timeout 60s，失敗沿用前次並標資料日
