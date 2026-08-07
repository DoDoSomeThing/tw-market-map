# fetch_margin.py — 個股融資餘額增減（TWSE MI_MARGN selectType=ALL，零 API key）
# 同一 TWSE 公開端點（fetch_market 用 MS 彙總；這裡用 ALL 取個股）→ data/margin.json
# 融資增減(張) = 今日餘額 − 前日餘額。僅上市（TPEx 上櫃為另一端點，暫不含）。
from __future__ import annotations

from tw_common import (col_index, http_get_json, parse_num, read_json,
                       write_error, write_json, ymd_to_iso)

MARGN_ALL_URL = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?selectType=ALL&response=json"
TOP = 30
MIN_BAL = 500   # 今日餘額 ≥500 張才列，濾極小融資標的雜訊


def margin_cols(fields: list) -> dict | None:
    """個股融資融券表 → 欄位索引（融資前日/今日餘額 + 融券今日餘額）。欄位改版回 None。

    ⚠️ 這張表的欄位名稱**會重複**：融資段與融券段都叫「買進/賣出/前日餘額/今日餘額」——
    直接用 {name: i} 建表會被後段的融券蓋掉，抓出來的「融資餘額」其實是融券餘額。
    所以用兩個唯一名稱當錨點：「現金償還」（融資段）與「現券償還」（融券段），
    只在這兩者之間找餘額欄。

    2026-08-06 實測欄序：
    代號 名稱 買進 賣出 現金償還 前日餘額 今日餘額 次一營業日限額
    買進 賣出 現券償還 前日餘額 今日餘額 次一營業日限額 資券互抵 註記
    """
    i_cash = col_index(fields, "現金償還")          # 融資段起點錨
    if i_cash is None:
        return None
    i_bond = col_index(fields, "現券償還", start=i_cash + 1)  # 融券段起點錨
    end = i_bond if i_bond is not None else len(fields)
    cols = {
        "代號": col_index(fields, "代號", "股票代號", end=i_cash),
        "名稱": col_index(fields, "名稱", "股票名稱", end=i_cash),
        "前日餘額": col_index(fields, "前日餘額", start=i_cash + 1, end=end),
        "今日餘額": col_index(fields, "今日餘額", start=i_cash + 1, end=end),
    }
    if not all(v is not None for v in cols.values()):
        return None
    # 融券今日餘額（券資比用）。找不到不算致命：融資段照舊出，券資比留 None。
    if i_bond is not None:
        cols["券今日餘額"] = col_index(fields, "今日餘額", start=i_bond + 1)
    return cols


def main() -> None:
    j = http_get_json(MARGN_ALL_URL, timeout=60)
    if not j or j.get("stat") != "OK":
        write_error("margin", "TWSE MI_MARGN ALL", f"回應非 OK: {(j or {}).get('stat')}")
        return

    # 找個股表：fields 含「代號」的那張（通常 rows ~1200+）
    table = None
    for t in j.get("tables", []):
        fields = t.get("fields") or []
        if fields and fields[0] == "代號" and len(t.get("data") or []) > 100:
            table = t
            break
    if not table:
        write_error("margin", "TWSE MI_MARGN ALL", "找不到個股融資融券表")
        return

    cols = margin_cols(table.get("fields") or [])
    if not cols:
        write_error("margin", "TWSE MI_MARGN ALL",
                    f"欄位改版，拒絕用位置硬猜：{table.get('fields')}")
        return
    i_short = cols.pop("券今日餘額", None)
    need = max([*cols.values(), i_short if i_short is not None else 0])

    daily = read_json("daily_all")
    meta = {}
    if daily.get("ok"):
        for s in daily["data"].get("stocks", []):
            meta[s["code"]] = s

    stocks = {}
    for row in table["data"]:
        if len(row) <= need:
            continue                  # 說明/合計等短列
        code = (row[cols["代號"]] or "").strip()
        if len(code) != 4 or not code.isdigit():
            continue
        prev = parse_num(row[cols["前日餘額"]])    # 融資前日餘額（張）
        today = parse_num(row[cols["今日餘額"]])   # 融資今日餘額（張）
        if prev is None or today is None:
            continue
        chg = today - prev
        short = parse_num(row[i_short]) if i_short is not None else None   # 融券今日餘額（張）
        # 券資比 = 融券餘額 ÷ 融資餘額。融資 0 時比率無意義（分母 0）→ None，不要寫 0 裝好看。
        sbr = round(short / today * 100, 2) if short is not None and today > 0 else None
        m = meta.get(code, {})
        stocks[code] = {"name": (row[cols["名稱"]] or "").strip() or code, "bal": int(today),
                        "chg": int(chg), "short": int(short) if short is not None else None,
                        "sbr": sbr, "pct": m.get("pct"), "close": m.get("close"),
                        "industry": m.get("industry") or ""}

    if not stocks:
        write_error("margin", "TWSE MI_MARGN ALL", "解析後無個股資料")
        return

    rated = [v | {"code": c} for c, v in stocks.items() if v["bal"] >= MIN_BAL]
    inc = sorted(rated, key=lambda x: x["chg"], reverse=True)[:TOP]
    dec = sorted(rated, key=lambda x: x["chg"])[:TOP]

    # 全量 by_code [融資餘額, 增減, 券資比%]（張／%）：inc/dec 只有 top 30，個股面板要查任一檔都得有值。
    # 精簡成陣列省 payload（~1200 檔約 25KB，內嵌進 index.html）。
    # 第 3 欄是後加的（2026-08-07 健診卡），舊快照只有 2 欄 → 讀取端一律用索引取值容錯。
    by_code = {c: [v["bal"], v["chg"], v["sbr"]] for c, v in stocks.items()}

    date_iso = ymd_to_iso(str(j.get("date"))) or (daily.get("data_date"))
    n_sbr = sum(1 for v in stocks.values() if v["sbr"] is not None)
    write_json("margin", {"inc": inc, "dec": dec, "by_code": by_code,
                          "n": len(stocks), "n_sbr": n_sbr, "min_bal": MIN_BAL},
               data_date=date_iso, source="TWSE MI_MARGN（個股融資餘額＋券資比，上市）")


if __name__ == "__main__":
    main()
