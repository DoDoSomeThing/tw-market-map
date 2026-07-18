# fetch_tdcc.py — TDCC 集保戶股權分散（週資料）→ 大戶持股比（四級距）+ 週變化排行
# 級距：11=200-400張 12=400-600 13=600-800 14=800-1000 15=千張以上 17=合計（股數 400,000=400 張）
# 每週存快照 data/history_tdcc/，有前週快照才算得出增減；首週先列千張大戶比。
# 快照格式（2026-07-18 起）：[r200, r400, r800, r1000] 四欄，與 backfill_tdcc.py 一致。
# 更舊的快照是 [r400, r1000] 兩欄 → 讀取端一律用 len 判斷，別假設欄位位置。
from __future__ import annotations

import csv
import io
import json
import subprocess

import requests

from tw_common import DATA_DIR, UA, read_json, write_error, write_json, ymd_to_iso

TDCC_URL = "https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
HISTORY_DIR = DATA_DIR / "history_tdcc"
TOP_N = 15
MIN_TRADE_VALUE = 5e7     # 排行門檻：日成交值 ≥ 5 千萬（殭屍股的大戶比噪音大）
LEVELS_200 = {"11", "12", "13", "14", "15"}
LEVELS_400 = {"12", "13", "14", "15"}
LEVELS_800 = {"14", "15"}


def prev_r400(p: list) -> float:
    """舊快照 [r400,r1000] 的 r400 在 [0];新快照 [r200,r400,r800,r1000] 在 [1]。"""
    return p[1] if len(p) >= 4 else p[0]


def download_csv() -> str:
    """requests 抓；SSL 驗證失敗（TDCC 憑證缺 SKI，新版 OpenSSL 拒收）→ curl 備援。"""
    try:
        r = requests.get(TDCC_URL, headers=UA, timeout=120)
        r.raise_for_status()
        r.encoding = "utf-8"
        return r.text
    except requests.exceptions.SSLError:
        p = subprocess.run(
            ["curl", "-s", "--max-time", "120", "-H", f"User-Agent: {UA['User-Agent']}", TDCC_URL],
            capture_output=True, timeout=150)
        if p.returncode != 0 or not p.stdout:
            raise RuntimeError(f"curl exit={p.returncode}")
        return p.stdout.decode("utf-8")


def parse(text: str) -> tuple[dict, str]:
    """回 ({code: {"r400": %, "r1000": %, "holders": 合計人數}}, iso_date)。只收 4 碼代號。"""
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or "持股分級" not in ",".join(header):
        raise RuntimeError(f"CSV 表頭不符：{header}")
    stocks: dict[str, dict] = {}
    data_date = ""
    for row in reader:
        if len(row) < 6:
            continue
        d8, code, level, holders, _shares, ratio = row[0], row[1].strip(), row[2].strip(), row[3], row[4], row[5]
        if len(code) != 4 or not code.isdigit():
            continue
        data_date = data_date or d8
        rec = stocks.setdefault(code, {"r200": 0.0, "r400": 0.0, "r800": 0.0, "r1000": 0.0, "holders": 0})
        try:
            pct = float(ratio)
        except ValueError:
            continue
        if level in LEVELS_200:
            rec["r200"] = round(rec["r200"] + pct, 2)
        if level in LEVELS_400:
            rec["r400"] = round(rec["r400"] + pct, 2)
        if level in LEVELS_800:
            rec["r800"] = round(rec["r800"] + pct, 2)
        if level == "15":
            rec["r1000"] = pct
        if level == "17":
            rec["holders"] = int(float(holders or 0))
    iso = ymd_to_iso(data_date)
    if not stocks or not iso:
        raise RuntimeError(f"解析失敗（{len(stocks)} 檔，日期 {data_date!r}）")
    return stocks, iso


def save_snapshot(iso: str, stocks: dict) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    snap = {c: [v["r200"], v["r400"], v["r800"], v["r1000"]] for c, v in stocks.items()}
    (HISTORY_DIR / f"{iso}.json").write_text(
        json.dumps(snap, separators=(",", ":")), encoding="utf-8")
    # 永久累積（append-only 正本，2026-07-16 起不再砍舊檔）：週資料、~59KB/支 → 壓縮後 ~1MB/年。


def load_prev_snapshot(current_iso: str) -> tuple[dict, str] | None:
    if not HISTORY_DIR.exists():
        return None
    files = sorted(f for f in HISTORY_DIR.glob("????-??-??.json") if f.stem < current_iso)
    if not files:
        return None
    f = files[-1]
    return json.loads(f.read_text(encoding="utf-8")), f.stem


def main() -> None:
    try:
        stocks, iso = parse(download_csv())
    except Exception as e:
        write_error("tdcc", "TDCC 股權分散 1-5", str(e))
        return

    save_snapshot(iso, stocks)
    prev = load_prev_snapshot(iso)

    # join 名稱/收盤/成交值（daily_all 缺檔時排行照出，只是少欄位）
    info = {}
    env = read_json("daily_all")
    if env.get("ok"):
        info = {s["code"]: s for s in env["data"].get("stocks", [])}

    def enrich(code: str, rec: dict, delta: float | None) -> dict:
        s = info.get(code, {})
        return {"code": code, "name": s.get("name") or "", "industry": s.get("industry"),
                "close": s.get("close"), "r400": rec["r400"], "r1000": rec["r1000"],
                "delta": delta}

    inc: list[dict] = []
    dec: list[dict] = []
    top_r1000: list[dict] = []
    prev_iso = None
    if prev:
        prev_snap, prev_iso = prev
        movers = []
        for code, rec in stocks.items():
            p = prev_snap.get(code)
            if not p:
                continue
            s = info.get(code)
            if not s or (s.get("value") or 0) < MIN_TRADE_VALUE:
                continue  # 無行情或成交太小
            delta = round(rec["r400"] - prev_r400(p), 2)
            if delta:
                movers.append(enrich(code, rec, delta))
        movers.sort(key=lambda m: m["delta"], reverse=True)
        inc = [m for m in movers if m["delta"] > 0][:TOP_N]
        dec = [m for m in movers if m["delta"] < 0][::-1][:TOP_N]
    else:
        ranked = sorted(
            (enrich(c, r, None) for c, r in stocks.items()
             if info.get(c) and (info[c].get("value") or 0) >= MIN_TRADE_VALUE),
            key=lambda m: m["r1000"], reverse=True)
        top_r1000 = ranked[:20]

    # 全量 by_code（個股面板用）：code -> [400張+持股比, 千張+持股比, 週增減pp, 股東人數]
    # 原本只輸出排行榜 Top15，個股面板看不到自己的大戶結構 → 補全量（1991 檔 ≈ 60KB）。
    prev_snap = prev[0] if prev else {}
    by_code = {}
    for code, rec in stocks.items():
        p = prev_snap.get(code)
        delta = round(rec["r400"] - prev_r400(p), 2) if p else None
        by_code[code] = [rec["r400"], rec["r1000"], delta, rec["holders"] or None]

    write_json("tdcc", {
        "inc": inc, "dec": dec, "top_r1000": top_r1000,
        "by_code": by_code,
        "prev_week": prev_iso, "n_stocks": len(stocks),
        "min_trade_value": MIN_TRADE_VALUE,
    }, data_date=iso, source="TDCC opendata 股權分散（週）", error=None)


if __name__ == "__main__":
    main()
