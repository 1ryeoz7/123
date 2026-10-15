from apscheduler.schedulers.background import BackgroundScheduler
import requests

# 儲存當日讀取的公開資料
DAILY_MARKET_DATA = {
    "interest_rate": 0.02,
    "interest_spread": 1.35,
    "cpi": 0.021,               
    "market_fyp_growth": 0.04   
}

def fetch_daily_public_data():
    """每天自動讀取公開網站上的利率指標、匯率、FYP 等資料"""
    global DAILY_MARKET_DATA
    try:
        # 這裡未來可以放你的爬蟲或公開 API 讀取程式碼
        DAILY_MARKET_DATA["interest_rate"] = 1.62
        DAILY_MARKET_DATA["exchange_rate"] = 32.25
        print("【系統訊息】已成功更新今日市場資料：", DAILY_MARKET_DATA)
    except Exception as e:
        print("【錯誤】抓取失敗：", e)

def init_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_daily_public_data, 'cron', hour=0, minute=0)
    scheduler.start()