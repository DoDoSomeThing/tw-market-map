# run_all.py — P1 管線：抓資料 → 聚合 → 產頁。單一模組失敗不擋全局（render 端顯示 ⚠️）。
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "fetch_indices.py",
    "fetch_market.py",
    "fetch_daily_all.py",
    "fetch_margin.py",     # 個股融資餘額增減（TWSE MI_MARGN ALL，零 key）— 需 daily_all 先做 meta
    "fetch_daytrade.py",   # 個股當沖比率（TWSE TWTB4U，零 key）— 需 daily_all 先做 meta
    "fetch_exrights.py",   # 除權息事件（上市補當月、上櫃累積快照）→ 還原價用
    "build_ohlc_window.py",  # 每日 append 今日 OHLC 進滾動視窗（種子須先手動 --seed）
    "build_ta.py",           # 從視窗算技術面指標 → data/ta.json
    "fetch_t86.py",
    "fetch_mops.py",
    "fetch_tdcc.py",
    "build_tdcc_view.py",    # 大戶級距×期間對比 → data/tdcc_view.json（吃 history_tdcc 快照）
    "fetch_fundamentals.py",
    "fetch_fin_history.py",   # 歷史季報 archive（MOPS t163sb04）— 首次須手動 --seed
    "build_fin_growth.py",    # TTM EPS 年增率／毛利率年增差 → data/fin_growth.json
    "fetch_valuation.py",   # PE/PB/市值（交易所每日公布值）
    "fetch_dividend.py",
    "fetch_news.py",
    "fetch_revenue.py",
    "build_market_trend.py",  # 大盤法人/資券近兩週趨勢（讀 history_market archive）
    "build_breadth.py",
    "build_heatmap.py",
    "build_rank.py",
    "build_inst_rank.py",
    "build_topics.py",
    "build_news_radar.py",
    "build_topic_discover.py",
    "build_changes.py",
    "build_chains.py",
    "build_flow.py",
    "build_summary.py",   # 今日一句白話摘要（純規則、讀 breadth/market/flow/heatmap）
    "build_alerts.py",    # 今日異常警示（純規則、讀 inst_rank/ta）
    "build_highlow.py",   # 逼近 52 週高/低（純規則、讀 ta pos52w）
    "build_sentiment.py", # 大盤情緒曲線（純規則、讀 history 快照收盤比對）
    "build_turnover.py",  # 成交值週轉率榜（純規則、讀 daily_all + valuation）
    "build_health.py",    # 四燈號健診卡（純規則、讀 ta/valuation/fin_growth/revenue/margin + archive）
    "render.py",
]


def main() -> int:
    here = Path(__file__).resolve().parent
    failed = []
    for s in SCRIPTS:
        print(f"── {s}")
        r = subprocess.run([sys.executable, str(here / s)])
        if r.returncode != 0:
            failed.append(s)
            print(f"[ERR] {s} exit={r.returncode}（續跑後面模組）")
    if failed:
        print(f"完成但有失敗模組: {failed}")
    else:
        print("全部模組完成")
    # render.py 失敗才算管線失敗（沒頁面=沒產品）；資料模組失敗頁面會顯示 ⚠️
    return 1 if "render.py" in failed else 0


if __name__ == "__main__":
    sys.exit(main())
