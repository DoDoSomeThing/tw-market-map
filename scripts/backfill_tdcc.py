#!/usr/bin/env python3
"""backfill_tdcc.py — 回填 TDCC 集保股權分散歷史 → data/history_tdcc/

緣起（2026-07-17）：大戶級距切換（200/400/800/1000 張）+ 期間切換（1/2/3/4 週）需要歷史快照，
但 history_tdcc/ 只有 2 支（功能 2026-07-03 才上線，git 歷史也翻過，沒有更舊的）。

為什麼不能用 opendata CSV 回填：
  opendata getOD.ashx?id=1-5 只給「當週」，沒有日期參數。
  歷史只能走查詢頁 https://www.tdcc.com.tw/portal/zh/smWeb/qryStock，
  它有 51 週下拉（約一年），但**一次只能查一檔**（POST 帶 stockNo）→ 全市場要 1959 次/週。

已驗證兩條路數字一致（2330 @ 2026-07-09）：
  查詢頁級距 15 = 85.01     → 對上 CSV 快照 r1000 = 85.01
  查詢頁 12+13+14+15 = 87.74 → 對上 CSV 快照 r400  = 87.74

用法（跑很久，建議本機、可中斷續跑）：
  python scripts/backfill_tdcc.py --list                 # 只列出可回填的週次，不抓
  python scripts/backfill_tdcc.py --weeks 5              # 回填最近 5 個週次（1/2/3/4 週對比需要 5 支快照）
  python scripts/backfill_tdcc.py --dates 20260626,20260618
  python scripts/backfill_tdcc.py --weeks 5 --limit 20   # 先小量試水溫
  python scripts/backfill_tdcc.py --verify 20260709      # 拿現有 CSV 快照對答案，不寫檔

中斷了直接重跑同一行：已抓到的個股會跳過（進度存在 <date>.partial.json）。

坑（都是 2026-07-17 實際踩過的，別再踩一次）：
  - TDCC 憑證缺 Subject Key Identifier，新版 OpenSSL 直接拒收 → requests 必噴 SSLError，
    全程走 curl（Mac/Windows 都有）。
  - POST 要帶 SYNCHRONIZER_TOKEN（CSRF）+ cookie，而且 token 是**一次性**的：
    同一顆連打第二發，TDCC 不報錯，只回一頁沒有表格的空表單。
    每次回應都夾帶下一顆 token → 接住它就能一直打。
  - 「token 死了」和「這檔真的沒資料」兩種回應長得一樣，都是沒表格。
    不要用頁面文字判斷——「請輸入證券代號」那串字在**成功的頁面裡也一直都在**。
    唯一可靠：重取 token 再問一次，還是沒表格才當真沒有（見 fetch_one）。
  - 查詢頁的「合計」是級距 16，opendata CSV 卻是 17（CSV 多一個「差異數調整」）
    → 別照抄 fetch_tdcc 的常數。
  - 對方是公務網站，別把 --sleep 調到 0。被擋就是自己害的。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tw_common import DATA_DIR, UA, read_json, ymd_to_iso  # noqa: E402

PAGE = "https://www.tdcc.com.tw/portal/zh/smWeb/qryStock"
HISTORY_DIR = DATA_DIR / "history_tdcc"

# 集保級距（查詢頁）：11=200,001-400,000股 12=400,001-600,000 13=600,001-800,000
# 14=800,001-1,000,000 15=1,000,001以上 16=合計。張 = 股 / 1000。
LV_200 = {"11", "12", "13", "14", "15"}   # 200 張以上
LV_400 = {"12", "13", "14", "15"}         # 400 張以上
LV_800 = {"14", "15"}                     # 800 張以上
LV_1000 = {"15"}                          # 千張以上


def curl(args: list[str], timeout: int = 60) -> str:
    p = subprocess.run(["curl", "-s", "--max-time", "40", "-H", f"User-Agent: {UA['User-Agent']}"] + args,
                       capture_output=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"curl exit={p.returncode}")
    return p.stdout.decode("utf-8", "replace")


TOKEN_RE = re.compile(r'name="SYNCHRONIZER_TOKEN"\s+value="([^"]*)"')


class Session:
    """cookie jar + CSRF token。

    坑（2026-07-17 實測）：token 是**一次性**的。用同一顆連打第二發，TDCC 不會報錯，
    只會回一個「請輸入證券代號」的空表單頁 → 看起來像「這檔查無資料」，其實是 token 過期。
    每次回應都夾帶下一顆 token，接著用就好；斷了才 refresh()。
    """

    def __init__(self) -> None:
        self.jar = Path(tempfile.gettempdir()) / "tdcc_backfill_cookies.txt"
        self.token = ""
        self.dates: list[str] = []
        self.refresh()

    def refresh(self) -> None:
        html = curl(["-c", str(self.jar), PAGE])
        m = TOKEN_RE.search(html)
        if not m:
            raise RuntimeError("查詢頁抓不到 SYNCHRONIZER_TOKEN（版型可能改了）")
        self.token = m.group(1)
        self.dates = re.findall(r'<option[^>]*value="(\d{8})"', html)

    def query(self, code: str, d8: str) -> str:
        data = (f"SYNCHRONIZER_TOKEN={self.token}&SYNCHRONIZER_URI=/portal/zh/smWeb/qryStock"
                f"&method=submit&sqlMethod=StockNo&firDate=&scaDate={d8}"
                f"&stockNo={code}&stockName=")
        html = curl(["-b", str(self.jar), "-c", str(self.jar), "-X", "POST",
                     "-H", "Content-Type: application/x-www-form-urlencoded",
                     "--data", data, PAGE])
        m = TOKEN_RE.search(html)      # 接住下一顆，沒接到就等呼叫端 refresh
        if m:
            self.token = m.group(1)
        return html


def parse_levels(html: str) -> dict[str, float] | None:
    """回 {級距: 佔集保庫存比%}。查無資料回 None。"""
    out: dict[str, float] = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).replace("\xa0", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) != 5 or not re.fullmatch(r"\d+", cells[0]):
            continue
        try:
            out[cells[0]] = float(cells[4])
        except ValueError:
            continue
    # 沒有級距 15 就當這檔沒資料（下市/該週未列入）
    return out if "15" in out else None


def fetch_one(sess: Session, code: str, d8: str, sleep: float) -> dict[str, float] | None:
    """回 levels，或 None＝該週真的沒這檔。

    坑：token 過期時 TDCC 不報錯，只回一頁「沒有表格的空表單」，外觀跟「這檔沒資料」一樣。
    別想用頁面文字分辨——「請輸入證券代號」那串字在**成功的頁面裡也一直都在**
    （2026-07-17 踩過：拿它當判斷 → 每一檔都被誤判成被拒）。
    唯一可靠的辦法是重取 token 再問一次：還是沒表格，才當真的沒有。
    """
    lv = parse_levels(sess.query(code, d8))
    if lv:
        return lv
    sess.refresh()
    time.sleep(sleep)
    return parse_levels(sess.query(code, d8))


def to_record(levels: dict[str, float]) -> list[float]:
    """[r200, r400, r800, r1000]，單位 %。"""
    def s(keys):
        return round(sum(levels.get(k, 0.0) for k in keys), 2)
    return [s(LV_200), s(LV_400), s(LV_800), s(LV_1000)]


def stock_codes(limit: int | None) -> list[str]:
    env = read_json("daily_all")
    if not env.get("ok"):
        raise RuntimeError("daily_all.json 讀不到 → 先跑 fetch_daily_all.py")
    codes = sorted({s["code"] for s in env["data"].get("stocks", [])
                    if len(s["code"]) == 4 and s["code"].isdigit()})
    return codes[:limit] if limit else codes


def verify(sess: Session, d8: str, n: int) -> int:
    """拿查詢頁的數字對現有 CSV 快照（只比 r400/r1000，舊格式就這兩個）。回不符筆數。"""
    iso = ymd_to_iso(d8)
    p = HISTORY_DIR / f"{iso}.json"
    if not p.exists():
        print(f"沒有 {iso} 的既有快照可對照")
        return -1
    snap = json.loads(p.read_text(encoding="utf-8"))
    codes = [c for c in stock_codes(None) if c in snap][:n]
    bad = 0
    for c in codes:
        lv = fetch_one(sess, c, d8, 0.5)
        if not lv:
            print(f"  {c} 查無資料（該週未列入）")
            continue
        r = to_record(lv)
        old = snap[c]
        ok400 = abs(r[1] - old[0]) < 0.01
        ok1000 = abs(r[3] - old[-1]) < 0.01
        if not (ok400 and ok1000):
            bad += 1
        print(f"  {c} r400 {r[1]:>6} vs {old[0]:>6} {'OK' if ok400 else 'X'}"
              f"   r1000 {r[3]:>6} vs {old[-1]:>6} {'OK' if ok1000 else 'X'}")
        time.sleep(0.5)
    print(f"\n對照 {len(codes)} 檔，不符 {bad} 筆")
    return bad


def backfill_date(sess: Session, d8: str, codes: list[str], sleep: float,
                  token_every: int, partial_only: bool = False) -> None:
    iso = ymd_to_iso(d8)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    final = HISTORY_DIR / f"{iso}.json"
    part = HISTORY_DIR / f"{iso}.partial.json"

    # 續跑：已抓到的跳過
    done: dict[str, list[float]] = {}
    if part.exists():
        done = json.loads(part.read_text(encoding="utf-8"))
        print(f"  接續上次：已有 {len(done)} 檔")

    todo = [c for c in codes if c not in done]
    print(f"  {iso}：待抓 {len(todo)} / {len(codes)} 檔")
    t0 = time.time()
    miss = fails = 0
    for i, code in enumerate(todo, 1):
        if token_every and i % token_every == 0:
            sess.refresh()          # 保險：正常情況每次回應都會換新 token，用不到這行
        try:
            lv = fetch_one(sess, code, d8, sleep)
        except Exception as e:
            fails += 1
            print(f"    {code} 例外：{e}（跳過，重跑會補）")
            if fails >= 20:
                part.write_text(json.dumps(done, separators=(",", ":")), encoding="utf-8")
                raise SystemExit("連續失敗過多 → 很可能被 TDCC 限速。進度已存，過幾小時再跑同一行續抓。")
            time.sleep(sleep * 6)
            continue
        fails = 0
        if lv:
            done[code] = to_record(lv)
        else:
            miss += 1
        if i % 25 == 0 or i == len(todo):
            part.write_text(json.dumps(done, separators=(",", ":")), encoding="utf-8")
            el = time.time() - t0
            eta = el / i * (len(todo) - i)
            print(f"    {i}/{len(todo)}  已存 {len(done)}  查無 {miss}  "
                  f"已花 {el/60:.1f} 分  剩約 {eta/60:.1f} 分", flush=True)
        time.sleep(sleep)

    part.write_text(json.dumps(done, separators=(",", ":")), encoding="utf-8")
    if partial_only:
        # --limit 是試水溫用的。少了這道，20 檔的測試跑會產出一支「看起來完成」的正式快照
        #（九成檢查拿 20/20 去比 → 直接通過），假快照混進 history_tdcc 會毀掉整個期間對比。
        print(f"  {iso} 試跑模式（--limit）→ 只留 {part.name}，不產正式快照")
        return
    if len(done) >= len(codes) * 0.9:      # 抓到九成以上才算完成（其餘多半是當週未列入的股）
        final.write_text(json.dumps(done, separators=(",", ":")), encoding="utf-8")
        part.unlink(missing_ok=True)
        print(f"  {iso} 完成 → {final.name}（{len(done)} 檔）")
    else:
        print(f"  {iso} 只抓到 {len(done)}/{len(codes)}，未達九成 → 保留 partial，重跑續抓")


def main() -> None:
    ap = argparse.ArgumentParser(description="回填 TDCC 集保股權分散歷史")
    ap.add_argument("--weeks", type=int, default=5,
                    help="回填最近幾個週次（預設 5：1/2/3/4 週對比需要 5 支快照）")
    ap.add_argument("--dates", help="指定週次，逗號分隔（如 20260626,20260618）")
    ap.add_argument("--limit", type=int, help="只抓前 N 檔（試水溫用）")
    ap.add_argument("--sleep", type=float, default=0.5, help="每檔間隔秒數（別調 0，對方是公務網站）")
    ap.add_argument("--token-every", type=int, default=200, help="每幾檔重取一次 CSRF token")
    ap.add_argument("--list", action="store_true", help="只列可回填的週次")
    ap.add_argument("--verify", metavar="YYYYMMDD", help="對照既有 CSV 快照，不寫檔")
    ap.add_argument("--force", action="store_true", help="已有完成檔也重抓")
    args = ap.parse_args()

    sess = Session()
    print(f"查詢頁 OK，可選週次 {len(sess.dates)} 個：{sess.dates[0]} ~ {sess.dates[-1]}")

    if args.list:
        for i, d in enumerate(sess.dates):
            mark = " ← 已有快照" if (HISTORY_DIR / f"{ymd_to_iso(d)}.json").exists() else ""
            print(f"  {i+1:>2}. {d}{mark}")
        return

    if args.verify:
        sys.exit(1 if verify(sess, args.verify, args.limit or 5) > 0 else 0)

    dates = args.dates.split(",") if args.dates else sess.dates[:args.weeks]
    bad = [d for d in dates if d not in sess.dates]
    if bad:
        print(f"這些週次查詢頁沒有：{bad}")
        return

    codes = stock_codes(args.limit)
    todo = [d for d in dates
            if args.force or not (HISTORY_DIR / f"{ymd_to_iso(d)}.json").exists()
            or (HISTORY_DIR / f"{ymd_to_iso(d)}.partial.json").exists()]
    skip = [d for d in dates if d not in todo]
    if skip:
        print(f"已完成、跳過：{skip}（要重抓加 --force）")

    total = len(todo) * len(codes)
    print(f"\n將抓 {len(todo)} 個週次 × {len(codes)} 檔 = {total:,} 次請求")
    # 實測（2026-07-17，Windows）：--sleep 0.4 時每檔約 0.6 秒 → 請求本身約 0.2 秒
    print(f"間隔 {args.sleep}s → 粗估 {total * (args.sleep + 0.2) / 3600:.1f} 小時（可中斷，重跑續抓）\n")

    for d in todo:
        backfill_date(sess, d, codes, args.sleep, args.token_every,
                      partial_only=bool(args.limit))

    print("\n全部完成。接著跑 build_tdcc_view.py（或 run_all.py）產出級距/期間對比。")


if __name__ == "__main__":
    main()
