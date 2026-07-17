# fetch_dividend.py — 除權息預告（即將除息的實際交易日）→ data/dividend.json
# 源：TWSE 除權除息預告表 rwd TWT48U（上市；含除息交易日 + 本次現金股利，比股利政策表即時）。
# 上櫃 TPEx 無穩定 openapi → 誠實缺（同 fundamentals 上櫃無股利的既有限制）。
# 解決「殖利率抓到去年股利」：這支是「即將除息」清單，cash = 本輪實際要配的現金。
from __future__ import annotations

import re
import subprocess
from datetime import datetime, timedelta

from tw_common import UA, read_json, tw_now, write_error, write_json

TWT48U = "https://www.twse.com.tw/rwd/zh/exRight/TWT48U?response=json"
TAG = re.compile(r"<[^>]+>")
ROC = re.compile(r"(\d+)年(\d+)月(\d+)日")


def fetch_json(url: str):
    import requests
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception:
        p = subprocess.run(["curl", "-s", "--max-time", "30",
                            "-H", f"User-Agent: {UA['User-Agent']}", url],
                           capture_output=True, text=True, timeout=45)
        if p.returncode != 0 or not p.stdout:
            raise RuntimeError(f"curl exit={p.returncode}")
        import json
        return json.loads(p.stdout)


def roc_to_iso(s: str) -> str | None:
    m = ROC.match(str(s).strip())
    if not m:
        return None
    return f"{int(m[1]) + 1911:04d}-{int(m[2]):02d}-{int(m[3]):02d}"


def last_buy_day(ex_iso: str) -> str:
    """最後買進日=除息日的前一個「交易日」（跳六日；不含國定連假，故標『約』）。"""
    d = datetime.strptime(ex_iso, "%Y-%m-%d").date() - timedelta(days=1)
    while d.weekday() >= 5:   # 5=六、6=日
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def main() -> None:
    try:
        j = fetch_json(TWT48U)
    except Exception as e:
        write_error("dividend", "TWSE TWT48U 除權息預告", str(e))
        return
    if j.get("stat") != "OK" or not j.get("data"):
        write_error("dividend", "TWSE TWT48U 除權息預告", f"stat={j.get('stat')}")
        return

    daily = read_json("daily_all")
    info = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}
    today = tw_now().strftime("%Y-%m-%d")

    items: list[dict] = []
    by_code: dict[str, dict] = {}
    for r in j["data"]:
        # 欄位：除權除息日期 / 股票代號 / 名稱 / 除權息 / … / 現金股利(第7欄，含 HTML)
        ex_date = roc_to_iso(r[0])
        code = str(r[1]).strip()
        name = str(r[2]).strip()
        typ = str(r[3]).strip()   # 息 / 權 / 權息
        if not ex_date or len(code) != 4 or not code.isdigit():
            continue
        cash_raw = TAG.sub("", str(r[7])).strip()
        try:
            cash = round(float(cash_raw), 4)
        except ValueError:
            cash = None   # 「待公告實際收益分配金額」（多為 ETF）
        s = info.get(code)
        close = s.get("close") if s else None
        item = {
            "code": code, "name": name, "ex_date": ex_date, "type": typ,
            "last_buy": last_buy_day(ex_date),
            "cash": cash, "close": close,
            "industry": s.get("industry") if s else None,
            "yield_pct": round(cash / close * 100, 2) if (cash and close) else None,
        }
        items.append(item)
        # by_code 取最近一次（同檔可能多筆，取除息日最早且 ≥ 今天）
        if ex_date >= today:
            cur = by_code.get(code)
            if not cur or ex_date < cur["ex_date"]:
                by_code[code] = {"ex_date": ex_date, "last_buy": last_buy_day(ex_date),
                                 "cash": cash, "type": typ}

    # 近期除息榜：只留今天(含)以後，依除息日近→遠
    upcoming = sorted((it for it in items if it["ex_date"] >= today),
                      key=lambda x: (x["ex_date"], -(x["yield_pct"] or 0)))

    write_json("dividend", {
        "upcoming": upcoming[:60],
        "by_code": by_code,
        "n_total": len(items),
    }, data_date=today, source="TWSE TWT48U 除權息預告表（上市；上櫃無資料）",
        error=None)
    print(f"     即將除息 {len(upcoming)} 檔（上市）")


if __name__ == "__main__":
    main()
