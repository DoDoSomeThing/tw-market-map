#!/usr/bin/env python3
"""backfill_market.py — 回填大盤法人/資券歷史（官方值）→ data/history_market/

緣起（2026-07-17）：想畫「近兩週三大法人買賣超／融資增減」趨勢圖，但 market.json
每天覆蓋、無歷史。原本打算用 history_t86 加總估算回填，實測誤差過大（外資 24%、
投信 50%）→ 放棄。改用 TWSE 端點的日期參數直接取官方歷史：

  BFI82U   ?dayDate=YYYYMMDD&type=day   → 三大法人買賣超（元）
  MI_MARGN ?date=YYYYMMDD&selectType=MS → 信用交易統計（融資仟元／融券交易單位）

用法：
  python scripts/backfill_market.py            # 回填近 30 個日曆日
  python scripts/backfill_market.py --days 90  # 回填更長
同日已有快照預設跳過（--force 覆寫）。TWSE 對雲端會限速 → 內建間隔，勿縮短。
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta

from tw_common import DATA_DIR, http_get_json, parse_num, tw_today, ymd_to_iso

ARCHIVE_DIR = DATA_DIR / "history_market"
BFI_URL = "https://www.twse.com.tw/rwd/zh/fund/BFI82U?dayDate={d8}&type=day&response=json"
MARGN_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={d8}&selectType=MS&response=json"

INST_KEYS = {
    "自營商(自行買賣)": "dealer_self",
    "自營商(避險)": "dealer_hedge",
    "投信": "trust",
    "外資及陸資(不含外資自營商)": "foreign",
    "合計": "total",
}


def _yi(v):
    return round(v / 1e8, 1) if v is not None else None


def fetch_inst(d8: str) -> dict | None:
    j = http_get_json(BFI_URL.format(d8=d8), timeout=45)
    if j.get("stat") != "OK" or not j.get("data"):
        return None
    if ymd_to_iso(str(j.get("date", ""))) != ymd_to_iso(d8):
        return None                      # 非交易日時 TWSE 會回最近一日 → 丟棄
    rows = {}
    for name, _buy, _sell, diff in j["data"]:
        k = INST_KEYS.get(name.strip())
        if k:
            rows[k] = parse_num(diff)
    if "total" not in rows:
        return None
    dealer = None
    if rows.get("dealer_self") is not None or rows.get("dealer_hedge") is not None:
        dealer = (rows.get("dealer_self") or 0) + (rows.get("dealer_hedge") or 0)
    return {"foreign": _yi(rows.get("foreign")), "trust": _yi(rows.get("trust")),
            "dealer": _yi(dealer), "total": _yi(rows.get("total"))}


def fetch_margin(d8: str) -> dict:
    try:
        j = http_get_json(MARGN_URL.format(d8=d8), timeout=45)
    except Exception:
        return {}
    if j.get("stat") != "OK" or ymd_to_iso(str(j.get("date", ""))) != ymd_to_iso(d8):
        return {}
    tbl = next((t for t in j.get("tables", []) if "信用交易統計" in t.get("title", "")), None)
    if not tbl:
        return {}
    out = {}
    for r in tbl.get("data", []):
        item = str(r[0])
        prev, today = parse_num(r[4]), parse_num(r[5])
        if prev is None or today is None:
            continue
        if item.startswith("融資金額"):          # 仟元 → 億
            out["margin_chg"] = round((today - prev) / 1e5, 1)
            out["margin_bal"] = round(today / 1e5, 1)
        elif item.startswith("融券"):            # 交易單位（張）
            out["short_chg"] = round(today - prev)
            out["short_bal"] = round(today)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="往回幾個日曆日")
    ap.add_argument("--force", action="store_true", help="已存在也重抓")
    args = ap.parse_args()

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = tw_today()
    ok = skip = miss = 0
    for i in range(args.days):
        d = today - timedelta(days=i)
        if d.weekday() >= 5:
            continue
        iso, d8 = d.isoformat(), d.strftime("%Y%m%d")
        p = ARCHIVE_DIR / f"{iso}.json"
        if p.exists() and not args.force:
            skip += 1
            continue
        try:
            inst = fetch_inst(d8)
        except Exception as e:
            print(f"  {iso} 例外：{e}")
            inst = None
        if not inst:
            miss += 1
            print(f"  {iso} 無資料（非交易日/未公布）")
            continue
        snap = {"date": iso, **inst, **fetch_margin(d8)}
        p.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        ok += 1
        print(f"  {iso} ✓ 外資 {snap['foreign']:>7.1f}億  投信 {snap['trust']:>6.1f}億"
              f"  融資增減 {snap.get('margin_chg', '—')}")
    print(f"\n回填完成：新增 {ok} 日、已存在跳過 {skip} 日、無資料 {miss} 日")


if __name__ == "__main__":
    main()
