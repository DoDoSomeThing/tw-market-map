# build_breadth.py — 市場寬度/情緒（從 daily_all 聚合，零新資料源）
# 上漲/下跌/平盤家數、漲停/跌停數、上漲成交值占比 → regime 儀表。
from __future__ import annotations

from tw_common import read_json, write_error, write_json

LIMIT_PCT = 9.8   # 漲跌停近似判定（一般股 ±10%；處置/全額交割 5% 會少算，屬近似）


def main() -> None:
    src = read_json("daily_all")
    if not src.get("ok"):
        write_error("breadth", "build_breadth", f"上游 daily_all 失敗: {src.get('error')}")
        return

    # 只算 4 碼個股（含 ETF 會稀釋情緒；權證/牛熊證噪音大）且有產業別 = 一般股
    stocks = [s for s in src["data"].get("stocks", [])
              if len(s["code"]) == 4 and s["code"].isdigit() and s.get("industry")]

    up = down = flat = limit_up = limit_down = 0
    up_value = total_value = 0.0
    for s in stocks:
        pct, val = s["pct"], s["value"] or 0.0
        total_value += val
        if pct > 0:
            up += 1
            up_value += val
            if pct >= LIMIT_PCT:
                limit_up += 1
        elif pct < 0:
            down += 1
            if pct <= -LIMIT_PCT:
                limit_down += 1
        else:
            flat += 1

    n = up + down + flat

    # 逐股清單：供「每日焦點」大盤異動點開列出實際個股（前端用 code 進個股面板）
    def row(s: dict) -> dict:
        return {"code": s["code"], "name": s["name"], "pct": s["pct"], "close": s["close"]}

    by_pct_desc = sorted(stocks, key=lambda s: s["pct"], reverse=True)
    lists = {
        "limit_up": [row(s) for s in by_pct_desc if s["pct"] >= LIMIT_PCT],
        "limit_down": [row(s) for s in reversed(by_pct_desc) if s["pct"] <= -LIMIT_PCT],
        "top_up": [row(s) for s in by_pct_desc[:30]],
        "top_down": [row(s) for s in by_pct_desc[::-1][:30]],
    }

    write_json("breadth", {
        "up": up, "down": down, "flat": flat, "n": n,
        "limit_up": limit_up, "limit_down": limit_down,
        "up_value_pct": round(up_value / total_value * 100, 1) if total_value else None,
        "note": "個股（含產業別、不含 ETF/權證）；漲跌停為 ±9.8% 近似判定",
        "lists": lists,
    }, data_date=src.get("data_date"), source="daily_all 聚合", error=src.get("error"))


if __name__ == "__main__":
    main()
