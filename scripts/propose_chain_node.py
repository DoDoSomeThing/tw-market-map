#!/usr/bin/env python3
# propose_chain_node.py — 半自動「新技術 → 價值鏈候選 node」產生器
#
# 為什麼半自動:價值鏈 chains.json 是人工校對 SSOT。機器亂猜「哪些股算某題材」是幻覺
# 重災區,寫死進去你會當真、污染整張圖。所以本工具只做「純統計、可審計」的候選提議 —
# 成員股最終由 Justin 圈定。偵測層(P10 topic_discover)已會浮出新題材詞;本工具接下一步:
# 題材詞 → 掃 history_news 找共現個股 → 比對行情 → 排序出候選 → 你圈選 → 插進 chains.json。
#
# 用法
# ── 探索(預設,不改任何檔)──────────────────────────────────────────────
#   python3 scripts/propose_chain_node.py --kw 類EMIB,矽橋,EMIB
#   python3 scripts/propose_chain_node.py --kw CPO --days 30 --min 2 --top 15
#     掃 data/history_news 標題含關鍵字的新聞 → 收集新聞已標的個股(stocks 欄) →
#     比對 daily_all 確認有行情 → 依「被幾則新聞點名」排序 → 印證據 + 可貼 node JSON,
#     並存一份審計檔到 data/chain_proposals/<kw>_<date>.json。
#
# ── 套用(改 chains.json;先探索、人工圈定 codes 後再跑)────────────────────
#   python3 scripts/propose_chain_node.py --apply \
#       --chain semiconductor --stage 下游 \
#       --label "類EMIB（內嵌矽橋）" \
#       --desc  "橋接晶片埋入基板/載板的先進封裝。新技術外溢受惠面廣" \
#       --codes 3037,8046,3189,2330
#     驗 codes 全有行情 → 備份 chains.json → 在指定鏈+段末插入 node(保留原緊湊排版) →
#     提示你跑 build_chains.py 驗證 + 自己 git commit/push。
#
# 原則:機器只提議、人拍板成員;不自動 git;改 chains.json 前先備份。
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime

from tw_common import DATA_DIR, ROOT, read_json, tw_now

CHAINS_PATH = ROOT / "chains" / "chains.json"
HIST_DIR = DATA_DIR / "history_news"
PROPOSAL_DIR = DATA_DIR / "chain_proposals"
CODE_RE = re.compile(r"(\d{4,6})")
NOISE_TITLE = re.compile(r"^(盤中速報|盤後速報|個股速報|盤中零股|鉅亨速報)")


# ── 共用 ────────────────────────────────────────────────────────────────
def load_market() -> dict[str, dict]:
    """daily_all → code → {name, market}。用來確認候選股有行情(否則 build_chains 會 WARN)。"""
    daily = read_json("daily_all")
    if not daily.get("ok"):
        sys.exit(f"[ERR] daily_all 不可用:{daily.get('error')} — 先跑 fetch_daily_all.py")
    return {s["code"]: {"name": s["name"], "market": s.get("market")}
            for s in daily["data"].get("stocks", [])}


def parse_code(tag: str) -> str | None:
    """news 的 stocks 標籤形如「欣興 3037」→ 取代號。"""
    m = CODE_RE.search(tag)
    return m.group(1) if m else None


# ── 探索模式 ────────────────────────────────────────────────────────────
def discover(kws: list[str], days: int | None, min_hits: int, top: int) -> None:
    market = load_market()
    files = sorted(HIST_DIR.glob("????-??-??.json"), reverse=True) if HIST_DIR.exists() else []
    if not files:
        sys.exit("[ERR] 找不到 data/history_news/ 新聞檔")
    if days:
        files = files[:days]
    kws_l = [k.lower() for k in kws]

    matched = []                       # 命中關鍵字的新聞
    for p in files:
        try:
            items = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for it in items:
            title = it.get("title", "")
            if NOISE_TITLE.match(title):
                continue
            tl = title.lower()
            if any(k in tl for k in kws_l):
                matched.append((p.stem, it))

    if not matched:
        print(f"[空] 近 {len(files)} 個新聞日內,標題無「{'/'.join(kws)}」。"
              f"可能題材太新/用詞不同 → 換關鍵字或等新聞累積。")
        return

    # 共現個股統計:被幾則點名(n)、跨幾個新聞日(days)
    stock_hits: dict[str, dict] = {}
    for d, it in matched:
        for tag in it.get("stocks", []):
            code = parse_code(tag)
            if not code or code not in market:   # 沒行情的丟掉(權證/已下市/純海外)
                continue
            s = stock_hits.setdefault(code, {"n": 0, "days": set()})
            s["n"] += 1
            s["days"].add(d)

    ranked = sorted(stock_hits.items(),
                    key=lambda kv: (-kv[1]["n"], -len(kv[1]["days"]), kv[0]))
    ranked = [(c, v) for c, v in ranked if v["n"] >= min_hits][:top]

    date_span = f"{matched[-1][0]} ~ {matched[0][0]}"
    print(f"\n關鍵字:{'/'.join(kws)}   命中新聞 {len(matched)} 則"
          f"（{len(files)} 個新聞日,{date_span}）\n")

    if not ranked:
        print(f"[無合格候選] 命中新聞未點名任何有行情個股(或都 < {min_hits} 次)。"
              f"新聞常只講技術不點股 → 需人工補成員股。")
    else:
        print(f"候選個股（依被點名次數排,≥{min_hits} 次;僅列有行情者）:")
        print(f"  {'代號':<6}{'股名':<10}{'點名':>4}{'天數':>4}  市場")
        for code, v in ranked:
            info = market[code]
            print(f"  {code:<6}{info['name']:<10}{v['n']:>4}{len(v['days']):>4}  {info.get('market') or '-'}")

    # 建議歸位:既有鏈的 name/desc/node label 含關鍵字者
    suggest = suggest_placement(kws_l)
    if suggest:
        print(f"\n建議歸位(既有鏈含相關詞):{suggest}")

    # 可貼 node JSON 草稿(label/desc 是你的決定,先放佔位)
    codes = [c for c, _ in ranked]
    draft = {
        "label": kws[0],
        "desc": f"(自動草稿 {tw_now():%Y-%m-%d}) 關鍵字 {'/'.join(kws)};成員待人工圈定",
        "codes": codes,
    }
    print("\n可貼進 chains.json 的候選 node（label/desc 請自行改;codes 請自行刪減）:")
    print("  " + json.dumps(draft, ensure_ascii=False))
    print("\n或圈定後直接套用:")
    print(f"  python3 scripts/propose_chain_node.py --apply --chain <鏈id> --stage <段關鍵字> \\")
    print(f"      --label \"{kws[0]}\" --desc \"…\" --codes {','.join(codes[:6])}")

    # 存審計檔(含證據原文,可回溯)
    PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)
    fname = re.sub(r"[^\w]+", "-", kws[0]).strip("-") or "kw"
    out = PROPOSAL_DIR / f"{fname}_{tw_now():%Y-%m-%d}.json"
    out.write_text(json.dumps({
        "keywords": kws,
        "generated_at": tw_now().strftime("%Y-%m-%d %H:%M:%S"),
        "news_days_scanned": len(files),
        "matched_news": len(matched),
        "candidates": [
            {"code": c, "name": market[c]["name"], "market": market[c].get("market"),
             "mentions": v["n"], "distinct_days": len(v["days"])}
            for c, v in ranked
        ],
        "draft_node": draft,
        "evidence": [
            {"date": d, "title": it["title"], "link": it.get("link", ""),
             "time": it.get("time", ""), "stocks": it.get("stocks", [])}
            for d, it in matched[:40]
        ],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[存] 審計檔 {out.relative_to(ROOT)}（含命中新聞原文,可回溯查證）")


def suggest_placement(kws_l: list[str]) -> str | None:
    try:
        chains = json.loads(CHAINS_PATH.read_text(encoding="utf-8"))["chains"]
    except Exception:
        return None
    for ch in chains:
        hay = (ch.get("name", "") + ch.get("desc", "")).lower()
        labels = " ".join(nd.get("label", "") for st in ch["stages"] for nd in st["nodes"]).lower()
        if any(k in hay or k in labels for k in kws_l):
            return f"{ch['id']}（{ch['name']}）"
    return None


# ── 套用模式:把一個 node 插進指定鏈+段(保留原緊湊排版)────────────────
def find_nodes_close(text: str, stage_key: str) -> int:
    """回傳指定段(名稱含 stage_key)的 nodes 陣列收尾 ']' 的位置。字串感知括號配對。"""
    # 定位段名 → 其後第一個 "nodes": [
    sm = re.search(r'"name"\s*:\s*"([^"]*' + re.escape(stage_key) + r'[^"]*)"', text)
    if not sm:
        return -1
    nm = re.search(r'"nodes"\s*:\s*\[', text[sm.end():])
    if not nm:
        return -1
    i = sm.end() + nm.end()            # 指向 '[' 之後第一個字元
    depth, in_str, esc = 1, False, False
    while i < len(text):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return i           # 這個 ']' 收掉 nodes 陣列
        i += 1
    return -1


def apply_node(chain_id: str, stage_key: str, label: str, desc: str, codes: list[str]) -> None:
    market = load_market()
    missing = [c for c in codes if c not in market]
    if missing:
        sys.exit(f"[ERR] 這些代號在 daily_all 對不到行情,拒絕寫入(build_chains 會 WARN):{missing}")

    raw = CHAINS_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)            # 驗證 JSON + 找鏈
    ch = next((c for c in data["chains"] if c["id"] == chain_id), None)
    if not ch:
        ids = ", ".join(c["id"] for c in data["chains"])
        sys.exit(f"[ERR] 找不到鏈 id「{chain_id}」。可用:{ids}")
    stages = [st for st in ch["stages"] if stage_key in st["name"]]
    if len(stages) != 1:
        names = " / ".join(st["name"] for st in ch["stages"])
        sys.exit(f"[ERR] 段關鍵字「{stage_key}」在鏈「{chain_id}」命中 {len(stages)} 個(需剛好 1)。段:{names}")
    stage_name = stages[0]["name"]
    if any(nd["label"] == label for nd in stages[0]["nodes"]):
        sys.exit(f"[ERR] 段「{stage_name}」已有同名 node「{label}」,不重複加。")

    # 只在該鏈範圍內找段,避免不同鏈同名段撞到。先切出這條鏈的文字區段。
    chain_anchor = re.search(r'"id"\s*:\s*"' + re.escape(chain_id) + r'"', raw)
    close = find_nodes_close(raw[chain_anchor.start():], stage_key)
    if close < 0:
        sys.exit(f"[ERR] 定位段「{stage_key}」的 nodes 收尾失敗,未改檔。")
    close += chain_anchor.start()

    # nodes 收尾 ']' 前一個非空白字元應是上一個 node 的 '}';插新 node 於其後。
    j = close - 1
    while j >= 0 and raw[j] in " \t\r\n":
        j -= 1
    if raw[j] != "}":
        sys.exit("[ERR] nodes 陣列結尾非預期(空陣列?),為安全未改檔。")
    indent = "            "            # 對齊既有 node(12 空格)
    node_line = "{ " + json.dumps({"label": label, "desc": desc, "codes": codes},
                                  ensure_ascii=False)[1:-1].strip() + " }"
    insert = ",\n" + indent + node_line
    new_raw = raw[:j + 1] + insert + raw[j + 1:]

    json.loads(new_raw)               # 插完再驗一次 JSON 合法
    bak = CHAINS_PATH.with_suffix(".json.bak")
    bak.write_text(raw, encoding="utf-8")
    CHAINS_PATH.write_text(new_raw, encoding="utf-8")
    print(f"[OK ] 已插入 node「{label}」({len(codes)} 檔) → {chain_id} / {stage_name}")
    print(f"      備份:{bak.relative_to(ROOT)}")
    print("      成員:" + "、".join(f"{c} {market[c]['name']}" for c in codes))
    print("\n下一步(自行執行):")
    print("  python3 scripts/build_chains.py        # 重算 view,確認無 WARN")
    print("  git add chains/chains.json && git commit && git push   # 你自己上傳")


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="新技術題材 → 價值鏈候選 node(半自動,人拍板成員)")
    ap.add_argument("--kw", help="關鍵字,逗號分隔(探索模式);OR 比對新聞標題")
    ap.add_argument("--days", type=int, default=None, help="只掃最近 N 個新聞日(預設全部)")
    ap.add_argument("--min", type=int, default=1, help="候選股最低被點名次數(預設 1)")
    ap.add_argument("--top", type=int, default=12, help="最多列幾檔候選(預設 12)")
    ap.add_argument("--apply", action="store_true", help="套用模式:把 node 插進 chains.json")
    ap.add_argument("--chain", help="(apply)目標鏈 id,如 semiconductor")
    ap.add_argument("--stage", help="(apply)段名關鍵字,如 下游")
    ap.add_argument("--label", help="(apply)node 標籤")
    ap.add_argument("--desc", default="", help="(apply)node 說明")
    ap.add_argument("--codes", help="(apply)成員代號,逗號分隔")
    args = ap.parse_args()

    if args.apply:
        need = {"--chain": args.chain, "--stage": args.stage,
                "--label": args.label, "--codes": args.codes}
        miss = [k for k, v in need.items() if not v]
        if miss:
            sys.exit(f"[ERR] apply 模式缺參數:{', '.join(miss)}")
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        apply_node(args.chain, args.stage, args.label, args.desc, codes)
    else:
        if not args.kw:
            sys.exit("[ERR] 探索模式需 --kw 關鍵字(逗號分隔)。或用 --apply 套用。")
        kws = [k.strip() for k in args.kw.split(",") if k.strip()]
        discover(kws, args.days, args.min, args.top)


if __name__ == "__main__":
    main()
