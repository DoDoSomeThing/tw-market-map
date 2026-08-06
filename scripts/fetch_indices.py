# fetch_indices.py — 7 指數卡：加權/費半/S&P500/台積ADR/日經/VIX/NVDA
# 加權指數走 TWSE 官方 FMTQIK；其餘走 yfinance。
from __future__ import annotations

from datetime import timedelta

from tw_common import (http_get_json, parse_num, roc_to_iso, sanity_check_pct,
                       tw_today, write_error, write_json)

SYMBOLS = [
    ("^TWII", "加權指數", "TAIEX"),
    ("^SOX", "費城半導體", "SOX"),
    ("^GSPC", "S&P 500", "S&P500"),
    ("TSM", "台積電 ADR", "TSM"),
    ("^N225", "日經 225", "N225"),
    ("^VIX", "VIX 恐慌", "VIX"),
    ("NVDA", "NVIDIA", "NVDA"),
]

# 每日市場成交資訊（含發行量加權股價指數收盤）。帶 date=某月1號 → 回該月全部交易日。
FMTQIK_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"


def _fmtqik_month(yyyymm01: str) -> list[tuple[str, float]]:
    """抓某一個月的加權指數收盤，回 [(iso_date, close), ...] 升冪。該月無資料回 []。"""
    j = http_get_json(f"{FMTQIK_URL}?date={yyyymm01}&response=json", timeout=30)
    if not j or j.get("stat") != "OK":
        return []
    ci = {n: i for i, n in enumerate(j.get("fields") or [])}
    if "日期" not in ci or "發行量加權股價指數" not in ci:
        # 欄位改版 → 往上報錯，不用位置硬猜（免得靜默寫出錯的數字）
        raise RuntimeError(f"FMTQIK 欄位改版：{j.get('fields')}")
    out = []
    for row in j.get("data") or []:
        iso = roc_to_iso(row[ci["日期"]])
        close = parse_num(row[ci["發行量加權股價指數"]])
        if iso and close:
            out.append((iso, close))
    return out


def fetch_taiex() -> dict | None:
    """加權指數走 TWSE FMTQIK（官方收盤，當日 14:00 後就有）。資料不足回 None。

    2026-08-06 從 yfinance 換過來：yfinance 的 ^TWII 會落後一個交易日 ——
    當天首頁第一張卡還掛 8/04 的 43360.66，官方 8/05 已收 44611.60，差 1251 點（2.8%）。
    數字沒錯，就是慢一天，而 data_date 被日經的當日資料拉到最新 → 過期的裝成新鮮的。
    改吃官方就沒有這個時差。
    """
    today = tw_today()
    rows = _fmtqik_month(today.strftime("%Y%m01"))
    if len(rows) < 2:
        # 月初（1~2 個交易日）當月湊不出前一根 → 補抓上個月接在前面
        prev_month = today.replace(day=1) - timedelta(days=1)
        rows = _fmtqik_month(prev_month.strftime("%Y%m01")) + rows
    if len(rows) < 2:
        return None

    (_, prev), (last_date, last) = rows[-2], rows[-1]
    if prev <= 0:
        return None
    pct = (last - prev) / prev * 100
    if not sanity_check_pct(pct, limit=25.0):
        return None
    return {
        "close": round(last, 2),
        "prev": round(prev, 2),
        "change": round(last - prev, 2),
        "pct": round(pct, 2),
        "date": last_date,
    }


def fetch_one(ticker_mod, symbol: str) -> dict | None:
    """近 10 日日線 → 最後兩根算漲跌%。資料不足回 None。"""
    df = ticker_mod.Ticker(symbol).history(period="10d", interval="1d", auto_adjust=False)
    if df is None or len(df) < 2:
        return None
    closes = df["Close"].dropna()
    if len(closes) < 2:
        return None
    last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
    if prev <= 0:
        return None
    pct = (last - prev) / prev * 100
    # 指數/個股單日 ±25% 視為抓錯（美股無漲跌停，放寬）
    if not sanity_check_pct(pct, limit=25.0):
        return None
    return {
        "close": round(last, 2),
        "prev": round(prev, 2),
        "change": round(last - prev, 2),
        "pct": round(pct, 2),
        "date": str(closes.index[-1].date()),
    }


def main() -> None:
    try:
        import yfinance as yf
    except ImportError as e:
        write_error("indices", "yfinance", f"yfinance 未安裝: {e}")
        return
    cards = []
    errors = []
    sources = set()
    for symbol, name, short in SYMBOLS:
        row = None
        src = "yfinance"
        if symbol == "^TWII":
            try:
                row = fetch_taiex()
                src = "TWSE FMTQIK"
                if row is None:
                    errors.append("^TWII:TWSE 資料不足")
            except Exception as e:  # TWSE 掛了才退回 yfinance（會落後一天，記進 error）
                errors.append(f"^TWII:TWSE 失敗({e})，退回 yfinance")
                row = None
        if row is None:
            src = "yfinance"
            try:
                row = fetch_one(yf, symbol)
            except Exception as e:  # 單一標的失敗不拖垮整組
                row = None
                errors.append(f"{symbol}:{e}")
        if row:
            sources.add(src)
        cards.append({"symbol": symbol, "name": name, "short": short, **(row or {"close": None})})
    dates = [c.get("date") for c in cards if c.get("date")]
    if not dates:
        write_error("indices", "yfinance", "全部標的抓取失敗: " + "; ".join(errors)[:200])
        return
    write_json("indices", {"cards": cards},
               data_date=max(dates), source=" + ".join(sorted(sources)) or "yfinance",
               error="; ".join(errors)[:200] or None)


if __name__ == "__main__":
    main()
