"""Fact-first executive report: the model may add qualitative advice only."""
from __future__ import annotations

import re


HEADINGS = (
    "【預算執行狀態與使用率分析】",
    "【超支與進度落後警報成因】",
    "【歷史比較與資料完整性檢視】",
    "【CFO 管理建議與下階段調控措施】",
)


def _money(value):
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "資料缺漏"


def _rate(value):
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "無法計算"


def _facts(dept_name, results, triggers, is_global):
    lines = []
    if is_global and isinstance(results, dict):
        for name, data in results.items():
            if not isinstance(data, dict):
                continue
            budget, forecast = data.get("B"), data.get("Forecast")
            actual = data.get("A")
            variance = None if budget is None or forecast is None else forecast - budget
            rate = None if not budget else variance / budget
            lines.append(
                f"{name}：年度預算 {_money(budget)} TWD；實際 {_money(actual)} TWD；"
                f"預測終值 {_money(forecast)} TWD；預測差異 {_money(variance)} TWD；差異率 {_rate(rate)}；"
                f"歷史 {_safe_text(data.get('H_display', '未提供'))}。"
            )
    elif isinstance(results, (list, tuple)):
        for row in results:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"{_safe_text(row.get('item_name', '未命名科目'))}：預算 {_money(row.get('B'))} TWD；"
                f"實際 {_money(row.get('A'))} TWD；預測終值 {_money(row.get('final_forecast'))} TWD；"
                f"差異 {_money(row.get('diff'))} TWD；差異率 {_rate(row.get('diff_rate'))}；"
                f"燈號 {_safe_text(row.get('light', '未知'))}；歷史 {_money(row.get('H')) if row.get('H') is not None else '無歷史資料'}。"
            )
    trigger_text = "；".join(_safe_text(item) for item in (triggers or [])) or "本期沒有觸發規則警示。"
    return "\n".join(lines) or f"{dept_name}：目前沒有可用預算列。", trigger_text


def _safe_text(value):
    return str(value).replace("\r", " ").replace("\n", " ")[:240]


def _qualitative_advice(dept_name, facts, triggers, market_data):
    """Ask the local model for a short narrative with no numeric claims."""
    try:
        import openai

        client = openai.OpenAI(
            base_url="http://localhost:11434/v1", api_key="ollama", timeout=20.0
        )
        response = client.chat.completions.create(
            model="llama3",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是保險公司財務管理顧問。只寫繁體中文的質性管理建議，最多四句。"
                        "不可輸出任何數字、百分比、金額、日期、段落標題或新事實。"
                        "只能依照提供的警示與指標狀態提出可執行的人工覆核建議。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"分析單位：{dept_name}\n資料摘要：{facts}\n觸發警示：{triggers}\n市場資料狀態：{market_data}",
                },
            ],
            temperature=0,
            max_tokens=350,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text or re.search(r"\d|[%％]|[零〇一二三四五六七八九十百千萬亿億兆兩壹貳參肆伍陸柒捌玖拾佰仟]", text) or any(h in text for h in HEADINGS):
            return None
        return text[:1200]
    except Exception:
        return None


def generate_executive_budget_report(dept_name, results_summary, triggers, market_data, is_global=False):
    facts, trigger_text = _facts(dept_name, results_summary, triggers, is_global)
    advice = _qualitative_advice(dept_name, facts, trigger_text, market_data)
    if not advice:
        advice = "依燈號及來源狀態逐項覆核預算假設；市場資料或歷史資料不完整時，先向資料責任單位確認，再調整資源配置。"

    history_notices = []
    if is_global and isinstance(results_summary, dict):
        for name, data in results_summary.items():
            if isinstance(data, dict) and data.get("H_display") in {"缺漏無資料"}:
                history_notices.append(f"{name}：無可用歷史資料。")
            elif isinstance(data, dict) and "部分缺漏" in str(data.get("H_display", "")):
                history_notices.append(f"{name}：歷史資料部分缺漏，僅以可用科目加總，不具完整年對年可比性。")
    elif isinstance(results_summary, (list, tuple)):
        missing = [row for row in results_summary if isinstance(row, dict) and row.get("H") is None]
        if missing:
            history_notices.append(f"有 {len(missing)} 個科目沒有歷史資料，歷史對照不完整。")
    if not history_notices:
        history_notices.append("未提供歷史缺漏狀態；請勿將缺值視為零支出。")

    return "\n\n".join(
        [
            f"**{HEADINGS[0]}**\n{facts}",
            f"**{HEADINGS[1]}**\n{trigger_text}",
            f"**{HEADINGS[2]}**\n" + " ".join(history_notices),
            f"**{HEADINGS[3]}**\n{advice}",
        ]
    )
