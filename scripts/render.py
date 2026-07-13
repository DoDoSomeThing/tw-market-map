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
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#05070d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="icon-180.png">
<script>(function(){try{var t=localStorage.getItem("twmm_theme")||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");document.documentElement.dataset.theme=t;}catch(e){}})();</script>
<style>
:root {
  --bg: #04060b; --panel: #0c1422; --panel2: #101b31; --border: #1c2a44; --border-hi: #2e4573;
  --fg: #e8eef6; --muted: #8593ab;
  --up: #ff453a; --down: #00c98d; --flat: #8593ab; /* 台股紅漲綠跌 */
  --warn: #ffab24; --accent: #4c8dff; --accent-soft: rgba(76,141,255,.13);
  --r: 10px; --tr: .18s ease;
  --surface: linear-gradient(180deg, var(--panel2), var(--panel));
  --shadow: 0 12px 32px rgba(0,0,0,.5);
  --num: "SF Mono", ui-monospace, Menlo, Consolas, monospace;
  --bar-flat: #3a4356;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif; margin: 0 auto;
  -webkit-font-smoothing: antialiased; font-variant-numeric: tabular-nums;
  background-image:
    radial-gradient(900px 360px at 50% -140px, rgba(76,141,255,.13), transparent 70%),
    linear-gradient(90deg, rgba(76,141,255,.04) 1px, transparent 0),
    linear-gradient(rgba(76,141,255,.04) 1px, transparent 0);
  background-size: 100% 100%, 42px 42px, 42px 42px; }
h1 { font-size: 1.12rem; letter-spacing: .02em; }
h2 { font-size: 1rem; padding: 16px 0 8px; color: var(--fg); }
h2::before { content: ""; display: inline-block; width: 3px; height: 13px; border-radius: 2px; background: var(--accent); margin-right: 8px; vertical-align: -1px; }

/* 捲軸 / 鍵盤焦點 / 減少動態 */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-thumb { background: #223250; border-radius: 5px; border: 2px solid var(--bg); }
::-webkit-scrollbar-track { background: transparent; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; border-radius: 4px; }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }

/* 頂部導覽 + 分頁 */
header.top { position: sticky; top: 0; z-index: 50; background: rgba(4,6,11,.82); backdrop-filter: blur(14px) saturate(1.4); -webkit-backdrop-filter: blur(14px) saturate(1.4); border-bottom: 1px solid rgba(46,69,115,.5); }
.top-inner { max-width: 1200px; margin: 0 auto; padding: 10px 12px 0; }
.brand { display: flex; align-items: center; gap: 9px; padding-bottom: 7px; }
.brand .logo { width: 20px; height: 20px; border-radius: 5px; flex: none; }
.brand h1 { white-space: nowrap; }
@media (max-width: 560px) { .brand > .sub { display: none; } #search { width: 132px; } }
.tabs { display: flex; gap: 2px; overflow-x: auto; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab { background: none; border: none; color: var(--muted); font-size: .92rem; padding: 9px 14px; cursor: pointer; white-space: nowrap; border-bottom: 2px solid transparent; font-family: inherit; border-radius: 8px 8px 0 0; transition: color var(--tr), background var(--tr); }
.tab:hover { color: var(--fg); background: rgba(76,141,255,.08); }
.tab.active { color: var(--accent); border-bottom-color: var(--accent); font-weight: 600; }
main { max-width: 1200px; margin: 0 auto; padding: 4px 12px 12px; }
.tabpane { display: none; }
.tabpane.active { display: block; animation: paneIn .22s ease; }
@keyframes paneIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* 搜尋 */
.searchwrap { position: relative; margin-left: auto; }
#search { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; color: var(--fg); padding: 6px 11px; font-size: .85rem; width: 172px; font-family: inherit; transition: border-color var(--tr), box-shadow var(--tr); }
#search:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
#search-res { position: absolute; right: 0; top: 38px; background: var(--surface); border: 1px solid var(--border-hi); border-radius: var(--r); min-width: 300px; max-height: 320px; overflow-y: auto; display: none; z-index: 60; box-shadow: var(--shadow); }
.sr-item { padding: 8px 10px; border-bottom: 1px solid var(--border); cursor: pointer; font-size: .85rem; display: flex; gap: 8px; align-items: center; transition: background var(--tr); }
.sr-item:hover { background: var(--accent-soft); }
.sr-item:last-child { border-bottom: none; }
.sr-badge { font-size: .68rem; border: 1px solid var(--border); border-radius: 999px; padding: 1px 7px; color: var(--muted); cursor: pointer; transition: color var(--tr), border-color var(--tr); }
.sr-badge:hover { border-color: var(--accent); color: var(--accent); }

/* 市場寬度 */
.breadth { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 12px; }
.b-bar { display: flex; height: 12px; border-radius: 6px; overflow: hidden; margin: 9px 0 7px; box-shadow: inset 0 1px 3px rgba(0,0,0,.5); }
.b-bar > div { height: 100%; }
.b-row { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: .85rem; }

/* 營收亮點卡 */
.rev-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 9px; }
.rev-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 10px 11px; font-size: .84rem; line-height: 1.55; cursor: pointer; transition: border-color var(--tr), box-shadow var(--tr); }
.rev-card:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-soft), 0 6px 18px rgba(0,0,0,.35); }
.rev-card b { font-size: .92rem; }

/* 日期回看 */
select { background: var(--panel); border: 1px solid var(--border); color: var(--fg); border-radius: 6px; padding: 3px 8px; font-size: .82rem; font-family: inherit; }
.sub { color: var(--muted); font-size: .78rem; }
.stamp { color: var(--muted); font-size: .75rem; margin-left: 8px; font-weight: 400; }
.stale { color: var(--warn); font-weight: 600; }
section { margin-bottom: 14px; }
.err { color: var(--warn); background: var(--panel); border: 1px solid rgba(255,171,36,.45); border-radius: var(--r); padding: 10px; font-size: .85rem; }

/* 指數卡 */
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 9px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 11px; }
.card .nm { font-size: .8rem; color: var(--muted); }
.card .px { font-size: 1.18rem; font-weight: 700; margin-top: 2px; font-family: var(--num); letter-spacing: -.01em; }
.card .chg { font-size: .85rem; }

/* 法人/資券 + 全站表格 */
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
table { width: 100%; border-collapse: separate; border-spacing: 0; background: var(--panel); border: 1px solid var(--border); border-radius: var(--r); overflow: hidden; font-size: .85rem; }
th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid rgba(28,42,68,.55); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 600; font-size: .74rem; letter-spacing: .04em; background: rgba(16,27,49,.85); user-select: none; cursor: pointer; }
th[data-dir="desc"]::after { content: " ▾"; color: var(--accent); }
th[data-dir="asc"]::after { content: " ▴"; color: var(--accent); }
tr:nth-child(even) td { background: rgba(255,255,255,.015); }
tr:hover td { background: rgba(76,141,255,.06); }
tr:last-child td { border-bottom: none; }

/* 熱力圖 */
#heatmap { width: 100%; }
.hm-group { margin-bottom: 8px; }
.hm-title { font-size: .8rem; color: var(--muted); padding: 4px 2px; }
.hm-title b { color: var(--fg); }
.hm-box { position: relative; width: 100%; border-radius: 8px; overflow: hidden; }
.hm-cell { position: absolute; overflow: hidden; border: 1px solid var(--bg); display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center; cursor: default; }
.hm-cell .c-nm { font-weight: 600; white-space: nowrap; }
.hm-cell .c-pc { white-space: nowrap; opacity: .9; }
.hm-cell[data-code] { cursor: pointer; transition: filter .12s ease; }
.hm-cell[data-code]:hover { filter: brightness(1.3); z-index: 2; }
.sticky-head th { position: sticky; top: 0; z-index: 1; }

.up { color: var(--up); } .down { color: var(--down); } .flat { color: var(--flat); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 0; }
.chip { background: var(--panel); border: 1px solid var(--border); border-radius: 999px; padding: 4px 12px; font-size: .82rem; cursor: pointer; color: var(--fg); font-family: inherit; transition: border-color var(--tr), background var(--tr); }
.chip:hover { border-color: var(--border-hi); }
.chip.active { border-color: var(--accent); background: var(--accent-soft); }
.chip .g { color: var(--muted); font-size: .7rem; margin-right: 4px; }
.streak { font-size: .7rem; border-radius: 4px; padding: 0 4px; margin-left: 4px; }
.streak.buy { background: rgba(255,69,58,.16); color: var(--up); }
.streak.sell { background: rgba(0,201,141,.14); color: var(--down); }
.tag { font-size: .7rem; border-radius: 4px; padding: 1px 6px; margin-right: 6px; white-space: nowrap; }
.tag.t澄清 { background: rgba(255,171,36,.16); color: var(--warn); }
.tag.t自結 { background: rgba(88,166,255,.15); color: #6cb2ff; }
.tag.t財務 { background: rgba(188,140,255,.15); color: #c69bff; }
.tag.t治理 { background: rgba(139,148,158,.18); color: var(--muted); }
.tag.t重大 { background: rgba(255,69,58,.16); color: var(--up); }
.mops-list { background: var(--panel); border: 1px solid var(--border); border-radius: var(--r); font-size: .85rem; max-height: 420px; overflow-y: auto; }
.mops-item { padding: 8px 10px; border-bottom: 1px solid rgba(28,42,68,.55); line-height: 1.5; transition: background var(--tr); }
.mops-item:hover { background: rgba(76,141,255,.05); }
.mops-item:last-child { border-bottom: none; }
.mops-item .who { color: var(--fg); font-weight: 600; margin-right: 6px; }
.mops-item .tm { color: var(--muted); font-size: .75rem; margin-right: 6px; }

/* 時事雷達 */
.radar-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 9px; padding: 6px 0; }
.radar-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 10px 11px; font-size: .84rem; line-height: 1.6; cursor: pointer; transition: border-color var(--tr), box-shadow var(--tr), background var(--tr); }
.radar-card:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-soft), 0 6px 18px rgba(0,0,0,.35); }
.radar-card.active { border-color: var(--accent); background: linear-gradient(180deg, #16264a, #101b31); }
.radar-card b { font-size: .95rem; }
.radar-heat { color: var(--warn); font-weight: 700; font-family: var(--num); }
.news-links { background: var(--panel); border: 1px solid var(--border); border-radius: var(--r); font-size: .84rem; margin-top: 8px; }
.news-links .mops-item a { color: var(--fg); text-decoration: none; }
.news-links .mops-item a:hover { color: var(--accent); }

/* 今日異動 */
.chg-list { background: var(--panel); border: 1px solid var(--border); border-radius: var(--r); font-size: .86rem; overflow: hidden; }
.chg-item { padding: 8px 11px; border-bottom: 1px solid rgba(28,42,68,.55); line-height: 1.5; cursor: pointer; transition: background var(--tr); }
.chg-item:hover { background: var(--accent-soft); }
.chg-item:last-child { border-bottom: none; }
.chg-item.wl { background: rgba(76,141,255,.09); border-left: 2px solid var(--accent); }

/* 手機：表格容器橫向捲動，不擠爆版面（min-width:0 讓 grid item 肯縮） */
.ranks > div, .grid2 > div, #market > div, #topic-detail, #radar-detail, #tdcc, #fund, #instrank, #ranks { overflow-x: auto; min-width: 0; }
@media (max-width: 700px) { th, td { white-space: nowrap; padding: 6px 8px; } }

/* 自選股 / 個股面板 / 排序 */
.wl-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(215px, 1fr)); gap: 9px; }
.wl-card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 10px 11px; font-size: .84rem; line-height: 1.7; cursor: pointer; transition: border-color var(--tr), box-shadow var(--tr); }
.wl-card:hover { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent-soft), 0 6px 18px rgba(0,0,0,.35); }
.star { cursor: pointer; color: var(--muted); font-size: 1rem; background: none; border: none; font-family: inherit; padding: 0 4px; line-height: 1; transition: color var(--tr), transform var(--tr); }
.star:hover { transform: scale(1.15); }
.star.on { color: var(--warn); }
.wl-news { color: var(--muted); font-size: .75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
#sp-overlay { position: fixed; inset: 0; background: rgba(2,4,9,.6); backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); z-index: 90; display: none; animation: fadeIn .18s ease; }
#sp-panel { position: fixed; z-index: 91; top: 50%; left: 50%; transform: translate(-50%,-50%); width: min(460px, 94vw); max-height: 86vh; overflow-y: auto; background: var(--surface); border: 1px solid var(--border-hi); border-radius: 14px; padding: 15px; display: none; box-shadow: var(--shadow); animation: spIn .18s ease; }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
@keyframes spIn { from { opacity: 0; transform: translate(-50%,-48.5%) scale(.97); } to { opacity: 1; transform: translate(-50%,-50%) scale(1); } }
#sp-panel h3 { font-size: 1.05rem; padding-bottom: 4px; }
#sp-panel .px { font-family: var(--num); }
.sp-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 7px; padding: 9px 0; font-size: .84rem; }
.sp-cell { background: rgba(4,6,11,.55); border: 1px solid var(--border); border-radius: 8px; padding: 6px 9px; }
.sp-cell .lbl { color: var(--muted); font-size: .7rem; display: block; }
.sp-close { float: right; background: none; border: none; color: var(--muted); font-size: 1.1rem; cursor: pointer; font-family: inherit; transition: color var(--tr); }
.sp-close:hover { color: var(--fg); }
.spark { vertical-align: middle; }

/* 價值鏈 */
.stage { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 11px; margin-bottom: 9px; }
.stage-title { font-size: .95rem; font-weight: 700; padding-bottom: 8px; }
.nodes { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 9px; }
.node { background: rgba(4,6,11,.5); border: 1px solid var(--border); border-radius: 8px; padding: 8px; }
.node-label { font-weight: 600; font-size: .88rem; }
.node-desc { color: var(--muted); font-size: .75rem; padding: 2px 0 6px; line-height: 1.4; }
.co { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 8px; border-top: 1px solid rgba(28,42,68,.55); padding: 6px 4px; cursor: pointer; border-radius: 6px; transition: background var(--tr); }
.co:hover { background: var(--accent-soft); }
.co .co-nm { font-weight: 600; font-size: .85rem; }
.co .co-px { margin-left: auto; font-size: .85rem; white-space: nowrap; }
.co .tag { margin-right: 0; }
.topic-desc { color: var(--muted); font-size: .82rem; padding: 6px 2px; }
.ranks { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
@media (max-width: 700px) { .ranks { grid-template-columns: 1fr; } }
footer { color: var(--muted); font-size: .72rem; padding: 18px 0; line-height: 1.6; border-top: 1px solid rgba(28,42,68,.5); margin-top: 16px; }

/* ── 淺色主題（--bg 等 token 覆蓋 + 寫死色補丁）── */
:root { color-scheme: dark; }
:root[data-theme="light"] {
  color-scheme: light;
  --bg: #f2f5fa; --panel: #ffffff; --panel2: #fbfcfe; --border: #dbe3ef; --border-hi: #b7c5dc;
  --fg: #17233a; --muted: #5a6a85;
  --up: #d92d20; --down: #067a5b; --flat: #5a6a85;
  --warn: #b26a00; --accent: #2563eb; --accent-soft: rgba(37,99,235,.10);
  --surface: linear-gradient(180deg, #ffffff, #fbfcfe);
  --shadow: 0 12px 32px rgba(23,35,58,.14);
  --bar-flat: #c6d0e0;
}
:root[data-theme="light"] body { background-image:
  radial-gradient(900px 360px at 50% -140px, rgba(37,99,235,.08), transparent 70%),
  linear-gradient(90deg, rgba(37,99,235,.05) 1px, transparent 0),
  linear-gradient(rgba(37,99,235,.05) 1px, transparent 0); }
:root[data-theme="light"] header.top { background: rgba(255,255,255,.85); border-bottom: 1px solid rgba(183,197,220,.6); }
:root[data-theme="light"] .tab:hover { background: rgba(37,99,235,.07); }
:root[data-theme="light"] th { background: rgba(238,243,250,.92); }
:root[data-theme="light"] th, :root[data-theme="light"] td { border-bottom-color: rgba(219,227,239,.95); }
:root[data-theme="light"] tr:nth-child(even) td { background: rgba(23,35,58,.025); }
:root[data-theme="light"] tr:hover td { background: rgba(37,99,235,.06); }
:root[data-theme="light"] .mops-item, :root[data-theme="light"] .chg-item { border-bottom-color: rgba(219,227,239,.95); }
:root[data-theme="light"] .co { border-top-color: rgba(219,227,239,.95); }
:root[data-theme="light"] .radar-card.active { background: linear-gradient(180deg, #e9f0fe, #f6f9ff); }
:root[data-theme="light"] .sp-cell { background: rgba(242,245,250,.9); }
:root[data-theme="light"] .node { background: #f6f8fc; }
:root[data-theme="light"] #sp-overlay { background: rgba(23,35,58,.35); }
:root[data-theme="light"] .tag.t自結 { color: #1d4ed8; background: rgba(37,99,235,.12); }
:root[data-theme="light"] .tag.t財務 { color: #7c3aed; background: rgba(124,58,237,.12); }
:root[data-theme="light"] ::-webkit-scrollbar-thumb { background: #c3cede; border: 2px solid var(--bg); }
:root[data-theme="light"] .b-bar { box-shadow: inset 0 1px 3px rgba(23,35,58,.15); }
.hm-cell { color: #f2f5fa; }  /* 熱力圖格內文字固定淺色（色塊深，兩主題皆可讀） */
.theme-btn { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; color: var(--muted); width: 34px; height: 31px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; flex: none; transition: color var(--tr), border-color var(--tr); }
.theme-btn:hover { color: var(--fg); border-color: var(--border-hi); }
.theme-btn svg { width: 16px; height: 16px; }
</style>
</head>
<body>
<header class="top"><div class="top-inner">
  <div class="brand"><svg class="logo" viewBox="0 0 20 20" aria-hidden="true"><rect x="0" y="0" width="12" height="9" rx="1.5" fill="#e0433f"/><rect x="13" y="0" width="7" height="9" rx="1.5" fill="#00a37a"/><rect x="0" y="10" width="7" height="10" rx="1.5" fill="#00a37a"/><rect x="8" y="10" width="12" height="10" rx="1.5" fill="#e0433f"/></svg><h1>台股產業地圖</h1><span class="sub">自用・現況呈現・不預測</span>
    <div class="searchwrap"><input id="search" placeholder="搜代號/股名…" autocomplete="off"><div id="search-res"></div></div><button id="theme-btn" class="theme-btn" aria-label="切換深淺色"></button></div>
  <nav class="tabs" id="tabs">
    <button class="tab" data-pane="focus">每日焦點</button>
    <button class="tab" data-pane="radar">時事雷達</button>
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
<section id="sec-changes"><h2>今日異動 <span class="stamp" data-stamp="changes"></span></h2>
<div class="sub">今天 vs 昨天的變化，規則寫死可驗證：法人連買賣 ≥3 日翻向｜新聞點名 ≥2 則｜澄清/重大公告｜營收新公布｜題材聲量 ≥昨日 2 倍｜現況描述，非訊號</div>
<div id="changes"></div></section>
<section id="sec-mywatch"><h2>自選股 <span class="sub" id="wl-hint"></span></h2><div id="watchlist"></div></section>
<section id="sec-indices"><h2>國際指數 <span class="stamp" data-stamp="indices"></span></h2><div id="indices"></div></section>
<section id="sec-breadth"><h2>市場寬度 <span class="stamp" data-stamp="breadth"></span></h2><div id="breadth"></div></section>
<section id="sec-revhl"><h2>營收亮點 <span class="stamp" data-stamp="revenue_hl"></span></h2><div class="sub" id="revhl-sub"></div><div id="revhl"></div></section>
<section id="sec-market"><h2>三大法人與資券 <span class="stamp" data-stamp="market"></span></h2><div id="market"></div></section>
<section id="sec-flow"><h2>法人資金流 <span class="stamp" data-stamp="flow"></span></h2><div class="sub">個股買賣超聚合到族群（金額=股數×收盤估算）｜「外資」是數百家機構彙總，這是族群淨流向，非同一筆錢的移動｜現況描述，非訊號</div><div id="flow"></div></section>
<section id="sec-inst"><h2>法人個股動向 <span class="stamp" data-stamp="inst_rank"></span></h2><div class="sub">買賣超金額=股數×收盤估算｜連買/連賣為現況描述，非進場訊號</div><div id="instrank"></div></section>
</div>

<div class="tabpane" id="pane-radar">
<section id="sec-radar"><h2>時事熱度 — 題材 <span class="stamp" data-stamp="news_radar"></span></h2>
  <div class="sub">聲量 = 近 3 日新聞標題/公告關鍵字比對則數（當日×1.0、昨×0.6、前×0.3；澄清/重大公告×0.8）｜關鍵字表為 AI 初稿+人工校對｜現況描述，非訊號、非投資建議</div>
  <div id="radar-cards"></div><div id="radar-detail"></div></section>
<section id="sec-discover"><h2>新題材候選（自動偵測） <span class="stamp" data-stamp="topic_discover"></span></h2>
  <div class="sub">近 2 日新聞詞頻突增 vs 前 7 日基線（純統計、可重現）｜偵測 ≠ 題材認定 — 看對眼再把關鍵字收進 topics.json 轉正｜雜訊詞加進 topics/discover_stopwords.txt</div>
  <div id="discover"></div></section>
<section id="sec-radar-stocks"><h2>時事熱度 — 個股</h2>
  <div class="sub">被新聞點名/發澄清重大公告的個股，依聲量排序｜點列開 Yahoo 股市</div><div id="radar-stocks"></div></section>
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
<section id="sec-exdiv"><h2>近期除息（依除息日近→遠） <span class="stamp" data-stamp="dividend"></span></h2><div class="sub">TWSE 除權息預告表｜<b>最後買進日</b>＝除息日前一交易日，當天收盤前買到才吃得到這次配息（未扣國定連假，遇連假可能早一天，僅供參考）｜殖利率=本次現金股利÷現價｜僅上市（上櫃無資料）｜點列開個股面板</div><div id="exdiv"></div></section>
</div>

<div class="tabpane" id="pane-news">
<section id="sec-news"><h2>市場新聞 <span class="stamp" data-stamp="news"></span></h2><div class="sub">鉅亨網 + Yahoo 股市 RSS 標題聚合｜內文請點標題回原站｜標籤為標題關鍵字自動比對</div><div id="news"></div></section>
</div>

<footer>
資料源：TWSE / TPEx 公開 API、yfinance、MOPS 公開資訊觀測站、TDCC 集保中心。每交易日 17:30 後自動更新。<br>
鐵則：只做現況呈現，不做預測；各區塊資料日不一致或過期時顯示 ⚠️。
</footer>
<div id="sp-overlay" onclick="spClose()"></div>
<div id="sp-panel"></div>
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
function lotsCell(v, streak) {
  return v == null ? `<span class="sub">—</span>`
    : `<span class="${cls(v)}">${(v > 0 ? "+" : "") + v.toLocaleString()}</span>` + streakBadge(streak);
}

// ── 共用個股索引（search 列：[code,name,industry,close,pct,mkt,成交值億,外資張,投信張,外連,投連]）──
const QUOTES = {};
(DATA.search || []).forEach(r => QUOTES[r[0]] = r);
const IN_TOPIC = {}, IN_CHAIN = {};   // code → [[id, name]]
if (DATA.topics_view.ok) DATA.topics_view.data.topics.forEach(t =>
  t.members.forEach(m => (IN_TOPIC[m.code] = IN_TOPIC[m.code] || []).push([t.id, t.name])));
if (DATA.chains_view.ok) DATA.chains_view.data.chains.forEach(ch =>
  ch.stages.forEach(st => st.nodes.forEach(nd => nd.members.forEach(m =>
    (IN_CHAIN[m.code] = IN_CHAIN[m.code] || []).push([ch.id, ch.name])))));
function newsFor(code, n) {
  if (!DATA.news.ok) return [];
  return (DATA.news.data.items || []).filter(it =>
    (it.stocks || []).some(s => s.endsWith(" " + code))).slice(0, n);
}

// ── 近日收盤序列（docs/history 快照，lazy fetch）＋ sparkline ──
const SPARK_CACHE = {};
function sparkSnap(d) {
  if (!SPARK_CACHE[d]) SPARK_CACHE[d] = fetch("history/" + d + ".json").then(r => r.json()).catch(() => ({}));
  return SPARK_CACHE[d];
}
async function seriesFor(codes, nDays = 6) {
  const dates = (DATA.history_dates || []).slice(0, nDays).reverse();   // 舊 → 新
  if (dates.length < 2) return {};
  const snaps = await Promise.all(dates.map(sparkSnap));
  const cOf = v => Array.isArray(v) ? v[0] : v;
  const out = {};
  for (const c of codes) {
    const s = snaps.map(sn => cOf(sn[c])).filter(v => v != null);
    if (s.length >= 2) out[c] = s;
  }
  return out;
}
function sparkSVG(s, w = 64, h = 20) {
  const mn = Math.min(...s), mx = Math.max(...s), rg = (mx - mn) || 1;
  const pts = s.map((v, i) =>
    `${(i / (s.length - 1) * (w - 2) + 1).toFixed(1)},${(h - 1 - (v - mn) / rg * (h - 2)).toFixed(1)}`).join(" ");
  const col = s[s.length - 1] >= s[0] ? "var(--up)" : "var(--down)";
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${col}" stroke-width="1.5"/></svg>`;
}

// ── 個股迷你面板 ──
function spClose() {
  document.getElementById("sp-overlay").style.display = "none";
  document.getElementById("sp-panel").style.display = "none";
}
window.spClose = spClose;
document.addEventListener("keydown", e => { if (e.key === "Escape") spClose(); });
function openStock(code) {
  const r = QUOTES[code];
  const yahoo = `https://tw.stock.yahoo.com/quote/${code}.${r && r[5] === "o" ? "TWO" : "TW"}`;
  if (!r) { window.open(yahoo, "_blank"); return; }
  const f = DATA.fundamentals.ok ? (DATA.fundamentals.data.stocks[code] || {}) : {};
  const rv = DATA.revenue_hl.ok ? (DATA.revenue_hl.data.stocks || {})[code] : null;
  const dv = DATA.dividend.ok ? (DATA.dividend.data.by_code || {})[code] : null;
  const badges = (IN_TOPIC[code] || []).map(([id, nm]) =>
      `<span class="sr-badge" onclick="spClose();showTab('topics');showTopic('${id}',true)">${nm}</span>`).join(" ")
    + " " + (IN_CHAIN[code] || []).map(([id, nm]) =>
      `<span class="sr-badge" onclick="spClose();showTab('chains');showChain('${id}',true)">${nm}</span>`).join(" ");
  const news = newsFor(code, 3).map(it => `<div class="mops-item"><span class="tm">${(it.time || "").slice(5)}</span>
    <a href="${it.link}" target="_blank" rel="noopener" style="color:var(--fg)">${it.title}</a></div>`).join("");
  const cell = (lbl, val) => `<div class="sp-cell"><span class="lbl">${lbl}</span>${val}</div>`;
  document.getElementById("sp-panel").innerHTML = `
    <button class="sp-close" onclick="spClose()">✕</button>
    <h3>${r[1]} <span class="sub">${code}${r[2] ? "・" + r[2] : ""}</span>
      <button class="star ${wlHas(code) ? "on" : ""}" data-code="${code}" onclick="wlToggle('${code}')">★</button></h3>
    <div><span class="px ${cls(r[4])}" style="font-size:1.3rem;font-weight:700">${r[3]}</span>
      <span class="${cls(r[4])}">（${sign(r[4])}%）</span> <span id="sp-spark" style="margin-left:8px"></span></div>
    <div class="sp-grid">
      ${cell("成交值", r[6] != null ? r[6] + " 億" : "—")}
      ${cell("外資(張)", lotsCell(r[7], r[9]))}
      ${cell("投信(張)", lotsCell(r[8], r[10]))}
      ${cell("EPS", f.eps ?? "—")}${cell("毛利率", f.gm != null ? f.gm + "%" : "—")}
      ${cell("殖利率", f.yield_pct != null ? f.yield_pct + "%" : "—")}
      ${dv ? cell("最後買進日", dv.last_buy ? `<b>${dv.last_buy.slice(5).replace("-", "/")}</b>` : "—")
           + cell("預計除息", `<span class="up">${dv.ex_date.slice(5).replace("-", "/")}</span>`)
           + cell("本次現金", dv.cash != null ? dv.cash + " 元" : "待公告") : ""}
      ${rv ? cell("當月營收", rv[0] + " 億") + cell("營收 YoY", rv[1] != null ? (rv[1] > 0 ? "+" : "") + rv[1] + "%" : "—")
           + cell("營收 MoM", rv[2] != null ? (rv[2] > 0 ? "+" : "") + rv[2] + "%" : "—") : ""}
    </div>
    <div id="sp-inst"></div>
    ${f.yq ? `<div class="sub">基本面季度：${f.yq}${f.debt_pct != null ? "｜負債比 " + f.debt_pct + "%" : ""}</div>` : ""}
    ${badges.trim() ? `<div style="padding:6px 0">${badges}</div>` : ""}
    ${news ? `<div class="news-links">${news}</div>` : `<div class="sub" style="padding:6px 0">近日無相關新聞標題</div>`}
    <div style="padding-top:10px"><a href="${yahoo}" target="_blank" rel="noopener" style="color:var(--accent)">開 Yahoo 股市頁 ↗</a>
      <span class="sub">（裝 kanpan 擴充會自動掛面板）</span></div>`;
  document.getElementById("sp-overlay").style.display = "block";
  document.getElementById("sp-panel").style.display = "block";
  seriesFor([code]).then(m => {
    const el = document.getElementById("sp-spark");
    if (el && m[code]) el.innerHTML = sparkSVG(m[code], 140, 30);
  });
  loadInst10().then(d => {
    const el = document.getElementById("sp-inst");
    if (!el || !d || !d.stocks || !d.stocks[code]) return;
    const seq = d.stocks[code];
    el.innerHTML = `<div class="sub" style="padding:2px 0">法人近 ${seq.length} 日買賣超（張）</div>
      <div><span class="sub">外資</span> ${barsSVG(seq.map(x => x[0]))}　<span class="sub">投信</span> ${barsSVG(seq.map(x => x[1]))}</div>`;
  });
}
window.openStock = openStock;

// ── 自選股（localStorage，本機不跨裝置）──
const WL_KEY = "twmm_watchlist";
function wlGet() { try { return JSON.parse(localStorage.getItem(WL_KEY) || "[]"); } catch (e) { return []; } }
function wlHas(code) { return wlGet().includes(code); }
function wlToggle(code) {
  const a = wlGet(), i = a.indexOf(code);
  if (i >= 0) a.splice(i, 1); else a.push(code);
  localStorage.setItem(WL_KEY, JSON.stringify(a));
  document.querySelectorAll(`.star[data-code="${code}"]`).forEach(s => s.classList.toggle("on", i < 0));
  renderWatchlist();
  if (typeof renderChanges === "function") renderChanges();
}
window.wlToggle = wlToggle;
function renderWatchlist() {
  const el = document.getElementById("watchlist");
  const codes = wlGet();
  document.getElementById("wl-hint").textContent = codes.length ? `${codes.length} 檔・存在本機瀏覽器` : "";
  if (!codes.length) {
    el.innerHTML = `<div class="sub">尚無自選股 — 右上搜尋個股，點 ★ 加入（存在本機瀏覽器，跨裝置不同步）</div>`;
    return;
  }
  el.innerHTML = `<div class="wl-cards">` + codes.map(code => {
    const r = QUOTES[code];
    if (!r) return `<div class="wl-card"><b>${code}</b> <span class="sub">查無行情</span>
      <button class="star on" data-code="${code}" style="float:right" onclick="event.stopPropagation();wlToggle('${code}')">★</button></div>`;
    const nw = newsFor(code, 1)[0];
    return `<div class="wl-card" onclick="openStock('${code}')" title="${fundLine(code) || ""}">
      <b>${r[1]}</b> <span class="sub">${code}</span>
      <button class="star on" data-code="${code}" style="float:right" onclick="event.stopPropagation();wlToggle('${code}')">★</button><br>
      <span class="${cls(r[4])}" style="font-weight:700">${r[3]}（${sign(r[4])}%）</span> <span class="spark" id="wl-sp-${code}"></span><br>
      <span class="sub">外資</span> ${lotsCell(r[7], r[9])}　<span class="sub">投信</span> ${lotsCell(r[8], r[10])}
      ${nw ? `<a class="wl-news" href="${nw.link}" target="_blank" rel="noopener" onclick="event.stopPropagation()">📰 ${nw.title}</a>` : ""}
    </div>`;
  }).join("") + `</div>`;
  seriesFor(codes).then(m => codes.forEach(c => {
    const sp = document.getElementById("wl-sp-" + c);
    if (sp && m[c]) sp.innerHTML = sparkSVG(m[c]);
  }));
}
renderWatchlist();

// ── 今日異動 ──
function renderChanges() {
  const env = DATA.changes, el = document.getElementById("changes");
  document.querySelector('[data-stamp="changes"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">異動資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data, wl = new Set(wlGet());
  const ICON = { mops: "📢", flip: "🔄", news: "📰", rev: "💰", streak: "📈" };
  const line = (e, isWl) => `<div class="chg-item${isWl ? " wl" : ""}" onclick="openStock('${e.code}')">
    ${ICON[e.t] || "•"} ${isWl ? `<span class="tag t重大">自選</span>` : ""}<b>${e.name}</b> <span class="sub">${e.code}</span>　${e.txt}</div>`;
  const wlEv = (d.stock_events || []).filter(e => wl.has(e.code));
  const others = (d.stock_events || []).filter(e => !wl.has(e.code));
  const mk = (d.market_events || []).map(e => `<div class="chg-item" style="cursor:default">⚠️ ${e.txt}</div>`).join("");
  const tp = (d.topic_events || []).map(e =>
    `<div class="chg-item" onclick="showTab('radar')">🔥 題材「<b>${e.name}</b>」${e.txt}</div>`).join("");
  const wlHtml = wl.size
    ? (wlEv.length ? wlEv.map(e => line(e, true)).join("") : `<div class="chg-item sub" style="cursor:default">自選股今日無異動</div>`)
    : `<div class="chg-item sub" style="cursor:default">尚未加自選股（右上搜尋點 ★），以下為全市場異動</div>`;
  const topOthers = others.slice(0, 8).map(e => line(e, false)).join("");
  const rest = others.length > 8
    ? `<details><summary class="sub" style="cursor:pointer;padding:7px 10px">更多全市場異動（${others.length - 8} 條）</summary>${others.slice(8, 80).map(e => line(e, false)).join("")}</details>` : "";
  if (!mk && !tp && !wlEv.length && !others.length) {
    el.innerHTML = `<div class="chg-list"><div class="chg-item sub" style="cursor:default">今日無特別異動</div></div>`;
    return;
  }
  el.innerHTML = `<div class="chg-list">${mk}${tp}${wlHtml}${topOthers}${rest}</div>`;
}
renderChanges();

// ── 法人近日買賣柱狀（inst10.json lazy fetch）──
let INST10 = null;
function loadInst10() {
  if (!INST10) INST10 = fetch("inst10.json").then(r => r.json()).catch(() => null);
  return INST10;
}
function barsSVG(vals, w = 150, h = 30) {
  const mx = Math.max(...vals.map(v => Math.abs(v)), 1);
  const bw = w / vals.length, mid = h / 2;
  const rects = vals.map((v, i) => {
    const bh = Math.max(1, Math.abs(v) / mx * (mid - 1));
    const y = v >= 0 ? mid - bh : mid;
    return `<rect x="${(i * bw + 1).toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${bh.toFixed(1)}" fill="${v >= 0 ? "var(--up)" : "var(--down)"}"/>`;
  }).join("");
  return `<svg class="spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="var(--border)"/>${rects}</svg>`;
}

// ── 表格點欄位排序（全站，事件委派）──
document.addEventListener("click", e => {
  const th = e.target.closest("th");
  if (!th) return;
  const table = th.closest("table");
  if (!table) return;
  const rows = Array.from(table.querySelectorAll("tr")).slice(1);
  if (rows.length < 2) return;
  const idx = Array.from(th.parentNode.children).indexOf(th);
  const dir = th.dataset.dir === "desc" ? "asc" : "desc";
  table.querySelectorAll("th").forEach(t => delete t.dataset.dir);
  th.dataset.dir = dir;
  const num = t => {
    const m = String(t).replace(/[,＋]/g, "").match(/-?\\d+(\\.\\d+)?/);
    return m ? parseFloat(m[0]) : null;
  };
  rows.sort((a, b) => {
    const at = a.children[idx] ? a.children[idx].innerText : "";
    const bt = b.children[idx] ? b.children[idx].innerText : "";
    const av = num(at), bv = num(bt);
    if (av == null && bv == null) return at.localeCompare(bt, "zh-Hant");
    if (av == null) return 1;
    if (bv == null) return -1;
    return dir === "desc" ? bv - av : av - bv;
  });
  rows.forEach(r => r.parentNode.appendChild(r));
});

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
      return `<div class="hm-cell" data-code="${c.code}" style="left:${c.x.toFixed(1)}px;top:${c.y.toFixed(1)}px;width:${c.w.toFixed(1)}px;height:${c.h.toFixed(1)}px;background:${pctColor(c.pct)};font-size:${fs.toFixed(0)}px"
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
      return `<div class="hm-cell" data-code="${c.code}" style="left:${c.x.toFixed(1)}px;top:${c.y.toFixed(1)}px;width:${c.w.toFixed(1)}px;height:${c.h.toFixed(1)}px;background:${pctColor(c.pct)};font-size:${fs.toFixed(0)}px"
        title="${c.code} ${c.name}　收 ${c.close}　${sign(c.pct)}%">
        <span class="c-nm">${c.name}</span>${c.h > 26 && c.w > 40 ? `<span class="c-pc">${sign(c.pct)}%</span>` : ""}</div>`;
    }).join("");
    const rows = t.members.map(m => `<tr style="cursor:pointer" onclick="openStock('${m.code}')" title="${fundLine(m.code)}">
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

// ── 時事雷達 ──
(function () {
  const env = DATA.news_radar;
  const cardsEl = document.getElementById("radar-cards");
  const detailEl = document.getElementById("radar-detail");
  const stocksEl = document.getElementById("radar-stocks");
  document.querySelector('[data-stamp="news_radar"]').innerHTML = stampFor(env);
  if (!env.ok) {
    cardsEl.innerHTML = `<div class="err">時事雷達資料失敗：${env.error || ""}</div>`;
    stocksEl.innerHTML = `<div class="sub">無資料</div>`;
    return;
  }
  const d = env.data, topics = d.topics || [];
  const note = env.error ? `<div class="sub stale" style="padding:2px 0 6px">⚠️ ${env.error}</div>` : "";

  function showDetail(id) {
    const t = topics.find(x => x.id === id);
    if (!t) { detailEl.innerHTML = ""; return; }
    cardsEl.querySelectorAll(".radar-card").forEach(c => c.classList.toggle("active", c.dataset.id === id));
    const rows = (t.members || []).map(m => `<tr style="cursor:pointer" onclick="openStock('${m.code}')" title="${fundLine(m.code)}">
      <td>${m.name} <span class="sub">${m.code}</span></td>
      <td class="${cls(m.pct)}">${sign(m.pct)}%</td><td>${m.close}</td>
      <td class="sub">${(m.value/1e8).toFixed(1)}億</td>
      <td class="${m.f_lots == null ? "sub" : cls(m.f_lots)}">${m.f_lots == null ? "—" : (m.f_lots > 0 ? "+" : "") + m.f_lots.toLocaleString()}${streakBadge(m.f_streak)}</td>
      <td class="${m.t_lots == null ? "sub" : cls(m.t_lots)}">${m.t_lots == null ? "—" : (m.t_lots > 0 ? "+" : "") + m.t_lots.toLocaleString()}${streakBadge(m.t_streak)}</td>
    </tr>`).join("");
    const memberTbl = rows
      ? `<table><tr><th>題材個股</th><th>漲跌</th><th>收盤</th><th>成交</th><th>外資(張)</th><th>投信(張)</th></tr>${rows}</table>`
      : `<div class="sub">題材行情資料缺（topics_view 失敗）</div>`;
    const newsHtml = (t.headlines || []).map(h => `<div class="mops-item">
      <span class="tm">${(h.time || "").slice(5)}</span><span class="tag t自結">${h.source}</span>
      <a href="${h.link}" target="_blank" rel="noopener">${h.title}</a></div>`).join("");
    const mopsHtml = (t.mops || []).map(m => `<div class="mops-item">
      <span class="tag t${m.tag}">${m.tag}</span><span class="who">${m.name} <span class="sub">${m.code}</span></span>${m.subject}</div>`).join("");
    detailEl.innerHTML = `<div class="topic-desc"><b>${t.name}</b>　聲量 <span class="radar-heat">${t.heat}</span>（今日 ${t.n_today} 則、近 3 日 ${t.n_3d} 則）　題材日漲跌 <span class="${cls(t.avg_pct || 0)}">${t.avg_pct == null ? "—" : sign(t.avg_pct) + "%"}</span>
      　<span class="sub" style="cursor:pointer;text-decoration:underline" onclick="showTab('topics');showTopic('${t.id}',true)">→ 題材頁看熱力圖</span></div>
      ${memberTbl}
      ${newsHtml ? `<div class="news-links">${newsHtml}</div>` : ""}
      ${mopsHtml ? `<div class="news-links">${mopsHtml}</div>` : ""}`;
  }

  if (!topics.length) {
    cardsEl.innerHTML = note + `<div class="sub">近 3 日新聞/公告無題材聲量（或關鍵字表待擴充）</div>`;
  } else {
    cardsEl.innerHTML = note + `<div class="radar-cards">` + topics.map(t => `
      <div class="radar-card" data-id="${t.id}">
        <b>${t.name}</b> <span class="sub">${t.group}</span><br>
        聲量 <span class="radar-heat">${t.heat}</span> <span class="sub">今日 ${t.n_today} 則</span><br>
        <span class="${cls(t.avg_pct || 0)}">${t.avg_pct == null ? "—" : sign(t.avg_pct) + "%"}</span> <span class="sub">題材日漲跌</span>
        <span class="spark" id="radar-sp-${t.id}" style="float:right"></span>
      </div>`).join("") + `</div>`;
    cardsEl.querySelectorAll(".radar-card").forEach(c => c.addEventListener("click", () => showDetail(c.dataset.id)));
    showDetail(topics[0].id);
    // 題材 5 日等權指數 sparkline（history 快照，等權、以共同窗首日=1 正規化）
    const allCodes = [...new Set(topics.flatMap(t => (t.members || []).map(m => m.code)))];
    seriesFor(allCodes).then(m => topics.forEach(t => {
      const sp = document.getElementById("radar-sp-" + t.id);
      const series = (t.members || []).map(x => m[x.code]).filter(s => s && s.length >= 2);
      if (!sp || !series.length) return;
      const L = Math.min(...series.map(s => s.length));
      const idxSeries = Array.from({ length: L }, (_, i) =>
        series.reduce((acc, s) => acc + s[s.length - L + i] / s[s.length - L], 0) / series.length);
      sp.innerHTML = sparkSVG(idxSeries);
    }));
  }

  const hot = d.stocks_hot || [];
  if (!hot.length) {
    stocksEl.innerHTML = `<div class="sub">近 3 日無個股被點名</div>`;
  } else {
    const body = hot.map((r, i) => {
      const latest = r.latest
        ? (r.latest.link ? `<a href="${r.latest.link}" target="_blank" rel="noopener" style="color:var(--muted)">${r.latest.title.slice(0, 32)}…</a>` : `<span class="sub">${r.latest.title.slice(0, 32)}…</span>`)
        : "—";
      return `<tr class="radar-hot-row" data-code="${r.code}" data-mkt="${r.market}" title="${fundLine(r.code) || "點擊開 Yahoo 股市"}">
        <td>${i + 1}. ${r.name} <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span></td>
        <td class="radar-heat">${r.heat}</td>
        <td class="${cls(r.pct)}">${sign(r.pct)}%</td><td>${r.close}</td>
        <td class="${r.f_lots == null ? "sub" : cls(r.f_lots)}">${r.f_lots == null ? "—" : (r.f_lots > 0 ? "+" : "") + r.f_lots.toLocaleString()}${streakBadge(r.f_streak)}</td>
        <td class="${r.t_lots == null ? "sub" : cls(r.t_lots)}">${r.t_lots == null ? "—" : (r.t_lots > 0 ? "+" : "") + r.t_lots.toLocaleString()}${streakBadge(r.t_streak)}</td>
        <td style="text-align:left;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${latest}</td></tr>`;
    }).join("");
    stocksEl.innerHTML = `<div style="overflow-x:auto"><table style="min-width:760px"><tr><th>個股</th><th>聲量</th><th>漲跌</th><th>收盤</th><th>外資(張)</th><th>投信(張)</th><th style="text-align:left">最新相關標題</th></tr>${body}</table></div>`;
    stocksEl.querySelectorAll(".radar-hot-row").forEach(tr => tr.addEventListener("click", e => {
      if (e.target.closest("a") || e.target.closest("th")) return;
      openStock(tr.dataset.code);
    }));
  }
})();

// ── 新題材候選（詞頻突增）──
(function () {
  const env = DATA.topic_discover, el = document.getElementById("discover");
  document.querySelector('[data-stamp="topic_discover"]').innerHTML = stampFor(env);
  if (!env.ok) { el.innerHTML = `<div class="err">偵測資料失敗：${env.error || ""}</div>`; return; }
  const d = env.data;
  if (d.note) { el.innerHTML = `<div class="sub">⏳ ${d.note}</div>`; return; }
  const cands = d.candidates || [];
  if (!cands.length) { el.innerHTML = `<div class="sub">近 2 日無明顯突增詞</div>`; return; }
  el.innerHTML = `<div class="radar-cards">` + cands.map(c => {
    const stocks = (c.stocks || []).map(s => {
      const code = s.tag.split(" ").pop();
      return `<span class="sr-badge" onclick="openStock('${code}')">${s.tag}×${s.n}</span>`;
    }).join(" ");
    const news = (c.headlines || []).map(h => `<div class="mops-item"><span class="tm">${(h.time || "").slice(5)}</span>
      <span class="tag t自結">${h.source}</span><a href="${h.link}" target="_blank" rel="noopener" style="color:var(--fg)">${h.title}</a></div>`).join("");
    return `<div class="radar-card" style="cursor:default">
      <b>${c.terms.join("／")}</b><br>
      <span class="radar-heat">${c.n_recent}</span> <span class="sub">則・突增 ×${c.burst}</span><br>
      ${stocks || `<span class="sub">未點名個股</span>`}
      <details style="padding-top:4px"><summary class="sub" style="cursor:pointer">相關標題</summary><div class="news-links">${news}</div></details>
    </div>`;
  }).join("") + `</div>`;
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
    el.querySelectorAll(".co").forEach(c => c.addEventListener("click", () => openStock(c.dataset.code)));
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

// ── 近期除息 ──
(function () {
  const env = DATA.dividend, el = document.getElementById("exdiv");
  document.querySelector('[data-stamp="dividend"]').innerHTML = stampFor(env, 60);
  if (!env.ok) { el.innerHTML = `<div class="err">除息資料失敗：${env.error || ""}</div>`; return; }
  const up = env.data.upcoming || [];
  if (!up.length) { el.innerHTML = `<div class="sub">近期無上市個股除息</div>`; return; }
  const todayISO = new Date().toISOString().slice(0, 10);
  const daysTo = iso => Math.round((new Date(iso + "T00:00:00") - new Date(todayISO + "T00:00:00")) / 86400000);
  const dayLabel = iso => { const d = daysTo(iso); return d <= 0 ? "今日" : (d === 1 ? "明日" : d + " 天後"); };
  const buyLabel = iso => { const d = daysTo(iso); return d < 0 ? `<span class="down">已過</span>` : (d === 0 ? `<span class="up">今日截止</span>` : (d === 1 ? "明日" : d + " 天後")); };
  const body = up.map(r => `<tr style="cursor:pointer" onclick="openStock('${r.code}')" title="${fundLine(r.code) || "點擊開個股面板"}">
    <td>${r.name} <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span></td>
    <td>${r.last_buy ? `<b>${r.last_buy.slice(5).replace("-", "/")}</b> <span class="sub">${buyLabel(r.last_buy)}</span>` : "—"}</td>
    <td><span class="up">${r.ex_date.slice(5).replace("-", "/")}</span></td>
    <td>${r.type}</td>
    <td>${r.cash != null ? r.cash + " 元" : "待公告"}</td>
    <td class="${r.yield_pct ? "up" : "sub"}">${r.yield_pct != null ? r.yield_pct + "%" : "—"}</td>
    <td>${r.close ?? "—"}</td></tr>`).join("");
  el.innerHTML = `<div style="max-height:460px;overflow:auto"><table class="sticky-head" style="min-width:700px"><tr><th>個股</th><th>最後買進日</th><th>除息日</th><th>類型</th><th>本次現金</th><th>殖利率</th><th>現價</th></tr>${body}</table></div>`;
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
      <div style="width:${pf}%;background:var(--bar-flat)"></div>
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
  el.querySelectorAll(".rev-card").forEach(c => c.addEventListener("click", () => openStock(c.dataset.code)));
})();

// ── 搜尋 ──
(function () {
  const inp = document.getElementById("search");
  const res = document.getElementById("search-res");
  const idx = DATA.search || [];
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
      const badges = (IN_TOPIC[r[0]] || []).map(([id, nm]) =>
          `<span class="sr-badge" data-t="${id}">${nm}</span>`).join("")
        + (IN_CHAIN[r[0]] || []).map(([id, nm]) =>
          `<span class="sr-badge" data-c="${id}">${nm}</span>`).join("");
      return `<div class="sr-item" data-code="${r[0]}" data-mkt="${r[5]}">
        <b>${r[1]}</b><span class="sub">${r[0]}${r[2] ? "・" + r[2] : ""}</span>
        <span class="${cls(r[4])}" style="margin-left:auto">${r[3]}（${sign(r[4])}%）</span>
        <button class="star ${wlHas(r[0]) ? "on" : ""}" data-code="${r[0]}" onclick="event.stopPropagation();wlToggle('${r[0]}')">★</button>${badges}</div>`;
    }).join("");
    res.style.display = "block";
    res.querySelectorAll(".sr-item[data-code]").forEach(it => it.addEventListener("click", e => {
      if (e.target.classList.contains("sr-badge") || e.target.classList.contains("star")) return;
      res.style.display = "none";
      openStock(it.dataset.code);
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
  const PANES = ["focus", "radar", "topics", "chains", "market", "watch", "fund", "news"];
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

// 熱力圖格子 → 個股面板（事件委派，含日期回看重繪後的格子）
document.addEventListener("click", e => {
  const hc = e.target.closest(".hm-cell[data-code]");
  if (hc) openStock(hc.dataset.code);
});

// ── 深淺色切換（head 已先定主題防閃爍；這裡只管按鈕與 meta）──
(function () {
  const SUN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>`;
  const MOON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>`;
  const btn = document.getElementById("theme-btn");
  const meta = document.querySelector('meta[name="theme-color"]');
  function paint() {
    const t = document.documentElement.dataset.theme || "dark";
    btn.innerHTML = t === "light" ? MOON : SUN;
    btn.title = t === "light" ? "切到深色" : "切到淺色";
    meta.setAttribute("content", t === "light" ? "#f2f5fa" : "#04060b");
  }
  paint();
  btn.addEventListener("click", () => {
    const t = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = t;
    localStorage.setItem("twmm_theme", t);
    paint();
  });
})();

// PWA service worker（GitHub Pages 為 https；本機測試 http 不註冊）
if ("serviceWorker" in navigator && location.protocol === "https:")
  navigator.serviceWorker.register("sw.js");

document.getElementById("built-at").textContent = "頁面產生時間 " + BUILT_AT;
</script>
</body>
</html>
"""


def main() -> None:
    data = {name: read_json(name) for name in
            ("indices", "market", "heatmap", "rank", "inst_rank", "topics_view", "mops",
             "tdcc", "chains_view", "flow", "fundamentals", "news", "breadth", "revenue_hl",
             "news_radar", "topic_discover", "changes", "dividend")}

    # 搜尋索引 + 個股面板/自選股資料：全市場 4 碼個股
    # [code, name, industry, close, pct, 市場(t/o), 成交值, 外資張, 投信張, 外資連買, 投信連買]
    from build_inst_rank import load_streaks
    t86 = read_json("t86")
    t86_stocks = t86["data"].get("stocks", {}) if t86.get("ok") else {}
    streaks = load_streaks(t86.get("data_date") or "9999-99-99") if t86.get("ok") else {}
    search = []
    daily = read_json("daily_all")
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            if len(s["code"]) == 4 and s["code"].isdigit():
                inst = t86_stocks.get(s["code"])
                sf, st = streaks.get(s["code"], (0, 0))
                search.append([s["code"], s["name"], s.get("industry") or "",
                               s["close"], s["pct"], "o" if s.get("market") == "tpex" else "t",
                               round(s.get("value", 0) / 1e8, 1),
                               round(inst["f"] / 1000) if inst else None,
                               round(inst["t"] / 1000) if inst else None,
                               sf, st])
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

    # 法人近 10 日序列 → docs/inst10.json（個股面板柱狀圖；lazy fetch 單檔，別內嵌撐爆頁面）
    t86_files = sorted((DATA_DIR / "history_t86").glob("????-??-??.json"))[-10:]
    if t86_files and daily.get("ok"):
        snaps10 = [json.loads(f.read_text(encoding="utf-8")) for f in t86_files]
        inst10: dict[str, list] = {}
        for s in daily["data"].get("stocks", []):
            code = s["code"]
            if len(code) != 4 or not code.isdigit():
                continue
            seq = [[round((sn.get(code) or [0, 0])[0] / 1000),
                    round((sn.get(code) or [0, 0])[1] / 1000)] for sn in snaps10]
            if any(v[0] or v[1] for v in seq):
                inst10[code] = seq
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_DIR / "inst10.json").write_text(
            json.dumps({"dates": [f.stem for f in t86_files], "stocks": inst10},
                       ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[OK ] docs/inst10.json（{len(inst10)} 檔 × {len(t86_files)} 日）")

    # 基本面全量內嵌（個股面板要查任意個股；只留面板用欄位，gzip 後負擔小）
    fund = data["fundamentals"]
    if fund.get("ok"):
        keep = ("eps", "gm", "om", "yield_pct", "debt_pct", "yq", "div_cash")
        fund["data"]["stocks"] = {
            c: {k: f[k] for k in keep if f.get(k) is not None}
            for c, f in fund["data"]["stocks"].items()}
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BUILT_AT__", datetime.now().strftime("%Y-%m-%d %H:%M")))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] docs/index.html ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
