# build_ohlc_window.py — 滾動 OHLC 視窗（技術面指標的資料底層）
#
# 產物：data/ohlc_window.json.gz（gzip，僅供 build_ta 計算，不給前端）
#   {ok, data_date, n_days, stocks:{code:[{d,o,h,l,c,v}, ... 舊→新, 最多 N=260 筆]}}
#
# 三模式：
#   種子（--seed，預設種子法）：一次性。TWSE/TPEx 逐「日」抓（每呼叫回整個市場一天 OHLC），
#                   往回 SEED_DAYS 個交易日建視窗。零 FinMind 配額，260 天約 15-25 分。
#   種子（--seed-finmind）：備援。FinMind 逐「檔」抓（1962 個請求、免費 600/hr、~3.3hr）。需 FINMIND_TOKEN。
#   每日（預設）：讀既有視窗 + 今日 data/daily_all.json 的 OHLC → append + 去重 + 裁 N → 存回。
#                 零新資料源（沿用 fetch_daily_all 擷到的 O/H/L/vol）。
#
# 用法：
#   python3 scripts/build_ohlc_window.py --seed              # 一次性種子（TWSE/TPEx 按日，建議）
#   FINMIND_TOKEN=... python3 scripts/build_ohlc_window.py --seed-finmind   # 備援種子法
#   python3 scripts/build_ohlc_window.py                     # 每日 append（run_all 內呼叫）
from __future__ import annotations

import argparse
import gzip
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

import tw_common
from tw_common import DATA_DIR, UA, parse_num, read_json

# ── 職責分離 ──
# archive（data/history_ohlc/YYYY-MM-DD.json）＝永久累積的正本：每日一支全市場 OHLCV，
#   append-only（舊檔永不改）→ git 只存新增那支（raw ~78KB／git 內部壓縮後 ~29KB）。
#   要更長歷史、換更長指標、或做回測，都從這裡重建。
# window（ohlc_window.json.gz）＝純計算快取：只留最近 N_DAYS 根給 build_ta 算指標，
#   gitignore、走 Actions cache；掉了就用 --from-archive 由 archive 秒重建（零網路）。
N_DAYS = 300                    # 視窗上限（MA240 需240根，300=年線+60緩衝）。archive 不受此限，永久累積
SEED_DAYS = 260                 # 種子回補的交易日數
WINDOW_PATH = DATA_DIR / "ohlc_window.json.gz"
ARCHIVE_DIR = DATA_DIR / "history_ohlc"

# ── 按日種子（TWSE/TPEx，主種子法）──
TWSE_MI_URL = ("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
               "?response=json&date={d8}&type=ALLBUT0999")
TPEX_DAY_URL = ("https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"
                "?date={d_slash}&type=EW&response=json")
SEED_INTERVAL = 1.5             # 按日種子的請求間隔（覆寫 tw_common 預設 3s，加速歷史回補）
SEED_LOOKBACK_LIMIT = 500       # 往回找交易日的日曆天上限（防呆）

# ── FinMind 種子參數（備援；移植自 tw-stock-bot/backfill_kline_deep.py）──
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
SLEEP_OK = 0.4                  # 正常請求間隔（秒）
SLEEP_BACKOFF = 30              # 網路失敗退避
FAIL_STOP = 8                   # 連續網路失敗自停
HOUR_BUFFER = 120               # 等配額重置的整點後緩衝
SAVE_EVERY = 50                 # 每 N 檔存一次（中斷不白做）


# ── gzip 讀寫 ──

def load_window() -> dict:
    if not WINDOW_PATH.exists():
        return {"ok": False, "data_date": None, "n_days": N_DAYS, "stocks": {}}
    try:
        with gzip.open(WINDOW_PATH, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"ok": False, "data_date": None, "n_days": N_DAYS, "stocks": {}}


def save_window(win: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WINDOW_PATH.with_suffix(".gz.tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(win, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, WINDOW_PATH)


# ── archive（永久正本）──

def write_day_snapshot(iso: str, day: dict[str, dict]) -> None:
    """寫 data/history_ohlc/<iso>.json（全市場當日 OHLCV，append-only）。
    存未壓縮 JSON：git 內部本來就 zlib 壓（~29KB），檔案還保持可讀。"""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out = {c: [b["o"], b["h"], b["l"], b["c"], b.get("v") or 0] for c, b in day.items()}
    (ARCHIVE_DIR / f"{iso}.json").write_text(
        json.dumps({"d": iso, "stocks": out}, separators=(",", ":")), encoding="utf-8")


def rebuild_from_archive(n: int = N_DAYS) -> int:
    """由 archive 最近 n 支快照重建視窗（cache miss 時用；零網路、秒級）。"""
    files = sorted(ARCHIVE_DIR.glob("????-??-??.json"))[-n:] if ARCHIVE_DIR.exists() else []
    if not files:
        print("[ERR] archive 空（data/history_ohlc/ 無快照）→ 無法重建，需跑 --seed")
        return 1
    stocks: dict[str, list] = {}
    for f in files:
        snap = json.loads(f.read_text(encoding="utf-8"))
        for c, v in snap.get("stocks", {}).items():
            stocks.setdefault(c, []).append(
                {"d": snap["d"], "o": v[0], "h": v[1], "l": v[2], "c": v[3], "v": v[4]})
    for c in stocks:
        stocks[c] = _trim(stocks[c])
    win = {"ok": True, "data_date": files[-1].stem, "n_days": N_DAYS,
           "stocks": stocks, "nodata": []}
    save_window(win)
    print(f"[OK ] 由 archive 重建視窗：{len(files)} 支快照 × {len(stocks)} 檔 → {WINDOW_PATH.name}")
    return 0


def materialize_archive() -> int:
    """一次性：把現有視窗攤成每日快照檔（建立 archive 正本）。已存在的檔不覆蓋。"""
    win = load_window()
    stocks = win.get("stocks", {})
    if not stocks:
        print("[ERR] 視窗為空，無法攤平")
        return 1
    by_date: dict[str, dict] = {}
    for c, bars in stocks.items():
        for b in bars:
            by_date.setdefault(b["d"], {})[c] = b
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    n_new = 0
    for iso, day in sorted(by_date.items()):
        if (ARCHIVE_DIR / f"{iso}.json").exists():
            continue
        write_day_snapshot(iso, day)
        n_new += 1
    print(f"[OK ] archive 攤平完成：新增 {n_new} 支（共 {len(by_date)} 個交易日）→ {ARCHIVE_DIR}")
    return 0


def _trim(bars: list[dict]) -> list[dict]:
    """去重（同日取後者）、依日期排序（舊→新）、裁到最後 N_DAYS 筆。"""
    by_d = {b["d"]: b for b in bars}
    ordered = [by_d[d] for d in sorted(by_d)]
    return ordered[-N_DAYS:]


# ── 每日模式：append 今日 daily_all OHLC ──

def daily_append() -> int:
    daily = read_json("daily_all")
    if not daily.get("ok"):
        print("[ERR] daily_all 未就緒，跳過 ohlc_window append")
        return 1
    dd = daily.get("data_date")
    if not dd:
        print("[ERR] daily_all 無 data_date，跳過")
        return 1

    win = load_window()
    stocks: dict[str, list] = win.get("stocks", {})
    today_day: dict[str, dict] = {}      # 今日全市場 → 寫 archive
    added = skipped = 0
    for s in daily["data"].get("stocks", []):
        code = s["code"]
        if len(code) != 4 or not code.isdigit():
            continue
        o, h, l, c = s.get("open"), s.get("high"), s.get("low"), s.get("close")
        v = s.get("vol")
        if o is None or h is None or l is None or c is None:
            skipped += 1            # 無 OHLC（如僅收盤的備援日）→ 不塞殘缺 bar
            continue
        bar = {"d": dd, "o": o, "h": h, "l": l, "c": c, "v": v or 0}
        today_day[code] = bar
        lst = stocks.setdefault(code, [])
        if lst and lst[-1]["d"] == dd:
            lst[-1] = bar           # 同日重跑覆蓋
        else:
            lst.append(bar)
        stocks[code] = _trim(lst)
        added += 1

    # archive（永久正本）：同日重跑會覆寫同一支，內容一致
    if today_day:
        write_day_snapshot(dd, today_day)

    win.update({"ok": True, "data_date": dd, "n_days": N_DAYS, "stocks": stocks})
    save_window(win)
    n_arc = len(list(ARCHIVE_DIR.glob("????-??-??.json"))) if ARCHIVE_DIR.exists() else 0
    print(f"[OK ] ohlc_window append data_date={dd} 更新 {added} 檔（略過無OHLC {skipped}）"
          f" 總 {len(stocks)} 檔；archive 累積 {n_arc} 個交易日")
    return 0


# ── 種子模式（主）：TWSE/TPEx 逐日抓，每呼叫回整市場一天 ──

def _fetch_twse_day(iso: str) -> dict[str, dict] | None:
    """TWSE MI_INDEX 某日全市場 OHLCV。非交易日/失敗回 None。回 {code:{o,h,l,c,v}}。"""
    d8 = iso.replace("-", "")
    try:
        j = tw_common.http_get_json(TWSE_MI_URL.format(d8=d8))
    except Exception:
        return None
    if j.get("stat") != "OK":
        return None
    table = next((t for t in j.get("tables", []) if "每日收盤行情" in t.get("title", "")), None)
    if not table or not table.get("data"):
        return None
    idx = {name: i for i, name in enumerate(table["fields"])}
    try:
        ic, io, ih, il, icl, iv = (idx["證券代號"], idx["開盤價"], idx["最高價"],
                                   idx["最低價"], idx["收盤價"], idx["成交股數"])
    except KeyError:
        return None
    out = {}
    for row in table["data"]:
        code = str(row[ic]).strip()
        if len(code) != 4 or not code.isdigit():
            continue
        o, h, l, c = parse_num(row[io]), parse_num(row[ih]), parse_num(row[il]), parse_num(row[icl])
        if None in (o, h, l, c) or c <= 0:
            continue
        out[code] = {"o": o, "h": h, "l": l, "c": c, "v": parse_num(row[iv]) or 0}
    return out or None


def _fetch_tpex_day(iso: str) -> dict[str, dict] | None:
    """TPEx dailyQuotes 某日全上櫃 OHLCV。非交易日/失敗回 None。"""
    d_slash = iso.replace("-", "/")
    try:
        j = tw_common.http_get_json(TPEX_DAY_URL.format(d_slash=d_slash))
    except Exception:
        return None
    if j.get("stat") != "ok":
        return None
    table = next((t for t in j.get("tables", []) if t.get("data")), None)
    if not table:
        return None
    idx = {name: i for i, name in enumerate(table["fields"])}
    try:
        ic, io, ih, il, icl, iv = (idx["代號"], idx["開盤"], idx["最高"],
                                   idx["最低"], idx["收盤"], idx["成交股數"])
    except KeyError:
        return None
    out = {}
    for row in table["data"]:
        code = str(row[ic]).strip()
        if len(code) != 4 or not code.isdigit():
            continue
        o, h, l, c = parse_num(row[io]), parse_num(row[ih]), parse_num(row[il]), parse_num(row[icl])
        if None in (o, h, l, c) or c <= 0:
            continue
        out[code] = {"o": o, "h": h, "l": l, "c": c, "v": parse_num(row[iv]) or 0}
    return out or None


def seed_bydate() -> int:
    """逐交易日往回抓 TWSE+TPEx，湊滿 SEED_DAYS 天 → 建視窗。零 FinMind 配額。"""
    tw_common.FETCH_INTERVAL = SEED_INTERVAL  # 覆寫成較短間隔，加速歷史回補
    series: dict[str, list] = {}
    got_days = 0
    cur = date.today()
    limit = cur - timedelta(days=SEED_LOOKBACK_LIMIT)
    print(f"[種子·按日] 目標 {SEED_DAYS} 交易日，往回抓 TWSE+TPEx…", flush=True)

    while got_days < SEED_DAYS and cur >= limit:
        if cur.weekday() >= 5:            # 週末不呼叫
            cur -= timedelta(days=1)
            continue
        iso = cur.isoformat()
        tw = _fetch_twse_day(iso)
        tp = _fetch_tpex_day(iso)
        if tw or tp:                      # 有任一市場資料 = 交易日
            day = {**(tw or {}), **(tp or {})}
            for code, bar in day.items():
                series.setdefault(code, []).append({"d": iso, **bar})
            got_days += 1
            if got_days % 20 == 0:
                print(f"[種子·按日] 已抓 {got_days}/{SEED_DAYS} 交易日（{iso}），"
                      f"{len(series)} 檔累積中…", flush=True)
        cur -= timedelta(days=1)

    if got_days == 0:
        print("[種子·按日] 沒抓到任何交易日資料（網路/端點問題）", flush=True)
        return 1

    # 各檔目前是新→舊（往回抓），反轉成舊→新、裁上限
    stocks = {code: _trim(list(reversed(bars))) for code, bars in series.items()}
    win = {"ok": True, "data_date": date.today().isoformat(), "n_days": N_DAYS,
           "stocks": stocks, "nodata": []}
    save_window(win)
    print(f"[種子·按日] 完成：{got_days} 交易日 × {len(stocks)} 檔 → {WINDOW_PATH.name}", flush=True)
    return 0


# ── 種子模式（備援）：FinMind 抓近 N 交易日 ──

def _secs_to_next_hour() -> int:
    now = datetime.now()
    nxt = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return int((nxt - now).total_seconds()) + HOUR_BUFFER


def fetch_finmind(code: str, start: str, end: str) -> tuple[list[dict], str]:
    """抓單檔區間日K。回 (bars 舊→新, status)。status: ok|quota|fail。"""
    try:
        r = requests.get(
            "https://api.finmindtrade.com/api/v4/data",
            params={"dataset": "TaiwanStockPrice", "data_id": code,
                    "start_date": start, "end_date": end, "token": FINMIND_TOKEN},
            headers=UA, timeout=40)
        j = r.json()
    except Exception:
        return [], "fail"
    st = j.get("status")
    msg = str(j.get("msg", ""))
    if st != 200:
        if st == 402 or "upper limit" in msg.lower():
            return [], "quota"
        return [], "fail"
    bars = []
    for x in j.get("data", []):
        try:
            bars.append({"d": x["date"], "o": float(x["open"]), "h": float(x["max"]),
                         "l": float(x["min"]), "c": float(x["close"]),
                         "v": float(x["Trading_Volume"])})
        except (KeyError, TypeError, ValueError):
            continue
    return bars, "ok"


def _covered(bars: list[dict], start: str) -> bool:
    """已抓過且最早 bar ≤ start 之月 → resume 跳過。"""
    return bool(bars) and bars[0]["d"][:7] <= start[:7]


def seed_finmind() -> int:
    if not FINMIND_TOKEN:
        print("[ERR] 無 FINMIND_TOKEN。export FINMIND_TOKEN=... 後重跑種子。")
        return 1

    # 目標股票清單：用 daily_all 的 4 碼個股（含 ETF；排除權證等 6 碼）
    daily = read_json("daily_all")
    if not daily.get("ok"):
        print("[ERR] 需先跑 fetch_daily_all 取得股票清單")
        return 1
    codes = sorted({s["code"] for s in daily["data"].get("stocks", [])
                    if len(s["code"]) == 4 and s["code"].isdigit()})

    end = date.today().isoformat()
    start = (date.today() - timedelta(days=400)).isoformat()  # 260 交易日 ≈ 375 天，多墊
    print(f"[種子] {len(codes)} 檔，區間 {start}~{end}，視窗裁 {N_DAYS} 交易日")

    win = load_window()
    stocks: dict[str, list] = win.get("stocks", {})
    nodata: set[str] = set(win.get("nodata", []))  # FinMind 無資料的碼（ETF/停牌等）→ 不重抓白燒配額
    done = skipped = failed = consec_fail = 0

    i = 0
    while i < len(codes):
        code = codes[i]
        if _covered(stocks.get(code, []), start) or code in nodata:
            skipped += 1
            i += 1
            continue

        bars, status = fetch_finmind(code, start, end)

        if status == "quota":
            win.update({"stocks": stocks, "nodata": sorted(nodata)})
            save_window(win)
            wait = _secs_to_next_hour()
            print(f"[種子] 配額爆（已存 {len(stocks)}/{len(codes)}）→ 睡 {wait//60} 分到整點續跑…", flush=True)
            time.sleep(wait)
            continue                      # 不動 i，醒來重試同一檔
        if status == "fail":
            failed += 1
            consec_fail += 1
            if consec_fail >= FAIL_STOP:
                win.update({"stocks": stocks, "nodata": sorted(nodata)})
                save_window(win)
                print(f"[種子] 連 {FAIL_STOP} 檔失敗自停（已存 {len(stocks)}），重跑接著補。", flush=True)
                return 1
            time.sleep(SLEEP_BACKOFF)
            i += 1
            continue

        consec_fail = 0
        if bars:
            stocks[code] = _trim(bars)
            done += 1
        else:
            nodata.add(code)          # 抓成功但空資料 → 記下，下輪不再請求（省配額）
        i += 1
        time.sleep(SLEEP_OK)
        if i % SAVE_EVERY == 0:
            win.update({"stocks": stocks, "nodata": sorted(nodata)})
            save_window(win)
            print(f"[種子] {i}/{len(codes)}：新增 {done} 跳過 {skipped} 失敗 {failed} 無資料 {len(nodata)}", flush=True)

    win.update({"ok": True, "data_date": end, "n_days": N_DAYS,
                "stocks": stocks, "nodata": sorted(nodata)})
    save_window(win)
    print(f"[種子] 完成：新增 {done} 跳過 {skipped} 失敗 {failed} 無資料 {len(nodata)}，"
          f"總 {len(stocks)} 檔 → {WINDOW_PATH.name}", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="store_true",
                    help="一次性種子回補（TWSE/TPEx 按日，建議）")
    ap.add_argument("--seed-finmind", action="store_true",
                    help="一次性種子回補（FinMind 逐檔，備援；需 FINMIND_TOKEN）")
    ap.add_argument("--from-archive", action="store_true",
                    help="由 data/history_ohlc/ 重建視窗（cache miss 用；零網路）")
    ap.add_argument("--materialize-archive", action="store_true",
                    help="一次性：把現有視窗攤成每日快照檔，建立 archive 正本")
    args = ap.parse_args()
    if args.seed_finmind:
        return seed_finmind()
    if args.seed:
        return seed_bydate()
    if args.from_archive:
        return rebuild_from_archive()
    if args.materialize_archive:
        return materialize_archive()
    return daily_append()


if __name__ == "__main__":
    raise SystemExit(main())
