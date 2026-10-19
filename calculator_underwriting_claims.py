class UnderwritingClaimsCalculator:
  def __init__(self):
    self.department_name = '核保與理賠部門'

  def fetch_underwriting_market_data(self):
    return {
        '外部醫療公證費用指數': 107.2,
        '理賠調查外包成本基準': '每件委外調查費用微幅上揚',
        '核保系統運作與雲端算力成本基準': '算力成本指數: 103.8',
    }

def calculate_underwriting_claims_budget(user_inputs, market_data):
  calc = UnderwritingClaimsCalculator()
  internal_data = user_inputs.get('update_data', {})

  if not market_data:
    market_data = calc.fetch_underwriting_market_data()

  med_index = market_data.get('外部醫療公證費用指數', 100.0)
  claims_pressure = max(1.0, med_index / 100.0)

  outsource_fee = internal_data.get('外部醫療公證與理賠調查外包費用', {}).get('amount', 25000000)
  it_cost = internal_data.get('核保與理賠系統維運及雲端算力成本', {}).get('amount', 18000000)
  personnel_fee = internal_data.get('核保理賠部門人事與專業鑑定培訓費用', {}).get('amount', 32000000)

  base_budget = float(user_inputs.get('base_budget', outsource_fee + it_cost + personnel_fee))
  growth_rate = float(user_inputs.get('growth_rate', 0.04))
  adjusted_growth = growth_rate * claims_pressure
  projected_budget = round(base_budget * (1 + adjusted_growth), 2)
  underwriting_score = round(min(100.0, max(0.0, (claims_pressure - 1.0) * 400 + 35)), 2)
  warning_level = '🔴 紅燈 (醫療公證與理賠調查成本大增)' if underwriting_score > 75 else ('🟡 黃燈 (理賠與系統成本警戒)' if underwriting_score > 50 else '🟢 綠燈 (核保理賠成本穩定)')

  summary_dict = {k: v['amount'] for k, v in internal_data.items()}

  return {
      'department': '核保與理賠部門',
      'warning_score': underwriting_score,
      'warning_level': warning_level,
      'internal_data_summary': summary_dict,
      'internal_data_full': internal_data,
      'base_budget': base_budget,
      'original_growth_rate': growth_rate,
      'adjusted_growth_rate': adjusted_growth,
      'projected_budget': projected_budget,
      'recommendation': '外部醫療公證與理賠調查外包費用指數走揚，核保與理賠核心開銷面臨上升壓力。',
      'market_snapshot': market_data,
  }