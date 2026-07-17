# tw_common.py — tw-market-map 共用工具
# freshness 守門移植自 tw-stock-bot/tw_common.py（2026-07-01 Y9999 bug 教訓）
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"

# ── 時區單一真相（2026-07-17）──
# 本站處理的全是台股資料，「今天/現在」一律指台北時間。
# 踩坑：原本用 datetime.now()／date.today()／astimezone()（跟著執行機器的時區跑）→
# 本機（台北）測都對，但 GitHub Actions runner 是 UTC → 線上新聞時間少 8 小時、
# freshness 在台北 08:00 前會把「今天」當成昨天而誤判過期。一律改用下列函式。
TW_TZ = timezone(timedelta(hours=8))


def tw_now() -> datetime:
    """現在（台北）。不受執行機器時區影響。"""
    return datetime.now(TW_TZ)


def tw_today():
    """今天（台北日期）。"""
    return tw_now().date()

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tw-market-map/1.0"}
FETCH_INTERVAL = 3.0  # TWSE/TPEx 連續請求間隔秒數（防封 IP）

_last_fetch = [0.0]


def _curl_get_json(url: str, timeout: int):
    """requests SSL 失敗時的備援（Mac LibreSSL 對 TPEx 部分節點憑證過度嚴格；curl 走系統信任鏈）。"""
    import subprocess
    r = subprocess.run(
        ["curl", "-s", "--max-time", str(timeout), "-H", f"User-Agent: {UA['User-Agent']}", url],
        capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout:
        raise RuntimeError(f"curl exit={r.returncode}")
    return json.loads(r.stdout)


def http_get_json(url: str, *, timeout: int = 30, retries: int = 2):
    """帶間隔與重試的 GET，回 parsed JSON。失敗 raise。"""
    for attempt in range(retries + 1):
        wait = FETCH_INTERVAL - (time.time() - _last_fetch[0])
        if wait > 0:
            time.sleep(wait)
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            _last_fetch[0] = time.time()
            r.raise_for_status()
            return r.json()
        except requests.exceptions.SSLError:
            _last_fetch[0] = time.time()
            return _curl_get_json(url, timeout)
        except Exception:
            if attempt >= retries:
                raise
            time.sleep(5 * (attempt + 1))


def roc_to_iso(roc: str) -> str | None:
    """民國日期 '1150703' / '115/07/03' → '2026-07-03'。解析失敗回 None。"""
    if not roc:
        return None
    s = str(roc).replace("/", "").strip()
    if not s.isdigit() or len(s) < 6:
        return None
    y, md = int(s[:-4]), s[-4:]
    try:
        return f"{y + 1911:04d}-{md[:2]}-{md[2:]}"
    except ValueError:
        return None


def ymd_to_iso(ymd: str) -> str | None:
    """'20260706' → '2026-07-06'。"""
    s = str(ymd).strip()
    if len(s) != 8 or not s.isdigit():
        return None
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def parse_num(s) -> float | None:
    """'347,168,147,530' / '-0.84 ' / '--' → float 或 None。"""
    if s is None:
        return None
    t = str(s).replace(",", "").strip()
    if t in ("", "--", "-", "X", "N/A"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


# ── 資料新鮮度守門 ──

def data_age_days(data_date: str) -> int | None:
    """data_date 'YYYY-MM-DD' → 距今幾個「交易日」(跳過六日；None=解析失敗)。"""
    if not data_date:
        return None
    try:
        d = datetime.strptime(str(data_date)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
    today = tw_today()
    if d >= today:
        return 0
    age = 0
    cur = today
    while cur > d:
        cur -= timedelta(days=1)
        if cur.weekday() < 5:
            age += 1
    return age


def _fmt_mmdd(data_date: str | None) -> str:
    try:
        return datetime.strptime(str(data_date)[:10], "%Y-%m-%d").strftime("%m/%d")
    except (ValueError, TypeError):
        return str(data_date) if data_date else "?"


def freshness_tag(data_date: str, max_stale: int = 2) -> tuple[bool, str]:
    """回 (是否新鮮, 標籤)。逾 max_stale 交易日 → (False, '⚠️資料為 MM/DD，可能過期')。"""
    age = data_age_days(data_date)
    if age is None:
        return False, "⚠️資料日期無法解析"
    if age > max_stale:
        return False, f"⚠️資料為 {_fmt_mmdd(data_date)}，可能過期（{age} 交易日前）"
    return True, ""


def sanity_check_pct(pct: float, limit: float = 10.0) -> bool:
    """台股單日漲跌 |%| 上限檢查（漲跌停板 ±10%）。"""
    try:
        return abs(float(pct)) <= limit + 0.05
    except (TypeError, ValueError):
        return False


# ── 題材關鍵字比對（時事雷達；fetch_news / build_news_radar 共用）──

def build_topic_matcher(topics_cfg: dict):
    """topics.json cfg → callable(text) -> [topic_id]。
    中文(含 CJK)關鍵字用子字串比對；純 ASCII 關鍵字用整字比對(避免 'VC' 誤中 'PVC')。
    題材名自動納入關鍵字（'CPO/矽光子' 以 '/' 切開各自成關鍵字）。"""
    import re as _re

    def is_ascii(s: str) -> bool:
        return all(ord(c) < 128 for c in s)

    rules = []  # (topic_id, [中文子字串], compiled_ascii_regex|None)
    for t in topics_cfg.get("topics", []):
        kws = list(t.get("keywords", []))
        for part in str(t.get("name", "")).split("/"):
            p = part.strip()
            if p and p not in kws:
                kws.append(p)
        cjk = [k for k in kws if not is_ascii(k)]
        ascii_kws = [k for k in kws if is_ascii(k) and len(k) >= 2]
        pat = None
        if ascii_kws:
            alt = "|".join(_re.escape(k) for k in sorted(ascii_kws, key=len, reverse=True))
            pat = _re.compile(rf"(?<![A-Za-z0-9])(?:{alt})(?![A-Za-z0-9])", _re.IGNORECASE)
        rules.append((t["id"], cjk, pat))

    def match(text: str) -> list[str]:
        hits = []
        for tid, cjk, pat in rules:
            if any(k in text for k in cjk) or (pat and pat.search(text)):
                hits.append(tid)
        return hits

    return match


# ── JSON 輸出（統一信封格式）──

def write_json(name: str, payload: dict, *, data_date: str | None, source: str,
               ok: bool = True, error: str | None = None) -> None:
    """data/<name>.json，信封：ok / data_date / fetched_at / source / error / data。"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    env = {
        "ok": ok,
        "data_date": data_date,
        "fetched_at": tw_now().strftime("%Y-%m-%d %H:%M:%S"),  # 台北時間（Actions 是 UTC）
        "source": source,
        "error": error,
        "data": payload,
    }
    out = DATA_DIR / f"{name}.json"
    out.write_text(json.dumps(env, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tag = "OK " if ok else "ERR"
    print(f"[{tag}] data/{name}.json data_date={data_date} {error or ''}")


def write_error(name: str, source: str, error: str) -> None:
    """抓取失敗時寫錯誤信封（render 端顯示 ⚠️，絕不拿舊資料裝新鮮）。"""
    write_json(name, {}, data_date=None, source=source, ok=False, error=error[:300])


def read_json(name: str) -> dict:
    """讀 data/<name>.json 信封；不存在回 ok=False 信封。"""
    p = DATA_DIR / f"{name}.json"
    if not p.exists():
        return {"ok": False, "data_date": None, "fetched_at": None,
                "source": name, "error": "檔案不存在（尚未抓取）", "data": {}}
    return json.loads(p.read_text(encoding="utf-8"))
