# build_news_radar.py — 時事雷達：近 3 日新聞/公告聲量 → 題材熱度 + 個股熱度 → data/news_radar.json
# 聲量=標題關鍵字比對則數（現況描述，非訊號、非預測）。權重：當日 1.0、昨日 0.6、前日 0.3；
# MOPS 公告（澄清/重大）×0.8 — 澄清公告常代表個股正被時事點名。
from __future__ import annotations

import json
from datetime import datetime

from build_inst_rank import load_streaks
from tw_common import DATA_DIR, ROOT, build_topic_matcher, read_json, write_error, write_json

TOPICS_PATH = ROOT / "topics" / "topics.json"
HIST_DIR = DATA_DIR / "history_news"
DAY_W = [1.0, 0.6, 0.3]      # 當日/昨日/前日權重
MOPS_W = 0.8                 # 公告相對新聞的權重
TOP_STOCKS = 15
TOP_HEADLINES = 6


def load_recent_news() -> tuple[list[dict], list[str]]:
    """近 3 個「有新聞的日子」的 items（跨檔同標題去重，新→舊）。回 (items, dates)。"""
    if not HIST_DIR.exists():
        return [], []
    files = sorted(HIST_DIR.glob("????-??-??.json"), reverse=True)[:3]
    items, seen = [], set()
    for p in files:
        try:
            day = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in day:
            key = "".join(str(it.get("title", "")).split())[:40]
            if key and key not in seen:
                seen.add(key)
                items.append(it)
    items.sort(key=lambda x: x.get("time", ""), reverse=True)
    return items, [p.stem for p in files]


def main() -> None:
    if not TOPICS_PATH.exists():
        write_error("news_radar", "build_news_radar", "topics/topics.json 不存在")
        return
    topics_cfg = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    news_items, news_dates = load_recent_news()
    if not news_items:
        write_error("news_radar", "build_news_radar", "無新聞歷史（fetch_news 尚未跑成）")
        return
    base_date = news_dates[0]  # 最新有新聞的日子
    date_w = {d: DAY_W[i] for i, d in enumerate(news_dates)}

    # ── 題材聲量（新聞）──
    heat: dict[str, float] = {}
    n_today: dict[str, int] = {}
    n_3d: dict[str, int] = {}
    headlines: dict[str, list[dict]] = {}
    stock_heat: dict[str, float] = {}
    stock_latest: dict[str, dict] = {}
    matcher = build_topic_matcher(topics_cfg)
    for it in news_items:
        d = str(it.get("time", ""))[:10]
        w = date_w.get(d)
        if w is None:
            continue
        tids = it.get("topic_ids")
        if tids is None:  # 舊格式歷史檔（升級前）沒存 ids → 重比對
            tids = matcher(it.get("title", ""))[:3]
        for tid in tids:
            heat[tid] = heat.get(tid, 0.0) + w
            n_3d[tid] = n_3d.get(tid, 0) + 1
            if d == base_date:
                n_today[tid] = n_today.get(tid, 0) + 1
            if len(headlines.setdefault(tid, [])) < TOP_HEADLINES:
                headlines[tid].append({"title": it["title"], "link": it.get("link", ""),
                                       "time": it.get("time", ""), "source": it.get("source", "")})
        for s in it.get("stocks", []):
            code = s.split()[-1]
            stock_heat[code] = stock_heat.get(code, 0.0) + w
            if code not in stock_latest:
                stock_latest[code] = {"title": it["title"], "link": it.get("link", "")}

    # ── MOPS 公告（澄清/重大）→ 個股熱度 + 反查題材 ──
    code2topics: dict[str, list[str]] = {}
    for t in topics_cfg.get("topics", []):
        for c in t.get("stocks", []):
            code2topics.setdefault(c, []).append(t["id"])
    mops = read_json("mops")
    topic_mops: dict[str, list[dict]] = {}
    if mops.get("ok"):
        for it in mops["data"].get("items", []):
            if it.get("tag") not in ("澄清", "重大"):
                continue
            w = date_w.get(it.get("date", ""), 0.0) * MOPS_W
            if w <= 0:
                continue
            code = it["code"]
            stock_heat[code] = stock_heat.get(code, 0.0) + w
            stock_latest.setdefault(code, {"title": f"[{it['tag']}公告] {it['subject'][:60]}", "link": ""})
            for tid in code2topics.get(code, []):
                heat[tid] = heat.get(tid, 0.0) + w
                if len(topic_mops.setdefault(tid, [])) < 4:
                    topic_mops[tid].append({"code": code, "name": it.get("name", ""),
                                            "tag": it["tag"], "subject": it["subject"][:80]})

    # ── join 題材行情（topics_view）──
    tv = read_json("topics_view")
    tv_by_id = {t["id"]: t for t in tv["data"].get("topics", [])} if tv.get("ok") else {}
    out_topics = []
    for tid, h in sorted(heat.items(), key=lambda kv: -kv[1]):
        t = tv_by_id.get(tid)
        cfg = next((x for x in topics_cfg["topics"] if x["id"] == tid), {})
        out_topics.append({
            "id": tid,
            "name": t["name"] if t else cfg.get("name", tid),
            "group": t["group"] if t else cfg.get("group", ""),
            "heat": round(h, 1),
            "n_today": n_today.get(tid, 0), "n_3d": n_3d.get(tid, 0),
            "avg_pct": t["avg_pct"] if t else None,
            "total_value": t["total_value"] if t else None,
            "members": t["members"] if t else [],
            "headlines": headlines.get(tid, []),
            "mops": topic_mops.get(tid, []),
        })

    # ── 個股熱度榜（join 行情 + 法人）──
    daily = read_json("daily_all")
    quotes = {s["code"]: s for s in daily["data"].get("stocks", [])} if daily.get("ok") else {}
    t86 = read_json("t86")
    t86_stocks = t86["data"].get("stocks", {}) if t86.get("ok") else {}
    streaks = load_streaks(t86.get("data_date") or "9999-99-99") if t86.get("ok") else {}
    stocks_hot = []
    for code, h in sorted(stock_heat.items(), key=lambda kv: -kv[1]):
        q = quotes.get(code)
        if not q:
            continue
        inst = t86_stocks.get(code)
        sf, st = streaks.get(code, (0, 0))
        stocks_hot.append({
            "code": code, "name": q["name"], "industry": q.get("industry") or "",
            "market": q.get("market") or "twse",
            "heat": round(h, 1), "close": q["close"], "pct": q["pct"], "value": q["value"],
            "f_lots": round(inst["f"] / 1000) if inst else None,
            "t_lots": round(inst["t"] / 1000) if inst else None,
            "f_streak": sf, "t_streak": st,
            "latest": stock_latest.get(code),
        })
        if len(stocks_hot) >= TOP_STOCKS:
            break

    errs = []
    if not tv.get("ok"):
        errs.append(f"topics_view 失敗（題材行情欄空白）: {tv.get('error')}")
    if not mops.get("ok"):
        errs.append(f"mops 失敗（公告未計入）: {mops.get('error')}")
    if len(news_dates) < 3:
        errs.append(f"新聞歷史僅 {len(news_dates)} 日（累積中，聲量會隨天數變準）")

    write_json("news_radar",
               {"topics": out_topics, "stocks_hot": stocks_hot,
                "news_dates": news_dates, "n_news": len(news_items)},
               data_date=base_date,
               source="history_news(近3日) + mops + topics_view + daily_all + t86",
               error="；".join(errs) or None)
    print(f"     題材 {len(out_topics)} 個有聲量、個股 {len(stocks_hot)} 檔上榜、新聞 {len(news_items)} 則/{len(news_dates)} 日")


if __name__ == "__main__":
    main()
