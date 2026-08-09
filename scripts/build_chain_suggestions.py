#!/usr/bin/env python3
# build_chain_suggestions.py — 新技術題材 → 價值鏈 node 候選提醒(接 P10 topic_discover)
#
# 定位:偵測層(build_topic_discover)已把新聞詞頻突增的候選題材算好。本步做「守門 + 提醒」:
# 濾掉市場口水詞、已在價值鏈/題材庫的舊題材、已提醒過的 → 剩下「真的新、且多檔個股共現」
# 的題材,寫成 data/chain_suggestions.json;daily.yml 見到非空就開一支 GitHub Issue 提醒 Justin
# 「要不要在 chains.json 加一條中下游 node」。開完 Issue 後以 --commit-state 記錄,同題材不再重提。
#
# 為什麼要重濾:topic_discover 的原始候選幾乎全是市場口水(營收速報/震盪/收跌/量縮…),
# 直接開 Issue 會洗版。門檻故意抓高(寧可靜默、別亂吵);漏抓就手動用 propose_chain_node.py。
# 黑名單是打地鼠檔 topics/suggest_blocklist.txt,看到雜詞就加(同 discover_stopwords 精神)。
#
# 用法
#   python3 scripts/build_chain_suggestions.py            # 算候選 → data/chain_suggestions.json(唯讀 state)
#   python3 scripts/build_chain_suggestions.py --commit-state   # 把本次候選記入 state(開完 Issue 後跑)
#
# 純統計、可審計。機器只「提醒」,加不加、加哪些股仍是 Justin 拍板(用 propose_chain_node.py 圈定)。
from __future__ import annotations

import argparse
import json
import re
import sys

from tw_common import DATA_DIR, ROOT, read_json, tw_now

CHAINS_PATH = ROOT / "chains" / "chains.json"
TOPICS_PATH = ROOT / "topics" / "topics.json"
BLOCK_PATH = ROOT / "topics" / "suggest_blocklist.txt"
DISCOVER_STOP = ROOT / "topics" / "discover_stopwords.txt"
STATE_PATH = DATA_DIR / "chain_suggest_state.json"
SUGG_PATH = DATA_DIR / "chain_suggestions.json"
CODE_RE = re.compile(r"(\d{4,6})")

MIN_BURST = 3.0     # 突增倍率門檻(topic_discover 已算)
MIN_STOCKS = 3      # 至少幾檔「有行情」個股共現(供應鏈本來就多家;單股≠題材)
MAX_SUGGEST = 4     # 一次最多提醒幾個題材(免一次塞太多)


def load_lines(path) -> set[str]:
    out = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                out.add(w)
    return out


def load_known_terms() -> set[str]:
    """已在價值鏈 or 題材庫的詞 → 不算「新」題材。"""
    known: set[str] = set()
    try:
        chains = json.loads(CHAINS_PATH.read_text(encoding="utf-8"))["chains"]
        for ch in chains:
            for part in str(ch.get("name", "")).split("/"):
                if part.strip():
                    known.add(part.strip())
            for st in ch["stages"]:
                for nd in st["nodes"]:
                    known.add(nd.get("label", ""))
    except Exception:
        pass
    try:
        topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8")).get("topics", [])
        for t in topics:
            known.update(k for k in t.get("keywords", []))
            for part in str(t.get("name", "")).split("/"):
                if part.strip():
                    known.add(part.strip())
    except Exception:
        pass
    return {k for k in known if len(k) >= 2}


def is_known(term: str, known: set[str]) -> bool:
    """雙向包含:「電網」已知 → 「智慧電網」也算已涵蓋。"""
    for k in known:
        if k in term or term in k:
            return True
    return False


def parse_code(tag: str) -> str | None:
    m = CODE_RE.search(tag)
    return m.group(1) if m else None


def load_state() -> set[str]:
    if STATE_PATH.exists():
        try:
            return set(json.loads(STATE_PATH.read_text(encoding="utf-8")).get("suggested", []))
        except Exception:
            return set()
    return set()


def signature(terms: list[str]) -> str:
    return "|".join(sorted(terms[:3]))


def build() -> dict:
    td = read_json("topic_discover")
    if not td.get("ok"):
        return {"suggestions": [], "note": f"topic_discover 不可用:{td.get('error')}"}
    cands = td["data"].get("candidates", [])
    if not cands:
        return {"suggestions": [], "note": td["data"].get("note") or "偵測層無候選"}

    market = read_json("daily_all")
    mkt = ({s["code"]: {"name": s["name"], "market": s.get("market")}
            for s in market["data"].get("stocks", [])} if market.get("ok") else {})

    block = load_lines(BLOCK_PATH) | load_lines(DISCOVER_STOP)
    known = load_known_terms()
    already = load_state()

    suggestions = []
    for c in cands:
        terms = c.get("terms", [])
        if not terms:
            continue
        if signature(terms) in already:
            continue
        if c.get("burst", 0) < MIN_BURST:
            continue
        # 任一主詞落黑名單 or 已在價值鏈/題材庫 → 跳過(不是新技術題材)
        if any(t in block for t in terms) or any(is_known(t, known) for t in terms):
            continue
        # 共現個股取「有行情」者
        stocks = []
        seen = set()
        for s in c.get("stocks", []):
            code = parse_code(s.get("tag", ""))
            if not code or code in seen or code not in mkt:
                continue
            seen.add(code)
            stocks.append({"code": code, "name": mkt[code]["name"],
                           "market": mkt[code].get("market"), "n": s.get("n", 0)})
        if len(stocks) < MIN_STOCKS:
            continue
        suggestions.append({
            "signature": signature(terms),
            "terms": terms,
            "burst": c.get("burst"),
            "n_recent": c.get("n_recent"),
            "stocks": stocks,
            "headlines": c.get("headlines", [])[:3],
        })

    suggestions.sort(key=lambda s: -(s["burst"] or 0))
    return {"suggestions": suggestions[:MAX_SUGGEST], "note": None}


def issue_markdown(sugg: list[dict]) -> tuple[str, str]:
    date = tw_now().strftime("%Y-%m-%d")
    title = f"🆕 新技術題材候選 {date}（{len(sugg)} 個，價值鏈可能要加中下游）"
    lines = [
        "偵測層(詞頻突增)發現**新聞在燒、但價值鏈還沒收的題材**。純統計、非題材認定，",
        "**要不要加 node、加哪些股由你拍板**。以下每個附共現個股與可直接跑的圈定指令。",
        "",
    ]
    for s in sugg:
        terms = "／".join(s["terms"])
        lines.append(f"### {terms}　`突增 {s['burst']}×`　`近期 {s['n_recent']} 則`")
        lines.append("共現個股（新聞已點名、有行情）：")
        for st in s["stocks"]:
            lines.append(f"- {st['name']} {st['code']}（{st.get('market') or '-'}，點名 {st['n']}）")
        if s["headlines"]:
            lines.append("<details><summary>例句</summary>\n")
            for h in s["headlines"]:
                lines.append(f"- [{h.get('title','')}]({h.get('link','')})")
            lines.append("\n</details>")
        codes = ",".join(st["code"] for st in s["stocks"])
        lines.append("\n先看完整證據，再圈定成員股：")
        lines.append("```bash")
        lines.append(f"python3 scripts/propose_chain_node.py --kw {s['terms'][0]}")
        lines.append("# 圈定後套用（改 chain/stage/label/codes）：")
        lines.append(f"python3 scripts/propose_chain_node.py --apply --chain <鏈id> "
                     f"--stage <段> --label \"{s['terms'][0]}\" --codes {codes}")
        lines.append("```")
        lines.append("")
    lines.append("---\n覺得是雜訊 → 把詞加進 `topics/suggest_blocklist.txt`，以後不再提。")
    return title, "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="新技術題材 → 價值鏈 node 候選提醒")
    ap.add_argument("--commit-state", action="store_true",
                    help="把 chain_suggestions.json 現有候選記入 state(開完 Issue 後跑,避免重複提醒)")
    args = ap.parse_args()

    if args.commit_state:
        try:
            sugg = json.loads(SUGG_PATH.read_text(encoding="utf-8"))["data"]["suggestions"]
        except Exception as e:
            sys.exit(f"[ERR] 讀 chain_suggestions.json 失敗:{e}")
        state = load_state()
        for s in sugg:
            state.add(s["signature"])
        STATE_PATH.write_text(json.dumps(
            {"suggested": sorted(state), "updated": tw_now().strftime("%Y-%m-%d %H:%M:%S")},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK ] state 記錄 {len(sugg)} 個候選,累計 {len(state)} 個已提醒")
        return

    res = build()
    sugg = res["suggestions"]
    title, body = issue_markdown(sugg) if sugg else ("", "")
    payload = {"suggestions": sugg, "note": res.get("note"),
               "issue_title": title, "issue_body": body}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SUGG_PATH.write_text(json.dumps(
        {"ok": True, "data_date": tw_now().strftime("%Y-%m-%d"),
         "fetched_at": tw_now().strftime("%Y-%m-%d %H:%M:%S"),
         "source": "topic_discover 濾（黑名單＋已知題材＋已提醒）", "error": None,
         "data": payload}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if sugg:
        print(f"[OK ] chain_suggestions.json — {len(sugg)} 個新題材候選待提醒")
        for s in sugg:
            print(f"      • {'／'.join(s['terms'])}（{s['burst']}× / {len(s['stocks'])} 檔）")
    else:
        print(f"[OK ] chain_suggestions.json — 無新題材候選（{res.get('note') or '全被濾掉'}）")


if __name__ == "__main__":
    main()
