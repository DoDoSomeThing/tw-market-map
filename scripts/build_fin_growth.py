# build_fin_growth.py — 季報 archive → TTM EPS 年增率 / 毛利率年增差 → data/fin_growth.json
#
# 讀 data/history_fin/<ROC>Q<n>.json（MOPS 綜合損益表，**當年累計**）。
#
# 為什麼用 TTM（近四季滾動）而不是單季：
#   單季 = 本季累計 − 上季累計，會把季節性（電子業 Q4 旺、傳產 Q1 淡）全吃進年增率，
#   雜訊大。TTM 對 TTM 是同長度、同季節組合的比較，這也是「EPS 年增率」慣用口徑。
#
# TTM 換算（累計制）：
#   ttm(y, s) = cum(y, s) + cum(y-1, 4) − cum(y-1, s)      （s < 4）
#   ttm(y, 4) = cum(y, 4)
#   → 一檔要算出「今年 TTM vs 去年 TTM」，需要 5 個季度都在：
#      (y,s) (y-1,4) (y-1,s) (y-2,4) (y-2,s)
#   缺任一個就誠實留 None（不用單季硬湊）。
#
# ⚠️ EPS 累計相減有股本變動失真（期間增資/減資會讓每股基礎不一致）。業界通用做法，
#    但它是近似值，健診卡上標示為「TTM 近似」。毛利率是比率、不受股本影響。
from __future__ import annotations

import json
import sys

from tw_common import DATA_DIR, write_json

FIN_DIR = DATA_DIR / "history_fin"
REV, GROSS, EPS = 0, 1, 2


def load_all() -> dict[tuple[int, int], dict]:
    """{(民國年, 季): {code: [rev, gross, eps]}}"""
    out = {}
    for p in sorted(FIN_DIR.glob("*Q*.json")):
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
            out[(int(j["roc"]), int(j["season"]))] = j.get("stocks") or {}
        except (ValueError, KeyError) as e:
            print(f"[WARN] 略過 {p.name}: {e}")
    return out


def cum(q: dict, code: str, idx: int):
    v = q.get(code)
    return v[idx] if v else None


def ttm(all_q: dict, code: str, y: int, s: int, idx: int):
    """近四季滾動值；任一環節缺就回 None。"""
    cur = cum(all_q.get((y, s), {}), code, idx)
    if cur is None:
        return None
    if s == 4:
        return cur
    fy_prev = cum(all_q.get((y - 1, 4), {}), code, idx)
    same_prev = cum(all_q.get((y - 1, s), {}), code, idx)
    if fy_prev is None or same_prev is None:
        return None
    return cur + fy_prev - same_prev


def growth(cur, prev) -> tuple[float | None, str | None]:
    """年增率%。分母 ≤0 時百分比無意義 → 回 (None, 標記)。"""
    if cur is None or prev is None:
        return None, None
    if prev > 0:
        return round((cur - prev) / prev * 100, 1), None
    if cur > 0:
        return None, "turn_profit"      # 去年虧、今年賺
    return None, "loss"                 # 兩年都虧


def main() -> int:
    all_q = load_all()
    if not all_q:
        print("[ERR] 沒有 history_fin 資料，先跑 fetch_fin_history.py --seed")
        return 1

    quarters = sorted(all_q)            # 由舊到新
    stocks: dict[str, dict] = {}
    codes = {c for q in all_q.values() for c in q}

    for code in codes:
        # 從最新季往回找第一個「TTM 兩年都算得出來」的季度
        for y, s in reversed(quarters):
            eps_c = ttm(all_q, code, y, s, EPS)
            eps_p = ttm(all_q, code, y - 1, s, EPS)
            if eps_c is None or eps_p is None:
                continue
            eps_yoy, eps_tag = growth(eps_c, eps_p)

            rev_c, rev_p = ttm(all_q, code, y, s, REV), ttm(all_q, code, y - 1, s, REV)
            gr_c, gr_p = ttm(all_q, code, y, s, GROSS), ttm(all_q, code, y - 1, s, GROSS)
            gm_c = round(gr_c / rev_c * 100, 2) if rev_c and gr_c is not None and rev_c > 0 else None
            gm_p = round(gr_p / rev_p * 100, 2) if rev_p and gr_p is not None and rev_p > 0 else None
            gm_diff = round(gm_c - gm_p, 2) if gm_c is not None and gm_p is not None else None

            stocks[code] = {
                "yq": f"{y + 1911}Q{s}",
                "eps_ttm": round(eps_c, 2), "eps_ttm_prev": round(eps_p, 2),
                "eps_yoy": eps_yoy, "eps_tag": eps_tag,
                "gm_ttm": gm_c, "gm_ttm_prev": gm_p, "gm_diff": gm_diff,
            }
            break

    latest = f"{quarters[-1][0] + 1911}Q{quarters[-1][1]}"
    n_eps = sum(1 for v in stocks.values() if v["eps_yoy"] is not None or v["eps_tag"])
    n_gm = sum(1 for v in stocks.values() if v["gm_diff"] is not None)
    print(f"[INFO] TTM 完整 {len(stocks)} 檔（EPS 年增 {n_eps}、毛利年增差 {n_gm}）；archive 最新季 {latest}")

    write_json("fin_growth", {"stocks": stocks, "latest_quarter": latest,
                              "n": len(stocks), "n_eps": n_eps, "n_gm": n_gm,
                              "basis": "TTM（近四季滾動，累計相減；EPS 未調整股本變動）"},
               data_date=None, source="MOPS t163sb04 季報 archive（data/history_fin）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
