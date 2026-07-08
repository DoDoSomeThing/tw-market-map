# fetch_market.py — TWSE 三大法人 BFI82U（上市）+ TPEx 法人彙總（上櫃）+ 資券 MI_MARGN
from __future__ import annotations

from datetime import date, timedelta

from tw_common import (data_age_days, http_get_json, parse_num, read_json, roc_to_iso,
                       write_error, write_json, ymd_to_iso)

BFI82U_URL = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json"
MARGN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?selectType=MS&response=json"
TPEX_INST_URL = "https://www.tpex.org.tw/www/zh-tw/insti/summary?type=Daily&date={d}&response=json"

# BFI82U 單位名稱 → 標準 key
INST_KEYS = {
    "自營商(自行買賣)": "dealer_self",
    "自營商(避險)": "dealer_hedge",
    "投信": "trust",
    "外資及陸資(不含外資自營商)": "foreign",
    "合計": "total",
}


def fetch_twse_inst() -> dict | None:
    j = http_get_json(BFI82U_URL)
    if j.get("stat") != "OK":
        return None
    rows = {}
    for name, buy, sell, diff in j.get("data", []):
        key = INST_KEYS.get(name.strip())
        if key:
            rows[key] = {"buy": parse_num(buy), "sell": parse_num(sell), "net": parse_num(diff)}
    if "total" not in rows:
        return None
    return {"date": ymd_to_iso(j.get("date")), "rows": rows}


def fetch_tpex_inst() -> dict | None:
    """上櫃三大法人買賣金額彙總。往回試 5 個日曆日（假日無資料）。失敗回 None。"""
    for back in range(6):
        d = date.today() - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        url = TPEX_INST_URL.format(d=d.strftime("%Y/%m/%d"))
        try:
            j = http_get_json(url)
        except Exception:
            continue
        tables = j.get("tables") or []
        if not tables or not tables[0].get("data"):
            continue
        t = tables[0]
        rows = {}
        for row in t["data"]:
            name = str(row[0]).strip()
            rec = {"buy": parse_num(row[1]), "sell": parse_num(row[2]), "net": parse_num(row[3])}
            if name == "外資及陸資合計":
                rows["foreign"] = rec
            elif name == "投信":
                rows["trust"] = rec
            elif name == "自營商合計":
                rows["dealer"] = rec
            elif name in ("合計", "總計"):
                rows["total"] = rec
        if rows:
            return {"date": roc_to_iso(t.get("date", "")) or d.isoformat(), "rows": rows}
    return None


def fetch_margin() -> dict | None:
    """信用交易統計（上市整體）。TWSE 註明餘額以「前日餘額」為準。
    rwd 端點對 GitHub Actions 偶爾很慢（2026-07-08 三次 30s 全逾時）→ timeout 拉 60。"""
    j = http_get_json(MARGN_URL, timeout=60)
    if j.get("stat") != "OK":
        return None
    table = None
    for t in j.get("tables", []):
        if "信用交易統計" in t.get("title", ""):
            table = t
            break
    if not table:
        return None
    out = {}
    for row in table.get("data", []):
        item = str(row[0])
        rec = {"buy": parse_num(row[1]), "sell": parse_num(row[2]),
               "redeem": parse_num(row[3]), "prev_bal": parse_num(row[4]),
               "today_bal": parse_num(row[5])}
        if item.startswith("融資金額"):
            out["margin_value"] = rec  # 仟元
        elif item.startswith("融資"):
            out["margin_units"] = rec
        elif item.startswith("融券"):
            out["short_units"] = rec
    if "margin_value" not in out:
        return None
    return {"date": ymd_to_iso(j.get("date")), "rows": out}


def main() -> None:
    try:
        twse = fetch_twse_inst()
        twse_err = None if twse else "BFI82U 回應非 OK"
    except Exception as e:
        twse = None
        twse_err = str(e)

    tpex = fetch_tpex_inst()  # 允許失敗（上櫃區顯示 ⚠️）

    try:
        margin = fetch_margin()
        margin_err = None if margin else "MI_MARGN 無信用交易統計表"
    except Exception as e:
        margin = None
        margin_err = str(e)

    if margin is None:
        # 沿用前次資券（≤2 交易日），render 端用 margin.date 標舊資料日,不裝新鮮
        prev = read_json("market")
        prev_margin = (prev.get("data") or {}).get("margin") if prev.get("ok") else None
        if prev_margin and data_age_days(prev_margin.get("date", "")) is not None \
                and data_age_days(prev_margin["date"]) <= 2:
            margin = prev_margin
            margin_err = f"本次抓取失敗，沿用 {prev_margin['date']} 資料（{margin_err}）"

    if not twse and not margin:
        write_error("market", "TWSE BFI82U+MI_MARGN",
                    f"法人:{twse_err}；資券:{margin_err}")
        return

    errs = [x for x in (
        f"上市法人:{twse_err}" if twse_err else None,
        "上櫃法人:抓取失敗" if tpex is None else None,
        f"資券:{margin_err}" if margin_err else None,
    ) if x]
    date_ = (twse or {}).get("date") or (margin or {}).get("date")
    write_json("market", {
        "inst_twse": twse,
        "inst_tpex": tpex,
        "margin": margin,
    }, data_date=date_, source="TWSE BFI82U/MI_MARGN + TPEx insti/summary",
        error="；".join(errs) or None)


if __name__ == "__main__":
    main()
