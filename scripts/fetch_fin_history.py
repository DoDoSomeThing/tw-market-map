# fetch_fin_history.py — 歷史季報（綜合損益表彙總）→ data/history_fin/<ROC>Q<n>.json
#
# 為什麼要另外抓：fetch_fundamentals 走 openapi t187ap06_L_ci，那支**只回「本季已公布者」**，
# 換季當下（如 2026-08-06 Q2 才報 213 家）其餘 78% 個股連當季 EPS 都是空的，
# 更沒有「去年同季」可比 → EPS 年增率／毛利率年增差算不出來。
#
# 來源：MOPS 綜合損益表彙總 ajax_t163sb04（POST，一請求拿「一個市場一整季」全市場）。
#   ⚠️ 網域必須用 mopsov.twse.com.tw；舊的 mops.twse.com.tw 會回 WAF 擋頁
#      「FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED」（HTTP 200，很容易誤判成成功）。
#   ⚠️ 回應是 HTML 多表：一般業／金融／證券／保險／其他業欄位各不相同，
#      **不能只讀第一張表**。銀行保險沒有「營業收入/毛利」概念 → 這兩欄誠實留 None，只取 EPS。
#   ⚠️ 數字是**當年累計**（Q1=Q1、Q2=上半年、Q3=前三季、Q4=全年），不是單季。
#      TTM 換算在 build_fin_growth.py 做。
#
# 用法：
#   python fetch_fin_history.py --seed        # 種子：民國 111Q1 ~ 最新，約 36 請求 / 2 分鐘
#   python fetch_fin_history.py               # 每日：只補缺 + 重抓最近 2 季（公布期內會持續補進來）
#   python fetch_fin_history.py --force 115 2 # 指定重抓某季
from __future__ import annotations

import argparse
import io
import json
import sys
import time

import pandas as pd
import requests

from tw_common import DATA_DIR, parse_num, tw_today

URL = "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04"
MARKETS = {"sii": "twse", "otc": "tpex"}
FIN_DIR = DATA_DIR / "history_fin"
START_ROC = 111          # 種子起點（民國）；再往前 MOPS 表格式會變動，收益也低
SLEEP = 3.0              # MOPS 對連打敏感
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tw-market-map/1.0",
      "Content-Type": "application/x-www-form-urlencoded"}

# 各表欄名不一致，這裡列出所有見過的別名（比對用 col_pick 前綴比對）
C_CODE = ("公司代號", "公司 代號")
C_NAME = ("公司名稱",)
C_REV = ("營業收入", "收益", "收入")          # 銀行=利息淨收益 → 不採計（見 _row_fields）
C_COST = ("營業成本",)
C_GROSS = ("營業毛利（毛損）淨額", "營業毛利（毛損）")
C_EPS = ("基本每股盈餘（元）", "基本每股盈餘")


def _norm(s) -> str:
    return str(s).replace(" ", "").replace("　", "").strip()


def _col(cols: list[str], names: tuple[str, ...]) -> str | None:
    """在欄位清單找第一個命中的欄名（去空白後完全相等）。找不到回 None。"""
    table = {_norm(c): c for c in cols}
    for n in names:
        if n in table:
            return table[n]
    return None


def _post_html(typek: str, roc_year: int, season: int) -> str:
    body = (f"encodeURIComponent=1&step=1&firstin=1&off=1&isQuery=Y"
            f"&TYPEK={typek}&year={roc_year}&season={season:02d}")
    r = requests.post(URL, data=body, headers=UA, timeout=90)
    r.raise_for_status()
    r.encoding = "utf-8"
    html = r.text
    if "CAN NOT BE ACCESSED" in html:
        raise RuntimeError("MOPS 回 WAF 擋頁（請確認網域為 mopsov.twse.com.tw）")
    return html


def _row_fields(df: pd.DataFrame) -> dict:
    """回這張表要用的欄位名對照；沒有代號欄回 {}。"""
    cols = list(df.columns)
    code = _col(cols, C_CODE)
    eps = _col(cols, C_EPS)
    if not code or not eps:
        return {}
    # 只有「營業收入」這個確切欄名才算營收；銀行的「利息淨收益」「收益」不是可比營收，
    # 跟一般業混在一起算毛利率會得到垃圾數字 → 寧可留 None。
    rev = _col(cols, ("營業收入",))
    return {"code": code, "name": _col(cols, C_NAME), "eps": eps,
            "rev": rev, "cost": _col(cols, C_COST) if rev else None,
            "gross": _col(cols, C_GROSS) if rev else None}


def fetch_quarter(roc_year: int, season: int) -> dict:
    """抓一季（含上市+上櫃）→ {code: [rev, gross, eps]}（rev/gross 單位千元，累計；缺=None）。"""
    stocks: dict[str, list] = {}
    per_market = {}
    for typek, tag in MARKETS.items():
        html = _post_html(typek, roc_year, season)
        got = 0
        for df in pd.read_html(io.StringIO(html)):
            f = _row_fields(df)
            if not f:
                continue
            for _, row in df.iterrows():
                code = _norm(row[f["code"]])
                if len(code) != 4 or not code.isdigit():
                    continue
                eps = parse_num(row[f["eps"]])
                rev = parse_num(row[f["rev"]]) if f["rev"] else None
                gross = parse_num(row[f["gross"]]) if f["gross"] else None
                if gross is None and rev is not None and f["cost"]:
                    cost = parse_num(row[f["cost"]])
                    gross = rev - cost if cost is not None else None
                if eps is None and rev is None:
                    continue
                stocks[code] = [rev, gross, eps]
                got += 1
        per_market[tag] = got
        time.sleep(SLEEP)
    return {"yq": f"{roc_year + 1911}Q{season}", "roc": roc_year, "season": season,
            "unit": "千元（當年累計）", "n": len(stocks), "by_market": per_market,
            "stocks": stocks}


def candidate_quarters() -> list[tuple[int, int]]:
    """已過公布期限、值得抓的 (民國年, 季)。公布期限：Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31。"""
    today = tw_today()
    roc_now = today.year - 1911
    out = []
    for y in range(START_ROC, roc_now + 1):
        for s in (1, 2, 3, 4):
            # 該季最早可能出現的日期（提早幾天開抓，早報的公司先進來）
            due = {1: (y, 5, 1), 2: (y, 8, 1), 3: (y, 11, 1), 4: (y + 1, 3, 1)}[s]
            dy, dm, dd = due
            if (dy + 1911, dm, dd) <= (today.year, today.month, today.day):
                out.append((y, s))
    return out


def save(q: dict) -> None:
    FIN_DIR.mkdir(parents=True, exist_ok=True)
    p = FIN_DIR / f"{q['roc']}Q{q['season']}.json"
    p.write_text(json.dumps(q, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"[OK ] {p.relative_to(DATA_DIR.parent)} n={q['n']} {q['by_market']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true", help="抓 111Q1 起全部（首次建檔）")
    ap.add_argument("--force", nargs=2, type=int, metavar=("ROC_YEAR", "SEASON"),
                    help="指定重抓某季")
    args = ap.parse_args()

    cands = candidate_quarters()
    if args.force:
        todo = [tuple(args.force)]
    elif args.seed:
        todo = cands
    else:
        # 每日：缺的補、最近 2 季重抓（公布期內家數會持續增加）
        missing = [(y, s) for y, s in cands if not (FIN_DIR / f"{y}Q{s}.json").exists()]
        todo = sorted(set(missing + cands[-2:]))

    if not todo:
        print("[OK ] history_fin 無待抓季度")
        return 0

    # 真缺口 vs 例行噪音：todo 同時含「從未抓到的季度」和「最近 2 季例行重抓」。
    # 後者本來就有檔，來源掛掉（MOPS WAF 擋雲端 IP）只是少補幾家新公布的，
    # 不該讓 pipeline 報失敗 → 否則每次 WAF 都開一張沒東西可修的 issue。
    missing_hard, failed_soft = [], []
    for y, s in todo:
        p = FIN_DIR / f"{y}Q{s}.json"
        try:
            q = fetch_quarter(y, s)
        except Exception as e:                      # noqa: BLE001 — 單季失敗不擋其他季
            print(f"[ERR] {y}Q{s}: {type(e).__name__} {str(e)[:150]}")
            (failed_soft if p.exists() else missing_hard).append(f"{y}Q{s}")
            continue
        if q["n"] == 0:
            print(f"[SKIP] {y}Q{s}: 無資料（尚未公布）")
            continue
        # 不讓殘缺蓋掉完整：家數比既有檔少一成以上就跳過（公布期內只會越來越多）
        if p.exists():
            old_n = json.loads(p.read_text(encoding="utf-8")).get("n", 0)
            if q["n"] < old_n * 0.9:
                print(f"[SKIP] {y}Q{s}: 本次 {q['n']} 檔 < 既有 {old_n} 檔九成，不覆蓋")
                continue
        save(q)

    if failed_soft:
        print(f"[WARN] 重抓失敗但已有存檔（不算缺口）: {failed_soft}")
    if missing_hard:
        print(f"[ERR ] 從未抓到的季度: {missing_hard}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
