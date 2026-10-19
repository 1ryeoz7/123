import yfinance as yf


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

def safe_float(value, default_value):
  """安全轉換 float 函式，防止空字串或非法字元引發當機"""
  try:
    if value is None or str(value).strip() == '':
      return default_value
    return float(value)
  except (ValueError, TypeError):
    return default_value


# 於計算函式中使用：
ics_capital_limit_usage = safe_float(
    user_inputs.get('ics_capital_limit_usage'), 70.0
)

def calculate_risk_actuarial_budget(user_inputs, market_data):
  calc = RiskActuarialCalculator()
  internal_data = user_inputs.get('update_data', {})

  if not market_data:
    market_data = calc.fetch_risk_market_data()

  # 1. 取得外部爬蟲指標
  vix_val = market_data.get('金融市場波動(VIX)', 15.0)
  esg_index = market_data.get('ESG與氣候數據指數', 100.0)

  # 2. 雙向指標與複合加權運算 (結合市場波動與合規壓力)
  volatility_pressure = max(1.0, vix_val / 18.0)
  esg_pressure = max(1.0, esg_index / 100.0)
  risk_multiplier = round(volatility_pressure * esg_pressure, 3)

  # 3. 取得內部預算項目金額
  software_fee = (
      internal_data.get('外部精算模型軟體授權與資料庫訂閱費', {})
      .get('amount', 15000000)
  )
  consultant_fee = (
      internal_data.get('外部顧問費與風管專案外包費用', {})
      .get('amount', 12000000)
  )
  it_maint = (
      internal_data.get('風險管理系統維護與外包開發費用', {})
      .get('amount', 10000000)
  )

  base_budget = float(
      user_inputs.get('base_budget', software_fee + consultant_fee + it_maint)
  )
  growth_rate = float(user_inputs.get('growth_rate', 0.05))

  # 內部 1: 精算負債與資金成本曲線壓力 % (預設 3.2%)（最後正式導入企業內部環境時要改成外部讀取連結）
  actuarial_liability_cost_rate = float(
      user_inputs.get('actuarial_liability_cost_rate', 3.2)
  )
  # 內部 2: 監理資本 (ICS/IFRS17) 與投資限額耗用率 % (預設 70%)
  ics_capital_limit_usage = float(
      user_inputs.get('ics_capital_limit_usage', 70.0)
  )
  # 內部 3: 外部精算軟體授權/資料庫訂閱/顧問費變異率 % (預設 8%)
  consulting_software_budget_var = float(
      user_inputs.get('consulting_software_budget_var', 8.0)
  )
  # 內部 4: 系統維護與外包開發費用超支率 % (預設 5%)
  system_outsourcing_cost = float(
      user_inputs.get('system_outsourcing_cost', 5.0)
  )

  # 內部綜合風險分數標準化
  internal_risk_score = min(
      100.0,
      max(
          0.0,
          (ics_capital_limit_usage * 0.4)
          + (consulting_software_budget_var * 2.5 * 0.3)
          + (system_outsourcing_cost * 2.0 * 0.3),
      ),
  )

  # ==========================================
  # 3. 雙向交叉加權計算：預警分數 (Warning Score, 0-100)
  # ==========================================
  # 權重：外部市場與氣候風險 45% + 內部資本合規與系統顧問開支 55%
  warning_score = round(
      0.45 * market_stress_score + 0.55 * internal_risk_score, 1
  )

  # ==========================================
  # 4. 預測價值：AI 預測當市場大跌時是否需追加外部系統/顧問預算
  # ==========================================
  if warning_score >= 75:
    status_light = '🔴 警戒紅燈 (Critical Risk)'
    budget_action = '【建議追加預算】外部市場暴跌且接軌 ICS/IFRS17 資本耗用吃緊，自動追加外部風管算力與專業顧問預算 +25%。'
    risk_multiplier = 1.25
  elif warning_score >= 60:
    status_light = '🟡 黃色預警 (Warning)'
    budget_action = '【預警監控】外部波動與精算/外包開發費用偏高，啟動 10% 彈性預算預留並密切追蹤。'
    risk_multiplier = 1.10
  else:
    status_light = '🟢 綠色安全 (Normal)'
    budget_action = (
        '【常態營運】雙向指標平穩，無須追加外部系統或顧問預算，按原計畫執行。'
    )
    risk_multiplier = 1.00

  # 最終預算計算
  adjusted_growth = growth_rate * risk_multiplier
  # 4. 計算調整後成長率與預測預算
  adjusted_growth = round(growth_rate * risk_multiplier, 4)
  projected_budget = round(base_budget * (1 + adjusted_growth), 2)

  # 5. 計算 0–100 分的複合預警分數與燈號判定
  risk_score = round(
      min(100.0, max(0.0, (risk_multiplier - 1.0) * 150 + 35)), 2
  )
  if risk_score > 75:
    warning_level = '🔴 紅燈 (市場大跌與合規高風險)'
  elif risk_score > 50:
    warning_level = '🟡 黃燈 (波動警戒)'
  else:
    warning_level = '🟢 綠燈 (風險平穩)'

  # 6. 整理內部總覽摘要
  summary_dict = {k: v['amount'] for k, v in internal_data.items()}

  return {
      'department': '風險管理部門',
      'warning_score': risk_score,
      'warning_level': warning_level,
      'internal_data_summary': summary_dict,
      'internal_data_full': internal_data,
      'base_budget': base_budget,
      'original_growth_rate': growth_rate,
      'adjusted_growth_rate': adjusted_growth,
      'projected_budget': projected_budget,
      'recommendation': (
          '市場波動劇烈且 ESG/氣候風險升高，建議追加外部風管系統升級與風險顧問預算。'
          if risk_multiplier > 1.15
          else '市場風險指標與波動平穩，維持現行風管預算配置即可。'
      ),
      'market_snapshot': market_data,
  }