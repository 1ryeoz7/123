from datetime import datetime
import threading
import time
import schedule

# 匯入精簡後的風管部門計算器
from calculator_risk_actuarial import RiskActuarialCalculator
from calculator_sales import SalesDepartmentCalculator

# 全域市場與風險數據變數，供 app.py 與各部門直接引用
DAILY_MARKET_DATA = {}


def update_daily_risk_market_data_job():
  global DAILY_MARKET_DATA
  print(
      f'=== [排程執行] 正在背景自動抓取風管專屬市場、信評與 ESG 數據:'
      f" {datetime.now()} ==="
  )
  calc = RiskActuarialCalculator()
  DAILY_MARKET_DATA = calc.fetch_risk_market_data()
  print(f'=== [排程完成] 風管最新市場數據已更新: {DAILY_MARKET_DATA} ===')


def run_scheduler_loop():
  while True:
    schedule.run_pending()
    time.sleep(1)


def init_scheduler():
  global DAILY_MARKET_DATA
  # 程式啟動時先執行一次抓取初始化全域數據
  calc = RiskActuarialCalculator()
  DAILY_MARKET_DATA = calc.fetch_risk_market_data()

  # 設定每天早上 08:30 定時更新
  schedule.every().day.at('08:30').do(update_daily_risk_market_data_job)

  # 以背景執行緒運行排程，避免阻斷 Flask 主服務
  t = threading.Thread(target=run_scheduler_loop, daemon=True)
  t.start()
  print('背景排程服務（含風管市場爬蟲）已成功初始化並啟動！')

  sales_calc = SalesDepartmentCalculator()
  sales_market_data = sales_calc.fetch_sales_market_data()