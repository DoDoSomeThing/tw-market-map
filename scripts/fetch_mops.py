# fetch_mops.py — 當日重大訊息（上市 TWSE openapi t187ap04_L + 上櫃 TPEx mopsfin_t187ap04_O）
# 免爬 MOPS 網頁：兩個 openapi 都是 JSON 整日彙總。TPEx 這支常滯後一天、量少，允許缺。
from __future__ import annotations

import re

from tw_common import http_get_json, roc_to_iso, write_error, write_json

TWSE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"

MAX_ITEMS = 120

# 分類標籤：由上往下第一個命中即定（澄清/自結/財務/治理/重大）
TAG_RULES = [
    ("澄清", re.compile(r"澄清|媒體報導|新聞報導|報導")),
    ("自結", re.compile(r"自結")),
    ("財務", re.compile(r"財務報告|財報|營收|盈餘|股利|除權|除息|現金增資|募集|可轉換公司債|籌資|減資")),
    ("治理", re.compile(r"董事|監察人|審計委員|股東會|經理人|總經理|財務主管|發言人|人事|更名|公司名稱|內部稽核")),
]


def classify(subject: str) -> str:
    for tag, pat in TAG_RULES:
        if pat.search(subject):
            return tag
    return "重大"


def _norm_row(row: dict) -> dict:
    """openapi 欄位 key 會混空白（TWSE '主旨 '），正規化後取值。"""
    return {str(k).replace(" ", ""): v for k, v in row.items()}


def _hhmm(t) -> str:
    """發言時間 '70003'/'183025' → '07:00'/'18:30'。"""
    s = str(t or "").strip().zfill(6)
    if not s.isdigit() or len(s) != 6:
        return "?"
    return f"{s[:2]}:{s[2:4]}"


def _parse(rows: list, market: str, code_key: str, name_key: str, date_key: str) -> list[dict]:
    out = []
    for raw in rows:
        r = _norm_row(raw)
        code = str(r.get(code_key, "")).strip()
        subject = str(r.get("主旨", "")).replace("\r\n", " ").replace("\n", " ").strip()
        d_iso = roc_to_iso(str(r.get(date_key, "")))
        if not code or not subject or not d_iso:
            continue
        out.append({
            "code": code,
            "name": str(r.get(name_key, "")).strip(),
            "date": d_iso,
            "time": _hhmm(r.get("發言時間")),
            "tag": classify(subject),
            "subject": subject,
            "market": market,
        })
    return out


def main() -> None:
    items: list[dict] = []
    errs = []
    try:
        rows = http_get_json(TWSE_URL)
        items += _parse(rows if isinstance(rows, list) else [], "twse",
                        "公司代號", "公司名稱", "發言日期")
        if not items:
            errs.append("上市 t187ap04_L 無資料")
    except Exception as e:
        errs.append(f"上市 t187ap04_L:{e}")

    try:
        rows = http_get_json(TPEX_URL)
        items += _parse(rows if isinstance(rows, list) else [], "tpex",
                        "SecuritiesCompanyCode", "CompanyName", "發言日期")
    except Exception as e:
        errs.append(f"上櫃 mopsfin_t187ap04_O:{e}")

    if not items:
        write_error("mops", "TWSE/TPEx openapi 重大訊息", "；".join(errs) or "無資料")
        return

    # 去重（openapi 原始資料同一則會出現多列）
    seen = set()
    uniq = []
    for it in items:
        key = (it["code"], it["date"], it["time"], it["subject"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    items = uniq

    # 只留最近兩個發言日（當日 + 前一晚），時間新→舊
    dates = sorted({it["date"] for it in items}, reverse=True)
    keep = set(dates[:2])
    items = [it for it in items if it["date"] in keep]
    items.sort(key=lambda it: (it["date"], it["time"]), reverse=True)
    items = items[:MAX_ITEMS]

    tags = {}
    for it in items:
        tags[it["tag"]] = tags.get(it["tag"], 0) + 1

    write_json("mops", {"items": items, "tag_counts": tags},
               data_date=dates[0], source="TWSE t187ap04_L + TPEx mopsfin_t187ap04_O",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
