# fetch_exrights.py — 除權除息事件（給還原價用）→ data/exrights.json
#
# 還原因子 factor = 除權息參考價 / 除權息前收盤價（<1）。後復權：把除權息日「之前」的
# 價格乘上其後所有事件因子的累積乘積 → 除權息造成的跳空被抹平，均線/乖離不再失真。
#
# 資料源：
#   上市 TWSE rwd TWT49U（除權除息計算結果表）：可帶 startDate/endDate 逐「月」回補歷史。
#   上櫃 TPEx openapi tpex_exright_daily（除權除息計算結果表）：**只有今明兩天的快照、無歷史**
#        → 每日跑時把當天事件累積進 exrights.json（append-only，未來自然齊）。
#        歷史缺口無源可補（同 fetch_dividend「上櫃誠實缺」的既有限制）。
#
# 用法：
#   python3 scripts/fetch_exrights.py                 # 每日：補當月上市 + 累積上櫃快照
#   python3 scripts/fetch_exrights.py --backfill      # 一次性：上市回補近 14 個月
from __future__ import annotations

import argparse
from datetime import date, timedelta

from tw_common import http_get_json, parse_num, read_json, roc_to_iso, write_json, ymd_to_iso

TWSE_EXRIGHT_URL = ("https://www.twse.com.tw/rwd/zh/exRight/TWT49U"
                    "?startDate={s}&endDate={e}&response=json")
TPEX_EXRIGHT_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_daily"

BACKFILL_MONTHS = 14        # 視窗 260 交易日 ≈ 13 個月，多墊一個月


def _month_ranges(n: int) -> list[tuple[str, str]]:
    """回最近 n 個月的 (startYYYYMMDD, endYYYYMMDD)，舊→新。"""
    out = []
    today = date.today()
    y, m = today.year, today.month
    for i in range(n - 1, -1, -1):
        yy, mm = y, m - i
        while mm <= 0:
            mm += 12
            yy -= 1
        start = date(yy, mm, 1)
        end = (date(yy + (mm == 12), (mm % 12) + 1, 1) - timedelta(days=1))
        if end > today:
            end = today
        out.append((start.strftime("%Y%m%d"), end.strftime("%Y%m%d")))
    return out


def fetch_twse(start: str, end: str) -> list[dict]:
    """上市除權除息事件。回 [{code, d, factor, type}]。"""
    try:
        j = http_get_json(TWSE_EXRIGHT_URL.format(s=start, e=end), timeout=60)
    except Exception as e:
        print(f"[WARN] 上市 {start}~{end} 抓取失敗：{e}")
        return []
    if j.get("stat") != "OK" or not j.get("data"):
        return []
    idx = {name: i for i, name in enumerate(j.get("fields", []))}
    try:
        i_d, i_c = idx["資料日期"], idx["股票代號"]
        i_prev, i_ref = idx["除權息前收盤價"], idx["除權息參考價"]
        i_type = idx["權/息"]
    except KeyError:
        print(f"[WARN] 上市 TWT49U 欄位改版，略過 {start}~{end}")
        return []
    out = []
    for r in j["data"]:
        iso = roc_to_iso(str(r[i_d]).replace("年", "").replace("月", "").replace("日", ""))
        prev, ref = parse_num(r[i_prev]), parse_num(r[i_ref])
        code = str(r[i_c]).strip()
        if not iso or not prev or not ref or prev <= 0 or ref <= 0:
            continue
        out.append({"code": code, "d": iso, "factor": round(ref / prev, 6),
                    "type": str(r[i_type]).strip(), "mkt": "twse"})
    return out


def fetch_tpex_today() -> list[dict]:
    """上櫃除權除息（openapi 只有今明快照）。回 [{code, d, factor, type}]。"""
    try:
        rows = http_get_json(TPEX_EXRIGHT_URL, timeout=40)
    except Exception as e:
        print(f"[WARN] 上櫃快照抓取失敗：{e}")
        return []
    if not isinstance(rows, list):
        return []
    out = []
    for r in rows:
        iso = ymd_to_iso(roc_ymd_to_ad(str(r.get("Date", ""))))
        prev = parse_num(r.get("ClosePriceBeforeExRightsDiviend"))
        ref = parse_num(r.get("ExRightsDiviendQuote"))
        code = str(r.get("SecuritiesCompanyCode", "")).strip()
        if not iso or not code or not prev or not ref or prev <= 0 or ref <= 0:
            continue
        out.append({"code": code, "d": iso, "factor": round(ref / prev, 6),
                    "type": str(r.get("ExRightsDiviend", "")).strip(), "mkt": "tpex"})
    return out


def roc_ymd_to_ad(s: str) -> str:
    """民國 '1150716' → 西元 '20260716'。非 7 碼原樣回。"""
    s = s.strip()
    if len(s) == 7 and s.isdigit():
        return f"{int(s[:3]) + 1911}{s[3:]}"
    return s


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backfill", action="store_true",
                    help=f"一次性回補上市近 {BACKFILL_MONTHS} 個月")
    args = ap.parse_args()

    # 既有事件（append-only 累積；上櫃歷史只能靠每日快積）
    old = read_json("exrights")
    events: dict[str, dict] = {}
    if old.get("ok"):
        for e in old["data"].get("events", []):
            events[f"{e['code']}|{e['d']}"] = e

    n_before = len(events)
    errs = []

    ranges = _month_ranges(BACKFILL_MONTHS) if args.backfill else _month_ranges(1)
    for s, e in ranges:
        rows = fetch_twse(s, e)
        for ev in rows:
            events[f"{ev['code']}|{ev['d']}"] = ev
        print(f"[上市] {s}~{e}：{len(rows)} 筆")

    tp = fetch_tpex_today()
    for ev in tp:
        events[f"{ev['code']}|{ev['d']}"] = ev
    print(f"[上櫃] 今明快照：{len(tp)} 筆（無歷史源，靠每日累積）")
    if not tp:
        errs.append("上櫃快照無資料")

    # 依股票分組，日期舊→新
    by_code: dict[str, list] = {}
    for ev in events.values():
        by_code.setdefault(ev["code"], []).append({"d": ev["d"], "factor": ev["factor"],
                                                   "type": ev.get("type", "")})
    for c in by_code:
        by_code[c].sort(key=lambda x: x["d"])

    n_tw = sum(1 for e in events.values() if e.get("mkt") == "twse")
    n_tp = sum(1 for e in events.values() if e.get("mkt") == "tpex")
    write_json("exrights", {
        "events": sorted(events.values(), key=lambda x: (x["d"], x["code"])),
        "by_code": by_code,
        "n_twse": n_tw, "n_tpex": n_tp,
        "note": "factor=除權息參考價/前收盤；上市 TWT49U 有完整歷史，"
                "上櫃 openapi 僅今明快照→靠每日累積，歷史缺口無源可補",
    }, data_date=date.today().isoformat(),
        source="TWSE TWT49U（上市，可回補）+ TPEx openapi tpex_exright_daily（上櫃，僅快照）",
        error="；".join(errs) or None)
    print(f"[OK ] data/exrights.json 事件 {n_before}→{len(events)}"
          f"（上市 {n_tw}、上櫃 {n_tp}），涵蓋 {len(by_code)} 檔")


if __name__ == "__main__":
    main()
