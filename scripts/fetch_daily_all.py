# fetch_daily_all.py — 全市場日行情（上市 STOCK_DAY_ALL + 上櫃 TPEx）+ 產業分類
from __future__ import annotations

from tw_common import http_get_json, parse_num, roc_to_iso, sanity_check_pct, write_error, write_json

TWSE_ALL_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_INDUSTRY_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
TPEX_ALL_URL = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TPEX_INDUSTRY_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"

# TWSE/TPEx 產業別代碼 → 名稱（公開分類標準）
INDUSTRY_NAMES = {
    "01": "水泥", "02": "食品", "03": "塑膠", "04": "紡織", "05": "電機機械",
    "06": "電器電纜", "08": "玻璃陶瓷", "09": "造紙", "10": "鋼鐵", "11": "橡膠",
    "12": "汽車", "14": "建材營造", "15": "航運", "16": "觀光餐旅", "17": "金融保險",
    "18": "貿易百貨", "19": "綜合", "20": "其他", "21": "化學", "22": "生技醫療",
    "23": "油電燃氣", "24": "半導體", "25": "電腦週邊", "26": "光電", "27": "通信網路",
    "28": "電子零組件", "29": "電子通路", "30": "資訊服務", "31": "其他電子",
    "32": "文化創意", "33": "農業科技", "34": "電子商務", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活",
    "80": "管理股票",
}


def fetch_industry_map() -> dict[str, str]:
    """公司代號 → 產業名。上市+上櫃；抓不到的市場略過（該市場個股歸「未分類」）。"""
    m: dict[str, str] = {}
    for url in (TWSE_INDUSTRY_URL, TPEX_INDUSTRY_URL):
        try:
            rows = http_get_json(url)
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for r in rows:
            # 上市 t187ap03_L 用中文欄位；上櫃 mopsfin_t187ap03_O 用英文欄位
            code = str(r.get("公司代號") or r.get("SecuritiesCompanyCode") or "").strip()
            ind = str(r.get("產業別") or r.get("SecuritiesIndustryCode") or "").strip()
            if code and ind:
                m[code] = INDUSTRY_NAMES.get(ind, f"其他({ind})")
    return m


def parse_twse(rows: list) -> tuple[list[dict], str | None]:
    out = []
    data_date = None
    for r in rows:
        data_date = data_date or roc_to_iso(r.get("Date", ""))
        close = parse_num(r.get("ClosingPrice"))
        change = parse_num(r.get("Change"))
        value = parse_num(r.get("TradeValue"))
        if close is None or change is None or close <= 0:
            continue
        prev = close - change
        if prev <= 0:
            continue
        pct = change / prev * 100
        if not sanity_check_pct(pct):
            continue  # 疑似欄位錯/除權息異常，寧可略過
        out.append({
            "code": str(r.get("Code", "")).strip(),
            "name": str(r.get("Name", "")).strip(),
            "close": close, "pct": round(pct, 2),
            "value": value or 0.0,  # 成交金額(元)
            "market": "twse",
        })
    return out, data_date


def parse_tpex(rows: list) -> tuple[list[dict], str | None]:
    out = []
    data_date = None
    for r in rows:
        data_date = data_date or roc_to_iso(r.get("Date", ""))
        close = parse_num(r.get("Close"))
        change = parse_num(r.get("Change"))
        value = parse_num(r.get("TransactionAmount"))
        if close is None or change is None or close <= 0:
            continue
        prev = close - change
        if prev <= 0:
            continue
        pct = change / prev * 100
        if not sanity_check_pct(pct):
            continue
        out.append({
            "code": str(r.get("SecuritiesCompanyCode", "")).strip(),
            "name": str(r.get("CompanyName", "")).strip(),
            "close": close, "pct": round(pct, 2),
            "value": value or 0.0,
            "market": "tpex",
        })
    return out, data_date


def main() -> None:
    stocks: list[dict] = []
    dates: list[str] = []
    errs: list[str] = []

    try:
        twse_rows, d = parse_twse(http_get_json(TWSE_ALL_URL))
        stocks += twse_rows
        if d:
            dates.append(d)
    except Exception as e:
        errs.append(f"上市:{e}")

    try:
        tpex_rows, d = parse_tpex(http_get_json(TPEX_ALL_URL))
        stocks += tpex_rows
        if d:
            dates.append(d)
    except Exception as e:
        errs.append(f"上櫃:{e}")

    if not stocks:
        write_error("daily_all", "TWSE STOCK_DAY_ALL + TPEx quotes", "；".join(errs) or "無資料")
        return

    ind_map = fetch_industry_map()
    if not ind_map:
        errs.append("產業分類抓取失敗（個股全歸未分類）")
    n_ind = 0
    for s in stocks:
        ind = ind_map.get(s["code"])
        s["industry"] = ind  # None = ETF/權證/未分類 → heatmap 排除
        if ind:
            n_ind += 1

    # 上市/上櫃資料日不一致 = 其中一邊還沒更新 → 取較舊那天並記警告
    data_date = min(dates) if dates else None
    if len(set(dates)) > 1:
        errs.append(f"上市/上櫃資料日不一致:{sorted(set(dates))}")

    write_json("daily_all", {"stocks": stocks, "n_industry_mapped": n_ind},
               data_date=data_date,
               source="TWSE STOCK_DAY_ALL + TPEx quotes + t187ap03",
               error="；".join(errs) or None)


if __name__ == "__main__":
    main()
