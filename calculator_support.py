import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

def calculate_support_department_budget(user_inputs, market_data):
    """
    內控、稽核與後勤部門預算預測模組 (Holt-Winters + CPI 通膨調整係數)
    
    參數:
    - user_inputs: 包含歷史後勤開銷資料或預測期數設定
    - market_data: 當前市場數據（包含 CPI 通膨率）
    """
    
    # ----------------------------------------------------
    # 1. 建立歷史後勤營運開銷時間序列資料 (含季節性與平穩趨勢)
    # ----------------------------------------------------
    np.random.seed(42)
    n_months = 36  # 過去 3 年共 36 個月
    dates = pd.date_range(start='2023-01-01', periods=n_months, freq='MS')
    
    # 模擬歷史後勤成本：具備穩定成長趨勢 + 年底結算的高峰季節性
    trend = np.linspace(5000000, 5800000, n_months)  # 基礎人事與租金逐年微幅上升
    seasonality = np.array([1.0, 0.98, 1.02, 1.0, 0.99, 1.01, 1.0, 0.99, 1.01, 1.02, 1.03, 1.15]) # 12月常態性結算高峰
    seasonal_36 = np.tile(seasonality, 3)
    
    noise = np.random.normal(0, 50000, n_months)
    hist_expense = trend * seasonal_36 + noise
    
    # 轉換為帶有頻率的 Pandas Series (Holt-Winters 需要明確的時間頻率)
    ts_data = pd.Series(hist_expense, index=dates)
    
    # ----------------------------------------------------
    # 2. 訓練 Holt-Winters 指數平滑模型
    # ----------------------------------------------------
    # 採用加法趨勢 (trend='add') 與加法季節性 (seasonal='add', seasonal_periods=12)
    hw_model = ExponentialSmoothing(
        ts_data, 
        trend='add', 
        seasonal='add', 
        seasonal_periods=12
    ).fit()
    
    # ----------------------------------------------------
    # 3. 預測未來期數（例如預測未來 1 個月或 1 季）並套用通膨調整係數
    # ----------------------------------------------------
    forecast_steps = int(user_inputs.get("forecast_steps", 1)) # 預測未來幾個月
    raw_forecast = hw_model.forecast(steps=forecast_steps)
    
    # 取得當前總經的通膨調整係數 (CPI 年增率，例如 2.1% 則係數為 1 + 0.021 = 1.021)
    cpi_rate = float(market_data.get("cpi", 0.021))
    inflation_factor = 1.0 + cpi_rate
    
    # 將 Holt-Winters 的原始預測值乘上通膨調整係數
    adjusted_forecast_expense = raw_forecast.iloc[-1] * inflation_factor
    
    # ----------------------------------------------------
    # 4. 後勤預算檢核與標準比對 (決定輸出種類)
    # ----------------------------------------------------
    # 假設標準後勤每月控制額度為 6,000,000
    budget_threshold = 6000000
    
    if adjusted_forecast_expense > 6500000:
        budget_category = "後勤部 - 紅燈警戒：預估開銷受通膨與合規檢核影響超支，需進行部門精簡與租金/外包合約重新議價 (Output: Cost-Reduction Plan)"
    elif adjusted_forecast_expense > budget_threshold:
        budget_category = "後勤部 - 黃燈注意：逼近行政預算上限，需加強日常辦公採購管控 (Output: Strict Expense Control)"
    else:
        budget_category = "後勤部 - 綠燈正常：行政與後勤開銷符合平穩預期，依常態撥款 (Output: Standard Support Budget)"
        
    return {
        "predicted_support_expense": round(adjusted_forecast_expense, 2),
        "raw_hw_forecast": round(raw_forecast.iloc[-1], 2),
        "applied_inflation_factor": inflation_factor,
        "budget_category": budget_category,
        "used_cpi": cpi_rate
    }