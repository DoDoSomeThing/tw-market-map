# fetch_fundamentals.py — 基本面（季報 + 股利）→ data/fundamentals.json
# 上市：t187ap17_L（毛利/營益/純益率）+ t187ap06_L_ci（EPS）+ t187ap07_L_ci（淨值/負債比）
#       + t187ap45_L（現金股利 → 殖利率）
# 上櫃：mopsfin_t187ap06_O_ci（自算比率+EPS）+ 07_O_ci（淨值/負債比）；
#       上櫃 17_O/45_O 端點目前回空 → 上櫃無殖利率（誠實缺）。
# 季資料：freshness 放寬（render 端 maxStale=95 交易日）。
from __future__ import annotations

from tw_common import (carry_over, http_get_json, parse_num, read_json, roc_to_iso,
                       write_error, write_json)

TWSE = "https://openapi.twse.com.tw/v1/opendata/"
TPEX = "https://www.tpex.org.tw/openapi/v1/"

TOP_N = 15
MIN_TRADE_VALUE = 5e7   # 排行門檻：日成交值 ≥ 5 千萬


def _norm(row: dict) -> dict:
    """欄位 key 去空白（openapi 會混入空白；TPEx 中英混用）。"""
    return {str(k).replace(" ", ""): v for k, v in row.items()}


def _rows(url: str) -> list[dict]:
    j = http_get_json(url, timeout=60)
    return [_norm(r) for r in j] if isinstance(j, list) else []


def _pick(r: dict, *keys: str):
    for k in keys:
        if k in r:
            return parse_num(r[k])
    return None


def _code_of(r: dict) -> str:
    return str(r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip()


def _yq_of(r: dict) -> str:
    y = str(r.get("年度") or r.get("Year") or "").strip()
    s = str(r.get("季別") or r.get("Season") or "").strip()
    if y.isdigit():
        y = str(int(y) + 1911) if int(y) < 1000 else y
    return f"{y}Q{s.lstrip('0') or s}" if y and s else ""


def _merge_latest(store: dict, code: str, yq: str, fields: dict) -> None:
    """同檔取最新年季；季報各表年季一致時合併。"""
    cur = store.setdefault(code, {"yq": yq})
    if yq > cur["yq"]:
        keep_div = {k: cur[k] for k in ("div_cash", "div_year") if k in cur}
        cur.clear()
        cur.update({"yq": yq, **keep_div})
    if yq >= cur["yq"]:
        cur.update({k: v for k, v in fields.items() if v is not None})


def main() -> None:
    stocks: dict[str, dict] = {}
    errs: list[str] = []
    dates: list[str] = []

    # ── 上市 營益分析（比率現成）──
    try:
        for r in _rows(TWSE + "t187ap17_L"):
            code = _code_of(r)
            yq = _yq_of(r)
            if len(code) != 4 or not yq:
                continue
            d = roc_to_iso(str(r.get("出表日期", "")))
            if d:
                dates.append(d)
            _merge_latest(stocks, code, yq, {
                "rev_m": _pick(r, "營業收入(百萬元)"),
                "gm": _pick(r, "毛利率(%)(營業毛利)/(營業收入)"),
                "om": _pick(r, "營業利益率(%)(營業利益)/(營業收入)"),
                "nm": _pick(r, "稅後純益率(%)(稅後純益)/(營業收入)"),
            })
    except Exception as e:
        errs.append(f"上市營益分析:{e}")

    # ── 上市 EPS ──
    try:
        for r in _rows(TWSE + "t187ap06_L_ci"):
            code = _code_of(r)
            yq = _yq_of(r)
            if len(code) != 4 or not yq:
                continue
            _merge_latest(stocks, code, yq, {"eps": _pick(r, "基本每股盈餘（元）", "基本每股盈餘(元)")})
    except Exception as e:
        errs.append(f"上市損益:{e}")

    # ── 上市 淨值/負債比 ──
    try:
        for r in _rows(TWSE + "t187ap07_L_ci"):
            code = _code_of(r)
            yq = _yq_of(r)
            if len(code) != 4 or not yq:
                continue
            assets = _pick(r, "資產總額", "資產總計")
            debts = _pick(r, "負債總額", "負債總計")
            _merge_latest(stocks, code, yq, {
                "bps": _pick(r, "每股參考淨值"),
                "debt_pct": round(debts / assets * 100, 1) if assets and debts else None,
            })
    except Exception as e:
        errs.append(f"上市資產負債:{e}")

    # ── 上櫃 損益（自算比率）──
    try:
        for r in _rows(TPEX + "mopsfin_t187ap06_O_ci"):
            code = _code_of(r)
            yq = _yq_of(r)
            if len(code) != 4 or not yq:
                continue
            rev = _pick(r, "營業收入")
            gross = _pick(r, "營業毛利（毛損）淨額", "營業毛利(毛損)淨額")
            op = _pick(r, "營業利益（損失）", "營業利益(損失)")
            net = _pick(r, "本期淨利（淨損）", "本期淨利(淨損)")
            _merge_latest(stocks, code, yq, {
                "rev_m": round(rev / 1e3, 0) if rev else None,   # 仟元 → 百萬（TPEx 財報單位=仟元）
                "gm": round(gross / rev * 100, 2) if rev and gross is not None else None,
                "om": round(op / rev * 100, 2) if rev and op is not None else None,
                "nm": round(net / rev * 100, 2) if rev and net is not None else None,
                "eps": _pick(r, "基本每股盈餘（元）", "基本每股盈餘(元)"),
            })
    except Exception as e:
        errs.append(f"上櫃損益:{e}")

    # ── 上櫃 淨值/負債比 ──
    try:
        for r in _rows(TPEX + "mopsfin_t187ap07_O_ci"):
            code = _code_of(r)
            yq = _yq_of(r)
            if len(code) != 4 or not yq:
                continue
            assets = _pick(r, "資產總計", "資產總額")
            debts = _pick(r, "負債總計", "負債總額")
            _merge_latest(stocks, code, yq, {
                "bps": _pick(r, "每股參考淨值"),
                "debt_pct": round(debts / assets * 100, 1) if assets and debts else None,
            })
    except Exception as e:
        errs.append(f"上櫃資產負債:{e}")

    # ── 上市 股利（現金股利合計；上櫃端點回空，誠實缺）──
    try:
        for r in _rows(TWSE + "t187ap45_L"):
            code = _code_of(r)
            if len(code) != 4:
                continue
            cash = sum(v for v in (
                _pick(r, "股東配發-盈餘分配之現金股利(元/股)", "股東配發-盈餘分配之現金股利（元/股）"),
                _pick(r, "股東配發-法定盈餘公積發放之現金(元/股)", "股東配發-法定盈餘公積、資本公積發放之現金(元/股)"),
                _pick(r, "股東配發-資本公積發放之現金(元/股)"),
            ) if v)
            if cash <= 0:
                continue
            year = str(r.get("股利年度", "")).strip()
            cur = stocks.setdefault(code, {"yq": ""})
            # 同檔多筆（季配息）：同股利年度累加，新年度取代
            if cur.get("div_year") == year:
                cur["div_cash"] = round(cur.get("div_cash", 0) + cash, 4)
            elif year > str(cur.get("div_year", "")):
                cur["div_year"] = year
                cur["div_cash"] = round(cash, 4)
    except Exception as e:
        errs.append(f"上市股利:{e}")

    if not stocks:
        write_error("fundamentals", "TWSE/TPEx 財報 openapi", "；".join(errs) or "無資料")
        return

    # 來源掛掉時補回前次的個股（見 tw_common.carry_over）。放在排行計算之前，
    # 沿用的個股才會一起參與殖利率/毛利排行，不然榜上會只剩上櫃。
    prev_env = read_json("fundamentals")
    stocks, carried = carry_over("fundamentals", "stocks", stocks, errs=errs)
    if carried:
        errs.append(carried)
        if not dates and prev_env.get("data_date"):
            dates.append(prev_env["data_date"])   # 全掛時別讓 data_date=None（前端會當「無資料」）

    # ── join 收盤 → 殖利率 + 排行 ──
    daily = read_json("daily_all")
    info = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}
    for code, f in stocks.items():
        s = info.get(code)
        if s and s.get("close") and f.get("div_cash"):
            f["yield_pct"] = round(f["div_cash"] / s["close"] * 100, 2)

    def enrich(code: str) -> dict:
        s = info.get(code, {})
        return {"code": code, "name": s.get("name") or "", "industry": s.get("industry"),
                "close": s.get("close"), **stocks[code]}

    liquid = [c for c in stocks
              if info.get(c) and (info[c].get("value") or 0) >= MIN_TRADE_VALUE]
    top_yield = sorted((enrich(c) for c in liquid if stocks[c].get("yield_pct")),
                       key=lambda x: x["yield_pct"], reverse=True)[:TOP_N]
    top_margin = sorted((enrich(c) for c in liquid if stocks[c].get("gm") is not None),
                        key=lambda x: x["gm"], reverse=True)[:TOP_N]

    write_json("fundamentals", {
        "stocks": stocks,
        "top_yield": top_yield,
        "top_margin": top_margin,
        "n_stocks": len(stocks),
        "min_trade_value": MIN_TRADE_VALUE,
    }, data_date=max(dates) if dates else None,
        source="TWSE t187ap17/06/07/45 + TPEx 06/07（季報；上櫃無股利資料）",
        error="；".join(errs) or None)


if __name__ == "__main__":
    main()
