# build_highlow.py — 創 52 週新高/新低清單（純規則、零 API）
# 讀 ta(pos52w) + daily_all(名稱/漲跌/成交值) → data/highlow.json
# pos52w = (收盤−52週低)/(52週高−52週低)，取最近 252 個交易日；≥0.95 近高、≤0.05 近低。
# 上市未滿 120 個交易日的個股 ta 不給 pos52w（區間太短，稱不上 52 週）→ 自然不會進榜。
from __future__ import annotations

from tw_common import read_json, write_error, write_json

HIGH_TH = 0.95      # pos52w ≥ 0.95 → 逼近 52 週高（=1.0 為當日創新高）
LOW_TH = 0.05       # pos52w ≤ 0.05 → 逼近 52 週低（=0.0 為當日創新低）
MIN_VALUE = 0.3e8   # 成交值 ≥ 3000 萬，濾冷門股雜訊
CAP = 30


def main() -> None:
    ta = read_json("ta")
    daily = read_json("daily_all")
    if not ta.get("ok"):
        write_error("highlow", "build_highlow", f"上游 ta 失敗: {ta.get('error')}")
        return

    meta = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            c = s["code"]
            if len(c) == 4 and c.isdigit() and s.get("industry"):
                meta[c] = s

    stocks = ta["data"].get("stocks", {})
    high, low = [], []
    for code, t in stocks.items():
        p = t.get("pos52w")
        m = meta.get(code)
        if p is None or not m:
            continue
        if (m.get("value") or 0) < MIN_VALUE:
            continue
        item = {"code": code, "name": m.get("name") or code,
                "industry": m.get("industry") or "", "pct": m.get("pct"),
                "close": m.get("close"), "pos": round(p * 100, 1),
                "value": round((m.get("value") or 0) / 1e8, 1)}
        if p >= HIGH_TH:
            high.append(item)
        elif p <= LOW_TH:
            low.append(item)

    high.sort(key=lambda x: x["value"], reverse=True)
    low.sort(key=lambda x: x["value"], reverse=True)

    write_json("highlow", {"high": high[:CAP], "low": low[:CAP],
               "thresholds": {"high": HIGH_TH, "low": LOW_TH}},
               data_date=ta.get("data_date"), source="規則彙整（ta pos52w）")


if __name__ == "__main__":
    main()
