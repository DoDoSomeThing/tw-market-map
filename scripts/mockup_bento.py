#!/usr/bin/env python3
"""mockup_bento.py — 首頁改版提案（Bento Grid）→ docs/mockup_bento.html

用途：純提案，不動 render.py / 不進管線。讀 data/*.json 的**真實資料**產出，
方便跟現況直接對比。滿意後才把樣式移植回 render.py。

設計依據（ui-ux-pro-max）：
  Style      Bento Grid — 高資訊密度但不雜亂（正是「擠在一起」的解方）
  Typography Fira Sans + Fira Code（dashboard/數據；數字等寬 = 金融標配）
  Color      藍資料 + 琥珀高亮（解決「沒有重點」）
  Rules      圓角 16-24px、gap 20px、卡片 1x1/2x1/2x2 依重要性、hover 微動
"""
from __future__ import annotations

import json
from datetime import datetime

from tw_common import DOCS_DIR, read_json


def cls(v):
    return "up" if (v or 0) > 0 else ("down" if (v or 0) < 0 else "flat")


def sg(v, d=2):
    return f"{'+' if (v or 0) > 0 else ''}{v:.{d}f}"


def trend_svg(series, key, w=560, h=90):
    vals = [s.get(key) for s in series if s.get(key) is not None]
    if len(vals) < 2:
        return ""
    mx = max(abs(v) for v in vals) or 1
    n, bw, mid = len(series), w / len(series), h / 2
    bars = []
    for i, s in enumerate(series):
        v = s.get(key)
        if v is None:
            continue
        bh = max(2, abs(v) / mx * (mid - 10))
        y = mid - bh if v >= 0 else mid
        c = "var(--up)" if v >= 0 else "var(--down)"
        bars.append(f'<rect x="{i*bw+2.5:.1f}" y="{y:.1f}" width="{max(2,bw-5):.1f}" '
                    f'height="{bh:.1f}" rx="2" fill="{c}"><title>{s["date"][5:]} {v:+.0f}億</title></rect>')
    return (f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" class="spark-bars">'
            f'<line x1="0" y1="{mid}" x2="{w}" y2="{mid}" stroke="var(--line)"/>'
            + "".join(bars) + "</svg>")


def main() -> None:
    idx = read_json("indices")
    br = read_json("breadth")
    mt = read_json("market_trend")
    flow = read_json("flow")
    rank = read_json("rank")
    rev = read_json("revenue_hl")

    cards = idx["data"]["cards"] if idx.get("ok") else []
    main_idx = next((c for c in cards if c["symbol"] == "^TWII"), None)
    others = [c for c in cards if c["symbol"] != "^TWII"][:6]
    b = br["data"] if br.get("ok") else {}
    series = mt["data"]["series"] if mt.get("ok") else []
    ind = flow["data"]["industries"][:5] if flow.get("ok") else []
    ups = rank["data"]["day_up"][:6] if rank.get("ok") else []
    revs = rev["data"]["items"][:4] if rev.get("ok") else []

    n = b.get("n", 1) or 1
    pu, pd = b.get("up", 0) / n * 100, b.get("down", 0) / n * 100
    last_t = next((s for s in reversed(series) if s.get("total") is not None), {})
    last_m = next((s for s in reversed(series) if s.get("margin_chg") is not None), {})

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bento 改版提案 — 台股產業地圖</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:#0a0e17; --card:#121826; --card2:#161d2e; --line:#232c40; --line-hi:#33415c;
  --fg:#e8edf5; --muted:#8a97ad;
  --up:#ff4d4f; --down:#00c98d; --flat:#8a97ad;
  --brand:#3b82f6; --brand-soft:rgba(59,130,246,.12); --hi:#f59e0b; --hi-soft:rgba(245,158,11,.12);
  --r:20px; --gap:20px;
  --sans:"Fira Sans",-apple-system,"PingFang TC","Microsoft JhengHei",sans-serif;
  --mono:"Fira Code",ui-monospace,monospace;
}}
:root[data-theme="light"] {{
  --bg:#f5f5f7; --card:#ffffff; --card2:#fbfcfe; --line:#e5e9f0; --line-hi:#cfd8e6;
  --fg:#131a26; --muted:#5b6880; --up:#d92d20; --down:#067a5b;
  --brand:#2563eb; --brand-soft:rgba(37,99,235,.09); --hi:#b45309; --hi-soft:rgba(180,83,9,.1);
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--fg);font-family:var(--sans);padding:24px;
  max-width:1240px;margin:0 auto;line-height:1.5;-webkit-font-smoothing:antialiased}}
.num{{font-family:var(--mono);font-feature-settings:"tnum"}}
.up{{color:var(--up)}} .down{{color:var(--down)}} .flat{{color:var(--flat)}}

header{{display:flex;align-items:baseline;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
h1{{font-size:1.3rem;font-weight:600;letter-spacing:-.01em}}
.sub{{color:var(--muted);font-size:.8rem}}
.badge{{background:var(--hi-soft);color:var(--hi);font-size:.7rem;padding:3px 10px;
  border-radius:999px;font-weight:600;margin-left:auto}}

/* Bento：卡片大小依重要性，不是把東西塞滿 */
.bento{{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap)}}
.c{{background:var(--card);border:1px solid var(--line);border-radius:var(--r);padding:18px 20px;
  transition:border-color .2s,transform .2s,box-shadow .2s}}
.c:hover{{border-color:var(--line-hi);transform:translateY(-2px);
  box-shadow:0 8px 28px rgba(0,0,0,.28)}}
.c-2{{grid-column:span 2}} .c-4{{grid-column:span 4}}
.c-hd{{display:flex;align-items:center;gap:8px;margin-bottom:12px}}
.c-hd h2{{font-size:.82rem;font-weight:600;color:var(--muted);letter-spacing:.02em}}
.c-hd .dot{{width:6px;height:6px;border-radius:50%;background:var(--brand)}}
.c-hd .when{{margin-left:auto;font-size:.68rem;color:var(--muted);font-family:var(--mono)}}

/* 主指數：最大、最重 = 視線第一站 */
.hero .v{{font-size:2.6rem;font-weight:700;letter-spacing:-.02em;line-height:1.1}}
.hero .d{{font-size:1rem;margin-top:2px}}
.mini{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px;
  padding-top:14px;border-top:1px solid var(--line)}}
.mini div{{font-size:.7rem;color:var(--muted)}}
.mini b{{display:block;font-size:.95rem;font-weight:600;margin-top:1px}}

/* 寬度條 */
.bar{{display:flex;height:8px;border-radius:4px;overflow:hidden;margin:10px 0 8px}}
.bar i{{display:block}}
.wrow{{display:flex;justify-content:space-between;font-size:.78rem}}
.big{{font-size:1.6rem;font-weight:700;letter-spacing:-.02em}}

.spark-bars{{width:100%;height:90px;display:block}}
.axis{{display:flex;justify-content:space-between;font-size:.65rem;color:var(--muted);
  font-family:var(--mono);margin-top:4px}}

/* 排行：不用表格，用列 */
.rows{{display:flex;flex-direction:column;gap:1px;background:var(--line);border-radius:12px;overflow:hidden}}
.row{{display:flex;align-items:center;gap:10px;background:var(--card);padding:9px 12px;font-size:.85rem;
  cursor:pointer;transition:background .15s}}
.row:hover{{background:var(--card2)}}
.row .rk{{font-family:var(--mono);font-size:.7rem;color:var(--muted);width:16px}}
.row .nm{{font-weight:500}}
.row .cd{{font-size:.7rem;color:var(--muted);font-family:var(--mono)}}
.row .pv{{margin-left:auto;font-family:var(--mono);font-weight:600}}

.flow-row{{display:flex;align-items:center;gap:10px;padding:7px 0;font-size:.85rem}}
.flow-row .nm{{width:78px;font-weight:500}}
.flow-bar{{flex:1;height:6px;background:var(--line);border-radius:3px;overflow:hidden;position:relative}}
.flow-bar i{{position:absolute;top:0;bottom:0;border-radius:3px}}
.flow-row .v{{width:74px;text-align:right;font-family:var(--mono);font-size:.78rem}}

.rev{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.rev .k{{background:var(--card2);border:1px solid var(--line);border-radius:14px;padding:12px 14px}}
.rev .k b{{font-size:.92rem}} .rev .k .y{{color:var(--up);font-family:var(--mono);font-weight:600;font-size:1.1rem}}

footer{{color:var(--muted);font-size:.72rem;margin-top:24px;line-height:1.7}}
@media(max-width:900px){{.bento{{grid-template-columns:repeat(2,1fr)}}.c-2,.c-4{{grid-column:span 2}}
  .rev{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:560px){{body{{padding:14px}}.bento{{grid-template-columns:1fr}}
  .c-2,.c-4{{grid-column:span 1}}.rev{{grid-template-columns:1fr}}}}
@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style></head><body>

<header>
  <h1>台股產業地圖</h1><span class="sub">現況呈現 · 不預測</span>
  <span class="badge">Bento 改版提案</span>
</header>

<div class="bento">

  <!-- 1. 加權指數：最大卡 = 第一眼 -->
  <div class="c c-2 hero">
    <div class="c-hd"><span class="dot"></span><h2>加權指數</h2>
      <span class="when">{main_idx['date'][5:].replace('-','/') if main_idx else ''}</span></div>
    <div class="v num {cls(main_idx['pct']) if main_idx else ''}">{f"{main_idx['close']:,.0f}" if main_idx else '—'}</div>
    <div class="d num {cls(main_idx['pct']) if main_idx else ''}">{sg(main_idx['change']) if main_idx else ''}（{sg(main_idx['pct']) if main_idx else ''}%）</div>
    <div class="mini">
      {''.join(f'<div>{c["short"]}<b class="num {cls(c["pct"])}">{sg(c["pct"])}%</b></div>' for c in others[:3])}
    </div>
  </div>

  <!-- 2. 市場寬度：今天多空一眼 -->
  <div class="c c-2">
    <div class="c-hd"><span class="dot"></span><h2>市場寬度</h2><span class="when">{b.get('n',0)} 檔個股</span></div>
    <div class="big num {'down' if pd > pu else 'up'}">{pd:.0f}% <span style="font-size:.9rem;font-weight:400;color:var(--muted)">下跌</span></div>
    <div class="bar"><i class="" style="width:{pu}%;background:var(--up)"></i>
      <i style="width:{b.get('flat',0)/n*100}%;background:var(--line-hi)"></i>
      <i style="width:{pd}%;background:var(--down)"></i></div>
    <div class="wrow"><span class="up num">▲ {b.get('up',0)}</span>
      <span class="sub num">平 {b.get('flat',0)}</span>
      <span class="down num">▼ {b.get('down',0)}</span></div>
    <div class="mini">
      <div>漲停<b class="up num">{b.get('limit_up',0)}</b></div>
      <div>跌停<b class="down num">{b.get('limit_down',0)}</b></div>
      <div>上漲成交值占比<b class="num">{b.get('up_value_pct','—')}%</b></div>
    </div>
  </div>

  <!-- 3. 法人趨勢：近兩週 -->
  <div class="c c-2">
    <div class="c-hd"><span class="dot" style="background:var(--hi)"></span><h2>三大法人買賣超</h2>
      <span class="when">近 {len(series)} 日</span></div>
    <div class="big num {cls(last_t.get('total'))}">{sg(last_t.get('total',0),1)} 億</div>
    {trend_svg(series, 'total')}
    <div class="axis"><span>{series[0]['date'][5:].replace('-','/') if series else ''}</span>
      <span>{series[-1]['date'][5:].replace('-','/') if series else ''}</span></div>
  </div>

  <!-- 4. 融資趨勢 -->
  <div class="c c-2">
    <div class="c-hd"><span class="dot" style="background:var(--hi)"></span><h2>融資增減</h2>
      <span class="when">近 {len(series)} 日</span></div>
    <div class="big num {cls(last_m.get('margin_chg'))}">{sg(last_m.get('margin_chg',0),1)} 億</div>
    {trend_svg(series, 'margin_chg')}
    <div class="axis"><span>{series[0]['date'][5:].replace('-','/') if series else ''}</span>
      <span>{series[-1]['date'][5:].replace('-','/') if series else ''}</span></div>
  </div>

  <!-- 5. 資金流 -->
  <div class="c c-2">
    <div class="c-hd"><span class="dot"></span><h2>外資產業資金流</h2><span class="when">今日</span></div>
    {''.join(f'''<div class="flow-row"><span class="nm">{r["name"]}</span>
      <span class="flow-bar"><i style="{'left:50%;' if r['f_val']>=0 else 'right:50%;'}width:{min(50, abs(r['f_val'])/max(abs(x['f_val']) for x in ind)*50):.0f}%;background:var({'--up' if r['f_val']>=0 else '--down'})"></i></span>
      <span class="v {cls(r['f_val'])}">{sg(r['f_val'],0)}億</span></div>''' for r in ind)}
  </div>

  <!-- 6. 強勢股 -->
  <div class="c c-2">
    <div class="c-hd"><span class="dot"></span><h2>今日強勢</h2><span class="when">成交值 ≥1億</span></div>
    <div class="rows">
      {''.join(f'''<div class="row"><span class="rk">{i+1}</span><span class="nm">{r["name"]}</span>
        <span class="cd">{r["code"]}</span><span class="pv up">{sg(r["pct"])}%</span></div>'''
        for i, r in enumerate(ups))}
    </div>
  </div>

  <!-- 7. 營收亮點 -->
  <div class="c c-4">
    <div class="c-hd"><span class="dot" style="background:var(--hi)"></span><h2>營收亮點</h2>
      <span class="when">{rev['data']['ym_label'] if rev.get('ok') else ''}</span></div>
    <div class="rev">
      {''.join(f'''<div class="k"><b>{r["name"]}</b> <span class="cd num" style="color:var(--muted);font-size:.7rem">{r["code"]}</span>
        <div class="y">+{r["yoy"]}%</div><div class="sub num">營收 {r["rev_yi"]} 億</div></div>''' for r in revs)}
    </div>
  </div>

</div>

<footer>
  Bento Grid 提案 · 卡片大小依重要性配置（加權指數/市場寬度最大）· Fira Sans + Fira Code（數字等寬）·
  藍=資料、琥珀=需注意<br>
  資料為真實值，產生於 {datetime.now().strftime('%Y-%m-%d %H:%M')} · 僅為版面提案，未接管線
</footer>
</body></html>"""

    out = DOCS_DIR / "mockup_bento.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] {out}（{out.stat().st_size/1024:.0f} KB）")


if __name__ == "__main__":
    main()
