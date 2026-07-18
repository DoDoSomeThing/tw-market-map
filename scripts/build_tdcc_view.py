# build_tdcc_view.py — 集保大戶「級距 × 期間」對比 → data/tdcc_view.json
# 讀 data/history_tdcc/ 最近 5 支週快照（1/2/3/4 週對比需要 5 支），產出:
#   dates:  快照週次（舊→新）
#   series: {code: 5週 × [r200,r400,r800,r1000]}（個股面板畫趨勢用;缺值 null）
#   rank:   {級距}{期間週數} → 加碼/減碼 Top15（沿用 fetch_tdcc 的成交值門檻）
# 檔案 ~400KB → render 複製到 docs/ 後由前端 lazy fetch（比照 ta.json,不內嵌）。
#
# 快照兩種格式並存（2026-07-18 之前是 2 欄）:
#   [r400, r1000]                → r200/r800 補 null,該級距的期間對比自動缺格
#   [r200, r400, r800, r1000]   → 全級距可用
from __future__ import annotations

import json

from tw_common import DATA_DIR, read_json, write_json

HISTORY_DIR = DATA_DIR / "history_tdcc"
N_SNAPS = 5
TOP_N = 15
MIN_TRADE_VALUE = 5e7          # 與 fetch_tdcc 一致:日成交值 ≥ 5 千萬才進排行
TIERS = ["r200", "r400", "r800", "r1000"]


def norm(p: list) -> list[float | None]:
    """任一格式快照列 → [r200, r400, r800, r1000](缺值 None)。"""
    if len(p) >= 4:
        return [p[0], p[1], p[2], p[3]]
    return [None, p[0], None, p[1]]


def main() -> None:
    files = sorted(HISTORY_DIR.glob("????-??-??.json"))[-N_SNAPS:]
    if len(files) < 2:
        write_json("tdcc_view", {"dates": [], "series": {}, "rank": {}},
                   data_date=None, source="TDCC 週快照（級距×期間對比）",
                   error=f"快照不足（{len(files)} 支,需 ≥2）")
        return

    snaps = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    dates = [f.stem for f in files]
    latest = snaps[-1]

    info = {}
    env = read_json("daily_all")
    if env.get("ok"):
        info = {s["code"]: s for s in env["data"].get("stocks", [])}

    series = {}
    for code in latest:
        row = []
        for snap in snaps:
            p = snap.get(code)
            row.append(norm(p) if p else [None] * 4)
        series[code] = row

    # rank[級距][週數] = {"inc": [...], "dec": [...]}
    rank: dict[str, dict[str, dict]] = {}
    for ti, tier in enumerate(TIERS):
        rank[tier] = {}
        for wk in range(1, len(snaps)):
            base = snaps[-1 - wk]
            movers = []
            for code, p in latest.items():
                b = base.get(code)
                if not b:
                    continue
                cur, old = norm(p)[ti], norm(b)[ti]
                if cur is None or old is None:
                    continue
                s = info.get(code)
                if not s or (s.get("value") or 0) < MIN_TRADE_VALUE:
                    continue
                delta = round(cur - old, 2)
                if delta:
                    movers.append({"code": code, "name": s.get("name") or "",
                                   "industry": s.get("industry"), "close": s.get("close"),
                                   "cur": cur, "delta": delta})
            movers.sort(key=lambda m: m["delta"], reverse=True)
            rank[tier][str(wk)] = {
                "base": dates[-1 - wk],
                "inc": [m for m in movers if m["delta"] > 0][:TOP_N],
                "dec": [m for m in movers if m["delta"] < 0][::-1][:TOP_N],
            }

    write_json("tdcc_view", {
        "dates": dates, "series": series, "rank": rank,
        "tiers": TIERS, "min_trade_value": MIN_TRADE_VALUE,
    }, data_date=dates[-1], source="TDCC 週快照（級距×期間對比）", error=None)


if __name__ == "__main__":
    main()
