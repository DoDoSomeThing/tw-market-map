# build_summary.py — 今日一句白話摘要（純規則、零新資料源、零 API）
# 讀 breadth/market/flow/heatmap → 套 if/else 模板組人話 → data/summary.json
# 定位：現況直述、非預測、非買賣訊號。規則寫死 = 可重現、不幻覺（呼應網站主張）。
from __future__ import annotations

from tw_common import read_json, write_error, write_json

MIN_GROUP_N = 5   # 產業強弱只看成分股 ≥5 檔的族群，避免小樣本雜訊


def _yi(v) -> float:
    """元 → 億。"""
    return (v or 0) / 1e8


def _net_word(yi: float) -> str:
    if yi > 0.5:
        return f"買超 {yi:.0f} 億"
    if yi < -0.5:
        return f"賣超 {abs(yi):.0f} 億"
    return "進出持平"


def main() -> None:
    breadth = read_json("breadth")
    market = read_json("market")
    flow = read_json("flow")
    heatmap = read_json("heatmap")

    lines: list[str] = []
    data_date = None
    for env in (breadth, market, flow, heatmap):
        if env.get("ok") and env.get("data_date"):
            data_date = env["data_date"]
            break

    # ── 1. 大盤寬度 ──
    if breadth.get("ok"):
        d = breadth["data"]
        up, down = d.get("up", 0), d.get("down", 0)
        if up >= down * 1.5:
            direction = "偏多、普遍上漲"
        elif down >= up * 1.5:
            direction = "偏空、賣壓較重"
        elif up > down:
            direction = "漲跌互見、略偏多"
        elif down > up:
            direction = "漲跌互見、略偏空"
        else:
            direction = "漲跌家數相當"
        upv = d.get("up_value_pct")
        upv_txt = ""
        if upv is not None:
            upv_txt = f"；上漲成交值占比 {upv}%（{'資金集中強勢股' if upv >= 50 else '強勢股撐盤有限'}）"
        lines.append(
            f"大盤{direction}：上漲 {up} 家、下跌 {down} 家，"
            f"漲停 {d.get('limit_up', 0)}、跌停 {d.get('limit_down', 0)}{upv_txt}。"
        )

    # ── 2. 三大法人（上市+上櫃合計）──
    if market.get("ok"):
        md = market["data"]
        twse = (md.get("inst_twse") or {}).get("rows", {})
        tpex = (md.get("inst_tpex") or {}).get("rows", {})

        def net(key: str) -> float:
            t = (twse.get(key) or {}).get("net", 0)
            o = (tpex.get(key) or {}).get("net", 0)
            return _yi(t) + _yi(o)

        foreign, trust = net("foreign"), net("trust")
        lines.append(f"三大法人：外資{_net_word(foreign)}、投信{_net_word(trust)}（上市＋上櫃合計）。")

    # ── 3. 資金流向（族群外資淨流入/流出極值）──
    if flow.get("ok"):
        inds = flow["data"].get("industries", [])
        rated = [g for g in inds if g.get("f_val") is not None]
        if rated:
            inflow = max(rated, key=lambda g: g["f_val"])
            outflow = min(rated, key=lambda g: g["f_val"])
            in_streak = inflow.get("f_streak", 0) or 0
            streak_txt = f"、連 {in_streak} 日" if in_streak >= 3 else ""
            lines.append(
                f"資金流向：外資最大流入{inflow['name']}（+{inflow['f_val']:.0f} 億{streak_txt}）、"
                f"最大流出{outflow['name']}（{outflow['f_val']:.0f} 億）。"
            )

    # ── 4. 產業強弱（熱力圖均漲跌極值）──
    if heatmap.get("ok"):
        groups = [g for g in heatmap["data"].get("groups", [])
                  if (g.get("n_stocks") or 0) >= MIN_GROUP_N and g.get("avg_pct") is not None]
        if groups:
            strong = max(groups, key=lambda g: g["avg_pct"])
            weak = min(groups, key=lambda g: g["avg_pct"])
            lines.append(
                f"產業表現：{strong['industry']}最強（均 {strong['avg_pct']:+.1f}%）、"
                f"{weak['industry']}最弱（均 {weak['avg_pct']:+.1f}%）。"
            )

    if not lines:
        write_error("summary", "build_summary", "上游資料全失敗，無法產生摘要")
        return

    lines.append("以上為當日數據直述、非買賣訊號。")
    write_json("summary", {"lines": lines}, data_date=data_date, source="規則彙整（breadth/market/flow/heatmap）")


if __name__ == "__main__":
    main()
