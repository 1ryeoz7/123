class SupportDepartmentCalculator:
  def __init__(self):
    self.department_name = '內控與後勤部門'

  def fetch_support_market_data(self):
    return {
        '最新金融法規動態': '金管會法規正常更新監理',
        '市場營運成本基準指數': 105.8,
        '商辦租金市場行情基準': '每坪平均 2,350 元',
        '後勤資料材料市場價格基準': '行政耗材指數: 102.4',
    }

def calculate_support_department_budget(user_inputs, market_data):
  calc = SupportDepartmentCalculator()
  internal_data = user_inputs.get('update_data', {})

  if not market_data:
    market_data = calc.fetch_support_market_data()

  cost_index = market_data.get('市場營運成本基準指數', 100.0)
  inflation_pressure = max(1.0, cost_index / 100.0)

  audit_fee = internal_data.get('內控、稽核與合規費用', {}).get('amount', 12000000)
  maint_fee = internal_data.get('軟硬體維護費', {}).get('amount', 18000000)
  personnel_fee = internal_data.get('人事費用', {}).get('amount', 45000000)
  admin_fee = internal_data.get('一般行政與辦公費用', {}).get('amount', 8000000)

  base_budget = float(user_inputs.get('base_budget', audit_fee + maint_fee + personnel_fee + admin_fee))
  growth_rate = float(user_inputs.get('growth_rate', 0.02))
  adjusted_growth = growth_rate * inflation_pressure
  projected_budget = round(base_budget * (1 + adjusted_growth), 2)
  support_score = round(min(100.0, max(0.0, (inflation_pressure - 1.0) * 300 + 30)), 2)
  warning_level = '🔴 紅燈 (通膨引發隱性超支高風險)' if support_score > 75 else ('🟡 黃燈 (成本上揚警戒)' if support_score > 50 else '🟢 綠燈 (成本穩定)')

  summary_dict = {k: v['amount'] for k, v in internal_data.items()}

  return {
      'department': '內控與後勤部門',
      'warning_score': support_score,
      'warning_level': warning_level,
      'internal_data_summary': summary_dict,
      'internal_data_full': internal_data,
      'base_budget': base_budget,
      'original_growth_rate': growth_rate,
      'adjusted_growth_rate': adjusted_growth,
      'projected_budget': projected_budget,
      'recommendation': '外部商辦租金與材料市場價格因通膨上揚，後勤成本中心面臨隱性超支風險。',
      'market_snapshot': market_data,
  }