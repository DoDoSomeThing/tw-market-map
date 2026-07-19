# build_inst_rank.py — 法人個股動向：外資/投信 買超賣超 Top15 + 連買/連賣天數
# 金額=買賣超股數×收盤價（估算）。連買僅描述現況（外資連買當訊號已驗證無 alpha）。
from __future__ import annotations

import json

from tw_common import DATA_DIR, read_json, write_error, write_json

TOP_N = 15
HISTORY_DIR = DATA_DIR / "history_t86"
MIN_NET_VALUE = 50_000_000  # 買賣超估值 < 5 千萬不入榜（雜訊）


def streak(vals: list[float]) -> int:
    """從最新往回數同向天數（kanpan inst._streak 思路）。正=連買、負=連賣。"""
    if not vals or not vals[0]:
        return 0
    sign = 1 if vals[0] > 0 else -1
    n = 0
    for v in vals:
        if v and (v > 0) == (sign > 0):
            n += 1
        else:
            break
    return n * sign


def load_streaks(data_date: str) -> dict[str, tuple[int, int]]:
    """{code: (外資streak, 投信streak)}。快照由 fetch_t86 逐日累積。"""
    files = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)
    files = [f for f in files if f.stem <= data_date]
    snaps = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    if not snaps:
        return {}
    out = {}
    for code in snaps[0]:
        fs = [s.get(code, [0, 0])[0] for s in snaps]
        ts = [s.get(code, [0, 0])[1] for s in snaps]
        out[code] = (streak(fs), streak(ts))
    return out


def main() -> None:
    t86 = read_json("t86")
    daily = read_json("daily_all")
    if not t86.get("ok"):
        write_error("inst_rank", "build_inst_rank", f"上游 t86 失敗: {t86.get('error')}")
        return

    closes = {}
    industries = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            closes[s["code"]] = s["close"]
            industries[s["code"]] = s.get("industry")

    streaks = load_streaks(t86.get("data_date") or "9999-99-99")

    rows = []
    for code, v in t86["data"]["stocks"].items():
        close = closes.get(code)
        if close is None or industries.get(code) is None:
            continue  # 只排有產業分類的個股（排除 ETF/權證）
        sf, st = streaks.get(code, (0, 0))
        rows.append({
            "code": code, "name": v["name"], "close": close,
            "industry": industries.get(code),
            "f_lots": round(v["f"] / 1000), "t_lots": round(v["t"] / 1000),
            "f_value": v["f"] * close, "t_value": v["t"] * close,
            "f_streak": sf, "t_streak": st,
        })

    def top(key: str, reverse: bool) -> list:
        xs = [r for r in rows if abs(r[key]) >= MIN_NET_VALUE]
        xs.sort(key=lambda r: r[key], reverse=reverse)
        pick = [r for r in xs if (r[key] > 0) == reverse][:TOP_N]
        return [{k: r[k] for k in ("code", "name", "close", "industry",
                                    "f_lots", "t_lots", "f_value", "t_value",
                                    "f_streak", "t_streak")} for r in pick]

    def co(buy: bool) -> list:
        """土洋共識:外資與投信同日同向。依兩者估值合計排序(門檻沿用 MIN_NET_VALUE)。"""
        xs = [r for r in rows
              if (r["f_value"] > 0) == buy and (r["t_value"] > 0) == buy
              and r["f_value"] != 0 and r["t_value"] != 0
              and abs(r["f_value"]) + abs(r["t_value"]) >= MIN_NET_VALUE]
        xs.sort(key=lambda r: abs(r["f_value"]) + abs(r["t_value"]), reverse=True)
        return [{k: r[k] for k in ("code", "name", "close", "industry",
                                    "f_lots", "t_lots", "f_value", "t_value",
                                    "f_streak", "t_streak")} for r in xs[:TOP_N]]

    write_json("inst_rank", {
        "foreign_buy": top("f_value", True),
        "foreign_sell": top("f_value", False),
        "trust_buy": top("t_value", True),
        "trust_sell": top("t_value", False),
        "co_buy": co(True),
        "co_sell": co(False),
        "n_history_days": len(list(HISTORY_DIR.glob("????-??-??.json"))),
    }, data_date=t86.get("data_date"), source=t86.get("source"), error=t86.get("error"))


if __name__ == "__main__":
    main()
