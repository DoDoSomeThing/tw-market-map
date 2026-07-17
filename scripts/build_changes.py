# build_changes.py — 今日異動：比對今日 vs 昨日資料，產「今天跟昨天不一樣的事」→ data/changes.json
# 規則全部寫死可驗證（非 AI 判斷）：
#   法人轉向   = 之前連買/連賣 ≥3 日、今日翻向（外資另設金額門檻濾雜訊）
#   連買達標   = 今日剛好湊滿連 3 日
#   新聞點名   = 今日新聞標題提及 ≥2 則
#   重大公告   = 當日 MOPS 澄清/重大
#   營收發布   = 本次批次新出現的代號（比對上次快照 data/changes_state.json）
#   題材聲量   = 今日 ≥5 則且 ≥ 昨日 2 倍
#   大盤寬度   = 下跌 ≥60% / 上漲 ≥60% / 漲停 ≥15 檔 / 上漲值占比 ≤30 或 ≥70
# 個股事件全量輸出（自選股在瀏覽器端才知道，由前端優先顯示自選 + 摺疊其餘）。
from __future__ import annotations

import json
from datetime import datetime

from build_inst_rank import HISTORY_DIR, streak
from tw_common import DATA_DIR, read_json, tw_now, write_json

STATE_PATH = DATA_DIR / "changes_state.json"
HIST_NEWS = DATA_DIR / "history_news"
FLIP_MIN_VALUE = 30_000_000   # 外資翻向的估值門檻（3 千萬），投信不設（部位小但指標性高）
NEWS_MIN = 2                  # 新聞點名門檻（則）


def main() -> None:
    daily = read_json("daily_all")
    quotes = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}

    stock_events: list[dict] = []   # {t, code, name, txt, v(排序用成交值)}
    market_events: list[dict] = []
    topic_events: list[dict] = []

    def add_stock(t: str, code: str, txt: str) -> None:
        q = quotes.get(code)
        if not q:
            return
        stock_events.append({"t": t, "code": code, "name": q["name"],
                             "txt": txt, "v": q.get("value") or 0})

    # ── 法人轉向 / 連買達標（history_t86 序列，最新檔=今日）──
    t86 = read_json("t86")
    t86_date = t86.get("data_date")
    files = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)
    if t86.get("ok") and len(files) >= 2 and files[0].stem == t86_date:
        snaps = [json.loads(f.read_text(encoding="utf-8")) for f in files[:8]]
        today_snap, prev_snaps = snaps[0], snaps[1:]
        closes = {c: q["close"] for c, q in quotes.items()}
        for code, (f_now, t_now) in today_snap.items():
            if len(code) != 4 or not code.isdigit() or code not in quotes:
                continue
            close = closes.get(code) or 0
            pf = streak([s.get(code, [0, 0])[0] for s in prev_snaps])
            pt = streak([s.get(code, [0, 0])[1] for s in prev_snaps])
            # 外資（帶金額門檻）
            if abs(f_now * close) >= FLIP_MIN_VALUE:
                if pf >= 3 and f_now < 0:
                    add_stock("flip", code, f"外資連買 {pf} 日 → 今轉賣 {round(-f_now/1000):,} 張")
                elif pf <= -3 and f_now > 0:
                    add_stock("flip", code, f"外資連賣 {-pf} 日 → 今轉買 {round(f_now/1000):,} 張")
                elif pf == 2 and f_now > 0:
                    add_stock("streak", code, f"外資連買達 3 日（今 +{round(f_now/1000):,} 張）")
            # 投信
            if pt >= 3 and t_now < 0:
                add_stock("flip", code, f"投信連買 {pt} 日 → 今轉賣 {round(-t_now/1000):,} 張")
            elif pt <= -3 and t_now > 0:
                add_stock("flip", code, f"投信連賣 {-pt} 日 → 今轉買 {round(t_now/1000):,} 張")
            elif pt == 2 and t_now > 0:
                add_stock("streak", code, f"投信連買達 3 日（今 +{round(t_now/1000):,} 張）")

    # ── 重大公告（當日 澄清/重大；同公司近似主旨去重）──
    mops = read_json("mops")
    if mops.get("ok"):
        seen_mops = set()
        for it in mops["data"].get("items", []):
            if it.get("date") == mops.get("data_date") and it.get("tag") in ("澄清", "重大"):
                key = (it["code"], it["subject"][:24])
                if key in seen_mops:
                    continue
                seen_mops.add(key)
                add_stock("mops", it["code"], f"【{it['tag']}】{it['subject'][:48]}")

    # ── 新聞點名（今日 ≥2 則）──
    news = read_json("news")
    news_date = news.get("data_date")
    if news.get("ok"):
        cnt: dict[str, int] = {}
        latest: dict[str, str] = {}
        for it in news["data"].get("items", []):
            if str(it.get("time", ""))[:10] != news_date:
                continue
            for s in it.get("stocks", []):
                code = s.split()[-1]
                cnt[code] = cnt.get(code, 0) + 1
                latest.setdefault(code, it["title"])
        for code, n in cnt.items():
            if n >= NEWS_MIN:
                add_stock("news", code, f"今日被 {n} 則新聞點名：{latest[code][:36]}…")

    # ── 營收發布（比對上次快照的新代號）──
    rev = read_json("revenue_hl")
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    if rev.get("ok"):
        rev_stocks = rev["data"].get("stocks", {})
        prev_codes = set(state.get("revenue_codes", []))
        ym = rev["data"].get("ym_label", "")
        if prev_codes and state.get("revenue_ym") == ym:
            for code, (rv, yoy, mom) in rev_stocks.items():
                if code in prev_codes or code not in quotes:
                    continue
                yy = f"YoY {'+' if (yoy or 0) >= 0 else ''}{yoy}%" if yoy is not None else ""
                mm = f"MoM {'+' if (mom or 0) >= 0 else ''}{mom}%" if mom is not None else ""
                add_stock("rev", code, f"公布{ym}營收 {rv} 億 {yy} {mm}".rstrip())
        STATE_PATH.write_text(json.dumps(
            {"revenue_codes": sorted(rev_stocks), "revenue_ym": ym,
             "saved_at": tw_now().strftime("%Y-%m-%d %H:%M")},
            ensure_ascii=False), encoding="utf-8")

    # ── 題材聲量暴增（今日 ≥5 且 ≥ 昨日 2 倍）──
    tv = read_json("topics_view")
    id2name = {t["id"]: t["name"] for t in tv["data"].get("topics", [])} if tv.get("ok") else {}
    hist = sorted(HIST_NEWS.glob("????-??-??.json"), reverse=True) if HIST_NEWS.exists() else []
    if len(hist) >= 2:
        def topic_counts(p) -> dict[str, int]:
            out: dict[str, int] = {}
            try:
                for it in json.loads(p.read_text(encoding="utf-8")):
                    for tid in it.get("topic_ids", []):
                        out[tid] = out.get(tid, 0) + 1
            except Exception:
                pass
            return out
        today_c, prev_c = topic_counts(hist[0]), topic_counts(hist[1])
        for tid, n in sorted(today_c.items(), key=lambda kv: -kv[1]):
            p = prev_c.get(tid, 0)
            if n >= 5 and n >= 2 * max(p, 1):
                topic_events.append({"t": "surge", "id": tid, "name": id2name.get(tid, tid),
                                     "txt": f"聲量 {n} 則（昨日 {p} 則）"})

    # ── 大盤寬度極端 ──
    br = read_json("breadth")
    if br.get("ok"):
        d = br["data"]
        n = d.get("n") or 1
        down_pct = d.get("down", 0) / n * 100
        up_pct = d.get("up", 0) / n * 100
        uv = d.get("up_value_pct")
        if down_pct >= 60:
            market_events.append({"t": "breadth", "list": "top_down", "txt": f"偏空寬度：{down_pct:.0f}% 個股下跌"})
        elif up_pct >= 60:
            market_events.append({"t": "breadth", "list": "top_up", "txt": f"普漲行情：{up_pct:.0f}% 個股上漲"})
        if (d.get("limit_up") or 0) >= 15:
            market_events.append({"t": "breadth", "list": "limit_up", "txt": f"漲停 {d['limit_up']} 檔（投機情緒偏熱）"})
        if uv is not None and (uv <= 30 or uv >= 70):
            market_events.append({"t": "breadth", "list": "top_down" if uv <= 30 else "top_up", "txt": f"上漲成交值占比 {uv}%（{'量能集中弱勢股' if uv <= 30 else '量能集中強勢股'}）"})

    # 排序：公告 > 法人轉向 > 新聞 > 營收 > 連買達標；同型依成交值
    order = {"mops": 0, "flip": 1, "news": 2, "rev": 3, "streak": 4}
    stock_events.sort(key=lambda e: (order.get(e["t"], 9), -e["v"]))
    for e in stock_events:
        del e["v"]

    write_json("changes", {
        "stock_events": stock_events[:400],
        "topic_events": topic_events[:6],
        "market_events": market_events[:4],
        "n_stock_events": len(stock_events),
        "based_on": {"t86": t86_date, "news": news_date,
                     "mops": mops.get("data_date"), "breadth": br.get("data_date")},
    }, data_date=daily.get("data_date"),
        source="t86 序列 + mops + news + revenue + breadth 逐日比對",
        error=None)
    print(f"     個股事件 {len(stock_events)}、題材 {len(topic_events)}、大盤 {len(market_events)}")


if __name__ == "__main__":
    main()
