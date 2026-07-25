# fetch_margin.py — 個股融資餘額增減（TWSE MI_MARGN selectType=ALL，零 API key）
# 同一 TWSE 公開端點（fetch_market 用 MS 彙總；這裡用 ALL 取個股）→ data/margin.json
# 融資增減(張) = 今日餘額 − 前日餘額。僅上市（TPEx 上櫃為另一端點，暫不含）。
from __future__ import annotations

from tw_common import (http_get_json, parse_num, read_json, write_error,
                       write_json, ymd_to_iso)

MARGN_ALL_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?selectType=ALL&response=json"
TOP = 30
MIN_BAL = 500   # 今日餘額 ≥500 張才列，濾極小融資標的雜訊


def main() -> None:
    j = http_get_json(MARGN_ALL_URL, timeout=60)
    if not j or j.get("stat") != "OK":
        write_error("margin", "TWSE MI_MARGN ALL", f"回應非 OK: {(j or {}).get('stat')}")
        return

    # 找個股表：fields 含「代號」的那張（通常 rows ~1200+）
    table = None
    for t in j.get("tables", []):
        fields = t.get("fields") or []
        if fields and fields[0] == "代號" and len(t.get("data") or []) > 100:
            table = t
            break
    if not table:
        write_error("margin", "TWSE MI_MARGN ALL", "找不到個股融資融券表")
        return

    daily = read_json("daily_all")
    meta = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            meta[s["code"]] = s

    stocks = {}
    for row in table["data"]:
        code = (row[0] or "").strip()
        if len(code) != 4 or not code.isdigit():
            continue
        prev = parse_num(row[5])      # 融資前日餘額（張）
        today = parse_num(row[6])     # 融資今日餘額（張）
        if prev is None or today is None:
            continue
        chg = today - prev
        m = meta.get(code, {})
        stocks[code] = {"name": (row[1] or "").strip() or code, "bal": int(today),
                        "chg": int(chg), "pct": m.get("pct"), "close": m.get("close"),
                        "industry": m.get("industry") or ""}

    if not stocks:
        write_error("margin", "TWSE MI_MARGN ALL", "解析後無個股資料")
        return

    rated = [v | {"code": c} for c, v in stocks.items() if v["bal"] >= MIN_BAL]
    inc = sorted(rated, key=lambda x: x["chg"], reverse=True)[:TOP]
    dec = sorted(rated, key=lambda x: x["chg"])[:TOP]

    date_iso = ymd_to_iso(str(j.get("date"))) or (daily.get("data_date"))
    write_json("margin", {"inc": inc, "dec": dec, "n": len(stocks), "min_bal": MIN_BAL},
               data_date=date_iso, source="TWSE MI_MARGN（個股融資餘額，上市）")


if __name__ == "__main__":
    main()
