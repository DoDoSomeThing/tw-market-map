# fetch_daytrade.py — 個股當沖比率（TWSE TWTB4U 當日沖銷交易，零 API key）
# 當沖比 = 當日沖銷交易成交股數 ÷ 該股總成交股數。高＝隔日沖/投機熱。
# 僅上市（TPEx 為另一端點，暫不含）→ data/daytrade.json。
from __future__ import annotations

from tw_common import (http_get_json, parse_num, read_json, tw_today,
                       write_error, write_json, ymd_to_iso)

TWTB4U_URL = "https://www.twse.com.tw/exchangeReport/TWTB4U?date={d}&response=json&selectType=All"
TOP = 30
MIN_VALUE = 0.5e8   # 成交值 ≥ 5000 萬


def main() -> None:
    daily = read_json("daily_all")
    # 用 daily 的資料日對齊；抓不到就用今天
    dd = (daily.get("data_date") or "").replace("-", "") or tw_today().strftime("%Y%m%d")
    j = http_get_json(TWTB4U_URL.format(d=dd), timeout=60)
    if not j or j.get("stat") != "OK":
        write_error("daytrade", "TWSE TWTB4U", f"回應非 OK: {(j or {}).get('stat')}")
        return

    table = None
    for t in j.get("tables", []):
        fields = t.get("fields") or []
        if fields and fields[0] == "證券代號" and len(t.get("data") or []) > 100:
            table = t
            break
    if not table:
        write_error("daytrade", "TWSE TWTB4U", "找不到當沖交易表")
        return

    meta = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            meta[s["code"]] = s

    rows = []
    for row in table["data"]:
        code = (row[0] or "").strip()
        m = meta.get(code)
        if len(code) != 4 or not code.isdigit() or not m:
            continue
        dt_shares = parse_num(row[3])       # 當沖成交股數
        vol = m.get("value") and m.get("vol")
        if not dt_shares or not vol or vol <= 0:
            continue
        if (m.get("value") or 0) < MIN_VALUE:
            continue
        ratio = min(dt_shares / vol * 100, 100)   # 當沖比%
        rows.append({"code": code, "name": (row[1] or "").strip() or code,
                     "industry": m.get("industry") or "", "pct": m.get("pct"),
                     "close": m.get("close"), "ratio": round(ratio, 1),
                     "value": round((m.get("value") or 0) / 1e8, 1)})

    if not rows:
        write_error("daytrade", "TWSE TWTB4U", "解析後無當沖資料")
        return

    rows.sort(key=lambda x: x["ratio"], reverse=True)
    write_json("daytrade", {"list": rows[:TOP], "min_value": MIN_VALUE},
               data_date=ymd_to_iso(str(j.get("date"))) or daily.get("data_date"),
               source="TWSE TWTB4U（當日沖銷交易，上市）")


if __name__ == "__main__":
    main()
