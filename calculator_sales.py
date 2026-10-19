import yfinance as yf

class SalesDepartmentCalculator:
  def __init__(self):
    self.department_name = '業務部門'

  def fetch_sales_market_data(self):
    data = {}
    try:
      us10y = yf.Ticker('^TNX')
      us10y_df = us10y.history(period='1d')
      if not us10y_df.empty:
        us_rate = float(us10y_df['Close'].iloc[-1]) / 10
        tw_rate = 1.875
        data['市場利率(台灣)'] = tw_rate
        data['台美利差'] = round(us_rate - tw_rate, 2)
      else:
        data['市場利率(台灣)'] = 1.875
        data['台美利差'] = -2.25
    except Exception:
      data['市場利率(台灣)'] = 1.875
      data['台美利差'] = -2.25

    data['通膨率CPI'] = 2.15
    data['FYP增長率'] = 6.80
    data['市場銷售情況'] = '熱絡成長 (Active)'
    return data

def calculate_sales_department_budget(user_inputs, market_data):
  calc = SalesDepartmentCalculator()
  internal_data = user_inputs.get('update_data', {})

  if not market_data:
    market_data = calc.fetch_sales_market_data()

  fyp_growth = market_data.get('FYP增長率', 5.0)
  spread = market_data.get('台美利差', -2.0)
  sales_multiplier = max(1.0, 1.0 + (fyp_growth - 5.0) / 40.0 + max(0, spread / 150.0))

  contest_bonus = internal_data.get('業務競賽獎金與激勵活動支出', {}).get('amount', 12000000)
  training_fee = internal_data.get('業務營運培訓與通訊運營費用', {}).get('amount', 8000000)
  marketing_fee = internal_data.get('業務通路常態行銷與推廣費用', {}).get('amount', 20000000)

  base_budget = float(user_inputs.get('base_budget', contest_bonus + training_fee + marketing_fee))
  growth_rate = float(user_inputs.get('growth_rate', 0.08))

  adjusted_growth = growth_rate * sales_multiplier
  projected_budget = round(base_budget * (1 + adjusted_growth), 2)
  sales_score = round(min(100.0, max(0.0, (sales_multiplier - 1.0) * 200 + 40)), 2)
  warning_level = '🔴 紅燈 (保單熱絡激進擴張)' if sales_score > 75 else ('🟡 黃燈 (穩健成長)' if sales_score > 50 else '🟢 綠燈 (常態營運)')

  summary_dict = {k: v['amount'] for k, v in internal_data.items()}

  return {
      'department': '業務部門',
      'warning_score': sales_score,
      'warning_level': warning_level,
      'internal_data_summary': summary_dict,
      'internal_data_full': internal_data,
      'base_budget': base_budget,
      'original_growth_rate': growth_rate,       # 補上
      'adjusted_growth_rate': adjusted_growth,   # 補上
      'projected_budget': projected_budget,
      'recommendation': '壽險公會統計顯示 FYP 表現強勢，彈性預算已自動調高前線業務佣金與行銷預算。',
      'market_snapshot': market_data,
  }