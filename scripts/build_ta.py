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

from tw_common import DATA_DIR, write_json

WINDOW_PATH = DATA_DIR / "ohlc_window.json.gz"


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


def ta_for(bars: list[dict]) -> dict | None:
    """單檔 bars（舊→新）→ ta 物件。少於 2 根回 None。"""
    if len(bars) < 2:
        return None
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

    return {
        "ma": ma, "above": above, "bias240": bias240, "bb": bb,
        "vol_ratio": vol_ratio, "pos52w": pos52w,
        "kd": kd, "rsi14": rsi14, "signals": sig,
    }


def main() -> None:
    if not WINDOW_PATH.exists():
        write_json("ta", {"stocks": {}}, data_date=None,
                   source="ohlc_window 計算", ok=False,
                   error="ohlc_window.json.gz 不存在（先跑 build_ohlc_window --seed）")
        return
    with gzip.open(WINDOW_PATH, "rt", encoding="utf-8") as f:
        win = json.load(f)

    stocks = {}
    for code, bars in win.get("stocks", {}).items():
        t = ta_for(bars)
        if t is not None:
            stocks[code] = t

    note = "描述性技術狀態；訊號僅供參考、非買賣建議；均線用原始收盤，除權息日前後失真屬已知"
    write_json("ta", {"stocks": stocks, "note": note}, data_date=win.get("data_date"),
               source="ohlc_window 計算",
               error=None if stocks else "視窗無足夠資料")
    print(f"[OK ] data/ta.json（{len(stocks)} 檔）")


if __name__ == "__main__":
    main()
