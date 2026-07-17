# fetch_market.py — TWSE 三大法人 BFI82U（上市）+ TPEx 法人彙總（上櫃）+ 資券 MI_MARGN
from __future__ import annotations

from datetime import date, timedelta

import json

from tw_common import (DATA_DIR, data_age_days, http_get_json, parse_num, read_json, roc_to_iso, tw_today, write_error, write_json, ymd_to_iso)

# 永久 archive（append-only，2026-07-17 起）：每日大盤法人/資券精簡快照。
# 目的：畫「近兩週三大法人買賣超 / 融資增減」趨勢柱狀圖——原本 market.json 每天覆蓋、
# 無歷史可畫。~200 bytes/天，可忽略。
ARCHIVE_DIR = DATA_DIR / "history_market"


def _yi(v):
    """元 → 億（BFI82U 給的是元）；None 照回 None。"""
    return round(v / 1e8, 1) if v is not None else None

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
        d = tw_today() - timedelta(days=back)
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

    # ── 永久 archive（append-only，2026-07-17 起）──
    # market.json 原本每天被覆蓋、沒有歷史 → 畫不出「近兩週法人買賣超/融資增減趨勢」。
    # 存精簡快照（僅趨勢圖需要的欄位，~200 bytes/天）→ build_market_trend 讀它畫圖。
    # 資券沿用前次時不存（避免同一天資料重複計入趨勢）。
    if date_:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        rows = (twse or {}).get("rows", {})
        snap = {
            "date": date_,
            # 億元；外資/投信/自營(自行+避險)/合計 買賣超
            "foreign": _yi(rows.get("foreign", {}).get("net")),
            "trust": _yi(rows.get("trust", {}).get("net")),
            "dealer": _yi((rows.get("dealer_self", {}).get("net") or 0)
                          + (rows.get("dealer_hedge", {}).get("net") or 0))
                      if rows.get("dealer_self") else None,
            "total": _yi(rows.get("total", {}).get("net")),
        }
        m = margin or {}
        if m.get("date") == date_:   # 只存當日真實抓到的資券（沿用的舊值不進趨勢）
            mv = m.get("rows", {}).get("margin_value", {})
            su = m.get("rows", {}).get("short_units", {})
            snap["margin_chg"] = (round((mv["today_bal"] - mv["prev_bal"]) / 1e5, 1)
                                  if mv.get("today_bal") is not None and mv.get("prev_bal") is not None else None)
            snap["margin_bal"] = round(mv["today_bal"] / 1e5, 1) if mv.get("today_bal") is not None else None
            snap["short_chg"] = (su["today_bal"] - su["prev_bal"]
                                 if su.get("today_bal") is not None and su.get("prev_bal") is not None else None)
            snap["short_bal"] = su.get("today_bal")
        (ARCHIVE_DIR / f"{date_}.json").write_text(
            json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[OK ] archive: history_market/{date_}.json")

    write_json("market", {
        "inst_twse": twse,
        "inst_tpex": tpex,
        "margin": margin,
    }, data_date=date_, source="TWSE BFI82U/MI_MARGN + TPEx insti/summary",
        error="；".join(errs) or None)


if __name__ == "__main__":
    main()
