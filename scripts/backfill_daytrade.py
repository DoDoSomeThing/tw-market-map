# backfill_daytrade.py — 回填大盤當沖比歷史（TWSE，零 API key，執行一次）
# 當沖比 = 當日沖銷成交股數(TWTB4U 加總) ÷ 大盤總成交股數(FMTQIK)。
# TWSE 端點吃任意舊日期 → 直接回填近 N 個交易日，不必等每日累積。
from __future__ import annotations

import time

from fetch_daytrade import twtb4u_cols   # 欄位定位共用一份，免得兩支各寫死一次索引
from tw_common import http_get_json, parse_num, roc_to_iso, write_json

FMTQIK = "https://www.twse.com.tw/exchangeReport/FMTQIK?date={ym}01&response=json"
TWTB4U = "https://www.twse.com.tw/exchangeReport/TWTB4U?date={d}&response=json&selectType=All"
MONTHS = ["202606", "202607"]   # 回填涵蓋月份（大盤成交統計月批次）
DAYS = 30                        # 最多回填交易日數


def market_totals() -> dict:
    """{iso_date: 大盤總成交股數}，取自 FMTQIK 月報。"""
    out = {}
    for ym in MONTHS:
        j = http_get_json(FMTQIK.format(ym=ym), timeout=40)
        if not j or j.get("stat") != "OK":
            continue
        for r in j.get("data", []):
            iso = roc_to_iso(r[0])
            shares = parse_num(r[1])
            if iso and shares:
                out[iso] = shares
    return out


def daytrade_shares(iso: str) -> float | None:
    """某交易日全市場當沖成交股數加總（TWTB4U）。"""
    j = http_get_json(TWTB4U.format(d=iso.replace("-", "")), timeout=60)
    if not j or j.get("stat") != "OK":
        return None
    total = 0.0
    for t in j.get("tables", []):
        fields = t.get("fields") or [""]
        if fields[0] != "證券代號":
            continue
        _, i_shares = twtb4u_cols(fields)
        if i_shares is None:
            continue
        for row in t.get("data", []):
            if len(row) <= i_shares:
                continue
            v = parse_num(row[i_shares])
            if v:
                total += v
    return total or None


def main() -> None:
    totals = market_totals()
    if not totals:
        print("[ERR] FMTQIK 無資料，放棄回填")
        return
    dates = sorted(totals)[-DAYS:]
    series = []
    for iso in dates:
        dt = daytrade_shares(iso)
        tot = totals.get(iso)
        if dt and tot:
            series.append({"date": iso, "ratio": round(dt / tot * 100, 1)})
            print(f"  {iso}  當沖比 {series[-1]['ratio']}%")
        time.sleep(0.4)   # 對 TWSE 客氣
    if not series:
        print("[ERR] 無任何交易日算出當沖比")
        return
    write_json("daytrade_trend", {"series": series}, data_date=series[-1]["date"],
               source="TWSE TWTB4U ÷ FMTQIK（大盤當沖比）")


if __name__ == "__main__":
    main()
