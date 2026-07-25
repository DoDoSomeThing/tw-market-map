# build_sentiment.py — 大盤情緒曲線（純規則、零新資料源、零 API）
# 讀 data/history/*.json（每日 {代號:[收盤,量]} 快照），比對相鄰兩日收盤
# → 每日上漲家數占比 → data/sentiment.json。>50% 偏多日、<50% 偏空日。
# 註：以原始收盤比對，少數除權息日會略失真，情緒趨勢用途可接受。
from __future__ import annotations

import json
from pathlib import Path

from tw_common import DATA_DIR, write_error, write_json

KEEP = 20   # 最多取最近 20 個交易日快照


def main() -> None:
    hist_dir = DATA_DIR / "history"
    files = sorted(hist_dir.glob("????-??-??.json"))[-KEEP:] if hist_dir.exists() else []
    if len(files) < 2:
        write_error("sentiment", "build_sentiment", f"歷史快照不足（{len(files)} 日，需 ≥2）")
        return

    snaps = []
    for f in files:
        try:
            snaps.append((f.stem, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue

    def close_of(v):
        """快照值可能是 [收盤,量] 或純收盤數字。"""
        if isinstance(v, (list, tuple)):
            return v[0] if v else None
        if isinstance(v, (int, float)):
            return v
        return None

    series = []
    for i in range(1, len(snaps)):
        date, cur = snaps[i]
        _, prev = snaps[i - 1]
        up = down = 0
        for code, v in cur.items():
            if len(code) != 4 or not code.isdigit():
                continue
            c0, p0 = close_of(v), close_of(prev.get(code))
            if c0 is None or p0 is None or p0 == 0:
                continue
            if c0 > p0:
                up += 1
            elif c0 < p0:
                down += 1
        n = up + down
        if n:
            series.append({"date": date, "up": up, "down": down,
                           "pct": round(up / n * 100, 1)})

    if not series:
        write_error("sentiment", "build_sentiment", "無法算出任何交易日情緒")
        return

    write_json("sentiment", {"series": series}, data_date=series[-1]["date"],
               source="規則彙整（history 快照收盤比對）")


if __name__ == "__main__":
    main()
