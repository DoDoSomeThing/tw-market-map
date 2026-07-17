# render.py — 讀 data/*.json → 產 docs/index.html（dark 單頁、RWD、無框架）
# 新鮮度在瀏覽端 JS 算：頁面可能隔好幾天才被打開，伺服端算會「裝新鮮」。
from __future__ import annotations

import json
from datetime import datetime

from tw_common import DATA_DIR, DOCS_DIR, read_json, tw_now

DOCS_HISTORY_KEEP = 30   # docs/history 只放最近 N 支（data/history 為永久 archive，不受此限）

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- Fira Sans/Code：dashboard 專用字組，數字等寬對齊；載不到時 fallback 系統字（見 --sans/--num） -->
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<title>台股產業地圖</title>
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#05070d">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<link rel="apple-touch-icon" href="icon-180.png">
<script>(function(){try{var t=localStorage.getItem("twmm_theme")||(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark");document.documentElement.dataset.theme=t;}catch(e){}})();</script>
<style>
/* 設計系統（2026-07-17 Bento 改版）— 依 ui-ux-pro-max 對 fintech dashboard 的建議：
   Bento Grid（高資訊密度但不雜亂）＋ Fira Sans/Fira Code（數字等寬=金融標配）
   ＋ 藍=資料、琥珀=需注意（給視線一個落點，解決「everything same weight」）。
   全站樣式走這組變數 → 改這裡即改七個分頁。 */
:root {
  --bg: #0a0e17; --panel: #121826; --panel2: #161d2e; --border: #232c40; --border-hi: #33415c;
  --fg: #e8edf5; --muted: #8a97ad;
  --up: #ff4d4f; --down: #00c98d; --flat: #8a97ad; /* 台股紅漲綠跌 */
  --warn: #f59e0b; --accent: #3b82f6; --accent-soft: rgba(59,130,246,.12);
  --hi: #f59e0b; --hi-soft: rgba(245,158,11,.12);   /* 琥珀：需注意/次要焦點 */
  --r: 18px; --r-sm: 12px; --gap: 16px; --tr: .2s ease;
  --surface: var(--panel);
  --shadow: 0 8px 28px rgba(0,0,0,.28);
  --num: "Fira Code", ui-monospace, "SF Mono", Menlo, Consolas, monospace;
  --sans: "Fira Sans", -apple-system, "PingFang TC", "Microsoft JhengHei", sans-serif;
  --bar-flat: #33415c;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--fg); font-family: var(--sans); margin: 0 auto;
  -webkit-font-smoothing: antialiased; font-variant-numeric: tabular-nums;
  /* 區塊改卡片後，格線與卡片邊框會互相打架 → 只留頂部一道柔光，其餘乾淨 */
  background-image: radial-gradient(1000px 400px at 50% -160px, rgba(59,130,246,.10), transparent 70%);
  background-repeat: no-repeat; }
h1 { font-size: 1.2rem; font-weight: 600; letter-spacing: -.01em; }
/* 區塊＝一張 Bento 卡（不再是裸區塊直接堆）→ 密度不變但有邊界、不糊在一起 */
section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r);
  padding: 16px 18px; margin-bottom: var(--gap); transition: border-color var(--tr); }
section:hover { border-color: var(--border-hi); }
h2 { font-size: .82rem; font-weight: 600; padding: 0 0 10px; color: var(--muted); letter-spacing: .02em; }
h2::before { content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  background: var(--accent); margin-right: 8px; vertical-align: 1px; }

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
/* ── 焦點頁 Bento 拼盤 ──
   原本 8 張卡由上到下各吃滿整寬 → 自選股只有 78px 高卻霸佔 1176px，整頁 4756px 要滾 5 個螢幕。
   改 12 欄 grid：矮卡(自選/寬度/指數)收進右側單欄疊放，其餘兩兩並排。
   .active 才設 grid，否則會蓋掉分頁切換的 display:none。 */
/* align-items:start = 每張卡自然高、誰也不被撐。
   用 stretch 的話今日異動卡會永遠被撐滿整列高 → syncChangesHeight() 量 sec.bottom 量到的是
   「列的底」而不是「卡的自然底」，delta 恆為固定值、每次呼叫再縮一次，永遠不收斂。 */
#pane-focus.active { display: grid; grid-template-columns: repeat(12, 1fr); gap: var(--gap); align-items: start; }
#pane-focus > section, #pane-focus > .bento-col { margin-bottom: 0; min-width: 0; }  /* min-width:0 = 允許內部寬表格自己捲，不撐爆格線 */
/* 右欄卡片保持自然高（align-content:start）。
   曾試過 stretch 撐滿左卡高度 → 卡是齊了，但卡內多出 70px 空白底，比空洞更醜。
   改由 syncChangesHeight() 反過來讓左卡（今日異動）去配合右欄高度。 */
#pane-focus > .bento-col { display: grid; gap: var(--gap); align-content: start; }
#pane-focus > #sec-changes { grid-column: span 8; }
#pane-focus > #bento-side  { grid-column: span 4; }
/* 國際指數不放右欄：381px 窄欄會把它從 299 撐到 554（卡片式排版塞不下就換行）→ 整條右欄暴增到 1017。 */
#pane-focus > #sec-indices { grid-column: span 12; }
/* 寬表格留整列：實測併成半寬(580px)後內容換行，高度反而多兩倍
   (營收亮點 541→1266、資金流 1014→1959、個股動向 1269→2589)。 */
#pane-focus > #sec-revhl, #pane-focus > #sec-market,
#pane-focus > #sec-flow,  #pane-focus > #sec-inst { grid-column: span 12; }
@media (max-width: 980px) {   /* 窄螢幕塌回單欄 */
  #pane-focus.active { display: block; }
  #pane-focus > section, #pane-focus > .bento-col { margin-bottom: var(--gap); }
  #pane-focus > .bento-col > section:last-child { margin-bottom: 0; }
}
@keyframes paneIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

/* 搜尋 */
.searchwrap { position: relative; margin-left: auto; }
#search { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; color: var(--fg); padding: 6px 11px; font-size: .85rem; width: 172px; font-family: inherit; transition: border-color var(--tr), box-shadow var(--tr); }
#search:focus { outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }
#search-res { position: absolute; right: 0; top: 38px; background: var(--surface); border: 1px solid var(--border-hi); border-radius: var(--r); min-width: 340px; max-width: min(420px, 92vw); max-height: 340px; overflow-y: auto; display: none; z-index: 60; box-shadow: var(--shadow); }
.sr-item { padding: 8px 10px; border-bottom: 1px solid var(--border); cursor: pointer; font-size: .85rem; transition: background var(--tr); }
.sr-item:hover { background: var(--accent-soft); }
.sr-item:last-child { border-bottom: none; }
/* 上列固定一行：股名不可被壓縮（題材多的股票如 2408 曾被徽章擠成直書）；徽章另起一列自己 wrap */
.sr-top { display: flex; gap: 8px; align-items: center; white-space: nowrap; }
.sr-top > b, .sr-top > .sub { flex: none; }
.sr-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; }
.sr-badge { flex: none; white-space: nowrap; font-size: .68rem; border: 1px solid var(--border); border-radius: 999px; padding: 1px 7px; color: var(--muted); cursor: pointer; transition: color var(--tr), border-color var(--tr); }
.sr-badge:hover { border-color: var(--accent); color: var(--accent); }

/* 市場寬度 */
.breadth { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r); padding: 12px; }
.b-bar { display: flex; height: 12px; border-radius: 6px; overflow: hidden; margin: 9px 0 7px; box-shadow: inset 0 1px 3px rgba(0,0,0,.5); }
.b-bar > div { height: 100%; }
.b-row { display: flex; flex-wrap: wrap; gap: 4px 18px; font-size: .85rem; }

/* 技術狀態篩選 + 個股面板技術面區 */
.ta-filter { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 9px; font-size: .82rem; color: var(--muted); }
.ta-filter button { background: var(--panel); border: 1px solid var(--border); color: var(--fg); border-radius: 6px; padding: 3px 10px; font-size: .82rem; font-family: inherit; cursor: pointer; transition: border-color var(--tr); }
.ta-filter button:hover { border-color: var(--accent); }
.ta-hd { font-weight: 600; margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); }
.ta-block { font-size: .85rem; line-height: 1.7; }
.ta-line { display: flex; flex-wrap: wrap; gap: 2px 6px; }
.ta-line .lbl { color: var(--muted); min-width: 62px; display: inline-block; }
.ta-tags { display: flex; flex-wrap: wrap; gap: 5px; padding: 6px 0 2px; }
.ta-tag { font-size: .76rem; padding: 1px 8px; border-radius: 10px; white-space: nowrap; }
.ta-tag.desc { background: var(--accent-soft); color: var(--accent); border: 1px solid var(--accent-soft); }
.ta-tag.ref { background: var(--panel); color: var(--muted); border: 1px solid var(--border); }

/* 布林通道圖（收盤折線＋上/中/下軌，近 60 日） */
.bb-chart-wrap { margin: 4px 0 2px; }
.bb-chart { display: block; overflow: visible; }
.bbc-band { fill: var(--accent-soft); stroke: none; }
.bbc-edge { fill: none; stroke: var(--accent); stroke-width: 1; opacity: .55; }
.bbc-mid  { fill: none; stroke: var(--muted); stroke-width: 1; stroke-dasharray: 3 3; opacity: .8; }
.bbc-price{ fill: none; stroke: var(--fg); stroke-width: 1.6; }
.bbc-dot  { fill: var(--fg); }
.bbc-lbl  { font-size: 9px; fill: var(--muted); font-family: inherit; }
.bbc-lbl.mid { fill: var(--muted); }

/* 指標說明：hover 提示（.help 虛線底提示可 hover）＋ 可展開說明區（手機用） */
.help { cursor: help; }
.help .lbl, span.lbl.help { border-bottom: 1px dotted var(--border); }
.ta-foot { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 6px; }
.ta-help-btn { background: none; border: 1px solid var(--border); color: var(--muted); border-radius: 6px;
  padding: 2px 8px; font-size: .76rem; font-family: inherit; cursor: pointer; white-space: nowrap; }
.ta-help-btn:hover { border-color: var(--accent); color: var(--accent); }
.ta-help { margin-top: 8px; padding: 10px; background: var(--panel); border: 1px solid var(--border);
  border-radius: var(--r); font-size: .78rem; line-height: 1.65; color: var(--muted); }
.ta-help-item { padding: 5px 0; border-top: 1px solid var(--border); }
.ta-help-item:first-child { border-top: none; padding-top: 0; }
.ta-help-item b { color: var(--fg); display: block; margin-bottom: 2px; }

/* 均線格子 */
.ma-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin: 8px 0; }
.ma-cell { border: 1px solid var(--border); border-radius: 8px; padding: 7px 6px; text-align: center; background: var(--panel); }
.ma-cell.up { background: rgba(251,44,54,.10); border-color: rgba(251,44,54,.35); }
.ma-cell.down { background: rgba(0,187,127,.10); border-color: rgba(0,187,127,.32); }
.ma-cell .k { font-size: .72rem; color: var(--muted); }
.ma-cell .v { font-size: .95rem; font-weight: 700; font-family: var(--num); margin: 1px 0; }
.ma-cell .s { font-size: .72rem; }
.ma-cell.na { opacity: .5; }

/* 布林迷你通道條 */
.bb-wrap { margin: 8px 0; }
.bb-head { display: flex; justify-content: space-between; font-size: .78rem; color: var(--muted); margin-bottom: 3px; }
.bb-track { position: relative; height: 22px; border-radius: 5px;
  background: linear-gradient(90deg, rgba(0,187,127,.22), rgba(125,138,160,.12) 50%, rgba(251,44,54,.22)); border: 1px solid var(--border); }
.bb-mid { position: absolute; top: -2px; bottom: -2px; left: 50%; width: 1px; background: var(--muted); opacity: .6; }
.bb-dot { position: absolute; top: 50%; width: 11px; height: 11px; border-radius: 50%; background: var(--fg);
  border: 2px solid var(--bg); transform: translate(-50%, -50%); box-shadow: 0 0 0 1px var(--fg); }
.bb-scale { display: flex; justify-content: space-between; font-size: .72rem; color: var(--muted); margin-top: 2px; font-family: var(--num); }

/* KD/RSI 迷你色條 */
.gauge { margin: 5px 0; }
.gauge-lbl { display: flex; justify-content: space-between; font-size: .78rem; margin-bottom: 2px; }
.gauge-lbl b { font-family: var(--num); }
.gauge-track { position: relative; height: 6px; border-radius: 3px; overflow: hidden;
  background: linear-gradient(90deg, rgba(0,187,127,.5) 0 20%, rgba(125,138,160,.25) 20% 70%, rgba(251,44,54,.5) 70% 100%); }
.gauge-dot { position: absolute; top: -3px; width: 3px; height: 12px; border-radius: 1px; background: var(--fg); transform: translateX(-50%); }

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

/* 指數卡一律排成一列（.cards 只有國際指數在用）。
   原本 grid auto-fill minmax(160px) 依寬度自動填欄 → 7 檔在 1176px 排成「上 6 下 1」，落單那張很醜。
   改 flex：flex:1 讓 N 張平均分寬，不管幾張都同一列；basis 140px 是下限，塞不下就整條橫捲。
   手機也不換行：7 是質數，一換行就變 2/2/2/1，最後一張照樣落單 → 寧可橫向滑動。 */
.cards { display: flex; gap: var(--gap); overflow-x: auto; }
.cards > .card { flex: 1 0 140px; min-width: 0; }
.card { background: var(--panel2); border: 1px solid var(--border); border-radius: var(--r-sm); padding: 13px 14px;
  transition: border-color var(--tr), transform var(--tr); }
.card:hover { border-color: var(--border-hi); transform: translateY(-2px); }
.card .nm { font-size: .74rem; color: var(--muted); }
.card .px { font-size: 1.45rem; font-weight: 700; margin-top: 3px; font-family: var(--num); letter-spacing: -.02em; }
.card .chg { font-size: .82rem; font-family: var(--num); }

/* 法人/資券 + 全站表格 */
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gap); }
@media (max-width: 700px) { .grid2 { grid-template-columns: 1fr; } }
/* 表格：區塊已是卡片 → 表格本身脫掉外框/底色，改用細分隔線＋留白（去「報表感」的關鍵） */
table { width: 100%; border-collapse: separate; border-spacing: 0; background: transparent; border: none; border-radius: var(--r-sm); overflow: hidden; font-size: .85rem; }
th, td { padding: 9px 10px; text-align: right; border-bottom: 1px solid var(--border); }
th:first-child, td:first-child { text-align: left; }
th { color: var(--muted); font-weight: 500; font-size: .7rem; letter-spacing: .04em; background: transparent; user-select: none; cursor: pointer; border-bottom-color: var(--border-hi); }
th[data-dir="desc"]::after { content: " ▾"; color: var(--accent); }
th[data-dir="asc"]::after { content: " ▴"; color: var(--accent); }
tr:nth-child(even) td { background: transparent; }   /* 斑馬紋拿掉：卡片＋分隔線已足夠，斑馬紋讓畫面更吵 */
tr:hover td { background: var(--accent-soft); }
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
.sticky-head { overflow: visible; }   /* 覆蓋全域 table overflow:hidden，否則 sticky 黏在不捲動的 table 上失效 */
.sticky-head thead th { position: sticky; top: 0; z-index: 2; box-shadow: inset 0 -1px 0 var(--border), 0 1px 0 var(--border); }

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
/* 全市場異動全部攤開（138 條）→ 靠卡內捲動控高度，不再收在 <details> 裡。
   桌機的 max-height 由 syncChangesHeight() 動態蓋成「右欄實際高度」；
   這裡的 480px 是手機單欄／JS 沒跑起來時的保底值。 */
.chg-list { background: var(--panel); border: 1px solid var(--border); border-radius: var(--r); font-size: .86rem; max-height: 480px; overflow-y: auto; }
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
/* 雙欄個股面板：左=基本資料+法人+新聞、右=技術面。
   桌機目標「一頁看完不捲動」→ 容器放寬 + 內容壓縮；≤820px（手機/窄窗）才退單欄並允許捲動。 */
#sp-panel.sp-wide { width: min(1060px, 96vw); max-height: 94vh; overflow-y: hidden; }
.sp-two { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; align-items: start; }
.sp-two .sp-col { min-width: 0; }
.sp-two .sp-grid { grid-template-columns: repeat(3, 1fr); padding: 6px 0; gap: 5px; }
.sp-two .sp-cell { padding: 4px 7px; }
.sp-two .sp-cell .lbl { font-size: .66rem; }
.sp-colhd { font-weight: 600; font-size: .8rem; color: var(--muted); padding: 4px 0 3px; border-bottom: 1px solid var(--border); margin-bottom: 2px; }
/* 面板內壓縮（一頁看完的關鍵；不影響面板外的同類元件） */
.sp-two .ta-block { line-height: 1.45; }
.sp-two .ma-grid { gap: 5px; margin: 5px 0; }
.sp-two .ma-cell { padding: 4px; }
.sp-two .bb-wrap { margin: 5px 0; }
.sp-two .gauge { margin: 3px 0; }
.sp-two .inst-chart { margin: 2px 0; }
.sp-two .news-links .mops-item { padding: 4px 8px; line-height: 1.4; }

/* 法人買賣超詳細圖表（左欄） */
.inst-chart { margin: 4px 0 2px; }
.inst-row { display: flex; align-items: center; gap: 6px; }
.inst-lbl { font-size: .72rem; color: var(--muted); width: 26px; flex: none; }
.inst-bars { flex: 1; min-width: 0; }
.inst-sum { font-size: .72rem; font-family: var(--num); width: 64px; text-align: right; flex: none; }
.inst-axis { display: flex; justify-content: space-between; font-size: .64rem; color: var(--muted); padding: 1px 64px 0 32px; }
.inst-axis span { flex: 1; text-align: center; }
/* 手機/窄窗：退單欄，改回可捲動（塞不下是必然，捲動才合理） */
@media (max-width: 820px) {
  #sp-panel.sp-wide { width: 94vw; max-height: 88vh; overflow-y: auto; }
  .sp-two { grid-template-columns: 1fr; gap: 4px; }
}
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
/* 長表摺疊：資料照渲染、只是收起 → 展開零延遲。用 hidden 而非 display:none? 不行，
   <tr> 的 hidden 在部分瀏覽器仍佔位 → 一律 display:none，代價是收起的列 Ctrl+F 找不到。 */
.foldx { display: none; }
.foldbox.open .foldx { display: table-row; }
.foldbox.open .rev-card.foldx { display: block; }
.foldbtn { display: block; width: 100%; margin-top: 8px; padding: 6px; background: transparent;
  border: 1px dashed var(--border-hi); border-radius: var(--r-sm); color: var(--muted);
  font-size: .74rem; cursor: pointer; transition: color var(--tr), border-color var(--tr); }
.foldbtn:hover { color: var(--accent); border-color: var(--accent); }
.ranks { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
@media (max-width: 700px) { .ranks { grid-template-columns: 1fr; } }
footer { color: var(--muted); font-size: .72rem; padding: 18px 0; line-height: 1.6; border-top: 1px solid rgba(28,42,68,.5); margin-top: 16px; }

/* ── 淺色主題（--bg 等 token 覆蓋 + 寫死色補丁）── */
:root { color-scheme: dark; }
:root[data-theme="light"] {
  color-scheme: light;
  --bg: #f5f5f7; --panel: #ffffff; --panel2: #fbfcfe; --border: #e5e9f0; --border-hi: #cfd8e6;
  --fg: #131a26; --muted: #5b6880;
  --up: #d92d20; --down: #067a5b; --flat: #5b6880;
  --warn: #b45309; --accent: #2563eb; --accent-soft: rgba(37,99,235,.09);
  --hi: #b45309; --hi-soft: rgba(180,83,9,.10);
  --surface: #ffffff;
  --shadow: 0 8px 28px rgba(23,35,58,.10);
  --bar-flat: #cfd8e6;
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
<div class="bento-col" id="bento-side">
  <section id="sec-mywatch"><h2>自選股 <span class="sub" id="wl-hint"></span></h2><div id="watchlist"></div></section>
  <section id="sec-breadth"><h2>市場寬度 <span class="stamp" data-stamp="breadth"></span></h2><div id="breadth"></div></section>
</div>
<section id="sec-indices"><h2>國際指數 <span class="stamp" data-stamp="indices"></span></h2><div id="indices"></div></section>
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
資料源：TWSE / TPEx 公開 API、yfinance、MOPS 公開資訊觀測站、TDCC 集保中心。每交易日收盤後自動更新（排程 17:30，GitHub Actions 實際多延遲至 19:00–20:30；各區塊以自身「資料日」為準）。<br>
鐵則：只做現況呈現，不做預測；各區塊資料日不一致或過期時顯示 ⚠️。
</footer>
<div id="sp-overlay" onclick="spClose()"></div>
<div id="sp-panel"></div>
</main>

<script>
const DATA = __DATA__;
// PE 高於此值＝「獲利極低導致失真」而非「昂貴」：EPS 趨近 0 時 PE 會爆到幾千倍
// （M31 PE 10300 = 近四季每股僅賺 0.04 元）→ 面板標示，避免與台積 PE 33 被當同尺度誤讀
const PE_ABSURD = 200;
const BUILT_AT = "__BUILT_AT__";

// ── 長表摺疊 ──
// 焦點頁 65% 的高度來自四張長表（資金流/個股動向/營收亮點/今日異動 合計 3035px）。
// 資料全部照渲染進 DOM、只是先收起來 → 展開零延遲、Ctrl+F 找得到（用 hidden 而非 display:none 會找不到）。
let _foldSeq = 0;
function foldWrap(html, total, shown, unit) {
  if (total <= shown) return html;
  const id = "fold" + (++_foldSeq);
  const label = `展開其餘 ${total - shown} ${unit} ▾`;
  return `<div class="foldbox" id="${id}">${html}
    <button class="foldbtn" data-fold="${id}" data-label="${label}">${label}</button></div>`;
}
// 前 shown 個原樣、其餘掛 .foldx（收起）。mark 由呼叫端給，因為 <tr> 跟 <div> 掛 class 的位置不同。
function foldSlice(arr, shown, mark) {
  return arr.map((h, i) => i < shown ? h : mark(h)).join("");
}
document.addEventListener("click", e => {
  const b = e.target.closest(".foldbtn");
  if (!b) return;
  const open = document.getElementById(b.dataset.fold).classList.toggle("open");
  b.textContent = open ? "收合 ▴" : b.dataset.label;
});

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
  const news = newsFor(code, 2).map(it => `<div class="mops-item"><span class="tm">${(it.time || "").slice(5)}</span>
    <a href="${it.link}" target="_blank" rel="noopener" style="color:var(--fg)">${it.title}</a></div>`).join("");
  const cell = (lbl, val) => `<div class="sp-cell"><span class="lbl">${lbl}</span>${val}</div>`;
  // 估值（交易所每日公布 PE/PB；虧損股不給 PE → 顯示「—」不裝有值）
  // PE 極高 ≠ 貴，而是 EPS 趨近 0 讓這把尺失效（M31 PE 10300 = 近四季每股只賺 0.04 元）→ 標示避免誤讀
  const va = DATA.valuation.ok ? (DATA.valuation.data.stocks[code] || {}) : {};
  const capTxt = va.cap == null ? "—"
    : va.cap >= 10000 ? (va.cap / 10000).toFixed(2) + " 兆" : va.cap.toLocaleString() + " 億";
  // 集保大戶（週資料）：[400張+%, 千張+%, 週增減pp, 股東人數]
  const bh = DATA.tdcc.ok ? (DATA.tdcc.data.by_code || {})[code] : null;
  const bhDelta = bh && bh[2] != null
    ? ` <span class="${cls(bh[2])}">${bh[2] > 0 ? "+" : ""}${bh[2]}pp</span>` : "";
  // 同題材相對位置：這檔在所屬題材裡的漲幅名次（我們獨有的角度）
  let rankBadges = "";
  if (DATA.topics_view.ok) {
    const rs = [];
    for (const t of DATA.topics_view.data.topics) {
      const ms = (t.members || []).filter(m => m.pct != null);
      if (ms.length < 3) continue;
      const sorted = [...ms].sort((a, b) => b.pct - a.pct);
      const i = sorted.findIndex(m => m.code === code);
      if (i >= 0) rs.push(`<span class="sr-badge" title="${t.name} 今日漲幅排名">${t.name} ${i + 1}/${sorted.length}</span>`);
    }
    if (rs.length) rankBadges = `<div class="sub" style="padding:4px 0 0">今日題材內漲幅名次 ${rs.join(" ")}</div>`;
  }
  const panelEl = document.getElementById("sp-panel");
  panelEl.classList.add("sp-wide");
  panelEl.innerHTML = `
    <button class="sp-close" onclick="spClose()">✕</button>
    <h3>${r[1]} <span class="sub">${code}${r[2] ? "・" + r[2] : ""}</span>
      <button class="star ${wlHas(code) ? "on" : ""}" data-code="${code}" onclick="wlToggle('${code}')">★</button></h3>
    <div><span class="px ${cls(r[4])}" style="font-size:1.3rem;font-weight:700">${r[3]}</span>
      <span class="${cls(r[4])}">（${sign(r[4])}%）</span> <span id="sp-spark" style="margin-left:8px"></span></div>
    <div class="sp-two">
      <div class="sp-col">
        <div class="sp-colhd">基本資料 · 法人</div>
        <div class="sp-grid">
          ${cell("成交值", r[6] != null ? r[6] + " 億" : "—")}
          ${cell("外資(張)", lotsCell(r[7], r[9]))}
          ${cell("投信(張)", lotsCell(r[8], r[10]))}
          ${cell("本益比 PE", va.pe == null ? `<span class="sub">—</span>`
              : va.pe > PE_ABSURD ? `${va.pe}<span class="sub"> ⚠️低獲利</span>` : va.pe)}
          ${cell("股價淨值比 PB", va.pb != null ? va.pb : "—")}
          ${cell("市值", capTxt)}
          ${cell("EPS", f.eps ?? "—")}${cell("毛利率", f.gm != null ? f.gm + "%" : "—")}
          ${cell("殖利率", va.yield_ex != null ? va.yield_ex + "%" : (f.yield_pct != null ? f.yield_pct + "%" : "—"))}
          ${bh ? cell("大戶 400張+", `${bh[0]}%${bhDelta}`) + cell("千張大戶", bh[1] + "%")
                 + cell("股東人數", bh[3] ? bh[3].toLocaleString() : "—") : ""}
          ${dv ? cell("最後買進日", dv.last_buy ? `<b>${dv.last_buy.slice(5).replace("-", "/")}</b>` : "—")
               + cell("預計除息", `<span class="up">${dv.ex_date.slice(5).replace("-", "/")}</span>`)
               + cell("本次現金", dv.cash != null ? dv.cash + " 元" : "待公告") : ""}
          ${rv ? cell("當月營收", rv[0] + " 億") + cell("營收 YoY", rv[1] != null ? (rv[1] > 0 ? "+" : "") + rv[1] + "%" : "—")
               + cell("營收 MoM", rv[2] != null ? (rv[2] > 0 ? "+" : "") + rv[2] + "%" : "—") : ""}
        </div>
        <div id="sp-inst"></div>
        ${rankBadges}
        ${f.yq ? `<div class="sub" style="padding-top:4px">基本面季度：${f.yq}${f.debt_pct != null ? "｜負債比 " + f.debt_pct + "%" : ""}${bh ? "｜大戶為集保週資料（" + (DATA.tdcc.data_date || "").slice(5).replace("-", "/") + "）" : ""}${va.pe != null && va.pe > PE_ABSURD ? "｜⚠️ PE " + va.pe + " 倍係近四季每股僅賺 " + (r[3] / va.pe).toFixed(2) + " 元所致，PE 參考性差" : ""}</div>` : ""}
        ${news ? `<div class="news-links" style="margin-top:4px">${news}</div>` : `<div class="sub" style="padding:6px 0">近日無相關新聞標題</div>`}
      </div>
      <div class="sp-col">
        <div id="sp-ta"></div>
        ${badges.trim() ? `<div style="padding:6px 0">${badges}</div>` : ""}
        <div style="padding-top:6px"><a href="${yahoo}" target="_blank" rel="noopener" style="color:var(--accent)">開 Yahoo 股市頁 ↗</a>
          <span class="sub">（裝 kanpan 擴充會自動掛面板）</span></div>
      </div>
    </div>`;
  document.getElementById("sp-overlay").style.display = "block";
  panelEl.style.display = "block";
  seriesFor([code]).then(m => {
    const el = document.getElementById("sp-spark");
    if (el && m[code]) el.innerHTML = sparkSVG(m[code], 140, 30);
  });
  loadInst10().then(d => {
    const el = document.getElementById("sp-inst");
    if (!el || !d || !d.stocks || !d.stocks[code]) return;
    const seq = d.stocks[code];
    const dates = d.dates || [];
    const fv = seq.map(x => x[0]), tv = seq.map(x => x[1]);
    const sum = a => a.reduce((s, v) => s + v, 0);
    const fs = sum(fv), ts = sum(tv);
    const tot = v => `${v > 0 ? "+" : ""}${v.toLocaleString()}`;
    el.innerHTML = `<div class="sp-colhd">法人買賣超 <span class="sub">近 ${seq.length} 日・張・滑過看每日</span></div>
      <div class="inst-chart">
        <div class="inst-row"><span class="inst-lbl">外資</span>${instBarsSVG(dates, fv)}<span class="inst-sum ${cls(fs)}">${tot(fs)}</span></div>
        <div class="inst-row"><span class="inst-lbl">投信</span>${instBarsSVG(dates, tv)}<span class="inst-sum ${cls(ts)}">${tot(ts)}</span></div>
        <div class="inst-axis">${dates.map(x => `<span>${x.slice(5).replace("-", "/")}</span>`).join("")}</div>
        <div class="sub" style="padding-top:3px">右側為 ${seq.length} 日累計淨買賣超</div>
      </div>`;
  });
  loadTa().then(d => {
    const el = document.getElementById("sp-ta");
    if (!el || !d || !d.ok) return;
    const t = (d.data.stocks || {})[code];
    const mmdd = d.data_date ? d.data_date.slice(5).replace("-", "/") : "?";
    if (!t) { el.innerHTML = `<div class="ta-block"><div class="sub">技術面：無資料（上市未滿或停牌）</div></div>`; return; }
    el.innerHTML = `<div class="ta-hd">技術面 <span class="sub">資料日 ${mmdd}</span></div>` + taRowsHTML(t);
    // 布林通道圖（另支 lazy fetch，晚到不擋面板其他內容）
    loadC80().then(cd => {
      const box = document.getElementById("sp-bbchart");
      if (!box || !cd || !cd.ok) return;
      const ser = (cd.data.stocks || {})[code];
      if (ser && ser.length >= 25) box.innerHTML = bbChartSVG(ser);
    });
  });
}
window.openStock = openStock;

// ── 大盤異動清單面板（漲停股 / 跌幅最大…）→ 每列可再點進個股面板 ──
const BR_LIST_LABEL = { limit_up: "漲停股", limit_down: "跌停股", top_up: "漲幅最大", top_down: "跌幅最大" };
function spList(tag) {
  const rows = (DATA.breadth.ok ? (DATA.breadth.data.lists || {})[tag] : null) || [];
  if (!rows.length) return;
  const items = rows.map(r => `<div class="chg-item" onclick="openStock('${r.code}')" style="cursor:pointer">
    <b>${r.name}</b> <span class="sub">${r.code}</span>
    <span class="px ${cls(r.pct)}" style="float:right">${sign(r.pct)}%　${r.close}</span></div>`).join("");
  document.getElementById("sp-panel").classList.remove("sp-wide");
  document.getElementById("sp-panel").innerHTML = `
    <button class="sp-close" onclick="spClose()">✕</button>
    <h3>${BR_LIST_LABEL[tag] || "個股清單"} <span class="sub">${rows.length} 檔・資料日 ${DATA.breadth.data_date || ""}</span></h3>
    <div class="chg-list" style="margin-top:8px">${items}</div>`;
  document.getElementById("sp-overlay").style.display = "block";
  document.getElementById("sp-panel").style.display = "block";
}
window.spList = spList;

// ── 技術狀態篩選清單（ta.json lazy；站上/跌破年線、爆量、多空排列）→ 點列進個股面板 ──
const TA_LIST = {
  above_year: ["站上年線", t => t.above && t.above["240"] === true],
  lose_year:  ["跌破年線", t => t.above && t.above["240"] === false],
  vol_spike:  ["今日爆量（量比≥2）", t => (t.signals || []).includes("vol_spike")],
  ma_bull:    ["均線多頭排列", t => (t.signals || []).includes("ma_bull")],
  ma_bear:    ["均線空頭排列", t => (t.signals || []).includes("ma_bear")],
};
function taList(kind) {
  const spec = TA_LIST[kind];
  if (!spec) return;
  const panel = document.getElementById("sp-panel");
  panel.classList.remove("sp-wide");
  panel.innerHTML = `<button class="sp-close" onclick="spClose()">✕</button>
    <h3>${spec[0]} <span class="sub">載入技術面…</span></h3>`;
  document.getElementById("sp-overlay").style.display = "block";
  panel.style.display = "block";
  loadTa().then(d => {
    if (!d || !d.ok) { panel.querySelector(".sub").textContent = "技術面資料尚未就緒"; return; }
    const st = d.data.stocks || {};
    const mmdd = d.data_date ? d.data_date.slice(5).replace("-", "/") : "?";
    // 命中且在 QUOTES（有股名/收盤/漲跌）；依成交值排序取前 200（避免面板過長）
    let rows = Object.keys(st).filter(c => spec[1](st[c]) && QUOTES[c])
      .map(c => ({ c, q: QUOTES[c], t: st[c] }))
      .sort((a, b) => (b.q[6] || 0) - (a.q[6] || 0));
    const total = rows.length;
    rows = rows.slice(0, 200);
    const items = rows.map(({ c, q, t }) => {
      const bias = t.bias240 != null ? ` <span class="sub">年線乖離 ${sign(t.bias240)}%</span>` : "";
      const vr = t.vol_ratio != null ? ` <span class="sub">量比 ${t.vol_ratio}×</span>` : "";
      return `<div class="chg-item" onclick="openStock('${c}')" style="cursor:pointer">
        <b>${q[1]}</b> <span class="sub">${c}${q[2] ? "・" + q[2] : ""}</span>${bias}${vr}
        <span class="px ${cls(q[4])}" style="float:right">${sign(q[4])}%　${q[3]}</span></div>`;
    }).join("");
    panel.innerHTML = `<button class="sp-close" onclick="spClose()">✕</button>
      <h3>${spec[0]} <span class="sub">${total} 檔${total > 200 ? "（顯示成交值前 200）" : ""}・資料日 ${mmdd}</span></h3>
      <div class="sub" style="padding:2px 0">技術狀態描述，非買賣建議</div>
      <div class="chg-list" style="margin-top:6px">${items}</div>`;
  });
}
window.taList = taList;

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
  const brLists = (DATA.breadth.ok ? (DATA.breadth.data.lists || {}) : {});
  const mk = (d.market_events || []).map(e => {
    const has = e.list && (brLists[e.list] || []).length;
    return has
      ? `<div class="chg-item" onclick="spList('${e.list}')" style="cursor:pointer">⚠️ ${e.txt} <span class="sub">›</span></div>`
      : `<div class="chg-item" style="cursor:default">⚠️ ${e.txt}</div>`;
  }).join("");
  const tp = (d.topic_events || []).map(e =>
    `<div class="chg-item" onclick="showTab('radar')">🔥 題材「<b>${e.name}</b>」${e.txt}</div>`).join("");
  const wlHtml = wl.size
    ? (wlEv.length ? wlEv.map(e => line(e, true)).join("") : `<div class="chg-item sub" style="cursor:default">自選股今日無異動</div>`)
    : `<div class="chg-item sub" style="cursor:default">尚未加自選股（右上搜尋點 ★），以下為全市場異動</div>`;
  // 全市場異動全部攤平（原本收在 <details> 裡）：卡片本身限高可捲，不再靠摺疊壓高度。
  // 順帶修掉舊 bug：summary 寫「更多異動（N 條）」但內容是 slice(8, 80)，
  // N 超過 80 時多出來的幾十條根本沒渲染 → 數字對不上內容。現在不切。
  const rest = others.map(e => line(e, false)).join("");
  if (!mk && !tp && !wlEv.length && !others.length) {
    el.innerHTML = `<div class="chg-list"><div class="chg-item sub" style="cursor:default">今日無特別異動</div></div>`;
    return;
  }
  el.innerHTML = `<div class="chg-list">${mk}${tp}${wlHtml}${rest}</div>`;
  syncChangesHeight();
}

// ── 今日異動高度跟著右欄走 ──
// 焦點頁第一列是「今日異動｜自選股+市場寬度」。兩邊不等高只有三種結局：露出透明空洞、
// 把右欄卡撐出白底、或把左卡寫死一個高度（右欄一長高就又不齊）。
// 純 CSS 辦不到——grid 列高取「最高」那個，而今日異動 138 條攤開有 5336px，
// 會反過來把整列撐爆。只能用 JS 量右欄真實高度，回頭限制左卡的捲動區。
// 右欄高度會變（自選股存在 localStorage，加減股票即時重畫）→ 用 ResizeObserver 持續跟。
function syncChangesHeight() {
  const pane = document.getElementById("pane-focus");
  const side = document.getElementById("bento-side");
  const sec = document.getElementById("sec-changes");
  const list = sec && sec.querySelector(".chg-list");
  if (!pane || !side || !list) return;
  const disp = getComputedStyle(pane).display;
  if (disp === "none") return;                                     // 切到別的分頁 → 量到的全是 0，別亂設
  if (disp !== "grid") { list.style.maxHeight = ""; return; }      // 手機單欄 → 交還給 CSS
  // 目標＝右欄最後一張卡的底緣。量卡片不量 wrapper：wrapper 是 grid 項目，
  // 一旦哪天又被設成 stretch 就會回報整列高 → 量到自己、變成循環參照。
  const kids = [...side.children];
  if (!kids.length) return;
  const target = kids[kids.length - 1].getBoundingClientRect().bottom;
  if (target <= 0) return;
  // 用差值調整而不是反推「標題+內距」的高度：一減一加兩邊量到的時機會不同步，
  // 之前那版每次切回分頁就飄 14px。差值式對齊後 delta=0 → 再跑幾次都不動。
  const delta = target - sec.getBoundingClientRect().bottom;
  if (Math.abs(delta) < 1) return;
  const h = list.getBoundingClientRect().height + delta;
  list.style.maxHeight = Math.max(240, Math.round(h)) + "px";   // 240 = 右欄極矮時的下限
}
renderChanges();
(function () {
  const side = document.getElementById("bento-side");
  if (!side || !window.ResizeObserver) return;
  // 觀察卡片本身（自然高、不受左卡影響）→ 不會跟 maxHeight 互相觸發成無限迴圈
  const ro = new ResizeObserver(() => syncChangesHeight());
  [...side.children].forEach(c => ro.observe(c));
  addEventListener("resize", syncChangesHeight);
})();

// ── 法人近日買賣柱狀（inst10.json lazy fetch）──
let INST10 = null;
function loadInst10() {
  if (!INST10) INST10 = fetch("inst10.json").then(r => r.json()).catch(() => null);
  return INST10;
}

// ── 技術面（ta.json lazy fetch；描述性為主、訊號僅供參考非買賣建議）──
let TA = null;
function loadTa() {
  if (!TA) TA = fetch("ta.json").then(r => r.json()).catch(() => null);
  return TA;
}
// 訊號旗標 → [前端文字, 樣式類]；訊號式(kd_*)用灰底「參考」，不放大
const TA_SIG = {
  ma_bull:    ["均線多頭排列", "ta-tag desc"],
  ma_bear:    ["均線空頭排列", "ta-tag desc"],
  vol_spike:  ["爆量", "ta-tag desc"],
  break_year: ["站上年線", "ta-tag desc"],
  lose_year:  ["跌破年線", "ta-tag desc"],
  kd_gc:      ["KD 黃金交叉 參考", "ta-tag ref"],
  kd_dc:      ["KD 死亡交叉 參考", "ta-tag ref"],
  bb_upper:   ["貼布林上軌 參考", "ta-tag ref"],
  bb_lower:   ["貼布林下軌 參考", "ta-tag ref"],
  macd_gc:    ["MACD 黃金交叉 參考", "ta-tag ref"],
  macd_dc:    ["MACD 死亡交叉 參考", "ta-tag ref"],
};
// ── 布林通道圖（closes80.json lazy fetch；收盤折線＋上/中/下軌，近 60 日）──
let C80 = null;
function loadC80() {
  if (!C80) C80 = fetch("closes80.json").then(r => r.json()).catch(() => null);
  return C80;
}
// 由 80 根收盤算滾動 MA20±2σ（母體標準差，與 build_ta 一致）→ 回最後 show 天的 {c,mid,up,lo}
function bbSeries(closes, n = 20, k = 2, show = 60) {
  const out = [];
  for (let i = n - 1; i < closes.length; i++) {
    const w = closes.slice(i - n + 1, i + 1);
    const mid = w.reduce((a, b) => a + b, 0) / n;
    const sd = Math.sqrt(w.reduce((a, b) => a + (b - mid) ** 2, 0) / n);
    out.push({ c: closes[i], mid, up: mid + k * sd, lo: mid - k * sd });
  }
  return out.slice(-show);
}
function bbChartSVG(closes, w = 480, h = 150) {
  const s = bbSeries(closes);
  if (s.length < 5) return "";
  const pad = { t: 8, r: 44, b: 6, l: 6 };
  const iw = w - pad.l - pad.r, ih = h - pad.t - pad.b;
  const lo = Math.min(...s.map(p => p.lo)), hi = Math.max(...s.map(p => p.up));
  const rg = (hi - lo) || 1;
  const X = i => pad.l + i / (s.length - 1) * iw;
  const Y = v => pad.t + (1 - (v - lo) / rg) * ih;
  const path = key => s.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p[key]).toFixed(1)}`).join("");
  const band = s.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(p.up).toFixed(1)}`).join("")
    + s.slice().reverse().map((p, i) => `L${X(s.length - 1 - i).toFixed(1)},${Y(p.lo).toFixed(1)}`).join("") + "Z";
  const last = s[s.length - 1];
  const lbl = (v, cl, txt) => `<text x="${w - pad.r + 3}" y="${(Y(v) + 3).toFixed(1)}" class="bbc-lbl ${cl || ""}">${txt}</text>`;
  return `<svg class="bb-chart" viewBox="0 0 ${w} ${h}" width="100%" height="${h}">
    <path d="${band}" class="bbc-band"/>
    <path d="${path("up")}" class="bbc-edge"/>
    <path d="${path("lo")}" class="bbc-edge"/>
    <path d="${path("mid")}" class="bbc-mid"/>
    <path d="${path("c")}" class="bbc-price"/>
    <circle cx="${X(s.length - 1).toFixed(1)}" cy="${Y(last.c).toFixed(1)}" r="2.5" class="bbc-dot"/>
    ${lbl(last.up, "", "上軌 " + last.up.toFixed(1))}
    ${lbl(last.mid, "mid", "中軌 " + last.mid.toFixed(1))}
    ${lbl(last.lo, "", "下軌 " + last.lo.toFixed(1))}
  </svg>`;
}

// 指標說明（描述性：講「是什麼／數值代表什麼」，不喊買賣）
// hover 用 title 屬性（桌機）；底部「指標說明」可展開（手機也讀得到）
// 每項存成行陣列 → title 用 &#10; 串（原生 tooltip 換行）、說明區用 <br>。避開跳脫字元問題。
const TA_HELP = {
  ma: ["均線＝近 N 個交易日的平均收盤價。MA5 週線、MA20 月線、MA60 季線、MA240 年線。",
       "現價站上均線＝近期買方成本較低、位置偏強；跌破＝偏弱。",
       "年線那格的「乖離」＝現價離年均價多遠（+44% 就是比一年均價貴 44%）。"],
  bb: ["布林通道＝中軌是 20 日均價，上/下軌為中軌 ±2 倍標準差（約 95% 時間在通道內）。",
       "%B＝現價在通道的位置：0＝貼下軌、50＝中段、100＝貼上軌。",
       "帶寬＝通道寬度佔中軌的 %：越小＝波動收斂（盤整）、越大＝波動放大。"],
  kd: ["KD＝近 9 日高低區間中，收盤落在哪（0~100）。",
       "＞80＝高檔（漲多、過熱區）、＜20＝低檔（跌深、超賣區）、中間＝無明顯偏向。",
       "K/D 交叉常被當買賣訊號，但大樣本驗過沒有實質優勢 → 這裡只當現象標記。"],
  rsi: ["RSI＝近 14 日上漲力道占總波動的比例（0~100）。",
        "＞70＝漲勢強／偏熱、＜30＝跌勢強／超賣、50＝多空均衡。"],
  macd: ["MACD＝兩條均線的距離，用來看動能轉折。",
         "DIF＝12 日與 26 日指數均線的差（短期動能）；DEA＝DIF 的 9 日均線（訊號線）；柱＝DIF−DEA。",
         "柱由負轉正＝短期動能轉強、正轉負＝轉弱；柱越長＝動能越強。",
         "數值大小隨股價高低而異（高價股數字就大），看方向與變化比看絕對值有意義。"],
  vr: ["量比＝今日成交量 ÷ 近 20 日平均成交量（不含今日）。",
       "1×＝與近期均量相當、≥2×＝爆量（通常有消息或事件）、＜0.5×＝量縮冷清。"],
  pos: ["52 週位置＝現價在過去一年高低區間的哪裡。",
        "100%＝一年最高價、0%＝一年最低價、50%＝區間正中間。"],
};
function helpAttr(k) {
  const s = (TA_HELP[k] || []).join("&#10;").replace(/"/g, "&quot;");
  return `title="${s}"`;
}
function taHelpHTML() {
  const item = (name, k) => `<div class="ta-help-item"><b>${name}</b><div>${(TA_HELP[k] || []).join("<br>")}</div></div>`;
  return `<div class="ta-help" id="ta-help" style="display:none">
    ${item("均線 MA5/20/60/240 · 乖離", "ma")}
    ${item("布林通道 · %B · 帶寬", "bb")}
    ${item("KD", "kd")}
    ${item("RSI", "rsi")}
    ${item("MACD · DIF/DEA/柱", "macd")}
    ${item("量比", "vr")}
    ${item("52 週位置", "pos")}
    <div class="sub" style="padding-top:6px">以上皆為現況描述。技術訊號經大樣本驗證無實質優勢，本站不作買賣建議。</div>
  </div>`;
}
function taHelpToggle() {
  const el = document.getElementById("ta-help");
  const btn = document.getElementById("ta-help-btn");
  if (!el) return;
  const show = el.style.display === "none";
  el.style.display = show ? "block" : "none";
  if (btn) btn.textContent = show ? "收合說明" : "ⓘ 指標說明";
}
window.taHelpToggle = taHelpToggle;

function taRowsHTML(t) {
  if (!t) return "";
  // 均線格子（MA5/20/60/240）
  const MA_LBL = { "5": "MA5 週", "20": "MA20 月", "60": "MA60 季", "240": "MA240 年" };
  const maCell = key => {
    const v = t.ma[key], ab = t.above[key];
    if (v == null) return `<div class="ma-cell na"><div class="k">${MA_LBL[key]}</div><div class="v">—</div><div class="s sub">未滿</div></div>`;
    const bias = key === "240" && t.bias240 != null ? `${sign(t.bias240)}%` : (ab ? "站上" : "跌破");
    return `<div class="ma-cell ${ab ? "up" : "down"}"><div class="k">${MA_LBL[key]}</div>
      <div class="v">${v}</div><div class="s ${ab ? "up" : "down"}">${bias}</div></div>`;
  };
  const maGrid = `<div class="ma-grid help" ${helpAttr("ma")}>${["5","20","60","240"].map(maCell).join("")}</div>`;

  // 布林迷你通道條：現價點位置 = %B（夾 0~100），衝破/跌破時貼邊
  let bbBlock = "";
  if (t.bb) {
    const b = t.bb;
    const pos = b.pctb == null ? 50 : Math.max(2, Math.min(98, b.pctb));
    const where = b.pctb == null ? "" : b.pctb >= 100 ? "衝破上軌" : b.pctb >= 80 ? "接近上軌"
      : b.pctb <= 0 ? "跌破下軌" : b.pctb <= 20 ? "接近下軌" : "通道中段";
    bbBlock = `<div class="bb-wrap help" ${helpAttr("bb")}>
      <div class="bb-head"><span>布林通道 <span class="sub">近 60 日・帶寬 ${b.width ?? "—"}%</span></span><span>${where}${b.pctb != null ? ` %B ${b.pctb}` : ""}</span></div>
      <div id="sp-bbchart" class="bb-chart-wrap">
        <div class="bb-track"><div class="bb-mid"></div><div class="bb-dot" style="left:${pos}%"></div></div>
        <div class="bb-scale"><span>${b.lower}</span><span>${b.mid}</span><span>${b.upper}</span></div>
      </div>
    </div>`;
  }

  // KD / RSI 迷你色條（0~100，超賣區綠、超買區紅）
  const gauge = (lbl, val, extra, hk) => {
    const ha = hk ? `class="gauge help" ${helpAttr(hk)}` : `class="gauge"`;
    if (val == null) return `<div ${ha}><div class="gauge-lbl"><span class="lbl">${lbl}</span><span>—</span></div></div>`;
    return `<div ${ha}><div class="gauge-lbl"><span class="lbl">${lbl}</span><b>${val}${extra || ""}</b></div>
      <div class="gauge-track"><div class="gauge-dot" style="left:${Math.max(1, Math.min(99, val))}%"></div></div></div>`;
  };
  const vr = t.vol_ratio != null
    ? `${t.vol_ratio}×${t.vol_ratio >= 2 ? ` <span class="down">爆量</span>` : ""}` : "—";
  const pos = t.pos52w != null ? Math.round(t.pos52w * 100) + "%" : "—";
  const kdBlock = t.kd ? gauge(`KD <span class="sub">${t.kd.k}/${t.kd.d}</span>`, t.kd.k, "", "kd") : gauge("KD", null, "", "kd");

  // MACD(12,26,9)：DIF/DEA + OSC 柱（紅=正、綠=負）。描述數值，交叉標籤走 tags（灰底參考）
  const macdBlock = t.macd
    ? `<div class="ta-line help" style="margin-top:4px" ${helpAttr("macd")}><span class="lbl">MACD</span>
        DIF ${t.macd.dif}　DEA ${t.macd.dea}
        <span class="lbl" style="margin-left:2px">柱</span><span class="${cls(t.macd.osc)}">${t.macd.osc > 0 ? "+" : ""}${t.macd.osc}</span></div>`
    : `<div class="ta-line help" style="margin-top:4px" ${helpAttr("macd")}><span class="lbl">MACD</span><span class="sub">—（未滿26日）</span></div>`;

  const tags = (t.signals || []).map(s => {
    const m = TA_SIG[s]; return m ? `<span class="${m[1]}">${m[0]}</span>` : "";
  }).join(" ");
  return `<div class="ta-block">
    ${maGrid}
    ${bbBlock}
    ${kdBlock}${gauge("RSI", t.rsi14, "", "rsi")}
    ${macdBlock}
    <div class="ta-line" style="margin-top:4px">
      <span class="lbl help" ${helpAttr("vr")}>量比</span>${vr}
      <span class="lbl help" style="margin-left:10px" ${helpAttr("pos")}>52週位置</span>${pos}</div>
    ${tags.trim() ? `<div class="ta-tags">${tags}</div>` : ""}
    <div class="ta-foot"><span class="sub">訊號僅供參考、非買賣建議</span>
      <button id="ta-help-btn" class="ta-help-btn" onclick="taHelpToggle()">ⓘ 指標說明</button></div>
    ${taHelpHTML()}
  </div>`;
}
// 法人買賣超詳細柱狀圖（每日一根，0 軸，hover 顯示日期+張數；紅買綠賣）
function instBarsSVG(dates, vals, w = 300, h = 40) {
  const mx = Math.max(...vals.map(v => Math.abs(v)), 1);
  const n = vals.length || 1, bw = w / n, mid = h / 2;
  const rects = vals.map((v, i) => {
    const bh = Math.max(1.5, Math.abs(v) / mx * (mid - 2));
    const y = v >= 0 ? mid - bh : mid;
    const dt = (dates[i] || "").slice(5).replace("-", "/");
    return `<rect x="${(i * bw + 2).toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(2, bw - 4).toFixed(1)}" height="${bh.toFixed(1)}" fill="${v >= 0 ? "var(--up)" : "var(--down)"}" rx="1"><title>${dt}　${v > 0 ? "+" : ""}${v.toLocaleString()} 張</title></rect>`;
  }).join("");
  return `<svg class="inst-bars" height="${h}" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <line x1="0" y1="${mid}" x2="${w}" y2="${mid}" stroke="var(--border)"/>${rects}</svg>`;
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

// 大盤法人/資券的近兩週趨勢柱狀圖（trendSVG / trendBlock / #market-trend）2026-07-17 整組移除：
// 兩張圖（三大法人買賣超、融資增減）看下來都不如上方的數字表好讀。函式沒別人叫 → 一起清掉，
// 免得留成沒人用的死碼。要復原去 git（commit 前一版）。
// 資料端刻意不動：history_market 每日照存、build_market_trend 照產 market_trend.json，
// 法人數列留著給之後的用途。

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
    const trs = rows.map((r, i) => {
      const lots = who === "f" ? r.f_lots : r.t_lots;
      const val = who === "f" ? r.f_value : r.t_value;
      const stk = who === "f" ? r.f_streak : r.t_streak;
      return `<tr><td>${i+1}. ${r.name} <span class="sub">${r.code}・${r.industry}</span>${streakBadge(stk)}</td>
        <td class="${cls(lots)}">${lots > 0 ? "+" : ""}${lots.toLocaleString()}</td>
        <td class="${cls(val)}">${(Math.abs(val)/1e8).toFixed(1)}億</td>
        <td>${r.close}</td></tr>`;
    });
    const N = 6;   // Top 15 全渲染，先露 6 名（四張表 ×15 列 = 這區 1269px 的來源）
    const body = foldSlice(trs, N, h => h.replace("<tr>", '<tr class="foldx">'));
    return `<div>${foldWrap(
      `<table><tr><th>${title}</th><th>張數</th><th>估金額</th><th>收盤</th></tr>${body}</table>`,
      trs.length, N, "名")}</div>`;
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
    const trs = rows.map(r => `<tr>
      <td>${r.name} <span class="sub">${r.n}檔</span></td>
      <td class="${cls(r.f_val)}">${sign(r.f_val)}億${stk(r.f_streak)}</td>
      <td class="${cls(r.t_val)}">${sign(r.t_val)}億${stk(r.t_streak)}</td>
      <td class="sub">${r.top.map(t => `${t.name}${sign(t.val)}`).join("、")}</td></tr>`);
    const N = 5;
    const body = foldSlice(trs, N, h => h.replace("<tr>", '<tr class="foldx">'));
    return `<div>${foldWrap(
      `<table><tr><th>${title}</th><th>外資</th><th>投信</th><th>主要個股(億)</th></tr>${body}</table>`,
      trs.length, N, "族群")}</div>`;
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
  el.innerHTML = `<div style="max-height:460px;overflow:auto"><table class="sticky-head" style="min-width:700px">
    <thead><tr><th>個股</th><th>最後買進日</th><th data-dir="asc">除息日</th><th>類型</th><th>本次現金</th><th>殖利率</th><th>現價</th></tr></thead>
    <tbody>${body}</tbody></table></div>`;
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
  </div>
  <div class="ta-filter">技術狀態篩選：
    <button onclick="taList('above_year')">站上年線</button>
    <button onclick="taList('lose_year')">跌破年線</button>
    <button onclick="taList('vol_spike')">今日爆量</button>
    <button onclick="taList('ma_bull')">多頭排列</button>
    <button onclick="taList('ma_bear')">空頭排列</button>
    <span class="sub">技術狀態描述、非買賣建議</span>
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
  const cards = items.map(r => `
    <div class="rev-card" data-code="${r.code}" title="${fundLine(r.code) || "點擊開 Yahoo 股市"}">
      <b>${r.name}</b> <span class="sub">${r.code}${r.industry ? "・" + r.industry : ""}</span><br>
      營收 <b>${r.rev_yi}</b> 億　<span class="up">YoY +${r.yoy}%</span>${r.mom != null ? `　<span class="sub">MoM ${r.mom > 0 ? "+" : ""}${r.mom}%</span>` : ""}<br>
      <span class="${cls(r.pct)}">${r.close}（${sign(r.pct)}%）</span>
    </div>`);
  const N = 8;
  el.innerHTML = foldWrap(
    `<div class="rev-cards">${foldSlice(cards, N, h => h.replace('class="rev-card"', 'class="rev-card foldx"'))}</div>`,
    cards.length, N, "檔");
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
        <div class="sr-top">
          <b>${r[1]}</b><span class="sub">${r[0]}${r[2] ? "・" + r[2] : ""}</span>
          <span class="${cls(r[4])}" style="margin-left:auto">${r[3]}（${sign(r[4])}%）</span>
          <button class="star ${wlHas(r[0]) ? "on" : ""}" data-code="${r[0]}" onclick="event.stopPropagation();wlToggle('${r[0]}')">★</button>
        </div>${badges ? `<div class="sr-tags">${badges}</div>` : ""}</div>`;
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
    // 焦點頁藏著時量不到尺寸（全 0）→ 一顯示回來就重算左卡高度
    if (id === "focus") syncChangesHeight();
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
    # 註：market_trend 刻意不進這包。趨勢柱狀圖 2026-07-17 拿掉後頁面沒人讀它，
    # 嵌進去只是白帶一份沒用的 payload；build_market_trend 仍照產 data/market_trend.json。
    data = {name: read_json(name) for name in
            ("indices", "market", "heatmap", "rank", "inst_rank", "topics_view", "mops",
             "tdcc", "chains_view", "flow", "fundamentals", "news", "breadth", "revenue_hl",
             "news_radar", "topic_discover", "changes", "dividend", "valuation")}

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

    # 日期回看：history 快照複製進 docs/（Pages 只 serve docs/），並嵌可選日期清單。
    # data/history 是永久 archive（不砍）；docs/ 只放最近 DOCS_HISTORY_KEEP 支——
    # 否則 docs 與內嵌的 history_dates 會隨累積無限膨脹。
    import shutil
    hist_src = DATA_DIR / "history"
    hist_dst = DOCS_DIR / "history"
    dates = []
    if hist_src.exists():
        hist_dst.mkdir(parents=True, exist_ok=True)
        keep = sorted(hist_src.glob("????-??-??.json"))[-DOCS_HISTORY_KEEP:]
        keep_names = {f.name for f in keep}
        for f in keep:
            shutil.copy2(f, hist_dst / f.name)
            dates.append(f.stem)
        for old in hist_dst.glob("????-??-??.json"):   # 清掉 docs 內超出保留範圍的舊快照
            if old.name not in keep_names:
                old.unlink()
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

    # 技術面 → docs/ta.json（個股面板 + 技術狀態篩選；lazy fetch 單檔，別內嵌撐爆頁面）
    ta = read_json("ta")
    if ta.get("ok"):
        DOCS_DIR.mkdir(parents=True, exist_ok=True)
        (DOCS_DIR / "ta.json").write_text(
            json.dumps(ta, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n_ta = len(ta["data"].get("stocks", {}))
        print(f"[OK ] docs/ta.json（{n_ta} 檔）")
    data["ta_meta"] = {"ok": ta.get("ok", False), "data_date": ta.get("data_date"),
                       "note": ta["data"].get("note") if ta.get("ok") else None}

    # 布林通道圖的收盤序列 → docs/closes80.json（lazy fetch，只在點開個股時抓）
    c80 = read_json("closes80")
    if c80.get("ok"):
        (DOCS_DIR / "closes80.json").write_text(
            json.dumps(c80, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"[OK ] docs/closes80.json（{len(c80['data'].get('stocks', {}))} 檔）")

    # 基本面全量內嵌（個股面板要查任意個股；只留面板用欄位，gzip 後負擔小）
    fund = data["fundamentals"]
    if fund.get("ok"):
        keep = ("eps", "gm", "om", "yield_pct", "debt_pct", "yq", "div_cash")
        fund["data"]["stocks"] = {
            c: {k: f[k] for k in keep if f.get(k) is not None}
            for c, f in fund["data"]["stocks"].items()}
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BUILT_AT__", tw_now().strftime("%Y-%m-%d %H:%M")))
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"[OK ] docs/index.html ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
