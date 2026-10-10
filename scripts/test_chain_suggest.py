#!/usr/bin/env python3
# test_chain_suggest.py — 新題材去重的回歸測試（零依賴，直接跑：python3 scripts/test_chain_suggest.py）
#
# 為什麼有這支：2026-09-16 發現同一個題材會重複開 Issue。
# 蘋果摺疊機 09/10 以詞群 `DUO|疊機|首款` 開了 #18，09/11 詞群漂成 `DUO|疊機` 又開了 #19。
# 原因是去重用「前三主詞完全比對」，詞群漂一個字就算全新候選。
# 改成主詞重疊判定後，用下面這組案例把行為釘住。
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_chain_suggestions import already_suggested, signature   # noqa: E402

# (terms, already, 期望, 說明)
CASES: list[tuple[list[str], set[str], bool, str]] = [
    # ── 本次事故本體：只記過 #18 的詞群時，#19 的漂移詞群必須被擋下來 ──
    (["DUO", "疊機"], {"DUO|疊機|首款"}, True, "詞群少一字（#19 重複開單的成因）"),
    (["DUO", "疊機", "螢幕"], {"DUO|疊機|首款"}, True, "詞群換一字"),
    (["DUO"], {"DUO|疊機|首款"}, True, "縮到剩單主詞（子集）"),
    (["DUO", "疊機", "首款"], {"DUO|疊機"}, True, "反向：舊的是子集"),

    # ── 單主詞 ──
    (["GOOGLE"], {"GOOGLE"}, True, "單主詞完全相同"),
    (["GOOGLE"], {"OCP"}, False, "單主詞不同"),

    # ── 不可誤殺：全新題材不能被既有簽章吃掉 ──
    (["CPO", "矽光子"], {"DUO|疊機|首款", "OCP"}, False, "全新題材"),
    (["高頻", "基板", "載板"], {"SEMICON|TAIWAN"}, False, "全新題材"),
    (["SEMICON", "劉揚偉"], {"SEMICON|TAIWAN"}, False, "只重疊一個主詞 → 保守視為不同"),

    # ── 邊界 ──
    ([], {"DUO|疊機"}, False, "空詞群"),
    (["DUO", "疊機"], set(), False, "狀態檔是空的"),
]


def main() -> int:
    bad = 0
    for terms, already, want, why in CASES:
        got = already_suggested(terms, already)
        if got != want:
            bad += 1
            print(f"[FAIL] {terms} vs {sorted(already)} → {got}，期望 {want}（{why}）")
        else:
            print(f"[ok  ] {terms} → {got}　{why}")

    # 舊邏輯的反證：完全比對確實擋不下 #19，證明這支測試守的是真的回歸
    if signature(["DUO", "疊機"]) in {"DUO|疊機|首款"}:
        bad += 1
        print("[FAIL] 舊的完全比對竟然擋得下 #19 → 測試前提有問題")

    print()
    print("全部通過" if bad == 0 else f"{bad} 個失敗")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
