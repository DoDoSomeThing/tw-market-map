# fetch_valuation.py — 估值：本益比 PE / 股價淨值比 PB / 市值 → data/valuation.json
#
# PE/PB：上市 TWSE BWIBBU_ALL、上櫃 TPEx tpex_mainboard_peratio_analysis（交易所每日直接公布，
#        不自算——自算要處理 EPS 認列期間/追溯調整，交易所版才是市場共同語言）。
# 市值 ：已發行普通股數 × 收盤（上市 t187ap03_L「已發行普通股數或TDR原股發行股數」、
#        上櫃 mopsfin_t187ap03_O「IssueShares」）。股數為月更靜態資料，除權後有數日落差屬已知。
# 注意：交易所 PE 用「近四季 EPS」；虧損股 PE 給 0 或空 → 一律轉 None，前端顯示「—」（不裝有值）。
from __future__ import annotations

import json

from tw_common import DATA_DIR, http_get_json, parse_num, read_json, roc_to_iso, write_error, write_json

# 永久 archive（append-only 正本，2026-07-17 起）：每日 PE/PB/殖利率/市值 快照。
# 目的：累積出「本益比河流圖」所需的歷史序列——單點 PE 33 看不出貴不貴，
# 要跟自己過去 N 年的 PE 區間比才有意義。今天不存，之後就永遠畫不出來。
# 體積：~1900 檔 × 4 值 ≈ 60KB/天 → ~15MB/年（同 history_ohlc 套路，進 git）。
ARCHIVE_DIR = DATA_DIR / "history_valuation"

TWSE_BWIBBU = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
TPEX_PER = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis"
TWSE_INFO = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_INFO = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"


def _norm(row: dict) -> dict:
    return {str(k).replace(" ", ""): v for k, v in row.items()}


def _rows(url: str) -> list[dict]:
    j = http_get_json(url, timeout=60)
    return [_norm(r) for r in j] if isinstance(j, list) else []


def _pos(v):
    """PE/PB ≤0 或無值 → None（虧損股交易所給 0，顯示 0 會誤導成「超便宜」）。"""
    n = parse_num(v)
    return n if n and n > 0 else None


def main() -> None:
    stocks: dict[str, dict] = {}
    errs: list[str] = []
    dates: list[str] = []

    # ── 上市 PE/PB/殖利率 ──
    try:
        for r in _rows(TWSE_BWIBBU):
            code = str(r.get("Code", "")).strip()
            if len(code) != 4 or not code.isdigit():
                continue
            d = roc_to_iso(str(r.get("Date", "")))
            if d:
                dates.append(d)
            stocks[code] = {"pe": _pos(r.get("PEratio")), "pb": _pos(r.get("PBratio")),
                            "yield_ex": _pos(r.get("DividendYield"))}
    except Exception as e:
        errs.append(f"上市 BWIBBU_ALL:{e}")

    # ── 上櫃 PE/PB/殖利率 ──
    try:
        for r in _rows(TPEX_PER):
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            if len(code) != 4 or not code.isdigit():
                continue
            d = roc_to_iso(str(r.get("Date", "")))
            if d:
                dates.append(d)
            stocks[code] = {"pe": _pos(r.get("PriceEarningRatio")), "pb": _pos(r.get("PriceBookRatio")),
                            "yield_ex": _pos(r.get("YieldRatio"))}
    except Exception as e:
        errs.append(f"上櫃 peratio_analysis:{e}")

    if not stocks:
        write_error("valuation", "TWSE BWIBBU_ALL + TPEx peratio", "；".join(errs) or "無資料")
        return

    # ── 已發行股數（市值用）──
    shares: dict[str, float] = {}
    try:
        for r in _rows(TWSE_INFO):
            code = str(r.get("公司代號", "")).strip()
            n = parse_num(r.get("已發行普通股數或TDR原股發行股數"))
            if len(code) == 4 and code.isdigit() and n:
                shares[code] = n
    except Exception as e:
        errs.append(f"上市股數:{e}")
    try:
        for r in _rows(TPEX_INFO):
            code = str(r.get("SecuritiesCompanyCode", "")).strip()
            n = parse_num(r.get("IssueShares"))
            if len(code) == 4 and code.isdigit() and n:
                shares[code] = n
    except Exception as e:
        errs.append(f"上櫃股數:{e}")

    # ── join 收盤 → 市值（億元）──
    daily = read_json("daily_all")
    info = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}
    n_cap = 0
    for code, v in stocks.items():
        s, sh = info.get(code), shares.get(code)
        if s and s.get("close") and sh:
            v["cap"] = round(sh * s["close"] / 1e8, 1)   # 元 → 億
            n_cap += 1

    # ── 永久 archive：每日快照（供日後畫本益比河流圖／估值歷史）──
    data_date = max(dates) if dates else None
    n_arch = 0
    if data_date:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        # 精簡格式 [pe, pb, yield, cap]，省空間；缺值 None。同日重跑覆蓋。
        snap = {c: [v.get("pe"), v.get("pb"), v.get("yield_ex"), v.get("cap")]
                for c, v in stocks.items()}
        (ARCHIVE_DIR / f"{data_date}.json").write_text(
            json.dumps(snap, separators=(",", ":")), encoding="utf-8")
        n_arch = len(snap)
        print(f"[OK ] archive: history_valuation/{data_date}.json（{n_arch} 檔）")

    write_json("valuation", {
        "stocks": stocks, "n_pe": sum(1 for v in stocks.values() if v.get("pe")),
        "n_cap": n_cap, "n_archived": n_arch,
        "note": "PE/PB 為交易所每日公布值（PE 採近四季 EPS）；虧損股不給 PE。"
                "市值=已發行普通股數×收盤（股數月更，除權後數日內可能落差）",
    }, data_date=data_date,
        source="TWSE BWIBBU_ALL + TPEx peratio_analysis + t187ap03 股數",
        error="；".join(errs) or None)


if __name__ == "__main__":
    main()
