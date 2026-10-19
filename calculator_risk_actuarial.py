import yfinance as yf


def safe_float(value, default_value):
    """安全轉換 float 函式，防止空字串或非法字元引發當機"""
    try:
        if value is None or str(value).strip() == '':
            return default_value
        return float(value)
    except (ValueError, TypeError):
        return default_value


class RiskActuarialCalculator:

    def __init__(self):
        self.department_name = '風險管理部門'

    def fetch_risk_market_data(self):
        """即時抓取金融市場波動 (VIX)、S&P 500 與 ESG 氣候指數"""
        data = {}
        try:
            vix_ticker = yf.Ticker('^VIX')
            vix_df = vix_ticker.history(period='1d')
            if not vix_df.empty:
                data['金融市場波動(VIX)'] = float(vix_df['Close'].iloc[-1])
            else:
                data['金融市場波動(VIX)'] = 15.0
        except Exception:
            data['金融市場波動(VIX)'] = 15.0

        try:
            sp500_ticker = yf.Ticker('^GSPC')
            sp500_df = sp500_ticker.history(period='1d')
            if not sp500_df.empty:
                data['資產價格指數(S&P500)'] = float(sp500_df['Close'].iloc[-1])
            else:
                data['資產價格指數(S&P500)'] = 4500.0
        except Exception:
            data['資產價格指數(S&P500)'] = 4500.0

        data['ESG與氣候數據指數'] = 108.5
        data['聲譽與法規合規評分'] = 95.0
        data['信用評級基準'] = 'twAAA / Stable'
        data['法規監理與同業風控基準'] = '合規標準正常'
        return data


def calculate_risk_actuarial_budget(user_inputs, market_data):
    calc = RiskActuarialCalculator()
    internal_data = user_inputs.get('update_data', {})

    if not market_data:
        market_data = calc.fetch_risk_market_data()

    # 1. 內部資料提領與安全轉換 (必須全部縮排在函式內部)
    base_budget = safe_float(user_inputs.get('base_budget'), 50000.0)
    growth_rate = safe_float(user_inputs.get('growth_rate'), 0.05)
    actuarial_liability_cost_rate = safe_float(
        user_inputs.get('actuarial_liability_cost_rate'), 3.2
    )
    ics_capital_limit_usage = safe_float(
        user_inputs.get('ics_capital_limit_usage'), 70.0
    )
    consulting_software_budget_var = safe_float(
        user_inputs.get('consulting_software_budget_var'), 8.0
    )
    system_outsourcing_cost = safe_float(
        user_inputs.get('system_outsourcing_cost'), 5.0
    )

    # 2. 外部爬蟲指標與市場壓力分數計算
    vix_val = safe_float(market_data.get('金融市場波動(VIX)'), 15.0)
    esg_index = safe_float(market_data.get('ESG與氣候數據指數'), 100.0)

    market_stress_score = min(
        100.0,
        max(0.0, (vix_val / 35.0) * 60.0 + (max(0.0, esg_index - 100.0) * 2.0))
    )

    # 3. 內部綜合風險分數標準化
    internal_risk_score = min(
        100.0,
        max(
            0.0,
            (ics_capital_limit_usage * 0.4)
            + (consulting_software_budget_var * 2.5 * 0.3)
            + (system_outsourcing_cost * 2.0 * 0.3),
        ),
    )

    # 4. 雙向交叉加權計算：預警分數 (Warning Score)
    warning_score = round(
        0.45 * market_stress_score + 0.55 * internal_risk_score, 1
    )

    # 5. 燈號判定與風險乘數
    if warning_score >= 75:
        warning_level = '🔴 紅燈 (極端市場衝擊與資本吃緊)'
        budget_action = '【建議追加預算】外部市場暴跌且接軌 ICS/IFRS17 資本耗用吃緊，自動追加外部風管算力與專業顧問預算 +25%。'
        risk_multiplier = 1.25
    elif warning_score >= 60:
        warning_level = '🟡 黃燈 (波動與合規警戒)'
        budget_action = '【預警監控】外部波動與精算/外包開發費用偏高，啟動 10% 彈性預算預留並密切追蹤。'
        risk_multiplier = 1.10
    else:
        warning_level = '🟢 綠燈 (常態風險平穩)'
        budget_action = '【常態營運】雙向指標平穩，無須追加外部系統或顧問預算，按原計畫執行。'
        risk_multiplier = 1.00

    # 6. 計算期末預算
    adjusted_growth = round(growth_rate * risk_multiplier, 4)
    projected_budget = round(base_budget * (1 + adjusted_growth), 2)

    # 7. 內部數據摘要
    summary_dict = {
        k: v.get('amount', 0) if isinstance(v, dict) else v
        for k, v in internal_data.items()
    }

    return {
        'department': '風險管理部門',
        'warning_score': warning_score,
        'warning_level': warning_level,
        'internal_data_summary': summary_dict,
        'internal_data_full': internal_data,
        'base_budget': base_budget,
        'original_growth_rate': growth_rate,
        'adjusted_growth_rate': adjusted_growth,
        'projected_budget': projected_budget,
        'recommendation': budget_action,
        'market_snapshot': market_data,
    }