# render.py — 讀 data/*.json → 產 docs/index.html（dark 單頁、RWD、無框架）
# 新鮮度在瀏覽端 JS 算：頁面可能隔好幾天才被打開，伺服端算會「裝新鮮」。
from __future__ import annotations

import json
from datetime import datetime

from tw_common import DATA_DIR, DOCS_DIR, read_json

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>台股產業地圖</title>
<style>
:root {
  --bg: #05070d; --panel: #0d1524; --border: #1e2c45;
  --fg: #e6edf3; --muted: #7d8aa0;
  --up: #fb2c36; --down: #00bb7f; --flat: #7d8aa0; /* 台股紅漲綠跌 */
  --warn: #f99c00; --accent: #3b82f6;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; margin: 0 auto;
  background-image: linear-gradient(90deg, #3b82f60d 1px, transparent 0), linear-gradient(#3b82f60d 1px, transparent 0);
  background-size: 42px 42px; }
h1 { font-size: 1.15rem; }
h2 { font-size: 1.05rem; padding: 14px 0 8px; color: var(--fg); }

/* 頂部導覽 + 分頁 */
header.top { position: sticky; top: 0; z-index: 50; background: rgba(5,7,13,.92); backdrop-filter: blur(6px); border-bottom: 1px solid var(--border); }
.top-inner { max-width: 1200px; margin: 0 auto; padding: 10px 12px 0; }
.brand { display: flex; align-items: baseline; gap: 10px; padding-bottom: 6px; }
.tabs { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab { background: none; border: none; color: var(--muted); font-size: .92rem; padding: 9px 14px; cursor: pointer; white-space: nowrap; border-bottom: 2px solid transparent; font-family: inherit; }
.tab:hover { color: var(--fg); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
main { max-width: 1200px; margin: 0 auto; padding: 4px 12px 12px; }
.tabpane { display: none; }
.tabpane.active { display: block; }

/* 搜尋 */
.searchwrap { position: relative; margin-left: auto; }
#search { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; color: var(--fg); padding: 5px 10px; font-size: .85rem; width: 170px; font-family: inherit; }
#search:focus { outline: none; border-color: var(--accent); }
#search-res { position: absolute; right: 0; top: 34px; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; min-width: 300px; max-height: 320px; overflow-y: auto; display: none; z-index: 60; }
.sr-item { padding: 7px 10px; border-bottom: 1px solid var(--border); cursor: pointer; font-size: .85rem; display: flex; gap: 8px; align-items: center; }
.sr-item:hover { background: #1a2438; }
.sr-item:last-child { border-bottom: none; }
.sr-badge { font-size: .68rem; border: 1px solid var(--border); border-radius: 999px; padding: 1px 7px; color: var(--muted); cursor: pointer; }
.sr-badge:hover { border-color: var(--accent); color: var(--accent); }

/* 市場寬度 */
.breadth { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px; }
.b-bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; margin: 8px 0 6px; }
.b-bar > div { height: 100%; }
.b-row { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: .85rem; }

/* 營收亮點卡 */
.rev-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 8px; }
.rev-card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 9px 10px; font-size: .84rem; line-height: 1.55; cursor: pointer; }
.rev-card:hover { border-color: var(--accent); }
.rev-card b { font-size: .92rem; }

/* 日期回看 */
select { background: var(--panel); border: 1px solid var(--border); color: var(--fg); border-radius: 6px; padding: 3px 8px; font-size: .82rem; font-family: inherit; }
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
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 0; }
.chip { background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; font-size: .82rem; cursor: pointer; color: var(--fg); }
.chip.active { border-color: var(--fg); background: #21262d; }
.chip .g { color: var(--muted); font-size: .7rem; margin-right: 4px; }
.streak { font-size: .7rem; border-radius: 4px; padding: 0 4px; margin-left: 4px; }
.streak.buy { background: rgba(248,81,73,.15); color: var(--up); }
.streak.sell { background: rgba(63,185,80,.15); color: var(--down); }
.tag { font-size: .7rem; border-radius: 4px; padding: 1px 6px; margin-right: 6px; white-space: nowrap; }
.tag.t澄清 { background: rgba(210,153,34,.18); color: var(--warn); }
.tag.t自結 { background: rgba(88,166,255,.15); color: #58a6ff; }
.tag.t財務 { background: rgba(188,140,255,.15); color: #bc8cff; }
.tag.t治理 { background: rgba(139,148,158,.18); color: var(--muted); }
.tag.t重大 { background: rgba(248,81,73,.15); color: var(--up); }
.mops-list { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; font-size: .85rem; max-height: 420px; overflow-y: auto; }
.mops-item { padding: 7px 10px; border-bottom: 1px solid var(--border); line-height: 1.5; }
.mops-item:last-child { border-bottom: none; }
.mops-item .who { color: var(--fg); font-weight: 600; margin-right: 6px; }
.mops-item .tm { color: var(--muted); font-size: .75rem; margin-right: 6px; }

/* 價值鏈 */
.stage { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px; margin-bottom: 8px; }
.stage-title { font-size: .95rem; font-weight: 700; padding-bottom: 8px; }
.nodes { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 8px; }
.node { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.node-label { font-weight: 600; font-size: .88rem; }
.node-desc { color: var(--muted); font-size: .75rem; padding: 2px 0 6px; line-height: 1.4; }
.co { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; border-top: 1px solid var(--border); padding: 6px 2px; cursor: pointer; }
.co:hover { background: #1c2129; }
.co .co-nm { font-weight: 600; font-size: .85rem; }
.co .co-px { margin-left: auto; font-size: .85rem; white-space: nowrap; }
.co .tag { margin-right: 0; }
.topic-desc { color: var(--muted); font-size: .82rem; padding: 6px 2px; }
.ranks { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
@media (max-width: 700px) { .ranks { grid-template-columns: 1fr; } }
footer { color: var(--muted); font-size: .72rem; padding: 18px 0; line-height: 1.6; }
</style>
</head>
<body>
<header class="top"><div class="top-inner">
  <div class="brand"><h1>台股產業地圖</h1><span class="sub">自用・現況呈現・不預測</span>
    <div class="searchwrap"><input id="search" placeholder="搜代號/股名…" autocomplete="off"><div id="search-res"></div></div></div>
  <nav class="tabs" id="tabs">
    <button class="tab" data-pane="focus">每日焦點</button>
    <button class="tab" data-pane="topics">題材</button>
    <button class="tab" data-pane="chains">產業鏈</button>
    <button class="tab" data-pane="market">市場熱力</button>
    <button class="tab" data-pane="watch">觀測站</button>
    <button class="tab" data-pane="fund">基本面</button>
    <button class="tab" data-pane="news">新聞</button>
  </nav>
</div></header>
<main>

<div class="tabpane" id="pane-focus">
<section id="sec-indices"><h2>國際指數 <span class="stamp" data-stamp="indices"></span></h2><div id="indices"></div></section>
<section id="sec-breadth"><h2>市場寬度 <span class="stamp" data-stamp="breadth"></span></h2><div id="breadth"></div></section>
<section id="sec-revhl"><h2>營收亮點 <span class="stamp" data-stamp="revenue_hl"></span></h2><div class="sub" id="revhl-sub"></div><div id="revhl"></div></section>
<section id="sec-market"><h2>三大法人與資券 <span class="stamp" data-stamp="market"></span></h2><div id="market"></div></section>
<section id="sec-flow"><h2>法人資金流 <span class="stamp" data-stamp="flow"></span></h2><div class="sub">個股買賣超聚合到族群（金額=股數×收盤估算）｜「外資」是數百家機構彙總，這是族群淨流向，非同一筆錢的移動｜現況描述，非訊號</div><div id="flow"></div></section>
<section id="sec-inst"><h2>法人個股動向 <span class="stamp" data-stamp="inst_rank"></span></h2><div class="sub">買賣超金額=股數×收盤估算｜連買/連賣為現況描述，非進場訊號</div><div id="instrank"></div></section>
</div>

<div class="tabpane" id="pane-topics">
<section id="sec-topics"><h2>題材 <span class="stamp" data-stamp="topics_view"></span></h2><div class="sub">題材對照為 AI 初稿+人工校對，非官方分類</div><div id="topic-chips"></div><div id="topic-detail"></div></section>
</div>

<div class="tabpane" id="pane-chains">
<section id="sec-chains"><h2>產業價值鏈 <span class="stamp" data-stamp="chains_view"></span></h2><div class="sub">內容自產（上中下游整理，非官方分類、非投資建議）｜點個股開 Yahoo 股市頁（裝 kanpan 擴充會自動掛面板）</div><div id="chain-chips"></div><div id="chains"></div></section>
</div>

<div class="tabpane" id="pane-market">
<section id="sec-heatmap"><h2>產業熱力圖 <span class="stamp" data-stamp="heatmap"></span>
  <span style="float:right"><select id="lookback"></select></span></h2>
  <div class="sub">格子大小=成交值｜顏色=漲跌%（紅漲綠跌）｜各產業取成交值前 25 檔<span id="lookback-note"></span></div><div id="heatmap"></div></section>
<section id="sec-rank"><h2>強勢/弱勢排行 <span class="stamp" data-stamp="rank"></span></h2><div id="ranks"></div></section>
</div>

<div class="tabpane" id="pane-watch">
<section id="sec-tdcc"><h2>大戶動向（週） <span class="stamp" data-stamp="tdcc"></span></h2><div class="sub">TDCC 集保股權分散｜大戶=400 張以上持股比（千張=1,000 張以上）｜每週五結算、週六公布</div><div id="tdcc"></div></section>
<section id="sec-mops"><h2>重大訊息 <span class="stamp" data-stamp="mops"></span></h2><div class="sub">MOPS 公開資訊觀測站（上市+上櫃）｜標籤為主旨關鍵字自動分類</div><div id="mops"></div></section>
</div>

<div class="tabpane" id="pane-fund">
<section id="sec-fund"><h2>基本面速覽 <span class="stamp" data-stamp="fundamentals"></span></h2><div class="sub">季報（TWSE/TPEx openapi）｜殖利率=已公告現金股利÷現價，僅上市（上櫃股利端點無資料）｜排行門檻：日成交值 ≥ 0.5 億</div><div id="fund"></div></section>
</div>

<div class="tabpane" id="pane-news">
<section id="sec-news"><h2>市場新聞 <span class="stamp" data-stamp="news"></span></h2><div class="sub">鉅亨網 + Yahoo 股市 RSS 標題聚合｜內文請點標題回原站｜標籤為標題關鍵字自動比對</div><div id="news"></div></section>
</div>

<footer>
資料源：TWSE / TPEx 公開 API、yfinance、MOPS 公開資訊觀測站、TDCC 集保中心。每交易日 17:30 後自動更新。<br>
鐵則：只做現況呈現，不做預測；各區塊資料日不一致或過期時顯示 ⚠️。
</footer>
</main>

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
function stampFor(env, maxStale = 2) {
  if (!env || !env.ok) return `<span class="stale">⚠️ 資料抓取失敗</span>`;
  const age = tradingDayAge(env.data_date);
  const mmdd = env.data_date ? env.data_date.slice(5).replace("-", "/") : "?";
  if (age === null) return `<span class="stale">⚠️ 資料日無法解析</span>`;
  if (age > maxStale) return `<span class="stale">⚠️ 資料日 ${mmdd}（${age} 交易日前，可能過期）</span>`;
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
      </table><div class="sub" style="padding:4px 2px">TWSE 註：餘額以「前日餘額」欄為準。${d.margin.date && env.data_date && d.margin.date !== env.data_date ? `<span class="stale">⚠️ 資券為 ${d.margin.date.slice(5).replace("-","/")} 資料（本次抓取失敗沿用）</span>` : ""}</div></div>`;
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
function drawHeatmap(groups) {
  const el = document.getElementById("heatmap");
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
}
(function () {
  const env = DATA.heatmap;
  document.querySelector('[data-stamp="heatmap"]').innerHTML = stampFor(env);
  if (!env.ok) { document.getElementById("heatmap").innerHTML = `<div class="err">熱力圖資料失敗：${env.error || ""}</div>`; return; }
  drawHeatmap(env.data.groups);
})();

// ── 日期回看（熱力圖顏色以歷史快照重建；格子大小沿用最新成交值=近似）──
(function () {
  const sel = document.getElementById("lookback");
  const note = document.getElementById("lookback-note");
  const dates = DATA.history_dates || [];
  if (!DATA.heatmap.ok || dates.length < 2) { sel.style.display = "none"; return; }
  sel.innerHTML = `<option value="">最新（${DATA.heatmap.data_date || "?"}）</option>` +
    dates.slice(0, dates.length - 1).map(d => `<option value="${d}">${d.slice(5).replace("-", "/")}</option>`).join("");
  const cache = {};
  async function snap(d) {
    if (!cache[d]) cache[d] = fetch("history/" + d + ".json").then(r => r.json());
    return cache[d];
  }
  const closeOf = v => Array.isArray(v) ? v[0] : v;
  sel.addEventListener("change", async () => {
    const d = sel.value;
    if (!d) { drawHeatmap(DATA.heatmap.data.groups); note.textContent = ""; return; }
    const prev = dates[dates.indexOf(d) + 1];
    if (!prev) { note.textContent = "｜⚠️ 無前一日快照可比"; return; }
    try {
      const [cur, base] = await Promise.all([snap(d), snap(prev)]);
      const groups = DATA.heatmap.data.groups.map(g => {
        const cells = g.cells.map(c => {
          const c1 = closeOf(cur[c.code]), c0 = closeOf(base[c.code]);
          if (!c1 || !c0) return null;
          return { ...c, close: c1, pct: Math.round((c1 / c0 - 1) * 10000) / 100 };
        }).filter(Boolean);
        if (!cells.length) return null;
        return { ...g, cells,
          avg_pct: Math.round(cells.reduce((s, c) => s + c.pct, 0) / cells.length * 100) / 100 };
      }).filter(Boolean);
      drawHeatmap(groups);
      note.textContent = `｜🕐 回看 ${d}（vs ${prev} 收盤重建；格子大小沿用最新成交值，為近似）`;
    } catch (e) { note.textContent = "｜⚠️ 歷史快照載入失敗"; }
  });
})();

// ── 法人個股動向 ──
function streakBadge(s) {
  if (s > 1) return `<span class="streak buy">連買${s}</span>`;
  if (s < -1) return `<span class="streak sell">連賣${-s}</span>`;
  return "";
}
(function () {
  const env = DATA.inst_rank, el = document.getElementById("instrank");
  document.querySelector('[data-stamp="inst_rank"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">法人個股資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  function tbl(title, rows, who) {
    if (!rows || !rows.length) return `<div><table><tr><th>${title}</th></tr><tr><td class="sub">無資料</td></tr></table></div>`;
    const body = rows.map((r, i) => {
      const lots = who === "f" ? r.f_lots : r.t_lots;
      const val = who === "f" ? r.f_value : r.t_value;
      const stk = who === "f" ? r.f_streak : r.t_streak;
      return `<tr><td>${i+1}. ${r.name} <span class="sub">${r.code}・${r.industry}</span>${streakBadge(stk)}</td>
        <td class="${cls(lots)}">${lots > 0 ? "+" : ""}${lots.toLocaleString()}</td>
        <td class="${cls(val)}">${(Math.abs(val)/1e8).toFixed(1)}億</td>
        <td>${r.close}</td></tr>`;
    }).join("");
    return `<div><table><tr><th>${title}</th><th>張數</th><th>估金額</th><th>收盤</th></tr>${body}</table></div>`;
  }
  el.innerHTML = `<div class="ranks">
    ${tbl("外資買超 Top 15", d.foreign_buy, "f")}${tbl("外資賣超 Top 15", d.foreign_sell, "f")}
    ${tbl("投信買超 Top 15", d.trust_buy, "t")}${tbl("投信賣超 Top 15", d.trust_sell, "t")}
  </div>` + (d.n_history_days < 3 ? `<div class="sub" style="padding:4px 2px">連買/連賣天數需累積快照（目前 ${d.n_history_days} 日），數字會隨天數變準。</div>` : "");
})();

// ── 法人資金流 ──
(function () {
  const env = DATA.flow, el = document.getElementById("flow");
  document.querySelector('[data-stamp="flow"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">資金流資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  function stk(s) {
    if (s > 1) return `<span class="streak buy">連買${s}日</span>`;
    if (s < -1) return `<span class="streak sell">連賣${-s}日</span>`;
    return "";
  }
  function tbl(title, rows) {
    if (!rows || !rows.length) return `<div><table><tr><th>${title}</th></tr><tr><td class="sub">無資料</td></tr></table></div>`;
    const body = rows.map(r => `<tr>
      <td>${r.name} <span class="sub">${r.n}檔</span></td>
      <td class="${cls(r.f_val)}">${sign(r.f_val)}億${stk(r.f_streak)}</td>
      <td class="${cls(r.t_val)}">${sign(r.t_val)}億${stk(r.t_streak)}</td>
      <td class="sub">${r.top.map(t => `${t.name}${sign(t.val)}`).join("、")}</td></tr>`).join("");
    return `<div><table><tr><th>${title}</th><th>外資</th><th>投信</th><th>主要個股(億)</th></tr>${body}</table></div>`;
  }
  const K = 8;
  function split(arr) {
    const inflow = arr.filter(r => r.f_val > 0).slice(0, K);
    const outflow = arr.filter(r => r.f_val < 0).slice(-K).reverse();
    return { inflow, outflow };
  }
  const ind = split(d.industries), top = split(d.topics);
  el.innerHTML = `<div class="ranks">
    ${tbl("產業流入（全市場）", ind.inflow)}${tbl("產業流出（全市場）", ind.outflow)}
    ${tbl("題材流入（自選）", top.inflow)}${tbl("題材流出（自選）", top.outflow)}
  </div>` + (d.n_history_days < 3 ? `<div class="sub" style="padding:4px 2px">連買/連賣天數需累積快照（目前 ${d.n_history_days} 日），數字會隨天數變準。</div>` : "");
})();

// ── 題材 ──
(function () {
  const env = DATA.topics_view;
  const chipsEl = document.getElementById("topic-chips");
  const detailEl = document.getElementById("topic-detail");
  document.querySelector('[data-stamp="topics_view"]').innerHTML = stampFor(env);
  if (!env.ok) { chipsEl.innerHTML = `<div class="err">題材資料失敗：${env.error || ""}</div>`; return; }
  const topics = env.data.topics;
  function show(id, push) {
    const t = topics.find(x => x.id === id);
    if (!t) { detailEl.innerHTML = ""; return; }
    document.querySelectorAll(".chip").forEach(c => c.classList.toggle("active", c.dataset.id === id));
    if (push) { const p = new URLSearchParams(location.search); p.set("topic", id); history.replaceState(null, "", "?" + p + location.hash); }
    const W = Math.min(detailEl.clientWidth || document.body.clientWidth, 1176);
    const cells = t.members.map(m => ({ ...m, v: m.value })).filter(m => m.v > 0);
    const h = Math.max(90, Math.min(240, Math.round(40 * Math.sqrt(cells.length))));
    const out = [];
    squarify(cells, 0, 0, W, h, out);
    const boxes = out.map(c => {
      const fs = Math.max(9, Math.min(15, Math.sqrt(c.w * c.h) / 6));
      return `<div class="hm-cell" style="left:${c.x.toFixed(1)}px;top:${c.y.toFixed(1)}px;width:${c.w.toFixed(1)}px;height:${c.h.toFixed(1)}px;background:${pctColor(c.pct)};font-size:${fs.toFixed(0)}px"
        title="${c.code} ${c.name}　收 ${c.close}　${sign(c.pct)}%">
        <span class="c-nm">${c.name}</span>${c.h > 26 && c.w > 40 ? `<span class="c-pc">${sign(c.pct)}%</span>` : ""}</div>`;
    }).join("");
    const rows = t.members.map(m => `<tr title="${fundLine(m.code)}">
      <td>${m.name} <span class="sub">${m.code}</span></td>
      <td class="${cls(m.pct)}">${sign(m.pct)}%</td><td>${m.close}</td>
      <td class="sub">${(m.value/1e8).toFixed(1)}億</td>
      <td class="${m.f_lots == null ? "sub" : cls(m.f_lots)}">${m.f_lots == null ? "—" : (m.f_lots > 0 ? "+" : "") + m.f_lots.toLocaleString()}${streakBadge(m.f_streak)}</td>
      <td class="${m.t_lots == null ? "sub" : cls(m.t_lots)}">${m.t_lots == null ? "—" : (m.t_lots > 0 ? "+" : "") + m.t_lots.toLocaleString()}${streakBadge(m.t_streak)}</td>
    </tr>`).join("");
    detailEl.innerHTML = `<div class="topic-desc">${t.desc}　<span class="${cls(t.avg_pct)}">${sign(t.avg_pct)}%</span>・成交 ${(t.total_value/1e8).toFixed(0)} 億・${t.members.length} 檔</div>
      <div class="hm-box" style="height:${h}px;margin-bottom:8px">${boxes}</div>
      <table><tr><th>個股</th><th>漲跌</th><th>收盤</th><th>成交</th><th>外資(張)</th><th>投信(張)</th></tr>${rows}</table>`;
  }
  window.showTopic = show;   // 搜尋徽章跳轉用
  chipsEl.innerHTML = `<div class="chips">` + topics.map(t =>
    `<button class="chip" data-id="${t.id}"><span class="g">${t.group}</span>${t.name} <span class="${cls(t.avg_pct)}">${sign(t.avg_pct)}%</span></button>`
  ).join("") + `</div>`;
  chipsEl.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => show(c.dataset.id, true)));
  const q = new URLSearchParams(location.search).get("topic");
  show(q && topics.some(t => t.id === q) ? q : topics[0].id, false);
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

// ── 大戶動向（TDCC 週資料）──
(function () {
  const env = DATA.tdcc, el = document.getElementById("tdcc");
  document.querySelector('[data-stamp="tdcc"]').innerHTML = stampFor(env, 7).replace("資料日", "資料週");
  if (!env.ok) { el.innerHTML = `<div class="err">大戶資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  function pp(v) { return (v > 0 ? "+" : "") + v.toFixed(2); }
  function tbl(title, rows) {
    if (!rows || !rows.length) return `<div><table><tr><th>${title}</th></tr><tr><td class="sub">無資料</td></tr></table></div>`;
    const body = rows.map((r, i) => `<tr>
      <td>${i+1}. ${r.name || r.code} <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span></td>
      <td class="${cls(r.delta)}">${pp(r.delta)}</td>
      <td>${r.r400.toFixed(2)}%</td><td class="sub">${r.r1000.toFixed(2)}%</td>
      <td>${r.close ?? "—"}</td></tr>`).join("");
    return `<div><table><tr><th>${title}</th><th>週增減(pp)</th><th>400張+持股比</th><th>千張+</th><th>收盤</th></tr>${body}</table></div>`;
  }
  if (d.inc.length || d.dec.length) {
    el.innerHTML = `<div class="ranks">${tbl("大戶加碼 Top " + d.inc.length, d.inc)}${tbl("大戶減碼 Top " + d.dec.length, d.dec)}</div>
      <div class="sub" style="padding:4px 2px">對照週：${d.prev_week ? d.prev_week.slice(5).replace("-","/") : "—"}｜門檻：日成交值 ≥ ${(d.min_trade_value/1e8).toFixed(1)} 億。</div>`;
  } else if (d.top_r1000 && d.top_r1000.length) {
    const body = d.top_r1000.map((r, i) => `<tr>
      <td>${i+1}. ${r.name || r.code} <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span></td>
      <td>${r.r1000.toFixed(2)}%</td><td>${r.r400.toFixed(2)}%</td><td>${r.close ?? "—"}</td></tr>`).join("");
    el.innerHTML = `<table><tr><th>千張大戶持股比 Top 20</th><th>千張+</th><th>400張+</th><th>收盤</th></tr>${body}</table>
      <div class="sub" style="padding:4px 2px">首週快照（尚無前週可比），下週起顯示加碼/減碼排行。</div>`;
  } else {
    el.innerHTML = `<div class="sub">無資料</div>`;
  }
})();

// ── 產業價值鏈 ──
(function () {
  const env = DATA.chains_view;
  const chipsEl = document.getElementById("chain-chips");
  const el = document.getElementById("chains");
  document.querySelector('[data-stamp="chains_view"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">價值鏈資料失敗：${env.error || ""}</div>`; return; }
  const chains = env.data.chains;
  function lotsTag(who, lots) {
    if (lots == null || lots === 0) return "";
    const buy = lots > 0;
    return `<span class="tag ${buy ? "t重大" : "t治理"}" style="color:${buy ? "var(--up)" : "var(--down)"}">${who}${buy ? "買" : "賣"}${Math.abs(lots).toLocaleString()}張</span>`;
  }
  function show(id, push) {
    const ch = chains.find(c => c.id === id);
    if (!ch) { el.innerHTML = ""; return; }
    chipsEl.querySelectorAll(".chip").forEach(c => c.classList.toggle("active", c.dataset.id === id));
    if (push) { const p = new URLSearchParams(location.search); p.set("chain", id); history.replaceState(null, "", "?" + p + location.hash); }
    el.innerHTML = `<div class="topic-desc">${ch.desc}</div>` + ch.stages.map(st => `
      <div class="stage"><div class="stage-title">${st.name}</div><div class="nodes">` +
      st.nodes.map(nd => `<div class="node"><div class="node-label">${nd.label} <span class="sub">${nd.members.length} 檔</span></div>
        <div class="node-desc">${nd.desc}</div>` +
        nd.members.map(m => `<div class="co" data-code="${m.code}" data-mkt="${m.market || "twse"}" title="開 Yahoo 股市 ${m.code}（kanpan 擴充自動掛面板）${fundLine(m.code) ? "&#10;" + fundLine(m.code) : ""}">
          <span class="co-nm">${m.name} <span class="sub">${m.code}</span></span>
          ${lotsTag("外資", m.f_lots)}${lotsTag("投信", m.t_lots)}
          <span class="co-px ${cls(m.pct)}">${m.close} (${sign(m.pct)}%)</span></div>`).join("") +
        `</div>`).join("") + `</div></div>`).join("");
    el.querySelectorAll(".co").forEach(c => c.addEventListener("click", () =>
      window.open(`https://tw.stock.yahoo.com/quote/${c.dataset.code}.${c.dataset.mkt === "tpex" ? "TWO" : "TW"}`, "_blank")));
  }
  window.showChain = show;   // 搜尋徽章跳轉用
  chipsEl.innerHTML = `<div class="chips">` + chains.map(c =>
    `<button class="chip" data-id="${c.id}">${c.name}</button>`).join("") + `</div>`;
  chipsEl.querySelectorAll(".chip").forEach(c => c.addEventListener("click", () => show(c.dataset.id, true)));
  const q = new URLSearchParams(location.search).get("chain");
  show(q && chains.some(c => c.id === q) ? q : chains[0].id, false);
})();

// ── 重大訊息（MOPS）──
(function () {
  const env = DATA.mops, el = document.getElementById("mops");
  document.querySelector('[data-stamp="mops"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">重大訊息抓取失敗：${env.error || ""}</div>`; return; }
  const items = env.data.items || [];
  if (!items.length) { el.innerHTML = `<div class="sub">今日無公告</div>`; return; }
  const counts = env.data.tag_counts || {};
  const chips = Object.entries(counts).map(([t, n]) => `<span class="tag t${t}">${t} ${n}</span>`).join("");
  el.innerHTML = `<div style="padding:4px 0 8px">${chips}</div><div class="mops-list">` + items.map(it => {
    const dd = it.date === env.data_date ? "" : it.date.slice(5).replace("-", "/") + " ";
    return `<div class="mops-item"><span class="tag t${it.tag}">${it.tag}</span><span class="tm">${dd}${it.time}</span><span class="who">${it.name} <span class="sub">${it.code}</span></span>${it.subject}</div>`;
  }).join("") + `</div>`;
})();

// ── 基本面速覽 ──
function fundLine(code) {
  const env = DATA.fundamentals;
  const f = env && env.ok ? env.data.stocks[code] : null;
  if (!f) return "";
  const p = [];
  if (f.eps != null) p.push(`EPS ${f.eps}`);
  if (f.gm != null) p.push(`毛利 ${f.gm}%`);
  if (f.om != null) p.push(`營益 ${f.om}%`);
  if (f.yield_pct != null) p.push(`殖利率 ${f.yield_pct}%`);
  if (f.debt_pct != null) p.push(`負債比 ${f.debt_pct}%`);
  return p.length ? `${p.join("｜")}（${f.yq}）` : "";
}
(function () {
  const env = DATA.fundamentals, el = document.getElementById("fund");
  document.querySelector('[data-stamp="fundamentals"]').innerHTML = stampFor(env, 95).replace("資料日", "出表日");
  if (!env.ok) { el.innerHTML = `<div class="err">基本面資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  function tbl(title, rows, fmt) {
    if (!rows || !rows.length) return `<div><table><tr><th>${title}</th></tr><tr><td class="sub">無資料</td></tr></table></div>`;
    const body = rows.map((r, i) => `<tr>
      <td>${i+1}. ${r.name || r.code} <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span></td>
      ${fmt(r)}<td>${r.close ?? "—"}</td></tr>`).join("");
    return `<div><table><tr><th>${title}</th>${title.includes("殖利率") ? "<th>殖利率</th><th>現金股利</th>" : "<th>毛利率</th><th>EPS</th>"}<th>收盤</th></tr>${body}</table></div>`;
  }
  el.innerHTML = `<div class="grid2">
    ${tbl("高殖利率 Top 15", d.top_yield, r => `<td>${r.yield_pct}%</td><td class="sub">${r.div_cash} 元</td>`)}
    ${tbl("高毛利率 Top 15", d.top_margin, r => `<td>${r.gm}%</td><td class="sub">${r.eps ?? "—"}</td>`)}
  </div><div class="sub" style="padding:4px 2px">殖利率以「已公告股利年度合計 ÷ 現價」估算，未必等於未來配息；高毛利榜含 IP/投資控股類（毛利結構特殊）。</div>`;
})();

// ── 市場新聞 ──
(function () {
  const env = DATA.news, el = document.getElementById("news");
  document.querySelector('[data-stamp="news"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">新聞抓取失敗：${env.error || ""}</div>`; return; }
  const items = env.data.items || [];
  if (!items.length) { el.innerHTML = `<div class="sub">無新聞</div>`; return; }
  el.innerHTML = `<div class="mops-list">` + items.map(it => {
    const tags = (it.topics || []).map(t => `<span class="tag t財務">${t}</span>`).join("")
               + (it.stocks || []).map(s => `<span class="tag t治理">${s}</span>`).join("");
    return `<div class="mops-item"><span class="tm">${(it.time || "").slice(5)}</span>
      <span class="tag t自結">${it.source}</span>${tags}
      <a href="${it.link}" target="_blank" rel="noopener" style="color:var(--fg)">${it.title}</a></div>`;
  }).join("") + `</div>`;
})();

// ── 市場寬度 ──
(function () {
  const env = DATA.breadth, el = document.getElementById("breadth");
  document.querySelector('[data-stamp="breadth"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">市場寬度資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data, n = d.n || 1;
  const pu = d.up / n * 100, pf = d.flat / n * 100, pd = d.down / n * 100;
  el.innerHTML = `<div class="breadth">
    <div class="b-row">
      <span class="up">上漲 ${d.up} 家（${pu.toFixed(0)}%）</span>
      <span class="flat">平盤 ${d.flat}</span>
      <span class="down">下跌 ${d.down} 家（${pd.toFixed(0)}%）</span>
      <span>漲停 <b class="up">${d.limit_up}</b>・跌停 <b class="down">${d.limit_down}</b></span>
      <span>上漲成交值占比 <b class="${d.up_value_pct >= 50 ? "up" : "down"}">${d.up_value_pct ?? "—"}%</b></span>
    </div>
    <div class="b-bar">
      <div style="width:${pu}%;background:var(--up)"></div>
      <div style="width:${pf}%;background:#3a4356"></div>
      <div style="width:${pd}%;background:var(--down)"></div>
    </div>
    <div class="sub">${d.note}｜齊跌+上漲值占比低 = 系統性賣壓；齊漲 = 普漲行情（現況描述，非訊號）</div>
  </div>`;
})();

// ── 營收亮點 ──
(function () {
  const env = DATA.revenue_hl, el = document.getElementById("revhl");
  document.querySelector('[data-stamp="revenue_hl"]').innerHTML = stampFor(env, 25).replace("資料日", "出表日");
  if (!env.ok) { el.innerHTML = `<div class="err">營收資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  document.getElementById("revhl-sub").textContent =
    `${d.ym_label} 營收（月營收於次月 10 日前公布，openapi 為月批次）｜${d.criteria}`;
  const items = d.items || [];
  if (!items.length) { el.innerHTML = `<div class="sub">本月無符合條件個股</div>`; return; }
  el.innerHTML = `<div class="rev-cards">` + items.map(r => `
    <div class="rev-card" data-code="${r.code}" title="${fundLine(r.code) || "點擊開 Yahoo 股市"}">
      <b>${r.name}</b> <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span><br>
      營收 <b>${r.rev_yi}</b> 億　<span class="up">YoY +${r.yoy}%</span>${r.mom != null ? `　<span class="sub">MoM ${r.mom > 0 ? "+" : ""}${r.mom}%</span>` : ""}<br>
      <span class="${cls(r.pct)}">${r.close}（${sign(r.pct)}%）</span>
    </div>`).join("") + `</div>`;
  el.querySelectorAll(".rev-card").forEach(c => c.addEventListener("click", () =>
    window.open("https://tw.stock.yahoo.com/quote/" + c.dataset.code + ".TW", "_blank")));
})();

// ── 搜尋 ──
(function () {
  const inp = document.getElementById("search");
  const res = document.getElementById("search-res");
  const idx = DATA.search || [];
  // code → 題材/價值鏈 反查
  const inTopic = {}, inChain = {};
  if (DATA.topics_view.ok) DATA.topics_view.data.topics.forEach(t =>
    t.members.forEach(m => (inTopic[m.code] = inTopic[m.code] || []).push([t.id, t.name])));
  if (DATA.chains_view.ok) DATA.chains_view.data.chains.forEach(ch =>
    ch.stages.forEach(st => st.nodes.forEach(nd => nd.members.forEach(m =>
      (inChain[m.code] = inChain[m.code] || []).push([ch.id, ch.name])))));
  function go(url) { window.open(url, "_blank"); }
  function render(q) {
    q = q.trim().toUpperCase();
    if (!q) { res.style.display = "none"; return; }
    const hits = [];
    for (const r of idx) {   // r = [code, name, industry, close, pct, mkt]
      if (r[0].startsWith(q) || r[1].includes(q)) {
        hits.push(r);
        if (hits.length >= 8) break;
      }
    }
    if (!hits.length) { res.innerHTML = `<div class="sr-item sub">無符合</div>`; res.style.display = "block"; return; }
    res.innerHTML = hits.map(r => {
      const badges = (inTopic[r[0]] || []).map(([id, nm]) =>
          `<span class="sr-badge" data-t="${id}">${nm}</span>`).join("")
        + (inChain[r[0]] || []).map(([id, nm]) =>
          `<span class="sr-badge" data-c="${id}">${nm}</span>`).join("");
      return `<div class="sr-item" data-code="${r[0]}" data-mkt="${r[5]}">
        <b>${r[1]}</b><span class="sub">${r[0]}${r[2] ? "・" + r[2] : ""}</span>
        <span class="${cls(r[4])}" style="margin-left:auto">${r[3]}（${sign(r[4])}%）</span>${badges}</div>`;
    }).join("");
    res.style.display = "block";
    res.querySelectorAll(".sr-item[data-code]").forEach(it => it.addEventListener("click", e => {
      if (e.target.classList.contains("sr-badge")) return;
      go(`https://tw.stock.yahoo.com/quote/${it.dataset.code}.${it.dataset.mkt === "o" ? "TWO" : "TW"}`);
    }));
    res.querySelectorAll(".sr-badge").forEach(b => b.addEventListener("click", () => {
      res.style.display = "none"; inp.value = "";
      if (b.dataset.t) { showTab("topics"); showTopic(b.dataset.t, true); }
      else { showTab("chains"); showChain(b.dataset.c, true); }
    }));
  }
  inp.addEventListener("input", () => render(inp.value));
  inp.addEventListener("focus", () => render(inp.value));
  document.addEventListener("click", e => {
    if (!e.target.closest(".searchwrap")) res.style.display = "none";
  });
})();

// ── 分頁切換 ──
(function () {
  const PANES = ["focus", "topics", "chains", "market", "watch", "fund", "news"];
  function show(id, push) {
    if (!PANES.includes(id)) id = "focus";
    document.querySelectorAll(".tabpane").forEach(p => p.classList.toggle("active", p.id === "pane-" + id));
    document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t.dataset.pane === id));
    if (push) history.replaceState(null, "", location.pathname + location.search + "#tab=" + id);
    window.scrollTo(0, 0);
  }
  window.showTab = id => show(id, true);   // 搜尋徽章跳轉用
  document.querySelectorAll(".tab").forEach(t =>
    t.addEventListener("click", () => show(t.dataset.pane, true)));
  const q = new URLSearchParams(location.search);
  const hashTab = (location.hash.match(/tab=([a-z]+)/) || [])[1];
  show(hashTab || (q.get("chain") ? "chains" : q.get("topic") ? "topics" : "focus"), false);
})();

document.getElementById("built-at").textContent = "頁面產生時間 " + BUILT_AT;
</script>
</body>
</html>
"""


def main() -> None:
    data = {name: read_json(name) for name in
            ("indices", "market", "heatmap", "rank", "inst_rank", "topics_view", "mops",
             "tdcc", "chains_view", "flow", "fundamentals", "news", "breadth", "revenue_hl")}

    # 搜尋索引：全市場 4 碼個股 [code, name, industry, close, pct, 市場(t/o)]
    search = []
    daily = read_json("daily_all")
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            if len(s["code"]) == 4 and s["code"].isdigit():
                search.append([s["code"], s["name"], s.get("industry") or "",
                               s["close"], s["pct"], "o" if s.get("market") == "tpex" else "t"])
    data["search"] = search

    # 日期回看：history 快照複製進 docs/（Pages 只 serve docs/），並嵌可選日期清單
    import shutil
    hist_src = DATA_DIR / "history"
    hist_dst = DOCS_DIR / "history"
    dates = []
    if hist_src.exists():
        hist_dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(hist_src.glob("????-??-??.json")):
            shutil.copy2(f, hist_dst / f.name)
            dates.append(f.stem)
    data["history_dates"] = sorted(dates, reverse=True)

    # 基本面全量 ~2000 檔會撐爆頁面 → 只內嵌「題材+價值鏈成員」子集（tooltip 用），排行表本身已在信封裡
    fund = data["fundamentals"]
    if fund.get("ok"):
        need: set[str] = set()
        if data["topics_view"].get("ok"):
            for t in data["topics_view"]["data"].get("topics", []):
                need.update(m["code"] for m in t.get("members", []))
        if data["chains_view"].get("ok"):
            for ch in data["chains_view"]["data"].get("chains", []):
                for st in ch.get("stages", []):
                    for nd in st.get("nodes", []):
                        need.update(m["code"] for m in nd.get("members", []))
        fund["data"]["stocks"] = {c: f for c, f in fund["data"]["stocks"].items() if c in need}
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BUILT_AT__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] docs/index.html ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
