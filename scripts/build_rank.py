# build_rank.py — 日/週強勢股排行 Top20（週=近 5 交易日累積，靠 data/history 快照）
from __future__ import annotations

import json

from tw_common import DATA_DIR, read_json, write_error, write_json

TOP_N = 20
MIN_TRADE_VALUE = 100_000_000  # 排行門檻：日成交值 ≥ 1 億（略過殭屍股/易操縱小型股）
HISTORY_DIR = DATA_DIR / "history"


def save_snapshot(data_date: str, stocks: list[dict]) -> None:
    """存當日 {code: [close, value]} 快照供週排行+日期回看；同日重跑覆蓋。
    （2026-07-08 前的舊快照是 {code: close} 純量，讀取端兩種都吃。）"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    snap = {s["code"]: [s["close"], round(s["value"])] for s in stocks}
    (HISTORY_DIR / f"{data_date}.json").write_text(
        json.dumps(snap, separators=(",", ":")), encoding="utf-8")
    # 永久累積（append-only 正本，2026-07-16 起不再砍舊檔）：這是唯一保有「成交值」的逐日歷史
    # （history_ohlc 存的是成交股數）。render 只複製最近 DOCS_HISTORY_KEEP 支進 docs/，
    # 所以 archive 無限長不會脹到網站。


def snap_close(v) -> float | None:
    """快照值 → 收盤價（相容新 [close, value] 與舊純量格式）。"""
    if isinstance(v, (list, tuple)):
        return v[0] if v else None
    return v


def week_ranks(data_date: str, stocks: list[dict]) -> tuple[list, list, str | None]:
    """近 5 交易日累積漲跌。快照不足時回 (空, 空, 原因)。"""
    files = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)
    files = [f for f in files if f.stem <= data_date]
    # 基準 = 往回第 5 個交易日快照；不足 5 份就用最舊那份（標示近 N 日）
    if len(files) < 2:
        return [], [], "歷史快照不足（需累積 ≥2 個交易日）"
    base_file = files[5] if len(files) > 5 else files[-1]
    n_days = files.index(base_file)
    base = json.loads(base_file.read_text(encoding="utf-8"))
    rows = []
    for s in stocks:
        b = snap_close(base.get(s["code"]))
        if not b or b <= 0 or s["value"] < MIN_TRADE_VALUE:
            continue
        rows.append({**{k: s[k] for k in ("code", "name", "close", "value", "industry")},
                     "pct": round((s["close"] - b) / b * 100, 2)})
    rows.sort(key=lambda x: -x["pct"])
    label = f"近{n_days}日" if n_days < 5 else "週"
    return rows[:TOP_N], rows[-TOP_N:][::-1], label


def main() -> None:
    src = read_json("daily_all")
    if not src.get("ok"):
        write_error("rank", "build_rank", f"上游 daily_all 失敗: {src.get('error')}")
        return
    data_date = src.get("data_date")
    stocks = [s for s in src["data"].get("stocks", []) if s.get("industry")]  # 排除 ETF/權證

    save_snapshot(data_date, stocks)

    liquid = [s for s in stocks if s["value"] >= MIN_TRADE_VALUE]
    day_sorted = sorted(liquid, key=lambda x: -x["pct"])
    day_up = day_sorted[:TOP_N]
    day_down = day_sorted[-TOP_N:][::-1]

    wk_up, wk_down, wk_label = week_ranks(data_date, stocks)

    def slim(rows):
        return [{k: r[k] for k in ("code", "name", "close", "pct", "value", "industry")} for r in rows]

    write_json("rank", {
        "day_up": slim(day_up), "day_down": slim(day_down),
        "week_up": slim(wk_up), "week_down": slim(wk_down),
        "week_label": wk_label,
        "min_trade_value": MIN_TRADE_VALUE,
    }, data_date=data_date, source=src.get("source"), error=src.get("error"))


if __name__ == "__main__":
    main()
