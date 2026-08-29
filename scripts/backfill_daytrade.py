# backfill_daytrade.py — 回填大盤當沖比歷史（TWSE，零 API key，執行一次）
# 當沖比 = 當日沖銷成交股數(TWTB4U 加總) ÷ 大盤總成交股數(FMTQIK)。
# TWSE 端點吃任意舊日期 → 直接回填近 N 個交易日，不必等每日累積。
from __future__ import annotations

import time

from fetch_daytrade import twtb4u_cols   # 欄位定位共用一份，免得兩支各寫死一次索引
from tw_common import (http_get_json, parse_num, read_json, roc_to_iso,
                       tw_today, write_json)

FMTQIK = "https://www.twse.com.tw/exchangeReport/FMTQIK?date={ym}01&response=json"
TWTB4U = "https://www.twse.com.tw/exchangeReport/TWTB4U?date={d}&response=json&selectType=All"
MONTHS_BACK = 3                  # 往回涵蓋幾個月（大盤成交統計是月批次）
DAYS = 30                        # 最多回填交易日數


def recent_months(n: int = MONTHS_BACK) -> list[str]:
    """近 n 個月的 YYYYMM（含本月）。原本寫死 ['202606','202607']，跨月就抓不到新資料。"""
    t = tw_today()
    y, m = t.year, t.month
    out = []
    for _ in range(n):
        out.append(f"{y}{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return sorted(out)


def market_totals() -> dict:
    """{iso_date: 大盤總成交股數}，取自 FMTQIK 月報。"""
    out = {}
    for ym in recent_months():
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

    # 只補「序列裡缺的交易日」並與既有合併。
    # 原本是重抓一批就整包 write_json 蓋掉 series → 涵蓋月份外的歷史全數蒸發，
    # 而這是累積型資料（缺口永久）。WAF 擋掉某天時就是靠這支補回來。
    prev = read_json("daytrade_trend")
    have = {}
    if prev.get("ok"):
        have = {x["date"]: x for x in (prev.get("data") or {}).get("series", []) if x.get("date")}

    dates = [d for d in sorted(totals)[-DAYS:] if d not in have]
    if not dates:
        print(f"[OK ] daytrade_trend 無缺口（近 {DAYS} 交易日已齊，共 {len(have)} 天）")
        return
    print(f"[INFO] 缺 {len(dates)} 個交易日：{dates}")

    added = 0
    for iso in dates:
        dt = daytrade_shares(iso)
        tot = totals.get(iso)
        if dt and tot:
            have[iso] = {"date": iso, "ratio": round(dt / tot * 100, 1)}
            added += 1
            print(f"  {iso}  當沖比 {have[iso]['ratio']}%")
        else:
            print(f"  {iso}  略過（當沖或大盤量抓不到）")
        time.sleep(0.4)   # 對 TWSE 客氣
    if not added:
        print("[ERR] 無任何交易日算出當沖比，原檔不動")
        return

    series = [have[d] for d in sorted(have)][-120:]
    write_json("daytrade_trend", {"series": series}, data_date=series[-1]["date"],
               source="TWSE TWTB4U ÷ FMTQIK（大盤當沖比）")
    print(f"[OK ] 補 {added} 天，序列 {len(series)} 天（{series[0]['date']} ~ {series[-1]['date']}）")


if __name__ == "__main__":
    main()
