"""Budget formulas. All calculator inputs and outputs are TWD reporting currency."""
from __future__ import annotations

from math import isfinite


def convert_to_reporting_currency(value, currency: str, rate: float) -> float:
    """Convert a source-currency amount to the management-reporting currency (TWD)."""
    if value is None:
        raise ValueError("金額不可為空")
    amount = float(value)
    fx = float(rate)
    if not isfinite(amount) or not isfinite(fx) or fx <= 0:
        raise ValueError("金額或匯率不是有效有限數值")
    code = str(currency).upper().strip()
    if code == "TWD":
        return amount
    if code != "USD":
        raise ValueError(f"不支援的幣別：{code}")
    return amount * fx


def apply_market_context(
    dept_id: str,
    category: str,
    F0_orig: float,
    index_ratio: float,
    a_trans: float,
    currency: str = "TWD",
    locked_ratio: float = 0.0,
    fx_spot: float = 32.0,
    fx_base: float = 31.0,
) -> float:
    """Apply eligible cost-index transmission and return remaining forecast in TWD.

    `F0_orig` is an original-currency remaining-period forecast. Locked USD exposure
    uses the configured budget/hedge reference rate; unhedged exposure uses spot.
    """
    f0, ratio, transmission = float(F0_orig), float(index_ratio), float(a_trans)
    locked, spot, base = float(locked_ratio), float(fx_spot), float(fx_base)
    vals = (f0, ratio, transmission, locked, spot, base)
    if not all(isfinite(x) for x in vals):
        raise ValueError("市場調整參數必須為有效有限數值")
    if f0 < 0 or not 0 <= transmission <= 1 or not 0 <= locked <= 1:
        raise ValueError("F0 不可為負數，傳導係數及避險比例須介於 0 與 1")
    if spot <= 0 or base <= 0:
        raise ValueError("匯率必須大於 0")

    adjusted = f0
    if dept_id == "support" and category in {"行政耗材", "軟硬體維護"}:
        adjusted *= 1 + (ratio - 1) * transmission
    elif dept_id == "underwriting_claims" and category == "公證外包":
        adjusted *= 1 + (ratio - 1) * transmission

    code = str(currency).upper().strip()
    if code == "TWD":
        return adjusted
    if code != "USD":
        raise ValueError(f"不支援的幣別：{code}")
    return adjusted * locked * base + adjusted * (1 - locked) * spot


def evaluate_traffic_light(B_annual, B_period, A, F_x, D, is_schedule):
    """Return (light, variance_rate, forecast_total, variance), all money in TWD."""
    values = (B_annual, B_period, A, F_x, D)
    if any(value is None for value in values):
        return "⚪ 灰色未知 (資料缺漏)", "n.a.", None, None
    B_annual, B_period, A, F_x, D = map(float, values)
    if not all(isfinite(x) for x in (B_annual, B_period, A, F_x, D)):
        return "⚪ 灰色未知 (數值無效)", "n.a.", None, None
    if min(B_annual, B_period, A, F_x, D) < 0:
        return "⚪ 灰色未知 (數值不得為負)", "n.a.", None, None

    forecast = A + F_x + D
    variance = forecast - B_annual
    if B_annual == 0:
        if forecast > 0:
            return "🔴 紅色警戒 (未編預算新增支出)", "n.a.", forecast, variance
        return "🟢 綠色安全", "n.a.", forecast, variance

    rate = variance / B_annual
    if rate >= 0.10:
        return "🔴 紅色警戒 (超支 >= 10%)", rate, forecast, variance
    if is_schedule:
        if B_period <= 0:
            return "⚪ 灰色未知 (缺乏同期預算)", rate, forecast, variance
        if max(0.0, B_period - A) >= B_period * 0.10:
            return "🔵 進度落後 (未執行額 >= 10%)", rate, forecast, variance
    if rate > 0:
        return "🟡 黃色注意 (溫和超支)", rate, forecast, variance
    return "🟢 綠色安全", rate, forecast, variance
