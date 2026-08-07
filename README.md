# tw-market-map — 自用台股產業地圖

網址：https://dodosomething.github.io/tw-market-map/

GitHub Actions 每交易日收盤後抓免費公開資料，產靜態 JSON + 單頁 HTML，掛 GitHub Pages。（排程設 17:30，但 Actions 免費排程實測平均遲到 ~134 分 → 實際更新約 19:00–20:30。）

**定位：只做現況呈現，不做預測。** 省看盤時間，不是找明牌。

## 功能（P1–P7 全上線，分頁式版型）

- **P1 核心盤面**：國際指數卡（加權/費半/S&P500/台積 ADR/日經/VIX/NVDA）、三大法人（上市 BFI82U＋上櫃 TPEx）、資券（MI_MARGN）、產業熱力圖（手刻 squarified treemap）、日/週強弱排行 Top20
- **P2 題材頁**：20 題材＋個股對照（已人工校對）；法人個股動向（T86/TPEx 買賣超、連買天數）
- **P3 觀測站**：MOPS 重大訊息＋TDCC 大戶持股週動向
- **P4 價值鏈**：產業價值鏈（3 鏈）＋個股直連 kanpan 面板（`?sid=`）
- **法人資金流**：法人買賣超聚合到產業/題材
- **P5 基本面深度＋市場新聞聚合**
- **P6 分頁式改版**（vanilla 重刻）
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
  fetch_fin_history.py 歷史季報 archive（MOPS t163sb04）→ data/history_fin/<民國年>Q<季>.json
  build_fin_growth.py  TTM EPS 年增率／毛利率年增差
  build_health.py      四燈號健診卡（12 格計分）→ data/health.json
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
- MI_MARGN 個股表**融資段與融券段欄名重複**（都叫「前日餘額/今日餘額」）→ 用「現金償還」「現券償還」當錨點分段，直接建 name→index 對照會拿到融券數字當融資
- 歷史季報只能走 MOPS `ajax_t163sb04`（POST）：openapi `t187ap06_L_ci` **只回本季已公布者**，換季當下多數個股連當季 EPS 都沒有，更沒有去年同季可比
  - 網域必須 `mopsov.twse.com.tw`；舊的 `mops.twse.com.tw` 回 WAF 擋頁但**狀態碼是 200**，很容易誤判成成功
  - 回應是多張表（一般業/金融/證券/保險/其他業欄位各不同），只讀第一張會漏掉一半市場；銀行保險沒有營收/毛利概念 → 誠實留空
  - 數字是**當年累計**不是單季（Q2=上半年、Q4=全年）→ TTM 換算見 `build_fin_growth.py`

## 健診卡的定位（別誤用）

四燈號健診是**描述性彙整**：把 12 個既有指標對照固定門檻換成顏色，一眼看完四個面向。
權重（40/30/30、每面 25 分）是人訂的、**未經回測**。所以：

- 只出現在個股面板，**不做總分排行榜、不出高分股清單**（燈號型評分在 tw-quant-lab 驗過沒有預測力）
- 配色照**台股邏輯：紅=強、綠=弱**，跟全站漲跌同一套語意。CSS 仍用獨立的 `--hc-strong/--hc-weak` 而不直接吃 `--up/--down`——健診的紅是「基本面強」、漲跌的紅是「今天漲」，只是碰巧同色，分開才不會改漲跌配色時被連坐
- 估值面是「同產業今日橫斷面分位」，**不是本益比河流**。河流要 3~5 年 PE 時間序列，`data/history_valuation/` 2026-07-16 才開始累積，長度不夠就別掛河流的名字賣分位數
- 券資比在台股普遍極低（全市場中位 ~0.2%）→ 這格實務上幾乎恆綠，只當風險旗標看；TWSE 僅公布上市，上櫃該格不計分
- **ETF 走 2 面制、滿分 50**（`is_etf` = 代號 0 開頭）。ETF 沒有 EPS／毛利／營收，PE／PB 對一籃子持股也不具個股意義 → 基本面與估值面標「不適用」整面不畫，只評籌碼＋技術。
  照個股規則算會出事：「缺資料不計入分母」讓 0050 湊出 **90 分**、0056 **92 分**，還跟個股分數並排——分母不同，比了等於騙自己。槓桿／反向型（代號結尾 L／R）另加長期偏離警語。
  註：目前只有 8 支四碼 ETF（0050~0061）進得了健診，5~6 碼 ETF（00631L、00878…共 373 支）不在 `ta.json` 涵蓋範圍內，面板不顯示健診卡
