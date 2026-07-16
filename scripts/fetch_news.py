# fetch_news.py — 市場新聞聚合（RSS 標題 + 連結回原站；不轉載內文，版權留原站）
# 源：鉅亨台股 + Yahoo 股市 + 鉅亨國際(wd_stock，時事雷達用)。
# 標籤：個股=股名/代號比對；題材=topics.json keywords（tw_common.build_topic_matcher）。
# 歷史：逐日累積到 data/history_news/YYYY-MM-DD.json，供 build_news_radar.py 算近 3 日聲量。
from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

import requests

from tw_common import DATA_DIR, ROOT, UA, build_topic_matcher, read_json, write_error, write_json
from email.utils import parsedate_to_datetime

FEEDS = [
    ("鉅亨網", "https://news.cnyes.com/rss/v1/news/category/tw_stock", "tw"),
    ("Yahoo股市", "https://tw.stock.yahoo.com/rss?category=tw-market", "tw"),
    ("鉅亨國際", "https://news.cnyes.com/rss/v1/news/category/wd_stock", "intl"),
]
TOPICS_PATH = ROOT / "topics" / "topics.json"
HIST_DIR = DATA_DIR / "history_news"
MAX_TW = 60          # 新聞分頁顯示上限（台股）
MAX_INTL = 40        # 新聞分頁顯示上限（國際）


def fetch_xml(url: str) -> str:
    try:
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        return r.text
    except requests.exceptions.SSLError:
        p = subprocess.run(["curl", "-s", "--max-time", "30",
                            "-H", f"User-Agent: {UA['User-Agent']}", url],
                           capture_output=True, timeout=45)
        if p.returncode != 0 or not p.stdout:
            raise RuntimeError(f"curl exit={p.returncode}")
        return p.stdout.decode("utf-8", "replace")


def parse_feed(source: str, scope: str, xml_text: str) -> list[dict]:
    out = []
    root = ET.fromstring(xml_text.encode("utf-8") if isinstance(xml_text, str) else xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not title or not link.startswith("http"):
            continue
        try:
            dt = parsedate_to_datetime(pub)
            iso = dt.astimezone().strftime("%Y-%m-%d %H:%M")
        except Exception:
            iso = ""
        out.append({"title": title, "link": link, "time": iso, "source": source, "scope": scope})
    return out


def build_stock_tagger():
    """title -> [「股名 代號」]（最多 2 個）。"""
    names = []
    daily = read_json("daily_all")
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            n = s.get("name") or ""
            # 2 字以下股名誤判率高（如「大成」「長榮」還行,「東元」ok;1字全丟）
            if len(n) >= 2 and len(s["code"]) == 4 and s["code"].isdigit():
                names.append((n, s["code"]))
    names.sort(key=lambda x: len(x[0]), reverse=True)   # 長名優先（台積電 > 台積）

    def stock_tags(title: str) -> list[str]:
        hits = []
        t = title
        for n, code in names:
            if n in t:
                hits.append(f"{n} {code}")
                t = t.replace(n, "■")   # 消掉已命中的長名，避免「聯發科」再讓「聯發」沾光
                if len(hits) >= 2:
                    break
        return hits

    return stock_tags


def title_key(title: str) -> str:
    return re.sub(r"\s+", "", title)[:40]


def save_history(items: list[dict]) -> None:
    """依「新聞自身日期」併入 history_news/<date>.json（同標題去重），並清舊檔。"""
    HIST_DIR.mkdir(parents=True, exist_ok=True)
    by_date: dict[str, list[dict]] = {}
    for it in items:
        d = it["time"][:10] if it.get("time") else None
        if d:
            by_date.setdefault(d, []).append(it)
    for d, day_items in by_date.items():
        p = HIST_DIR / f"{d}.json"
        old = []
        if p.exists():
            try:
                old = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                old = []
        seen = {title_key(o["title"]) for o in old}
        merged = old + [it for it in day_items if title_key(it["title"]) not in seen]
        p.write_text(json.dumps(merged, ensure_ascii=False, separators=(",", ":")),
                     encoding="utf-8")
    # 永久累積（append-only 正本，2026-07-16 起不再砍舊檔）：~102KB/天 → 壓縮後 ~6MB/年。
    # 消費端都只讀最近幾支（news_radar [:3]、topic_discover dates[:RECENT+BASELINE]），累積不影響效能。


def main() -> None:
    items: list[dict] = []
    errs = []
    for source, url, scope in FEEDS:
        try:
            items += parse_feed(source, scope, fetch_xml(url))
        except Exception as e:
            errs.append(f"{source}:{e}")

    if not items:
        write_error("news", "鉅亨/Yahoo RSS", "；".join(errs) or "無資料")
        return

    # 去重（跨源同標題）+ 時間新→舊
    seen = set()
    uniq = []
    for it in sorted(items, key=lambda x: x["time"], reverse=True):
        key = title_key(it["title"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)

    # 打標籤：個股 + 題材（keywords 比對；ids 給雷達、names 給頁面顯示）
    stock_tags = build_stock_tagger()
    topics_cfg = {}
    try:
        topics_cfg = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        errs.append(f"topics.json:{e}")
    matcher = build_topic_matcher(topics_cfg)
    id2name = {t["id"]: t["name"] for t in topics_cfg.get("topics", [])}
    for it in uniq:
        it["stocks"] = stock_tags(it["title"]) if it["scope"] == "tw" else []
        tids = matcher(it["title"])[:3]
        it["topic_ids"] = tids
        it["topics"] = [id2name[t] for t in tids]

    save_history(uniq)

    tw = [it for it in uniq if it["scope"] == "tw"][:MAX_TW]
    intl = [it for it in uniq if it["scope"] == "intl"][:MAX_INTL]
    items = sorted(tw + intl, key=lambda x: x["time"], reverse=True)

    today = datetime.now().strftime("%Y-%m-%d")
    write_json("news", {"items": items},
               data_date=items[0]["time"][:10] if items and items[0]["time"] else today,
               source="鉅亨網(台股+國際) + Yahoo股市 RSS（標題聚合，內文請點回原站）",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
