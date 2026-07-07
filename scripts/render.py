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
<h1>台股產業地圖 <span class="sub">自用・現況呈現・不預測</span></h1>
<div class="sub" id="built-at"></div>

<section id="sec-indices"><h2>國際指數 <span class="stamp" data-stamp="indices"></span></h2><div id="indices"></div></section>
<section id="sec-market"><h2>三大法人與資券 <span class="stamp" data-stamp="market"></span></h2><div id="market"></div></section>
<section id="sec-inst"><h2>法人個股動向 <span class="stamp" data-stamp="inst_rank"></span></h2><div class="sub">買賣超金額=股數×收盤估算｜連買/連賣為現況描述，非進場訊號</div><div id="instrank"></div></section>
<section id="sec-tdcc"><h2>大戶動向（週） <span class="stamp" data-stamp="tdcc"></span></h2><div class="sub">TDCC 集保股權分散｜大戶=400 張以上持股比（千張=1,000 張以上）｜每週五結算、週六公布</div><div id="tdcc"></div></section>
<section id="sec-topics"><h2>題材 <span class="stamp" data-stamp="topics_view"></span></h2><div class="sub">題材對照為 AI 初稿+人工校對，非官方分類</div><div id="topic-chips"></div><div id="topic-detail"></div></section>
<section id="sec-heatmap"><h2>產業熱力圖 <span class="stamp" data-stamp="heatmap"></span></h2><div class="sub">格子大小=成交值｜顏色=漲跌%（紅漲綠跌）｜各產業取成交值前 25 檔</div><div id="heatmap"></div></section>
<section id="sec-rank"><h2>強勢/弱勢排行 <span class="stamp" data-stamp="rank"></span></h2><div id="ranks"></div></section>
<section id="sec-chains"><h2>產業價值鏈 <span class="stamp" data-stamp="chains_view"></span></h2><div class="sub">內容自產（上中下游整理，非官方分類、非投資建議）｜點個股開 kanpan 面板（需本機後端）</div><div id="chain-chips"></div><div id="chains"></div></section>
<section id="sec-mops"><h2>重大訊息 <span class="stamp" data-stamp="mops"></span></h2><div class="sub">MOPS 公開資訊觀測站（上市+上櫃）｜標籤為主旨關鍵字自動分類</div><div id="mops"></div></section>

<footer>
資料源：TWSE / TPEx 公開 API、yfinance、MOPS 公開資訊觀測站、TDCC 集保中心。每交易日 17:30 後自動更新。<br>
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
    if (push) { const p = new URLSearchParams(location.search); p.set("topic", id); history.replaceState(null, "", "?" + p); }
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
    const rows = t.members.map(m => `<tr>
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
    if (push) { const p = new URLSearchParams(location.search); p.set("chain", id); history.replaceState(null, "", "?" + p); }
    el.innerHTML = `<div class="topic-desc">${ch.desc}</div>` + ch.stages.map(st => `
      <div class="stage"><div class="stage-title">${st.name}</div><div class="nodes">` +
      st.nodes.map(nd => `<div class="node"><div class="node-label">${nd.label} <span class="sub">${nd.members.length} 檔</span></div>
        <div class="node-desc">${nd.desc}</div>` +
        nd.members.map(m => `<div class="co" data-code="${m.code}" title="開 kanpan 面板（需本機後端 127.0.0.1:8771）">
          <span class="co-nm">${m.name} <span class="sub">${m.code}</span></span>
          ${lotsTag("外資", m.f_lots)}${lotsTag("投信", m.t_lots)}
          <span class="co-px ${cls(m.pct)}">${m.close} (${sign(m.pct)}%)</span></div>`).join("") +
        `</div>`).join("") + `</div></div>`).join("");
    el.querySelectorAll(".co").forEach(c => c.addEventListener("click", () =>
      window.open("http://127.0.0.1:8771/?sid=" + c.dataset.code, "_blank")));
  }
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

document.getElementById("built-at").textContent = "頁面產生時間 " + BUILT_AT;
</script>
</body>
</html>
"""


def main() -> None:
    data = {name: read_json(name) for name in
            ("indices", "market", "heatmap", "rank", "inst_rank", "topics_view", "mops", "tdcc", "chains_view")}
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BUILT_AT__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] docs/index.html ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
