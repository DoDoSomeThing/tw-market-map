# build_health.py — 四燈號健診卡（基本面／籌碼面／技術面／估值面 各 3 項）→ data/health.json
#
# ⚠️ 定位（跟全站一致）：**描述性健診，不是選股訊號、不是買賣建議。**
#    分數＝把既有數字對照固定門檻換成顏色，方便一眼看完 12 個面向；
#    權重是人訂的、未經回測。本站不出「高分股清單」也不做總分排行榜——
#    燈號型評分在 tw-quant-lab 驗過沒有預測力（見 kanpan 燈號判決），拿它選股會虧錢。
#
# 計分：每面 3 項，權重 40/30/30；綠=滿分、黃=半分、紅=0。
#   面分 = 已評分項的得分 ÷ 已評分項的權重 × 25   （缺資料的項目不算分母，不會被沒抓到的東西拖低）
#   總分 = 四面加總（0~100），全部缺資料則為 None。
#
# 資料來源與口徑：
#   基本面 EPS 年增率 / 毛利率年增差 → fin_growth.json（TTM 近四季滾動，MOPS 季報 archive）
#          月營收年增率              → revenue_hl.json
#   籌碼面 外資/投信近 5 日買賣超 ÷ 20 日均量 → history_t86 + history_ohlc archive
#          券資比 = 融券餘額 ÷ 融資餘額        → margin.json（TWSE 僅上市，上櫃留 None）
#   技術面 均線排列 / RSI(14) / 布林 %B        → ta.json（已做除權息還原）
#   估值面 PE / PB **同業橫斷面分位**、殖利率  → valuation.json
#          ⚠️ 這裡不是「本益比河流」。河流要 3~5 年 PE 時間序列，本站 history_valuation
#             2026-07-16 才開始累積，現在不夠長 → 改用「同產業今日橫斷面分位」，
#             口徑不同必須照實寫在卡上，不能掛河流的名字賣分位數。
from __future__ import annotations

import json
import sys
from statistics import mean

from tw_common import DATA_DIR, read_json, write_json

T86_DIR = DATA_DIR / "history_t86"
OHLC_DIR = DATA_DIR / "history_ohlc"
INST_DAYS = 5        # 法人累計天數
VOL_DAYS = 20        # 均量天數
MIN_PEER = 8         # 同業樣本數門檻，不足退回全市場分位

GREEN, AMBER, RED = 2, 1, 0


# ── 各項目評分（回 (grade, value)；資料缺 → (None, None)）──

def g_band(v, hi, lo, *, reverse=False):
    """通用三段式：v > hi → 綠、lo ≤ v ≤ hi → 黃、v < lo → 紅。reverse=True 反過來（越小越好）。"""
    if v is None:
        return None, None
    if reverse:
        return (GREEN if v < lo else AMBER if v <= hi else RED), v
    return (GREEN if v > hi else AMBER if v >= lo else RED), v


def g_eps(fg: dict | None):
    if not fg:
        return None, None
    tag = fg.get("eps_tag")
    if tag == "turn_profit":                 # 去年虧、今年賺：年增率算不出來但方向明確
        return GREEN, "轉盈"
    if tag == "loss":                        # 兩年皆虧
        return RED, "續虧"
    return g_band(fg.get("eps_yoy"), 5, -5)


def g_ma(ta: dict | None):
    """多頭排列 MA5>MA20>MA60 綠、空頭排列 MA5<MA20<MA60 紅、其餘「多空交錯」黃。

    ⚠️ 這格黃燈原本寫「整理中」，使用者第一眼讀成「資料整理中」（以為是載入狀態）。
    面板上的值一律要能一眼看出是「市場狀態」而不是「系統狀態」，別用兩義詞。
    """
    ma = (ta or {}).get("ma") or {}
    a, b, c = ma.get("5"), ma.get("20"), ma.get("60")
    if a is None or b is None or c is None:
        return None, None
    if a > b > c:
        return GREEN, "多頭排列"
    if a < b < c:
        return RED, "空頭排列"
    return AMBER, "多空交錯"


def g_rsi(ta: dict | None):
    v = (ta or {}).get("rsi14")
    if v is None:
        return None, None
    if 50 <= v <= 70:
        return GREEN, v
    if 30 <= v < 50 or 70 < v <= 80:
        return AMBER, v
    return RED, v


def g_bb(ta: dict | None):
    """布林位置用 %B：中軌之上未觸上軌=綠、中軌之下=黃、觸上軌或跌破下軌=紅（過熱/破線都是風險）。"""
    p = ((ta or {}).get("bb") or {}).get("pctb")
    if p is None:
        return None, None
    if p >= 95:
        return RED, "觸及上軌"
    if p <= 5:
        return RED, "跌破下軌"
    if p >= 50:
        return GREEN, "中軌之上"
    return AMBER, "中軌之下"


def g_pctile(p):
    """估值分位：越低越好。<35 偏低=綠、35~65 合理=黃、>65 偏高=紅。"""
    if p is None:
        return None, None
    return (GREEN if p < 35 else AMBER if p <= 65 else RED), p


# ── 分位計算 ──

def percentiles(values: dict[str, float]) -> dict[str, float]:
    """{code: 值} → {code: 百分位 0~100}（值越大百分位越高）。同值取平均名次。"""
    if not values:
        return {}
    items = sorted(values.items(), key=lambda kv: kv[1])
    n = len(items)
    out, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and items[j + 1][1] == items[i][1]:
            j += 1
        rank = (i + j) / 2                    # 0-based 平均名次
        pct = round(rank / (n - 1) * 100, 1) if n > 1 else 50.0
        for k in range(i, j + 1):
            out[items[k][0]] = pct
        i = j + 1
    return out


def peer_percentiles(vals: dict[str, float], industry: dict[str, str]) -> dict[str, float]:
    """同產業內分位；該產業樣本 < MIN_PEER（或無產業別）退回全市場分位。"""
    market = percentiles(vals)
    groups: dict[str, dict[str, float]] = {}
    for c, v in vals.items():
        ind = industry.get(c)
        if ind:
            groups.setdefault(ind, {})[c] = v
    out = dict(market)
    for ind, g in groups.items():
        if len(g) >= MIN_PEER:
            out.update(percentiles(g))
    return out


# ── archive 讀取 ──

def recent_files(d, n: int) -> list:
    return sorted(d.glob("*.json"))[-n:] if d.exists() else []


def inst_ratios() -> tuple[dict[str, float], dict[str, float], int, int]:
    """近 5 日外資/投信買賣超股數 ÷ 20 日均量 → {code: %}。回 (外資, 投信, 用了幾天t86, 幾天量)。"""
    t86_files = recent_files(T86_DIR, INST_DAYS)
    vol_files = recent_files(OHLC_DIR, VOL_DAYS)
    fore: dict[str, float] = {}
    trust: dict[str, float] = {}
    for p in t86_files:
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for code, v in j.items():
            if not isinstance(v, list) or len(v) < 2:
                continue
            if v[0] is not None:
                fore[code] = fore.get(code, 0.0) + float(v[0])
            if v[1] is not None:
                trust[code] = trust.get(code, 0.0) + float(v[1])

    vols: dict[str, list[float]] = {}
    for p in vol_files:
        try:
            j = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for code, row in (j.get("stocks") or {}).items():
            if isinstance(row, list) and len(row) >= 5 and row[4]:
                vols.setdefault(code, []).append(float(row[4]))

    avg = {c: mean(v) for c, v in vols.items() if v and mean(v) > 0}
    fr = {c: round(s / avg[c] * 100, 2) for c, s in fore.items() if c in avg}
    tr = {c: round(s / avg[c] * 100, 2) for c, s in trust.items() if c in avg}
    return fr, tr, len(t86_files), len(vol_files)


# ── 主流程 ──

FACES = [
    ("f", ["eps_yoy", "rev_yoy", "gm_diff"]),
    ("c", ["fore", "trust", "sbr"]),
    ("t", ["ma", "rsi", "bb"]),
    ("v", ["pe", "pb", "yield"]),
]
WEIGHTS = [40, 30, 30]
ETF_FACES = {"c", "t"}      # ETF 只評籌碼面與技術面（原因見 is_etf）


def is_etf(code: str) -> bool:
    """台股 ETF／ETN 代號一律 0 開頭（0050、00631L、00878…），個股不會。

    為什麼要分開評：ETF 沒有 EPS／毛利率／月營收（基本面三格全空），
    PE／PB 對一籃子持股也不具個股那種意義（交易所根本不公布）。
    若照個股規則算，「缺資料的項目不計入分母」會讓 ETF 只用籌碼＋技術兩面湊出
    **0050 = 90 分、0056 = 92 分**這種假高分，還跟個股的分數並排比較——
    分母根本不同，比了等於騙自己。故 ETF 改成 2 面制、滿分 50，前端另外標示。
    """
    return code.startswith("0")


def face_score(items: list[tuple]) -> int | None:
    """[(grade, value)×3] → 0~25 分；全缺回 None。"""
    earned = avail = 0.0
    for (grade, _), w in zip(items, WEIGHTS):
        if grade is None:
            continue
        avail += w
        earned += w * grade / 2
    if avail == 0:
        return None
    return round(earned / avail * 25)


def main() -> int:
    ta_env, val_env = read_json("ta"), read_json("valuation")
    fg_env, rev_env, mg_env = read_json("fin_growth"), read_json("revenue_hl"), read_json("margin")
    daily = read_json("daily_all")
    if not ta_env.get("ok") or not val_env.get("ok"):
        print("[ERR] 缺 ta/valuation，健診卡不產出（不用殘缺資料湊分數）")
        return 1

    ta = (ta_env["data"].get("stocks") or {})
    val = (val_env["data"].get("stocks") or {})
    fg = (fg_env.get("data") or {}).get("stocks") or {}
    rev = (rev_env.get("data") or {}).get("stocks") or {}
    mg = (mg_env.get("data") or {}).get("by_code") or {}

    industry, market = {}, {}
    for s in (daily.get("data") or {}).get("stocks", []):
        if s.get("industry"):
            industry[s["code"]] = s["industry"]
        market[s["code"]] = s.get("market")

    pe_pct = peer_percentiles({c: v["pe"] for c, v in val.items()
                               if v.get("pe") and v["pe"] > 0}, industry)
    pb_pct = peer_percentiles({c: v["pb"] for c, v in val.items()
                               if v.get("pb") and v["pb"] > 0}, industry)
    fore, trust, n_t86, n_vol = inst_ratios()

    stocks: dict[str, dict] = {}
    for code in sorted(set(ta) | set(val)):
        f = fg.get(code)
        rv = rev.get(code)
        m = mg.get(code) or []
        t = ta.get(code)
        v = val.get(code) or {}

        items = {
            "eps_yoy": g_eps(f),
            "rev_yoy": g_band(rv[1] if isinstance(rv, list) and len(rv) > 1 else None, 5, -5),
            "gm_diff": g_band((f or {}).get("gm_diff"), 2, -2),
            "fore": g_band(fore.get(code), 10, -10),
            "trust": g_band(trust.get(code), 5, -5),
            # 券資比越低越安全（融券多＝空方壓力／或軋空題材，兩面刃）；
            # ⚠️ 台股融券普遍極低（全市場中位 ~0.2%），這格實務上幾乎恆綠、資訊量低，僅當風險旗標。
            "sbr": g_band(m[2] if len(m) > 2 else None, 15, 5, reverse=True),
            "ma": g_ma(t),
            "rsi": g_rsi(t),
            "bb": g_bb(t),
            "pe": g_pctile(pe_pct.get(code)),
            "pb": g_pctile(pb_pct.get(code)),
            "yield": g_band(v.get("yield_ex"), 5, 2),
        }

        etf = is_etf(code)
        rec, scores, earned, avail = {}, [], 0.0, 0.0
        for key, keys in FACES:
            if etf and key not in ETF_FACES:
                rec[key] = None                   # 不適用（跟「有這面但資料缺」要分得開）
                scores.append(None)
                continue
            trio = [items[k] for k in keys]
            rec[key] = [[g, val_] for g, val_ in trio]
            scores.append(face_score(trio))
            for (g, _), w in zip(trio, WEIGHTS):
                if g is not None:
                    avail += w
                    earned += w * g / 2
        if avail == 0:
            continue
        # ETF 滿分 50（2 面）、個股 100（4 面）；tot_max 一起送出去，前端才不會把兩者當同一把尺
        tot_max = 25 * (len(ETF_FACES) if etf else len(FACES))
        scored_keys = ETF_FACES if etf else {k for k, _ in FACES}
        na = sum(1 for (key, keys) in FACES if key in scored_keys
                 for k in keys if items[k][0] is None)
        stocks[code] = {**rec, "sc": scores, "tot": round(earned / avail * tot_max),
                        "max": tot_max, "kind": "etf" if etf else "stock",
                        "na": na, "yq": None if etf else (f or {}).get("yq")}

    n_etf = sum(1 for v in stocks.values() if v["kind"] == "etf")
    full = sum(1 for v in stocks.values() if v["na"] == 0 and v["kind"] == "stock")
    print(f"[INFO] 健診 {len(stocks)} 檔（個股 {len(stocks) - n_etf}，其中 12 格全備 {full} 檔；"
          f"ETF {n_etf} 檔走 2 面制滿分 50）；"
          f"法人用 {n_t86} 日 t86 / {n_vol} 日均量；"
          f"PE 分位 {len(pe_pct)} 檔、PB {len(pb_pct)} 檔")
    if n_t86 < INST_DAYS or n_vol < VOL_DAYS:
        print(f"[WARN] archive 天數不足（t86 {n_t86}/{INST_DAYS}、量 {n_vol}/{VOL_DAYS}），"
              f"籌碼面比率會偏小，等 archive 累積即自動修正")

    write_json("health", {
        "stocks": stocks,
        "n": len(stocks), "n_full": full, "n_etf": n_etf,
        "inst_days": n_t86, "vol_days": n_vol,
        "quarter": (fg_env.get("data") or {}).get("latest_quarter"),
        "note": "描述性健診，非選股訊號或買賣建議；權重為人訂、未經回測。"
                "估值面為同產業橫斷面分位（非本益比河流）；EPS／毛利率為 TTM 近四季滾動。"
                "ETF 無 EPS／毛利／營收，PE／PB 對一籃子持股也不具個股意義 → "
                "只評籌碼面＋技術面，滿分 50，不與個股的 100 分制混用。",
    }, data_date=ta_env.get("data_date"), source="ta + valuation + fin_growth + revenue + margin + t86/ohlc archive")
    return 0


if __name__ == "__main__":
    sys.exit(main())
