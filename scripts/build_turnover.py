# build_turnover.py — 成交值週轉率榜（純規則、零新資料源、零 API）
# 週轉率 = 當日成交值 ÷ 市值。高週轉＝資金換手熱、投機度高。
# 讀 daily_all(成交值) + valuation(市值) → data/turnover.json。
from __future__ import annotations

from tw_common import read_json, write_error, write_json

MIN_VALUE = 0.5e8   # 成交值 ≥ 5000 萬，濾冷門股
CAP = 30


def main() -> None:
    daily = read_json("daily_all")
    val = read_json("valuation")
    if not daily.get("ok"):
        write_error("turnover", "build_turnover", f"上游 daily_all 失敗: {daily.get('error')}")
        return

    caps = val["data"].get("stocks", {}) if val.get("ok") else {}
    rows = []
    for s in daily["data"].get("stocks", []):
        c = s["code"]
        if len(c) != 4 or not c.isdigit() or not s.get("industry"):
            continue
        value = s.get("value") or 0
        cap = (caps.get(c) or {}).get("cap")   # 市值（億）
        if value < MIN_VALUE or not cap or cap <= 0:
            continue
        turnover = value / (cap * 1e8) * 100    # %
        rows.append({"code": c, "name": s.get("name") or c,
                     "industry": s.get("industry") or "", "pct": s.get("pct"),
                     "close": s.get("close"), "turnover": round(turnover, 2),
                     "value": round(value / 1e8, 1), "cap": cap})

    rows.sort(key=lambda x: x["turnover"], reverse=True)
    write_json("turnover", {"list": rows[:CAP], "min_value": MIN_VALUE},
               data_date=daily.get("data_date"), source="規則彙整（daily_all 成交值 ÷ valuation 市值）")


if __name__ == "__main__":
    main()
