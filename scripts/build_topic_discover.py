# build_topic_discover.py — 新題材候選：新聞標題詞頻突增偵測 → data/topic_discover.json
# 原理：近 2 個新聞日的詞頻 vs 之前最多 7 日基線，突增且達最低則數的詞為候選；
# 同標題高共現的詞聚成一組，附相關個股與例句。純統計、可重現，非題材認定 —
# Justin 看對眼再把關鍵字收進 topics/topics.json 轉正。
# 雜訊靠 topics/discover_stopwords.txt 迭代（看到雜詞就加）。
from __future__ import annotations

import json
import re
from datetime import datetime

from tw_common import DATA_DIR, ROOT, read_json, write_json

TOPICS_PATH = ROOT / "topics" / "topics.json"
STOP_PATH = ROOT / "topics" / "discover_stopwords.txt"
HIST_DIR = DATA_DIR / "history_news"

RECENT_DAYS = 2        # 近期窗（最新 2 個新聞日，權重 1.0 / 0.5）
BASELINE_DAYS = 7      # 基線窗（近期窗之前最多 7 個新聞日）
MIN_BASELINE_DAYS = 3  # 基線不足此天數 → 只回報累積中
MIN_RECENT = 3         # 近期至少出現在幾則標題
MIN_BURST = 2.0        # 突增倍率門檻
MAX_CANDIDATES = 8
NOISE_TITLE = re.compile(r"^(盤中速報|盤後速報|個股速報|盤中零股|鉅亨速報)")
CJK = re.compile(r"[一-鿿]")
ASCII_TERM = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]{2,11}")


def load_stopwords() -> set[str]:
    out = set()
    if STOP_PATH.exists():
        for line in STOP_PATH.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                out.add(w)
    return out


def load_known_terms() -> set[str]:
    """既有題材名/關鍵字 + 全市場股名 → 已知詞（新題材偵測要排除）。"""
    known = set()
    try:
        cfg = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
        for t in cfg.get("topics", []):
            known.update(k for k in t.get("keywords", []))
            known.update(p.strip() for p in str(t.get("name", "")).split("/") if p.strip())
    except Exception:
        pass
    daily = read_json("daily_all")
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            n = s.get("name") or ""
            if len(n) >= 2:
                known.add(n)
    return known


def is_known(tok: str, known: set[str], known_lower: set[str]) -> bool:
    """已知詞雙向包含檢查（「電網」已知 → 「智慧電網」也算已知）。"""
    if tok in known or tok.lower() in known_lower:
        return True
    for k in known:
        if len(k) >= 2 and (k in tok or (len(tok) >= 2 and tok in k)):
            return True
    return False


def tokenize(title: str, jieba_mod) -> set[str]:
    toks = set()
    for w in jieba_mod.cut(title):
        w = w.strip()
        if len(w) >= 2 and CJK.search(w):
            toks.add(w)
    for m in ASCII_TERM.findall(title):
        if not m.replace("-", "").replace(".", "").isdigit() and not m.endswith("-US"):
            toks.add(m.upper())
    return toks


def main() -> None:
    files = sorted(HIST_DIR.glob("????-??-??.json"), reverse=True) if HIST_DIR.exists() else []
    dates = [p.stem for p in files]
    recent_dates = dates[:RECENT_DAYS]
    base_dates = dates[RECENT_DAYS:RECENT_DAYS + BASELINE_DAYS]
    today = datetime.now().strftime("%Y-%m-%d")

    if len(base_dates) < MIN_BASELINE_DAYS:
        write_json("topic_discover",
                   {"candidates": [], "n_baseline_days": len(base_dates),
                    "note": f"基線累積中（{len(base_dates)}/{MIN_BASELINE_DAYS} 日），"
                            f"約 {MIN_BASELINE_DAYS - len(base_dates)} 個交易日後開始偵測"},
                   data_date=dates[0] if dates else today,
                   source="history_news 詞頻突增偵測", error=None)
        return

    import jieba
    jieba.setLogLevel(60)
    stop = load_stopwords()
    known = load_known_terms()
    known_lower = {k.lower() for k in known}
    for k in known:   # 已知詞餵進 jieba，切得乾淨才排除得乾淨
        if CJK.search(k):
            jieba.add_word(k)

    def day_items(d: str) -> list[dict]:
        try:
            items = json.loads((HIST_DIR / f"{d}.json").read_text(encoding="utf-8"))
        except Exception:
            return []
        return [it for it in items if not NOISE_TITLE.match(it.get("title", ""))]

    # 詞 → 每日出現則數；近期窗另記出現的標題（分組/例句/個股用）
    recent_items: list[dict] = []
    recent_count: dict[str, float] = {}
    term_titles: dict[str, set[int]] = {}
    for wi, d in enumerate(recent_dates):
        w = 1.0 if wi == 0 else 0.5
        for it in day_items(d):
            idx = len(recent_items)
            recent_items.append(it)
            for tok in tokenize(it["title"], jieba):
                if tok in stop or is_known(tok, known, known_lower):
                    continue
                recent_count[tok] = recent_count.get(tok, 0.0) + w
                term_titles.setdefault(tok, set()).add(idx)

    base_count: dict[str, float] = {}
    for d in base_dates:
        for it in day_items(d):
            for tok in tokenize(it["title"], jieba):
                if tok in recent_count:   # 只需要候選詞的基線
                    base_count[tok] = base_count.get(tok, 0.0) + 1.0

    # 突增分數
    scored = []
    for tok, rc in recent_count.items():
        n_titles = len(term_titles.get(tok, ()))
        if n_titles < MIN_RECENT:
            continue
        b_avg = base_count.get(tok, 0.0) / len(base_dates)
        burst = (rc + 0.5) / (b_avg + 0.5)
        if burst >= MIN_BURST:
            scored.append((tok, burst, n_titles))
    scored.sort(key=lambda x: -(x[1] * (1 + x[2])))
    scored = scored[:30]

    # 高共現詞聚組（union-find；共現/較小集合 ≥ 0.6 視為同組）
    parent = {t: t for t, _, _ in scored}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    terms = [t for t, _, _ in scored]
    for i, a in enumerate(terms):
        for b in terms[i + 1:]:
            ta, tb = term_titles[a], term_titles[b]
            if len(ta & tb) / min(len(ta), len(tb)) >= 0.6:
                parent[find(a)] = find(b)

    groups: dict[str, list[str]] = {}
    for t in terms:
        groups.setdefault(find(t), []).append(t)

    burst_of = {t: b for t, b, _ in scored}
    candidates = []
    for g in groups.values():
        idxs = set()
        for t in g:
            idxs |= term_titles[t]
        if len(idxs) < MIN_RECENT:
            continue
        items = sorted((recent_items[i] for i in idxs),
                       key=lambda x: x.get("time", ""), reverse=True)
        stock_n: dict[str, int] = {}
        for it in items:
            for s in it.get("stocks", []):
                stock_n[s] = stock_n.get(s, 0) + 1
        g.sort(key=lambda t: -len(term_titles[t]))
        candidates.append({
            "terms": g[:4],
            "n_recent": len(idxs),
            "burst": round(max(burst_of[t] for t in g), 1),
            "stocks": [{"tag": s, "n": n} for s, n
                       in sorted(stock_n.items(), key=lambda kv: -kv[1])[:5]],
            "headlines": [{"title": it["title"], "link": it.get("link", ""),
                           "time": it.get("time", ""), "source": it.get("source", "")}
                          for it in items[:4]],
        })
    candidates.sort(key=lambda c: -(c["burst"] * (1 + c["n_recent"])))
    candidates = candidates[:MAX_CANDIDATES]

    write_json("topic_discover",
               {"candidates": candidates, "n_baseline_days": len(base_dates),
                "recent_dates": recent_dates, "note": None},
               data_date=recent_dates[0] if recent_dates else today,
               source=f"history_news 詞頻突增（近{len(recent_dates)}日 vs 前{len(base_dates)}日基線）",
               error=None)
    print(f"     候選 {len(candidates)} 組（基線 {len(base_dates)} 日）")


if __name__ == "__main__":
    main()
