# run_all.py — P1 管線：抓資料 → 聚合 → 產頁。單一模組失敗不擋全局（render 端顯示 ⚠️）。
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "fetch_indices.py",
    "fetch_market.py",
    "fetch_daily_all.py",
    "fetch_exrights.py",   # 除權息事件（上市補當月、上櫃累積快照）→ 還原價用
    "build_ohlc_window.py",  # 每日 append 今日 OHLC 進滾動視窗（種子須先手動 --seed）
    "build_ta.py",           # 從視窗算技術面指標 → data/ta.json
    "fetch_t86.py",
    "fetch_mops.py",
    "fetch_tdcc.py",
    "fetch_fundamentals.py",
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
