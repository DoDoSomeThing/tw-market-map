# build_flow.py — 法人資金流：t86 個股買賣超聚合到「產業（全市場）」與「題材（自選）」
# 金額=股數×當日收盤（估算）。連續天數用 history_t86 快照的聚合方向（僅現況描述，非訊號）。
# 「外資是幾百家機構的彙總」：這裡呈現的是族群層級的淨流向，不是同一筆錢的移動路徑。
from __future__ import annotations

import json

from tw_common import DATA_DIR, ROOT, read_json, write_error, write_json

TOPICS_PATH = ROOT / "topics" / "topics.json"
HISTORY_DIR = DATA_DIR / "history_t86"
TOP_N = 12
MAX_STREAK_DAYS = 10


def load_snapshots() -> list[tuple[str, dict]]:
    """[(iso_date, {code: [f股, t股]})]，新→舊。"""
    if not HISTORY_DIR.exists():
        return []
    files = sorted(HISTORY_DIR.glob("????-??-??.json"), reverse=True)[:MAX_STREAK_DAYS]
    out = []
    for f in files:
        try:
            out.append((f.stem, json.loads(f.read_text(encoding="utf-8"))))
        except Exception:
            continue
    return out


def streak_of(day_sums: list[float]) -> int:
    """聚合淨額序列（新→舊）→ 連續同向天數。+3=連3日淨買、-2=連2日淨賣。"""
    if not day_sums or day_sums[0] == 0:
        return 0
    sign = 1 if day_sums[0] > 0 else -1
    n = 0
    for v in day_sums:
        if (v > 0) == (sign > 0) and v != 0:
            n += 1
        else:
            break
    return n * sign


def aggregate(groups: dict[str, list[str]], info: dict, stocks_t86: dict,
              snapshots: list[tuple[str, dict]]) -> list[dict]:
    """groups: 名稱 -> [codes]。回每群 {name, f_val, t_val, f_streak, t_streak, top}。"""
    out = []
    for name, codes in groups.items():
        f_val = t_val = 0.0
        contrib = []
        for c in codes:
            s = info.get(c)
            iv = stocks_t86.get(c)
            if not s or not iv:
                continue
            fv = iv["f"] * s["close"]
            tv = iv["t"] * s["close"]
            f_val += fv
            t_val += tv
            contrib.append((abs(fv), c, s["name"], fv))
        if not contrib:
            continue
        # 連續天數：快照逐日聚合外資/投信淨股數（同群加總）的方向
        f_series, t_series = [], []
        for _d, snap in snapshots:
            fs = sum(snap[c][0] for c in codes if c in snap)
            ts = sum(snap[c][1] for c in codes if c in snap)
            f_series.append(fs)
            t_series.append(ts)
        contrib.sort(reverse=True)
        out.append({
            "name": name,
            "f_val": round(f_val / 1e8, 1),   # 億
            "t_val": round(t_val / 1e8, 1),
            "f_streak": streak_of(f_series),
            "t_streak": streak_of(t_series),
            "n": len(contrib),
            "top": [{"code": c, "name": nm, "val": round(v / 1e8, 1)}
                    for _a, c, nm, v in contrib[:3]],
        })
    out.sort(key=lambda x: x["f_val"], reverse=True)
    return out


def main() -> None:
    t86 = read_json("t86")
    daily = read_json("daily_all")
    if not t86.get("ok") or not daily.get("ok"):
        write_error("flow", "t86 + daily_all 聚合",
                    f"t86:{t86.get('error')}；daily_all:{daily.get('error')}")
        return
    stocks_t86 = t86["data"]["stocks"]
    info = {s["code"]: s for s in daily["data"]["stocks"]}
    snapshots = load_snapshots()

    # 產業（全市場，TWSE/TPEx 官方分類）
    ind_groups: dict[str, list[str]] = {}
    for c, s in info.items():
        if s.get("industry") and len(c) == 4 and c.isdigit():
            ind_groups.setdefault(s["industry"], []).append(c)
    industries = aggregate(ind_groups, info, stocks_t86, snapshots)

    # 題材（自選 topics.json）
    topic_groups: dict[str, list[str]] = {}
    try:
        topics = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))["topics"]
        for t in topics:
            topic_groups[t["name"]] = t["stocks"]
    except Exception as e:
        print(f"[WARN] topics.json 讀取失敗：{e}")
    topics_flow = aggregate(topic_groups, info, stocks_t86, snapshots)

    write_json("flow", {
        "industries": industries[:TOP_N] + industries[-TOP_N:] if len(industries) > TOP_N * 2 else industries,
        "topics": topics_flow,
        "n_history_days": len(snapshots),
        "top_n": TOP_N,
    }, data_date=t86.get("data_date"), source="T86 聚合（金額=股數×收盤估算）",
        error=None)


if __name__ == "__main__":
    main()
