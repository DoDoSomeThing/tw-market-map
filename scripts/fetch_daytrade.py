# fetch_daytrade.py — 個股當沖比率（TWSE TWTB4U 當日沖銷交易，零 API key）
# 當沖比 = 當日沖銷交易成交股數 ÷ 該股總成交股數。高＝隔日沖/投機熱。
# 僅上市（TPEx 為另一端點，暫不含）→ data/daytrade.json。
from __future__ import annotations

from tw_common import (http_get_json, parse_num, read_json, roc_to_iso,
                       tw_today, write_error, write_json, ymd_to_iso)

TWTB4U_URL = "https://www.twse.com.tw/exchangeReport/TWTB4U?date={d}&response=json&selectType=All"
SOURCE = "TWSE TWTB4U（當日沖銷交易，上市）"
TOP = 30
MIN_VALUE = 0.5e8   # 成交值 ≥ 5000 萬


def keep_previous(reason: str) -> None:
    """來源失敗 → 保留前次快照並標註原因，不要用錯誤信封蓋掉好資料。

    2026-08-28 事故：TWSE WAF 間歇對 GitHub Actions 回 307 擋頁，本模組直接
    write_error → daytrade.json 從完整快照變成 ok:false 空殼，面板整區消失。
    當沖比是「當日快照」不是累積值，留前一日的數字＋原本的 data_date 即可，
    面板端靠 data_date 判斷交易日齡會自己標 ⚠️，不會把舊值裝成新鮮。
    真的沒有前次可留（首跑）才寫錯誤信封。
    """
    prev = read_json("daytrade")
    if not prev.get("ok") or not (prev.get("data") or {}).get("by_code"):
        write_error("daytrade", SOURCE, reason)
        return
    write_json("daytrade", prev["data"], data_date=prev.get("data_date"), source=SOURCE,
               error=f"{reason}；沿用 {prev.get('data_date')} 快照（來源失敗，寧可標舊也不裝新鮮）")


def twtb4u_cols(fields: list) -> tuple[int | None, int | None]:
    """回傳 (證券名稱欄, 當沖成交股數欄) 的索引；找不到給 None。"""
    i_name = i_shares = None
    for i, f in enumerate(fields):
        f = (f or "").strip()
        if f == "證券名稱":
            i_name = i
        elif "成交股數" in f and i_shares is None:
            i_shares = i
    return i_name, i_shares


def main() -> None:
    daily = read_json("daily_all")
    # 用 daily 的資料日對齊；抓不到就用今天
    dd = (daily.get("data_date") or "").replace("-", "") or tw_today().strftime("%Y%m%d")
    try:
        j = http_get_json(TWTB4U_URL.format(d=dd), timeout=60)
    except Exception as e:                      # noqa: BLE001 — WAF/連線失敗都算來源掛
        keep_previous(f"TWTB4U 抓取失敗：{str(e)[:200]}")
        return
    if not j or j.get("stat") != "OK":
        keep_previous(f"回應非 OK: {(j or {}).get('stat')}")
        return

    table = None
    seen_fields = []
    for t in j.get("tables", []):
        fields = t.get("fields") or []
        if fields and fields[0] == "證券代號":
            seen_fields.append(fields)
        _, i_shares = twtb4u_cols(fields)
        if fields and fields[0] == "證券代號" and i_shares is not None and len(t.get("data") or []) > 100:
            table = t
            break
    if not table:
        keep_previous(f"找不到當沖交易表，候選欄位：{seen_fields[:3]}")
        return

    # 欄位位置用名稱查，不寫死索引：TWSE 曾在同一端點回不同欄數的版本（少了註記欄
    # 就整批 IndexError，整個模組掛掉 → 當天當沖資料靜默缺一格）。
    i_name, i_shares = twtb4u_cols(table.get("fields") or [])
    if i_shares is None:
        keep_previous(f"當沖表找不到成交股數欄，實得欄位：{table.get('fields')}")
        return

    meta = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            meta[s["code"]] = s

    rows = []
    by_code = {}    # 全量 {code: 當沖比%}：list 只有 top 30，個股面板要查任一檔都得有值
    for row in table["data"]:
        if len(row) <= i_shares:
            continue
        code = (row[0] or "").strip()
        m = meta.get(code)
        if len(code) != 4 or not code.isdigit() or not m:
            continue
        dt_shares = parse_num(row[i_shares])       # 當沖成交股數
        vol = m.get("value") and m.get("vol")
        if not dt_shares or not vol or vol <= 0:
            continue
        ratio = min(dt_shares / vol * 100, 100)   # 當沖比%
        by_code[code] = round(ratio, 1)
        # 排行榜濾小量（成交值 <5000 萬時當沖比分母小、比率容易失真）；by_code 不濾，
        # 面板顯示時另標註成交值供判讀。
        if (m.get("value") or 0) < MIN_VALUE:
            continue
        nm = (row[i_name] or "").strip() if i_name is not None and len(row) > i_name else ""
        rows.append({"code": code, "name": nm or code,
                     "industry": m.get("industry") or "", "pct": m.get("pct"),
                     "close": m.get("close"), "ratio": round(ratio, 1),
                     "value": round((m.get("value") or 0) / 1e8, 1)})

    if not rows:
        keep_previous("解析後無當沖資料")
        return

    rows.sort(key=lambda x: x["ratio"], reverse=True)
    date_iso = ymd_to_iso(str(j.get("date"))) or daily.get("data_date")
    write_json("daytrade", {"list": rows[:TOP], "by_code": by_code, "min_value": MIN_VALUE},
               data_date=date_iso, source=SOURCE)

    # 追加今日大盤當沖比進趨勢序列（歷史由 backfill_daytrade.py 種；此處每日 upsert 今天）
    _update_trend(j, date_iso)


def _update_trend(twtb_json: dict, date_iso: str | None) -> None:
    """大盤當沖比 = 全市場當沖成交股數 ÷ 大盤總成交股數（FMTQIK）；upsert 進 daytrade_trend.json。"""
    if not date_iso:
        return
    dt_total = 0.0
    for t in twtb_json.get("tables", []):
        fields = t.get("fields") or [""]
        if fields[0] != "證券代號":
            continue
        _, i_shares = twtb4u_cols(fields)
        if i_shares is None:
            continue
        for row in t.get("data", []):
            if len(row) <= i_shares:
                continue
            v = parse_num(row[i_shares])
            if v:
                dt_total += v
    ym = date_iso.replace("-", "")[:6]
    try:
        f = http_get_json(f"https://www.twse.com.tw/exchangeReport/FMTQIK?date={ym}01&response=json", timeout=40)
    except Exception as e:                      # noqa: BLE001 — 大盤量抓不到就不記這天，不要炸掉整支
        print(f"[WARN] daytrade_trend 略過 {date_iso}：FMTQIK 抓取失敗 {str(e)[:120]}")
        return
    mkt = None
    if f and f.get("stat") == "OK":
        for r in f.get("data", []):
            if roc_to_iso(r[0]) == date_iso:
                mkt = parse_num(r[1])
                break
    if not dt_total or not mkt:
        return
    ratio = round(dt_total / mkt * 100, 1)
    prev = read_json("daytrade_trend")
    series = prev["data"].get("series", []) if prev.get("ok") else []
    series = [x for x in series if x.get("date") != date_iso]
    series.append({"date": date_iso, "ratio": ratio})
    series.sort(key=lambda x: x["date"])
    write_json("daytrade_trend", {"series": series[-120:]},
               data_date=date_iso, source="TWSE TWTB4U ÷ FMTQIK（大盤當沖比）")


if __name__ == "__main__":
    main()
