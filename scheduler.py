from datetime import datetime
import threading
import time
import schedule

# 匯入五大部門的計算與爬蟲模組
from calculator_investment import InvestmentDepartmentCalculator
from calculator_risk_actuarial import RiskActuarialCalculator
from calculator_sales import SalesDepartmentCalculator
from calculator_support import SupportDepartmentCalculator
from calculator_underwriting_claims import UnderwritingClaimsCalculator

# 全域市場與部門即時爬蟲數據變數
DAILY_MARKET_DATA = {}


def update_daily_all_departments_market_data_job():
  global DAILY_MARKET_DATA
  print(
      f'=== [排程執行] 正在背景即時爬取五大部門最新指定數據:'
      f" {datetime.now()} ==="
  )

  try:
    risk_calc = RiskActuarialCalculator()
    sales_calc = SalesDepartmentCalculator()
    inv_calc = InvestmentDepartmentCalculator()
    support_calc = SupportDepartmentCalculator()
    uw_calc = UnderwritingClaimsCalculator()

    risk_data = risk_calc.fetch_risk_market_data()
    sales_data = sales_calc.fetch_sales_market_data()
    inv_data = inv_calc.fetch_investment_market_data()
    support_data = support_calc.fetch_support_market_data()
    uw_data = uw_calc.fetch_underwriting_market_data()

    # 組合完整的巢狀資料，並額外建立一個平坦化的 overview 專供首頁(index.html)使用
    DAILY_MARKET_DATA = {
        'risk_data': risk_data,
        'sales_data': sales_data,
        'investment_data': inv_data,
        'support_data': support_data,
        'uw_data': uw_data,
        # 專供首頁總覽顯示的重要外部指標彙整
        'overview': {
            '金融市場波動(VIX)': risk_data.get('金融市場波動(VIX)', 15.0),
            '台美利差': sales_data.get('台美利差', -2.25),
            '通膨率CPI': sales_data.get('通膨率CPI', 2.15),
            'GDP成長率': inv_data.get('GDP成長率總經數據', 3.12),
            'FYP增長率': sales_data.get('FYP增長率', 5.40),
        },
    }
    print(f'=== [排程完成] 五大部門即時爬蟲數據已全部更新成功 ===')
  except Exception as e:
    print(f'=== [排程警告] 執行即時爬蟲時發生例外錯誤: {e} ===')


def run_scheduler_loop():
  while True:
    schedule.run_pending()
    time.sleep(1)


def init_scheduler():
  global DAILY_MARKET_DATA
  # 程式啟動時先執行一次即時爬蟲初始化全域數據
  update_daily_all_departments_market_data_job()

  # 設定每天早上 08:30 定時執行即時爬蟲
  schedule.every().day.at('08:30').do(
      update_daily_all_departments_market_data_job
  )

  # 以背景執行緒運行排程，避免阻斷 Flask 主服務
  t = threading.Thread(target=run_scheduler_loop, daemon=True)
  t.start()
  print('背景排程服務已成功初始化並啟動！')