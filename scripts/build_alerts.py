# build_alerts.py — 今日異常警示（純規則、零新資料源、零 API）
# 讀 inst_rank/ta/daily_all → 挑超過門檻的極端事件 → data/alerts.json
# 定位：現況直述、非買賣訊號。門檻寫死 = 可重現、不幻覺。
from __future__ import annotations

from tw_common import read_json, write_error, write_json

FOREIGN_YI = 30.0   # 外資單股買/賣超 ≥ 30 億 → 異常
TRUST_YI = 10.0     # 投信單股買/賣超 ≥ 10 億 → 異常
VOL_X = 3.0         # 今日量 ≥ 3 倍 20 日均量 → 爆量
MAX_ALERTS = 12     # 最多列幾檔（避免洗版）


def _streak_txt(streak) -> str:
    s = abs(streak or 0)
    return f"・連 {s} 日" if s >= 3 else ""


def main() -> None:
    inst = read_json("inst_rank")
    ta = read_json("ta")
    daily = read_json("daily_all")

    # code → 個股基本資料（名稱/漲跌/收盤/產業）
    meta: dict[str, dict] = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            c = s["code"]
            if len(c) == 4 and c.isdigit():
                meta[c] = {"name": s.get("name") or c, "pct": s.get("pct"),
                           "close": s.get("close"), "industry": s.get("industry") or ""}

    alerts: dict[str, dict] = {}   # code → {code,name,industry,pct,tags:[{t,dir}],score}

    def add(code: str, name: str, industry: str, pct, tag: str, direction: str, score: float) -> None:
        a = alerts.get(code)
        if not a:
            a = alerts[code] = {"code": code, "name": name, "industry": industry,
                                "pct": pct, "tags": [], "score": 0.0}
        a["tags"].append({"t": tag, "dir": direction})
        a["score"] = max(a["score"], score)

    # ── 法人爆買爆賣（inst_rank 已按金額排序）──
    if inst.get("ok"):
        d = inst["data"]

        def scan(rows, value_key, streak_key, who, yi_thresh):
            for r in rows or []:
                yi = (r.get(value_key) or 0) / 1e8
                if abs(yi) < yi_thresh:
                    break   # 已排序，低於門檻後面更小 → 停
                direction = "up" if yi > 0 else "down"   # 買超(正)紅、賣超(負)綠（台股紅漲綠跌）
                word = "買超" if yi > 0 else "賣超"
                tag = f"{who}{word} {abs(yi):.0f} 億{_streak_txt(r.get(streak_key))}"
                add(r["code"], r.get("name") or r["code"], r.get("industry") or "",
                    meta.get(r["code"], {}).get("pct"), tag, direction, abs(yi))

        scan(d.get("foreign_buy"), "f_value", "f_streak", "外資", FOREIGN_YI)
        scan(d.get("foreign_sell"), "f_value", "f_streak", "外資", FOREIGN_YI)
        scan(d.get("trust_buy"), "t_value", "t_streak", "投信", TRUST_YI)
        scan(d.get("trust_sell"), "t_value", "t_streak", "投信", TRUST_YI)

    # ── 爆量（ta.vol_ratio ≥ 3）──
    if ta.get("ok"):
        for code, t in ta["data"].get("stocks", {}).items():
            vr = t.get("vol_ratio")
            if vr is None or vr < VOL_X:
                continue
            m = meta.get(code)
            if not m:
                continue   # 沒基本資料（ETF/權證等）跳過
            add(code, m["name"], m["industry"], m["pct"],
                f"爆量 {vr:.1f} 倍", "warn", vr * 15)   # ×15 讓量能與億級金額同量級可排序

    # 分兩組：法人異常（有買賣超 tag）優先且獨立於爆量，避免小型股爆量洗掉大型股法人巨量
    def has_inst(a) -> bool:
        return any(t["dir"] in ("up", "down") for t in a["tags"])

    inst_list = sorted((a for a in alerts.values() if has_inst(a)),
                       key=lambda a: a["score"], reverse=True)[:MAX_ALERTS]
    vol_list = sorted((a for a in alerts.values() if not has_inst(a)),
                      key=lambda a: a["score"], reverse=True)[:MAX_ALERTS]

    if not (inst.get("ok") or ta.get("ok")):
        write_error("alerts", "build_alerts", "上游 inst_rank/ta 全失敗")
        return

    data_date = inst.get("data_date") or ta.get("data_date") or daily.get("data_date")
    write_json("alerts", {"inst": inst_list, "vol": vol_list, "thresholds":
               {"foreign_yi": FOREIGN_YI, "trust_yi": TRUST_YI, "vol_x": VOL_X}},
               data_date=data_date, source="規則彙整（inst_rank/ta）")


if __name__ == "__main__":
    main()
