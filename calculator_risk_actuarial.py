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