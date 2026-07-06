# build_topics.py — 題材表 join 行情+法人 → data/topics_view.json
# 比對不到行情的代號列入 unmatched（題材表校對線索），不靜默吞掉。
from __future__ import annotations

import json

from build_inst_rank import load_streaks
from tw_common import ROOT, read_json, write_error, write_json

TOPICS_PATH = ROOT / "topics" / "topics.json"


def main() -> None:
    if not TOPICS_PATH.exists():
        write_error("topics_view", "build_topics", "topics/topics.json 不存在")
        return
    topics_cfg = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))

    daily = read_json("daily_all")
    if not daily.get("ok"):
        write_error("topics_view", "build_topics", f"上游 daily_all 失敗: {daily.get('error')}")
        return
    t86 = read_json("t86")
    t86_stocks = t86["data"].get("stocks", {}) if t86.get("ok") else {}
    streaks = load_streaks(t86.get("data_date") or "9999-99-99") if t86.get("ok") else {}

    quotes = {s["code"]: s for s in daily["data"].get("stocks", [])}

    out_topics = []
    unmatched: dict[str, list[str]] = {}
    for t in topics_cfg.get("topics", []):
        members = []
        for code in t.get("stocks", []):
            q = quotes.get(code)
            if not q:
                unmatched.setdefault(t["id"], []).append(code)
                continue
            inst = t86_stocks.get(code)
            sf, st = streaks.get(code, (0, 0))
            members.append({
                "code": code, "name": q["name"], "close": q["close"],
                "pct": q["pct"], "value": q["value"],
                "f_lots": round(inst["f"] / 1000) if inst else None,
                "t_lots": round(inst["t"] / 1000) if inst else None,
                "f_streak": sf, "t_streak": st,
            })
        if not members:
            unmatched.setdefault(t["id"], []).append("(全部比對失敗)")
            continue
        total_v = sum(m["value"] for m in members) or 1
        avg = sum(m["pct"] * m["value"] for m in members) / total_v
        members.sort(key=lambda m: -m["value"])
        out_topics.append({
            "id": t["id"], "name": t["name"], "group": t.get("group", "其他"),
            "desc": t.get("desc", ""),
            "avg_pct": round(avg, 2), "total_value": total_v,
            "members": members,
        })

    errs = []
    if unmatched:
        errs.append("代號比對不到行情（校對題材表）: " + json.dumps(unmatched, ensure_ascii=False))
    if not t86.get("ok"):
        errs.append(f"t86 失敗（法人欄空白）: {t86.get('error')}")

    write_json("topics_view", {"topics": out_topics, "groups": topics_cfg.get("groups", []),
                               "unmatched": unmatched},
               data_date=daily.get("data_date"), source="topics.json + daily_all + t86",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
