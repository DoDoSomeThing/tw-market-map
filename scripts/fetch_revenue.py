# fetch_revenue.py — 月營收亮點（上市 t187ap05_L + 上櫃 mopsfin_t187ap05_O）
# 自動掃「年增高 + 月增正」的營收動能股 → 每日焦點卡片。零編輯、零人工。
# 「創歷史新高」單月 API 判不出來（無歷史序列），不裝——只標年增/月增。
from __future__ import annotations

from tw_common import http_get_json, parse_num, read_json, roc_to_iso, write_error, write_json

URLS = [
    ("twse", "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"),
    ("tpex", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"),
]
TOP_N = 20
MIN_TRADE_VALUE = 5e7    # 日成交值 ≥ 5 千萬
MIN_YOY = 30.0           # 年增 ≥ 30% 才算亮點
MIN_REV = 1e8            # 當月營收 ≥ 1 億（小基數暴增沒意義）


def _norm(row: dict) -> dict:
    return {str(k).replace(" ", ""): v for k, v in row.items()}


def main() -> None:
    rows: list[dict] = []
    errs: list[str] = []
    latest_ym = ""
    out_date = None
    for market, url in URLS:
        try:
            data = http_get_json(url, timeout=60)
            if not isinstance(data, list):
                errs.append(f"{market} 回應非列表")
                continue
            for raw in data:
                r = _norm(raw)
                code = str(r.get("公司代號", "")).strip()
                ym = str(r.get("資料年月", "")).strip()          # 民國 YYYMM
                rev = parse_num(r.get("營業收入-當月營收"))       # 仟元
                yoy = parse_num(r.get("營業收入-去年同月增減(%)"))
                mom = parse_num(r.get("營業收入-上月比較增減(%)"))
                if len(code) != 4 or not code.isdigit() or not ym or rev is None:
                    continue
                out_date = out_date or roc_to_iso(str(r.get("出表日期", "")))
                latest_ym = max(latest_ym, ym)
                rows.append({"code": code, "ym": ym, "rev": rev, "yoy": yoy,
                             "mom": mom, "market": market})
        except Exception as e:
            errs.append(f"{market}:{e}")

    if not rows:
        write_error("revenue_hl", "TWSE/TPEx 月營收 openapi", "；".join(errs) or "無資料")
        return

    # 只留最新資料年月（公布潮期間兩市場同月）
    rows = [r for r in rows if r["ym"] == latest_ym]
    y = int(latest_ym[:-2]) + 1911
    ym_label = f"{y}/{int(latest_ym[-2:])}月"

    daily = read_json("daily_all")
    info = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}

    picks = []
    for r in rows:
        s = info.get(r["code"])
        if not s or (s.get("value") or 0) < MIN_TRADE_VALUE:
            continue
        if r["yoy"] is None or r["yoy"] < MIN_YOY or (r["mom"] is not None and r["mom"] < 0):
            continue
        if r["rev"] * 1000 < MIN_REV:      # 仟元 → 元
            continue
        picks.append({
            "code": r["code"], "name": s["name"], "industry": s.get("industry"),
            "close": s["close"], "pct": s["pct"],
            "rev_yi": round(r["rev"] / 1e5, 1),   # 仟元 → 億
            "yoy": round(r["yoy"], 1), "mom": round(r["mom"], 1) if r["mom"] is not None else None,
        })
    picks.sort(key=lambda x: -x["yoy"])

    # 全量營收 map（個股面板 + 今日異動用）：code -> [當月營收億, YoY%, MoM%]
    stocks = {r["code"]: [round(r["rev"] / 1e5, 1),
                          round(r["yoy"], 1) if r["yoy"] is not None else None,
                          round(r["mom"], 1) if r["mom"] is not None else None]
              for r in rows}

    write_json("revenue_hl", {
        "ym_label": ym_label, "items": picks[:TOP_N], "n_reported": len(rows),
        "stocks": stocks,
        "criteria": f"年增 ≥{MIN_YOY:.0f}% 且月增不為負；當月營收 ≥1 億；日成交值 ≥0.5 億",
    }, data_date=out_date, source="TWSE t187ap05_L + TPEx mopsfin_t187ap05_O（月營收）",
        error="；".join(errs) or None)


if __name__ == "__main__":
    main()
