"""Market and internal indicator ingestion with explicit provenance and durable cache."""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import yfinance as yf

_logger = logging.getLogger(__name__)
_DAILY_MARKET_DATA = {}
_scheduler_thread = None
_scheduler_lock = threading.Lock()

INDICATOR_KEYS = {
    "RBC": "公司_RBC_資本適足率",
    "INDUSTRY_FYP": "同業_FYP_平均成長率",
    "COMPANY_FYP": "本公司_FYP_成長率",
    "CLAIMS_MOM": "醫療險理賠通報頻率_MoM",
    "CPI": "市場通膨指數 (CPI)",
    "CPI_BASE": "預算基準通膨 (CPI Base)",
    "MEDICAL_INDEX": "醫療公證費用指數 (Medical Index)",
    "MEDICAL_BASE": "預算基準醫療指數 (Medical Base)",
}
DEMO_VALUES = {
    "RBC": (245.0, "季度核定申報示範值"),
    "INDUSTRY_FYP": (0.045, "同業 FYP 月報示範值"),
    "COMPANY_FYP": (0.038, "本公司 FYP 月報示範值"),
    "CLAIMS_MOM": (0.021, "理賠月增示範值"),
    "CPI": (105.2, "CPI 示範值"),
    "CPI_BASE": (100.0, "年度 CPI 基準示範值"),
    "MEDICAL_INDEX": (107.0, "醫療指數示範值"),
    "MEDICAL_BASE": (100.0, "年度醫療指數基準示範值"),
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _cache_path():
    configured = os.environ.get("MARKET_CACHE_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "instance" / "market_data_cache.json"


def _load_cache():
    path = _cache_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}


def _save_cache(data):
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    except OSError:
        # The app still serves the in-memory snapshot; the metadata exposes fallback use.
        pass


def wrap_market_data(value, source="System", is_cached=False, fetch_time=None, data_type="static_simulation", note=""):
    return {
        "value": value,
        "source": source,
        "fetch_time": fetch_time or _utc_now(),
        "is_cached": bool(is_cached),
        "data_type": data_type,
        "note": note,
    }


def _last_close(symbol):
    for attempt in range(3):
        try:
            history = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=False, timeout=8)
            if history.empty or history["Close"].dropna().empty:
                raise ValueError(f"Yahoo 暫時未回傳 {symbol} 的有效日收盤資料")
            closes = history["Close"].dropna()
            value = float(closes.iloc[-1])
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{symbol} 回傳的日收盤數值無效")
            stamp = closes.index[-1].to_pydatetime()
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return value, stamp.astimezone(timezone.utc).isoformat(timespec="seconds")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)


def _cached_or_unavailable(key, cache, fallback, source, note):
    old = cache.get(key)
    if isinstance(old, dict) and old.get("value") is not None:
        return wrap_market_data(
            old["value"], f"{source} (持久快取)", True,
            old.get("fetch_time", "無可用資料時間"), old.get("data_type", "realtime_api"), note,
        )
    return wrap_market_data(
        fallback, f"{source} (預設備援，非實測)", True, "無成功抓取紀錄",
        "unavailable_fallback", note,
    )


def _fetch_internal_indicators(cache):
    url = os.environ.get("INTERNAL_MARKET_API_URL", "").strip()
    token = os.environ.get("INTERNAL_MARKET_API_TOKEN", "").strip()
    if not url:
        return {
            INDICATOR_KEYS[key]: wrap_market_data(
                value, "程式內示範常數", False, "非實測資料", "static_simulation", note
            )
            for key, (value, note) in DEMO_VALUES.items()
        }

    try:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = Request(url, headers=headers, method="GET")
        with urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("內部指標 API 必須回傳 JSON object")
        out = {}
        global_stamp = payload.get("updated_at")
        for external_key, app_key in INDICATOR_KEYS.items():
            raw = payload.get(external_key)
            if isinstance(raw, dict):
                value = raw.get("value")
                source = raw.get("source", "企業內部 API")
                stamp = raw.get("fetch_time", global_stamp)
            else:
                value, source, stamp = raw, "企業內部 API", global_stamp
            if value is None:
                raise ValueError(f"內部 API 缺少 {external_key}")
            if stamp is None:
                raise ValueError(f"內部 API 缺少 {external_key} 的 ISO-8601 資料時間")
            value = float(value)
            if not math.isfinite(value):
                raise ValueError(f"內部 API 的 {external_key} 不是有限數字")
            if external_key in {"RBC", "CPI", "CPI_BASE", "MEDICAL_INDEX", "MEDICAL_BASE"} and value <= 0:
                raise ValueError(f"內部 API 的 {external_key} 必須大於零")
            out[app_key] = wrap_market_data(value, source, False, stamp, "realtime_api", "企業 API 回傳")
        return out
    except Exception as exc:
        old = cache.get("internal", {})
        out = {}
        for key, app_key in INDICATOR_KEYS.items():
            previous = old.get(app_key) if isinstance(old, dict) else None
            if previous:
                out[app_key] = wrap_market_data(
                    previous.get("value"), previous.get("source", "企業內部 API"), True,
                    previous.get("fetch_time", "無可用資料時間"), "realtime_api",
                    f"內部 API 失敗，使用持久快取：{str(exc)[:100]}",
                )
            else:
                demo, note = DEMO_VALUES[key]
                out[app_key] = wrap_market_data(
                    demo, "預設備援 (非實測)", True, "無成功抓取紀錄",
                    "unavailable_fallback", f"內部 API 失敗，未有有效快取：{str(exc)[:100]}；{note}",
                )
        return out


def update_market_data_job():
    global _DAILY_MARKET_DATA
    cache = _load_cache()
    now = _utc_now()
    values = {}

    for key, ticker, fallback in (
        ("金融市場波動 (VIX)", "^VIX", 18.5),
        ("USD_TWD_Spot", "USDTWD=X", 32.15),
        ("USD_TWD_US_10Y", "^TNX", 4.0),
    ):
        try:
            value, market_time = _last_close(ticker)
            if value <= 0:
                raise ValueError("回傳值必須大於零")
            values[key] = wrap_market_data(
                round(value, 3), f"Yahoo Finance {ticker} 最近可用日收盤",
                False, market_time, "realtime_api", "最近五個交易日資料中的最後一筆日收盤，不是盤中即時報價",
            )
        except Exception as exc:
            _logger.warning("Market data fetch failed for %s after 3 attempts", ticker, exc_info=True)
            values[key] = _cached_or_unavailable(
                key, cache, fallback, f"Yahoo Finance {ticker}",
                f"本次抓取已嘗試 3 次。原因：{str(exc)[:100]}",
            )

    us_yield = float(values["USD_TWD_US_10Y"]["value"]) / 100.0
    tw_yield = float(os.environ.get("TWD_ANNUAL_RATE", "0.01875"))
    spot = float(values["USD_TWD_Spot"]["value"])
    try:
        if values["USD_TWD_Spot"]["data_type"] == "unavailable_fallback" or values["USD_TWD_US_10Y"]["data_type"] == "unavailable_fallback":
            raise ValueError("推算所需輸入不是有效抓取資料")
        forward = spot * (1 + tw_yield) / (1 + us_yield)
        values["USD_TWD_Forward_1Y"] = wrap_market_data(
            round(forward, 3), "利率平價估算模型", values["USD_TWD_Spot"]["is_cached"] or values["USD_TWD_US_10Y"]["is_cached"],
            now, "derived_model", f"使用最近可用美國 10 年期日收盤及設定台幣年利率 {tw_yield:.4%}；僅為示範估算，非市場遠期報價",
        )
    except Exception as exc:
        values["USD_TWD_Forward_1Y"] = _cached_or_unavailable(
            "USD_TWD_Forward_1Y", cache, round(spot - 0.75, 3), "遠期匯率模型",
            f"推算失敗：{str(exc)[:100]}",
        )
        values["USD_TWD_Forward_1Y"]["data_type"] = "unavailable_fallback"

    values.update(_fetch_internal_indicators(cache))
    _DAILY_MARKET_DATA = values
    cache.update({key: val for key, val in values.items() if not val.get("is_cached") and val.get("data_type") != "static_simulation"})
    cache["internal"] = {
        key: val for key, val in values.items()
        if key in INDICATOR_KEYS.values() and val.get("data_type") == "realtime_api"
    }
    cache["updated_at"] = now
    _save_cache(cache)


def init_scheduler():
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        def run_loop():
            while True:
                try:
                    update_market_data_job()
                    retry_needed = any(
                        item.get("is_cached") or item.get("data_type") == "unavailable_fallback"
                        for item in get_market_data().values()
                    )
                    delay = 60 if retry_needed else 30 * 60
                except Exception:
                    _logger.exception("Market data refresh failed; retrying in 1 minute")
                    delay = 60
                time.sleep(delay)

        _scheduler_thread = threading.Thread(target=run_loop, daemon=True, name="market-data-scheduler")
        _scheduler_thread.start()


def get_market_data():
    return dict(_DAILY_MARKET_DATA)
