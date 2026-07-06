# fetch_indices.py — yfinance 抓 7 指數卡：加權/費半/S&P500/台積ADR/日經/VIX/NVDA
from __future__ import annotations

from tw_common import sanity_check_pct, write_error, write_json

SYMBOLS = [
    ("^TWII", "加權指數", "TAIEX"),
    ("^SOX", "費城半導體", "SOX"),
    ("^GSPC", "S&P 500", "S&P500"),
    ("TSM", "台積電 ADR", "TSM"),
    ("^N225", "日經 225", "N225"),
    ("^VIX", "VIX 恐慌", "VIX"),
    ("NVDA", "NVIDIA", "NVDA"),
]


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
    for symbol, name, short in SYMBOLS:
        try:
            row = fetch_one(yf, symbol)
        except Exception as e:  # 單一標的失敗不拖垮整組
            row = None
            errors.append(f"{symbol}:{e}")
        cards.append({"symbol": symbol, "name": name, "short": short, **(row or {"close": None})})
    dates = [c.get("date") for c in cards if c.get("date")]
    if not dates:
        write_error("indices", "yfinance", "全部標的抓取失敗: " + "; ".join(errors)[:200])
        return
    write_json("indices", {"cards": cards},
               data_date=max(dates), source="yfinance",
               error="; ".join(errors)[:200] or None)


if __name__ == "__main__":
    main()
