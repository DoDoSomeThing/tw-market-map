# fetch_t86.py — 個股三大法人買賣超（上市 T86 + 上櫃 TPEx 3insti），股數
# 每日存快照 data/history_t86/ 供「連買 n 日」計算（僅顯示現況，非進場訊號）。
from __future__ import annotations

import json
from datetime import date, timedelta

from tw_common import (DATA_DIR, http_get_json, parse_num, roc_to_iso, tw_today, write_error, write_json)

T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date={d8}&selectType=ALL&response=json"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"

HISTORY_DIR = DATA_DIR / "history_t86"


def fetch_twse() -> tuple[dict, str] | None:
    """往回試 5 個交易日。回 ({code: {f, t, d, total}}, iso_date)，單位=股。"""
    for back in range(8):
        d = tw_today() - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        j = http_get_json(T86_URL.format(d8=d.strftime("%Y%m%d")))
        if j.get("stat") != "OK" or not j.get("data"):
            continue
        idx = {name: i for i, name in enumerate(j.get("fields", []))}
        col_f = idx.get("外陸資買賣超股數(不含外資自營商)")
        col_t = idx.get("投信買賣超股數")
        col_d = idx.get("自營商買賣超股數")
        col_all = idx.get("三大法人買賣超股數")
        if col_f is None or col_t is None:
            return None  # 欄位改版 → 上層報錯，別亂對位
        need = max(c for c in (col_f, col_t, col_d or 0, col_all or 0))
        out = {}
        for row in j["data"]:
            if len(row) <= need:
                continue  # 說明/合計等短列
            code = str(row[0]).strip()
            out[code] = {
                "name": str(row[1]).strip(),
                "f": parse_num(row[col_f]) or 0.0,
                "t": parse_num(row[col_t]) or 0.0,
                "d": (parse_num(row[col_d]) or 0.0) if col_d is not None else 0.0,
                "total": (parse_num(row[col_all]) or 0.0) if col_all is not None else 0.0,
            }
        return out, d.isoformat()
    return None


def _pick(row: dict, *candidates: str):
    """TPEx openapi 欄位名有空白亂插，正規化後比對。"""
    norm = {k.replace(" ", ""): v for k, v in row.items()}
    for c in candidates:
        if c in norm:
            return parse_num(norm[c])
    return None


def fetch_tpex() -> tuple[dict, str] | None:
    j = http_get_json(TPEX_URL)
    if not isinstance(j, list) or not j:
        return None
    out = {}
    d_iso = None
    for row in j:
        code = str(row.get("SecuritiesCompanyCode", "")).strip()
        if not code:
            continue
        d_iso = d_iso or roc_to_iso(row.get("Date", ""))
        f = _pick(row, "ForeignInvestorsIncludeMainlandAreaInvestors-Difference",
                  "ForeignInvestorsincludeMainlandAreaInvestors(ForeignDealersexcluded)-Difference")
        t = _pick(row, "SecuritiesInvestmentTrustCompanies-Difference")
        dl = _pick(row, "Dealers-Difference")
        total = _pick(row, "TotalDifference")
        out[code] = {"name": str(row.get("CompanyName", "")).strip(),
                     "f": f or 0.0, "t": t or 0.0, "d": dl or 0.0,
                     "total": total if total is not None else (f or 0) + (t or 0) + (dl or 0)}
    if not out:
        return None
    return out, d_iso


def save_snapshot(data_date: str, stocks: dict) -> None:
    """{code: [外資net, 投信net]}（股）供連買計算；同日重跑覆蓋。"""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    snap = {c: [v["f"], v["t"]] for c, v in stocks.items()}
    (HISTORY_DIR / f"{data_date}.json").write_text(
        json.dumps(snap, separators=(",", ":")), encoding="utf-8")
    # 永久累積（append-only 正本，2026-07-16 起不再砍舊檔）：
    # 舊檔永不改 → git 只存新增那支（~281KB/天、壓縮後 ~14MB/年）。法人歷史是資產，砍掉就追不回。
    # 消費端都只讀最近幾支（render inst10 取 [-10:]、build_changes 取 [:8]），累積不影響效能。


def main() -> None:
    stocks: dict = {}
    dates = []
    errs = []
    try:
        r = fetch_twse()
        if r:
            twse, d = r
            for c, v in twse.items():
                stocks[c] = {**v, "market": "twse"}
            dates.append(d)
        else:
            errs.append("上市 T86 欄位改版或無資料")
    except Exception as e:
        errs.append(f"上市 T86:{e}")
    try:
        r = fetch_tpex()
        if r:
            tpex, d = r
            for c, v in tpex.items():
                stocks.setdefault(c, {**v, "market": "tpex"})
            if d:
                dates.append(d)
        else:
            errs.append("上櫃 3insti 無資料")
    except Exception as e:
        errs.append(f"上櫃 3insti:{e}")

    if not stocks:
        write_error("t86", "TWSE T86 + TPEx 3insti", "；".join(errs) or "無資料")
        return

    data_date = min(dates) if dates else None
    if len(set(dates)) > 1:
        errs.append(f"上市/上櫃法人資料日不一致:{sorted(set(dates))}")
    if data_date:
        save_snapshot(data_date, stocks)

    write_json("t86", {"stocks": stocks},
               data_date=data_date, source="TWSE T86 + TPEx 3insti（股數）",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
