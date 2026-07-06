# build_heatmap.py — daily_all → treemap 資料（依產業聚合；區塊大小=成交值、顏色=漲跌%）
from __future__ import annotations

from tw_common import read_json, write_error, write_json

MAX_STOCKS_PER_INDUSTRY = 25   # 每產業最多呈現檔數（其餘併入產業統計但不畫格）
MIN_TRADE_VALUE = 30_000_000   # 個股低於 3 千萬成交值不畫格（避免殭屍股塞版面）


def main() -> None:
    src = read_json("daily_all")
    if not src.get("ok"):
        write_error("heatmap", "build_heatmap", f"上游 daily_all 失敗: {src.get('error')}")
        return

    stocks = src["data"].get("stocks", [])
    groups: dict[str, dict] = {}
    for s in stocks:
        ind = s.get("industry")
        if not ind:
            continue  # ETF/權證/未分類不進熱力圖
        g = groups.setdefault(ind, {"industry": ind, "value": 0.0, "wsum": 0.0, "stocks": []})
        g["value"] += s["value"]
        g["wsum"] += s["pct"] * s["value"]
        g["stocks"].append(s)

    out_groups = []
    for g in groups.values():
        if g["value"] <= 0:
            continue
        cells = sorted(g["stocks"], key=lambda x: -x["value"])
        shown = [x for x in cells[:MAX_STOCKS_PER_INDUSTRY] if x["value"] >= MIN_TRADE_VALUE]
        out_groups.append({
            "industry": g["industry"],
            "value": g["value"],
            "avg_pct": round(g["wsum"] / g["value"], 2),  # 成交值加權平均漲跌
            "n_stocks": len(g["stocks"]),
            "cells": [{"code": x["code"], "name": x["name"], "pct": x["pct"],
                       "value": x["value"], "close": x["close"]} for x in shown],
        })
    out_groups.sort(key=lambda x: -x["value"])

    write_json("heatmap", {"groups": out_groups},
               data_date=src.get("data_date"), source=src.get("source"),
               error=src.get("error"))


if __name__ == "__main__":
    main()
