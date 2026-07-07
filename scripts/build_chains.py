# build_chains.py — chains/chains.json + daily_all + t86 → data/chains_view.json
# 個股掛現價/漲跌/成交值/法人；chains.json 裡對不到行情的代號印警告（校對用）。
from __future__ import annotations

import json

from tw_common import ROOT, read_json, write_error, write_json

CHAINS_PATH = ROOT / "chains" / "chains.json"


def main() -> None:
    try:
        chains = json.loads(CHAINS_PATH.read_text(encoding="utf-8"))["chains"]
    except Exception as e:
        write_error("chains_view", "chains/chains.json", f"讀取失敗:{e}")
        return

    daily = read_json("daily_all")
    if not daily.get("ok"):
        write_error("chains_view", "chains/chains.json",
                    f"daily_all 不可用:{daily.get('error')}")
        return
    info = {s["code"]: s for s in daily["data"].get("stocks", [])}

    t86 = read_json("t86")
    inst = t86["data"].get("stocks", {}) if t86.get("ok") else {}

    missing = []
    out_chains = []
    for ch in chains:
        stages = []
        for st in ch["stages"]:
            nodes = []
            for nd in st["nodes"]:
                members = []
                for code in nd["codes"]:
                    s = info.get(code)
                    if not s:
                        missing.append(f"{ch['id']}/{nd['label']}/{code}")
                        continue
                    iv = inst.get(code, {})
                    members.append({
                        "code": code, "name": s["name"], "close": s["close"],
                        "pct": s["pct"], "value": s["value"],
                        "market": s.get("market"),   # twse/tpex → Yahoo .TW/.TWO
                        "f_lots": round(iv["f"] / 1000) if iv else None,
                        "t_lots": round(iv["t"] / 1000) if iv else None,
                    })
                if members:
                    nodes.append({"label": nd["label"], "desc": nd.get("desc", ""),
                                  "members": members})
            if nodes:
                stages.append({"name": st["name"], "nodes": nodes})
        out_chains.append({"id": ch["id"], "name": ch["name"], "desc": ch["desc"],
                           "stages": stages})

    for m in missing:
        print(f"[WARN] 價值鏈代號比對不到行情：{m}")

    write_json("chains_view", {"chains": out_chains, "missing": missing},
               data_date=daily.get("data_date"), source="chains.json + daily_all + t86",
               error=f"{len(missing)} 代號對不到行情" if missing else None)


if __name__ == "__main__":
    main()
