# fetch_news.py — 市場新聞聚合（RSS 標題 + 連結回原站；不轉載內文，版權留原站）
# 源：鉅亨台股 RSS + Yahoo 股市 RSS。依個股名/代號 + 題材名自動打標籤。
from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import requests

from tw_common import ROOT, UA, read_json, write_error, write_json

FEEDS = [
    ("鉅亨網", "https://news.cnyes.com/rss/v1/news/category/tw_stock"),
    ("Yahoo股市", "https://tw.stock.yahoo.com/rss?category=tw-market"),
]
TOPICS_PATH = ROOT / "topics" / "topics.json"
MAX_ITEMS = 60


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


def parse_feed(source: str, xml_text: str) -> list[dict]:
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
        out.append({"title": title, "link": link, "time": iso, "source": source})
    return out


def build_taggers():
    """回 (stock_tagger, topic_names)。stock_tagger: title -> [個股名]（最多2個）。"""
    names = []
    daily = read_json("daily_all")
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            n = s.get("name") or ""
            # 2 字以下股名誤判率高（如「大成」「長榮」還行,「東元」ok;1字全丟）
            if len(n) >= 2 and len(s["code"]) == 4 and s["code"].isdigit():
                names.append((n, s["code"]))
    names.sort(key=lambda x: len(x[0]), reverse=True)   # 長名優先（台積電 > 台積）

    topics = []
    try:
        for t in json.loads(TOPICS_PATH.read_text(encoding="utf-8"))["topics"]:
            topics.append(t["name"])
    except Exception:
        pass

    def stock_tags(title: str) -> list[str]:
        hits = []
        for n, code in names:
            if n in title:
                hits.append(f"{n} {code}")
                if len(hits) >= 2:
                    break
        return hits

    def topic_tags(title: str) -> list[str]:
        return [t for t in topics if t in title][:2]

    return stock_tags, topic_tags


def main() -> None:
    items: list[dict] = []
    errs = []
    for source, url in FEEDS:
        try:
            items += parse_feed(source, fetch_xml(url))
        except Exception as e:
            errs.append(f"{source}:{e}")

    if not items:
        write_error("news", "鉅亨/Yahoo RSS", "；".join(errs) or "無資料")
        return

    # 去重（跨源同標題）+ 時間新→舊
    seen = set()
    uniq = []
    for it in sorted(items, key=lambda x: x["time"], reverse=True):
        key = re.sub(r"\s+", "", it["title"])[:40]
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    items = uniq[:MAX_ITEMS]

    stock_tags, topic_tags = build_taggers()
    for it in items:
        it["stocks"] = stock_tags(it["title"])
        it["topics"] = topic_tags(it["title"])

    today = datetime.now().strftime("%Y-%m-%d")
    write_json("news", {"items": items},
               data_date=items[0]["time"][:10] if items and items[0]["time"] else today,
               source="鉅亨網 + Yahoo股市 RSS（標題聚合，內文請點回原站）",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
