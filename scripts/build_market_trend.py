# build_market_trend.py — 大盤法人/資券「近 N 日趨勢」→ data/market_trend.json
#
# 資料源：data/history_market/（官方 TWSE BFI82U + MI_MARGN 的每日快照）
#   - 每日由 fetch_market.py append 當日
#   - 歷史由 backfill_market.py 一次補齊（兩個端點都吃日期參數）
#
# 2026-07-17 決策：原本想用 history_t86（個股買賣超股數×收盤）加總估算大盤法人，
# 實測誤差過大（外資 24%、投信 50%）→ 放棄估算，一律用官方值。寧可等資料，不給假數字。
from __future__ import annotations

import json

from tw_common import DATA_DIR, write_error, write_json

MKT_DIR = DATA_DIR / "history_market"
N_DAYS = 14      # 近兩週（前端可只取尾段）


def main() -> None:
    if not MKT_DIR.exists():
        write_error("market_trend", "history_market",
                    "無歷史快照（跑 scripts/backfill_market.py 回填）")
        return

    series = []
    for f in sorted(MKT_DIR.glob("????-??-??.json")):
        try:
            series.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    if not series:
        write_error("market_trend", "history_market", "快照解析失敗")
        return

    series = series[-N_DAYS:]
    n_margin = sum(1 for s in series if s.get("margin_chg") is not None)

    write_json("market_trend", {
        "series": series,          # [{date, foreign, trust, dealer, total, margin_chg, margin_bal, short_chg, short_bal}]
        "n_days": len(series), "n_margin": n_margin,
        "note": "TWSE 官方值：法人買賣超（BFI82U，上市，億元）、"
                "融資增減（MI_MARGN，億元）。僅呈現現況，非買賣訊號。",
    }, data_date=series[-1]["date"],
        source="TWSE BFI82U + MI_MARGN（每日 archive）", error=None)
    print(f"[OK ] market_trend：{len(series)} 日（含資券 {n_margin} 日）"
          f" {series[0]['date']} ~ {series[-1]['date']}")


if __name__ == "__main__":
    main()
