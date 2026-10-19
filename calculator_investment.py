import yfinance as yf

class InvestmentDepartmentCalculator:
  def __init__(self):
    self.department_name = '投資管理部門'

  def fetch_investment_market_data(self):
    return {'市場利率(台灣)': 1.875, '台美利差': -2.25, '投資報酬率基準': 4.25}

def calculate_investment_department_budget(user_inputs, market_data):
  calc = InvestmentDepartmentCalculator()
  internal_data = user_inputs.get('update_data', {})

  if not market_data:
    market_data = calc.fetch_investment_market_data()

  base_budget = float(user_inputs.get('base_budget', 50000000))
  growth_rate = float(user_inputs.get('growth_rate', 0.05))
  adjusted_growth = growth_rate
  projected_budget = round(base_budget * (1 + adjusted_growth), 2)
  summary_dict = {k: v['amount'] for k, v in internal_data.items()}

  return {
      'department': '投資管理部門',
      'warning_score': 45.0,
      'warning_level': '🟢 綠燈 (投資部位穩健)',
      'internal_data_summary': summary_dict,
      'internal_data_full': internal_data,
      'base_budget': base_budget,
      'original_growth_rate': growth_rate,
      'adjusted_growth_rate': adjusted_growth,
      'projected_budget': projected_budget,
      'recommendation': '投資部位收益與避險現金流維持正常，符合資產配置規範。',
      'market_snapshot': market_data,
  }