# build_ta.py — 技術面指標（描述性為主、訊號式為輔，非買賣建議）
#
# 讀 data/ohlc_window.json.gz → 算 §SPEC 指標 → data/ta.json（信封）→ 部署時 render 複製到 docs/。
# 指標：MA20/60/240、站上/跌破、距年線乖離、量比、52週位置、KD、RSI14、訊號旗標。
# 用原始收盤（不做除權還原）；除權息日前後均線/乖離失真屬已知，前端 note 標明。
# 不足天數的指標 → null，前端顯示「—」。
from __future__ import annotations

import gzip
import json
from pathlib import Path

from tw_common import DATA_DIR, read_json, write_json

WINDOW_PATH = DATA_DIR / "ohlc_window.json.gz"
SERIES_N = 80        # 給前端畫布林通道圖的收盤序列長度（60 日圖 + 20 日 MA20 暖機）
SERIES_MIN = 25      # 少於此根數不給序列（畫不出通道）


def back_adjust(bars: list[dict], evs: list[dict]) -> tuple[list[dict], int]:
    """後復權：把除權息日「之前」的價格乘上其後所有事件因子的累積乘積 → 抹平除權息跳空。
    今日 bar 之後無事件 → 因子 1 → 今日價維持原始（面板顯示直覺不變）。
    回 (還原後 bars, 視窗內套用的事件數)。evs 需依日期舊→新。成交量不調整（除權會變股數，
    但量比只看近 21 日、事件罕見；屬已知小瑕疵）。"""
    if not evs:
        return bars, 0
    out = [dict(b) for b in bars]
    cum, applied = 1.0, 0
    ei = len(evs) - 1
    for i in range(len(out) - 1, -1, -1):
        d = out[i]["d"]
        while ei >= 0 and evs[ei]["d"] > d:
            cum *= evs[ei]["factor"]
            applied += 1
            ei -= 1
        if cum != 1.0:
            for k in ("o", "h", "l", "c"):
                out[i][k] = out[i][k] * cum
    return out, applied


def sma(vals: list[float], n: int) -> float | None:
    return round(sum(vals[-n:]) / n, 2) if len(vals) >= n else None


def bollinger(closes: list[float], n: int = 20, k: float = 2.0) -> dict | None:
    """布林通道：中軌=MA20、上下軌=±k×母體標準差(σ)。回 {mid,upper,lower,pctb,width}。
    %B=(close−下軌)/(上軌−下軌)；帶寬=(上軌−下軌)/中軌×100（判盤整vs收縮）。不足 n 根回 None。"""
    if len(closes) < n:
        return None
    win = closes[-n:]
    mid = sum(win) / n
    var = sum((c - mid) ** 2 for c in win) / n     # 母體標準差（與多數看盤軟體一致）
    sd = var ** 0.5
    upper, lower = mid + k * sd, mid - k * sd
    close = closes[-1]
    pctb = round((close - lower) / (upper - lower) * 100, 1) if upper > lower else None
    width = round((upper - lower) / mid * 100, 1) if mid else None
    return {"mid": round(mid, 2), "upper": round(upper, 2), "lower": round(lower, 2),
            "pctb": pctb, "width": width}


def _ema_series(vals: list[float], n: int) -> list[float]:
    """EMA 序列，初值用第一根（與多數看盤軟體一致）。"""
    k = 2 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def compute_macd(closes: list[float], fast=12, slow=26, sig_n=9):
    """MACD(12,26,9)。回 [(dif, dea, osc), ...] 對齊每根 bar；不足 slow 根回全 None。
    DIF=EMA12−EMA26；DEA(訊號線)=EMA9(DIF)；OSC(柱)=DIF−DEA。"""
    if len(closes) < slow:
        return [None] * len(closes)
    ef, es = _ema_series(closes, fast), _ema_series(closes, slow)
    dif = [a - b for a, b in zip(ef, es)]
    dea = _ema_series(dif, sig_n)
    return [(dif[i], dea[i], dif[i] - dea[i]) for i in range(len(closes))]


def compute_kd(highs, lows, closes, n=9):
    """標準 KD(9,3,3)，初值 50。回 [(k,d), ...] 對齊每根 bar（不足 n 根前為 None）。"""
    out = [None] * len(closes)
    k = d = 50.0
    for i in range(len(closes)):
        if i + 1 < n:
            continue
        hn = max(highs[i - n + 1:i + 1])
        ln = min(lows[i - n + 1:i + 1])
        rsv = 50.0 if hn == ln else (closes[i] - ln) / (hn - ln) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
        out[i] = (k, d)
    return out


def compute_rsi(closes, n=14) -> float | None:
    """Wilder RSI14。不足 n+1 根回 None。"""
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    avg_g, avg_l = gains / n, losses / n
    for i in range(n + 1, len(closes)):
        ch = closes[i] - closes[i - 1]
        avg_g = (avg_g * (n - 1) + max(ch, 0.0)) / n
        avg_l = (avg_l * (n - 1) + max(-ch, 0.0)) / n
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    rs = avg_g / avg_l
    return round(100 - 100 / (1 + rs), 1)


def ta_for(bars: list[dict], evs: list[dict] | None = None) -> dict | None:
    """單檔 bars（舊→新）→ ta 物件。少於 2 根回 None。
    evs = 該檔除權息事件（舊→新，僅含已發生的）→ 指標用後復權序列算；今日價維持原始。"""
    if len(bars) < 2:
        return None
    # 後復權下今日因子=1 → closes[-1] 仍是原始收盤，與面板顯示的現價一致（比較不會錯位）
    bars, adj_n = back_adjust(bars, evs or [])
    closes = [b["c"] for b in bars]
    highs = [b["h"] for b in bars]
    lows = [b["l"] for b in bars]
    vols = [b.get("v") or 0 for b in bars]
    close = closes[-1]

    ma5, ma20, ma60, ma240 = sma(closes, 5), sma(closes, 20), sma(closes, 60), sma(closes, 240)
    ma = {"5": ma5, "20": ma20, "60": ma60, "240": ma240}
    above = {k: (close >= v) if v is not None else None for k, v in ma.items()}
    bias240 = round((close - ma240) / ma240 * 100, 1) if ma240 else None
    bb = bollinger(closes)

    # 量比 = 今量 / 前 20 日均量（不含今日）
    vol_ratio = None
    if len(vols) >= 21:
        base = vols[-21:-1]
        avg = sum(base) / len(base)
        if avg > 0 and vols[-1]:
            vol_ratio = round(vols[-1] / avg, 2)

    # 52 週位置（視窗內最多 260 日高低）
    pos52w = None
    hi, lo = max(highs), min(lows)
    if hi > lo:
        pos52w = round((close - lo) / (hi - lo), 2)

    kd_series = compute_kd(highs, lows, closes)
    kd = None
    if kd_series[-1] is not None:
        kd = {"k": round(kd_series[-1][0], 1), "d": round(kd_series[-1][1], 1)}
    rsi14 = compute_rsi(closes)

    macd_series = compute_macd(closes)
    macd = None
    if macd_series[-1] is not None:
        d0, s0, o0 = macd_series[-1]
        macd = {"dif": round(d0, 2), "dea": round(s0, 2), "osc": round(o0, 2)}

    # ── 訊號旗標（僅供參考、非買賣建議）──
    sig = []
    if None not in (ma20, ma60, ma240):
        if close > ma20 > ma60 > ma240:
            sig.append("ma_bull")
        elif close < ma20 < ma60 < ma240:
            sig.append("ma_bear")
    if vol_ratio is not None and vol_ratio >= 2:
        sig.append("vol_spike")
    if kd_series[-1] and kd_series[-2]:
        (k0, d0), (k1, d1) = kd_series[-2], kd_series[-1]
        if k0 < d0 and k1 > d1:
            sig.append("kd_gc")
        elif k0 > d0 and k1 < d1:
            sig.append("kd_dc")
    # 站上/跌破年線（今昨相對 MA240 翻轉；需 ≥241 根算昨日年線）
    if len(closes) >= 241:
        ma240_prev = sum(closes[-241:-1]) / 240
        prev_close = closes[-2]
        if prev_close < ma240_prev <= close:
            sig.append("break_year")
        elif prev_close >= ma240_prev > close:
            sig.append("lose_year")

    # 布林位置描述（灰底參考，非訊號）：貼上軌 %B≥95、貼下軌 %B≤5
    if bb and bb["pctb"] is not None:
        if bb["pctb"] >= 95:
            sig.append("bb_upper")
        elif bb["pctb"] <= 5:
            sig.append("bb_lower")
    # MACD 交叉（DIF 穿越 DEA）：訊號式，前端灰底「參考」
    if macd_series[-1] and macd_series[-2]:
        (d_prev, s_prev, _), (d_now, s_now, _) = macd_series[-2], macd_series[-1]
        if d_prev < s_prev and d_now > s_now:
            sig.append("macd_gc")
        elif d_prev > s_prev and d_now < s_now:
            sig.append("macd_dc")

    return {
        "ma": ma, "above": above, "bias240": bias240, "bb": bb,
        "vol_ratio": vol_ratio, "pos52w": pos52w,
        "kd": kd, "rsi14": rsi14, "macd": macd, "signals": sig,
        "adj_n": adj_n,     # 視窗內套用的除權息次數（0=無事件或無資料源；前端可標「已還原 N 次」）
    }


def main() -> None:
    if not WINDOW_PATH.exists():
        write_json("ta", {"stocks": {}}, data_date=None,
                   source="ohlc_window 計算", ok=False,
                   error="ohlc_window.json.gz 不存在（先跑 build_ohlc_window --seed）")
        return
    with gzip.open(WINDOW_PATH, "rt", encoding="utf-8") as f:
        win = json.load(f)

    # 除權息事件 → 後復權。只取「已發生」的（未來除息日不能先套，否則今日以前全被誤乘）
    data_date = win.get("data_date") or ""
    ex = read_json("exrights")
    ex_by_code: dict[str, list] = {}
    if ex.get("ok"):
        for code, evs in ex["data"].get("by_code", {}).items():
            past = [e for e in evs if e["d"] <= data_date]
            if past:
                ex_by_code[code] = past

    stocks = {}
    closes80: dict[str, list] = {}     # 布林通道圖用：還原後收盤序列（與 ta.json 的布林同基準）
    for code, bars in win.get("stocks", {}).items():
        evs = ex_by_code.get(code)
        t = ta_for(bars, evs)
        if t is not None:
            stocks[code] = t
            adj, _ = back_adjust(bars, evs or [])
            if len(adj) >= SERIES_MIN:
                closes80[code] = [round(b["c"], 2) for b in adj[-SERIES_N:]]

    # 前端畫近 60 日通道需 80 根（前 20 根給 MA20 暖機）
    write_json("closes80", {"stocks": closes80, "n": SERIES_N,
                            "note": "還原後收盤序列；前端自算 MA20±2σ 畫布林通道"},
               data_date=data_date, source="ohlc_window 後復權收盤",
               error=None if closes80 else "無足夠序列")

    n_adj = sum(1 for t in stocks.values() if t["adj_n"] > 0)
    note = ("描述性技術狀態；訊號僅供參考、非買賣建議。"
            "指標用後復權價（除權息跳空已抹平）；上市有完整除權息歷史，"
            "上櫃無歷史源（僅每日累積），故上櫃早期除權息仍可能小幅失真。"
            "面板顯示的現價為原始收盤。")
    write_json("ta", {"stocks": stocks, "note": note, "n_adjusted": n_adj},
               data_date=data_date, source="ohlc_window 計算 + exrights 後復權",
               error=None if stocks else "視窗無足夠資料")
    print(f"[OK ] data/ta.json（{len(stocks)} 檔，其中 {n_adj} 檔套用過除權息還原）")


if __name__ == "__main__":
    main()
