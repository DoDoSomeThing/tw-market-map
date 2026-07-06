# render.py — 讀 data/*.json → 產 docs/index.html（dark 單頁、RWD、無框架）
# 新鮮度在瀏覽端 JS 算：頁面可能隔好幾天才被打開，伺服端算會「裝新鮮」。
from __future__ import annotations

import json
from datetime import datetime

from tw_common import DOCS_DIR, read_json

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股產業地圖</title>
<style>
:root {
  --bg: #0d1117; --panel: #161b22; --border: #30363d;
  --fg: #e6edf3; --muted: #8b949e;
  --up: #f85149; --down: #3fb950; --flat: #8b949e; /* 台股紅漲綠跌 */
  --warn: #d29922;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; padding: 12px; max-width: 1200px; margin: 0 auto; }
h1 { font-size: 1.3rem; padding: 8px 0; }
h2 { font-size: 1.05rem; padding: 14px 0 8px; color: var(--fg); }
.sub { color: var(--muted); font-size: .78rem; }
.stamp { color: var(--muted); font-size: .75rem; margin-left: 8px; }
.stale { color: var(--warn); font-weight: 600; }
section { margin-bottom: 10px; }
.err { color: var(--warn); background: var(--panel); border: 1px solid var(--warn); border-radius: 8px; padding: 10px; font-size: .85rem; }

/* 指數卡 */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.card .nm { font-size: .8rem; color: var(--muted); }
.card .px { font-size: 1.15rem; font-weight: 700; margin-top: 2px; }
.card .chg { font-size: .85rem; }

/* 法人/資券 */
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; font-size: .85rem; }
th, td { padding: 6px 10px; text-align: right; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 500; font-size: .78rem; }
tr:last-child td { border-bottom: none; }

/* 熱力圖 */
#heatmap { width: 100%; }
.hm-group { margin-bottom: 6px; }
.hm-title { font-size: .8rem; color: var(--muted); padding: 4px 2px; }
.hm-title b { color: var(--fg); }
.hm-box { position: relative; width: 100%; border-radius: 6px; overflow: hidden; }
.hm-cell { position: absolute; overflow: hidden; border: 1px solid var(--bg); display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; cursor: default; }
.hm-cell .c-nm { font-weight: 600; white-space: nowrap; }
.hm-cell .c-pc { white-space: nowrap; opacity: .9; }

.up { color: var(--up); } .down { color: var(--down); } .flat { color: var(--flat); }
.ranks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 700px) { .ranks { grid-template-columns: 1fr; } }
footer { color: var(--muted); font-size: .72rem; padding: 18px 0; line-height: 1.6; }
</style>
</head>
<body>
<h1>台股產業地圖 <span class="sub">自用・現況呈現・不預測</span></h1>
<div class="sub" id="built-at"></div>

<section id="sec-indices"><h2>國際指數 <span class="stamp" data-stamp="indices"></span></h2><div id="indices"></div></section>
<section id="sec-market"><h2>三大法人與資券 <span class="stamp" data-stamp="market"></span></h2><div id="market"></div></section>
<section id="sec-heatmap"><h2>產業熱力圖 <span class="stamp" data-stamp="heatmap"></span></h2><div class="sub">格子大小=成交值｜顏色=漲跌%（紅漲綠跌）｜各產業取成交值前 25 檔</div><div id="heatmap"></div></section>
<section id="sec-rank"><h2>強勢/弱勢排行 <span class="stamp" data-stamp="rank"></span></h2><div id="ranks"></div></section>

<footer>
資料源：TWSE / TPEx 公開 API、yfinance。每交易日 17:30 後自動更新。<br>
鐵則：只做現況呈現，不做預測；各區塊資料日不一致或過期時顯示 ⚠️。
</footer>

<script>
const DATA = __DATA__;
const BUILT_AT = "__BUILT_AT__";

// ── 新鮮度（瀏覽端算，跳過六日）──
function tradingDayAge(iso) {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return null;
  const today = new Date(); today.setHours(0,0,0,0);
  if (d >= today) return 0;
  let age = 0, cur = new Date(today);
  while (cur > d) {
    cur.setDate(cur.getDate() - 1);
    const w = cur.getDay();
    if (w !== 0 && w !== 6) age++;
  }
  return age;
}
function stampFor(env) {
  if (!env || !env.ok) return `<span class="stale">⚠️ 資料抓取失敗</span>`;
  const age = tradingDayAge(env.data_date);
  const mmdd = env.data_date ? env.data_date.slice(5).replace("-", "/") : "?";
  if (age === null) return `<span class="stale">⚠️ 資料日無法解析</span>`;
  if (age > 2) return `<span class="stale">⚠️ 資料日 ${mmdd}（${age} 交易日前，可能過期）</span>`;
  return `資料日 ${mmdd}`;
}
function cls(p) { return p > 0 ? "up" : (p < 0 ? "down" : "flat"); }
function sign(p) { return (p > 0 ? "+" : "") + p.toFixed(2); }
function yi(v) { return v == null ? "—" : (v / 1e8).toFixed(1); } // 元 → 億

// ── 指數卡 ──
(function () {
  const env = DATA.indices, el = document.getElementById("indices");
  document.querySelector('[data-stamp="indices"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">指數抓取失敗：${env.error || ""}</div>`; return; }
  el.innerHTML = `<div class="cards">` + env.data.cards.map(c => {
    if (c.close == null) return `<div class="card"><div class="nm">${c.name}</div><div class="px stale">⚠️ 無資料</div></div>`;
    return `<div class="card"><div class="nm">${c.name} <span class="sub">${c.short}</span></div>
      <div class="px ${cls(c.pct)}">${c.close.toLocaleString()}</div>
      <div class="chg ${cls(c.pct)}">${sign(c.change)}（${sign(c.pct)}%）</div>
      <div class="sub">${c.date ? c.date.slice(5).replace("-","/") : ""}</div></div>`;
  }).join("") + `</div>`;
})();

// ── 法人/資券 ──
(function () {
  const env = DATA.market, el = document.getElementById("market");
  document.querySelector('[data-stamp="market"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">法人/資券抓取失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  const NAMES = { foreign: "外資", trust: "投信", dealer_self: "自營(自行)", dealer_hedge: "自營(避險)", dealer: "自營合計", total: "合計" };
  function instTable(title, inst) {
    if (!inst) return `<div><table><tr><th>${title}</th></tr><tr><td class="stale">⚠️ 抓取失敗</td></tr></table></div>`;
    const order = ["foreign", "trust", "dealer_self", "dealer_hedge", "dealer", "total"];
    const rows = order.filter(k => inst.rows[k]).map(k => {
      const r = inst.rows[k], n = r.net;
      return `<tr><td>${NAMES[k]}</td><td>${yi(r.buy)}</td><td>${yi(r.sell)}</td>
        <td class="${cls(n || 0)}">${n == null ? "—" : sign(n / 1e8)}</td></tr>`;
    }).join("");
    return `<div><table><tr><th>${title}（億）</th><th>買進</th><th>賣出</th><th>買賣超</th></tr>${rows}</table></div>`;
  }
  let marginHtml = "";
  if (d.margin) {
    const mv = d.margin.rows.margin_value, su = d.margin.rows.short_units;
    const chg = (mv.today_bal != null && mv.prev_bal != null) ? (mv.today_bal - mv.prev_bal) / 1e5 : null; // 仟元→億
    marginHtml = `<div><table><tr><th>資券（上市）</th><th>前日餘額</th><th>今日餘額</th><th>增減</th></tr>
      <tr><td>融資金額(億)</td><td>${mv.prev_bal != null ? (mv.prev_bal/1e5).toFixed(1) : "—"}</td>
      <td>${mv.today_bal != null ? (mv.today_bal/1e5).toFixed(1) : "—"}</td>
      <td class="${cls(chg || 0)}">${chg == null ? "—" : sign(chg)}</td></tr>
      ${su ? `<tr><td>融券(張)</td><td>${su.prev_bal?.toLocaleString() ?? "—"}</td><td>${su.today_bal?.toLocaleString() ?? "—"}</td>
      <td>${su.today_bal != null && su.prev_bal != null ? sign(su.today_bal - su.prev_bal).replace(".00","") : "—"}</td></tr>` : ""}
      </table><div class="sub" style="padding:4px 2px">TWSE 註：餘額以「前日餘額」欄為準。</div></div>`;
  } else {
    marginHtml = `<div class="err">資券抓取失敗</div>`;
  }
  el.innerHTML = `<div class="grid2">${instTable("上市法人", d.inst_twse)}${instTable("上櫃法人", d.inst_tpex)}</div>
    <div style="margin-top:8px">${marginHtml}</div>`;
})();

// ── 熱力圖（squarified treemap，手刻無依賴）──
function squarify(items, x, y, w, h, out) {
  // items: [{v, ...}] 已依 v 降冪。經典 squarify：逐列塞，長寬比最平衡時換列。
  if (!items.length) return;
  const total = items.reduce((s, it) => s + it.v, 0);
  if (total <= 0) return;
  const scale = (w * h) / total;
  let row = [], rest = items.slice(), rx = x, ry = y, rw = w, rh = h;
  function worst(row, side) {
    const s = row.reduce((a, b) => a + b.v * scale, 0);
    const s2 = s * s, side2 = side * side;
    let mx = 0, mn = Infinity;
    for (const it of row) { const a = it.v * scale; if (a > mx) mx = a; if (a < mn) mn = a; }
    return Math.max(side2 * mx / s2, s2 / (side2 * mn));
  }
  function layoutRow(row) {
    const s = row.reduce((a, b) => a + b.v * scale, 0);
    const horiz = rw >= rh; // 短邊排列
    const side = horiz ? rh : rw;
    const thick = s / side;
    let off = 0;
    for (const it of row) {
      const len = (it.v * scale) / thick;
      if (horiz) out.push({ ...it, x: rx, y: ry + off, w: thick, h: len });
      else out.push({ ...it, x: rx + off, y: ry, w: len, h: thick });
      off += len;
    }
    if (horiz) { rx += thick; rw -= thick; } else { ry += thick; rh -= thick; }
  }
  while (rest.length) {
    const side = Math.min(rw, rh);
    const it = rest[0];
    if (!row.length || worst(row.concat(it), side) <= worst(row, side)) {
      row.push(rest.shift());
    } else {
      layoutRow(row); row = [];
    }
  }
  if (row.length) layoutRow(row);
}
function pctColor(p) {
  // 紅漲綠跌，強度隨 |pct| 到 ±5% 飽和
  const t = Math.min(Math.abs(p) / 5, 1);
  if (p > 0) return `rgb(${Math.round(60+140*t)}, ${Math.round(45-20*t+15)}, ${Math.round(45-10*t+10)})`;
  if (p < 0) return `rgb(${Math.round(35)}, ${Math.round(60+110*t)}, ${Math.round(55+25*t)})`;
  return "#30363d";
}
(function () {
  const env = DATA.heatmap, el = document.getElementById("heatmap");
  document.querySelector('[data-stamp="heatmap"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">熱力圖資料失敗：${env.error || ""}</div>`; return; }
  const groups = env.data.groups;
  const totalValue = groups.reduce((s, g) => s + g.value, 0);
  const W = Math.min(el.clientWidth || document.body.clientWidth, 1176);
  el.innerHTML = groups.map((g, gi) => {
    const cells = g.cells.map(c => ({ ...c, v: c.value }));
    if (!cells.length) return "";
    // 產業區塊高度 ∝ sqrt(佔市場成交值比重)，最小 60px
    const h = Math.max(60, Math.round(Math.sqrt(g.value / totalValue) * 420));
    const out = [];
    squarify(cells, 0, 0, W, h, out);
    const boxes = out.map(c => {
      const fs = Math.max(9, Math.min(16, Math.sqrt(c.w * c.h) / 6));
      const showPct = c.h > 26 && c.w > 40;
      return `<div class="hm-cell" style="left:${c.x.toFixed(1)}px;top:${c.y.toFixed(1)}px;width:${c.w.toFixed(1)}px;height:${c.h.toFixed(1)}px;background:${pctColor(c.pct)};font-size:${fs.toFixed(0)}px"
        title="${c.code} ${c.name}　收 ${c.close}　${sign(c.pct)}%　成交 ${(c.value/1e8).toFixed(1)}億">
        <span class="c-nm">${c.name}</span>${showPct ? `<span class="c-pc">${sign(c.pct)}%</span>` : ""}</div>`;
    }).join("");
    return `<div class="hm-group"><div class="hm-title"><b>${g.industry}</b>
      <span class="${cls(g.avg_pct)}">${sign(g.avg_pct)}%</span>・成交 ${(g.value/1e8).toFixed(0)} 億・${g.n_stocks} 檔</div>
      <div class="hm-box" style="height:${h}px">${boxes}</div></div>`;
  }).join("");
})();

// ── 排行 ──
(function () {
  const env = DATA.rank, el = document.getElementById("ranks");
  document.querySelector('[data-stamp="rank"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">排行資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  function tbl(title, rows) {
    if (!rows || !rows.length) return `<div><table><tr><th>${title}</th></tr><tr><td class="sub">${d.week_label || "無資料"}</td></tr></table></div>`;
    const body = rows.map((r, i) => `<tr><td>${i+1}. ${r.name} <span class="sub">${r.code}・${r.industry}</span></td>
      <td>${r.close}</td><td class="${cls(r.pct)}">${sign(r.pct)}%</td><td class="sub">${(r.value/1e8).toFixed(1)}億</td></tr>`).join("");
    return `<div><table><tr><th>${title}</th><th>收盤</th><th>漲跌</th><th>成交</th></tr>${body}</table></div>`;
  }
  const wk = d.week_label && !d.week_label.includes("不足") ? d.week_label : "週";
  el.innerHTML = `<div class="ranks">
    ${tbl("日強勢 Top 20", d.day_up)}${tbl("日弱勢 Top 20", d.day_down)}
    ${tbl(wk + "強勢 Top 20", d.week_up)}${tbl(wk + "弱勢 Top 20", d.week_down)}
  </div><div class="sub" style="padding:4px 2px">排行門檻：日成交值 ≥ ${(d.min_trade_value/1e8).toFixed(0)} 億。</div>`;
})();

document.getElementById("built-at").textContent = "頁面產生時間 " + BUILT_AT;
</script>
</body>
</html>
"""


def main() -> None:
    data = {name: read_json(name) for name in ("indices", "market", "heatmap", "rank")}
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BUILT_AT__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] docs/index.html ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
