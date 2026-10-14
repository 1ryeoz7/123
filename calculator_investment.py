import numpy as np
import pandas as pd
from prophet import Prophet

def calculate_investment_department_budget(user_inputs, market_data):
    """
    投資管理部門預算與避險成本預測模組 (Prophet + Macro Regressors)
    
    參數:
    - user_inputs: 使用者輸入的歷史數據或預測期數設定
    - market_data: 當前總經指標（如 GDP 增長率、CPI、台美利差）
    """
    
    # ----------------------------------------------------
    # 1. 建立歷史訓練資料集 (包含時間 ds、目標開銷 y、以及總經外生變數)
    # ----------------------------------------------------
    np.random.seed(42)
    n_months = 36
    dates = pd.date_range(start='2023-01-01', periods=n_months, freq='MS')
    
    # 模擬歷史總經外生變數
    hist_gdp = np.random.normal(0.03, 0.01, n_months)          # GDP 增長率
    hist_cpi = np.random.normal(0.02, 0.005, n_months)         # CPI inflation
    hist_spread = np.random.normal(1.20, 0.2, n_months)        # 台美利差 (%)
    
    # 歷史投資/避險營運開銷 (Y) 受利差與資產規模擴大影響
    base_expense = 15000000
    noise = np.random.normal(0, 500000, n_months)
    hist_expense = base_expense + (hist_spread * 3000000) + (hist_cpi * 2000000) + noise
    
    # 整理成 Prophet 格式的 DataFrame (必須包含 ds, y 以及外生變數欄位)
    df_train = pd.DataFrame({
        'ds': dates,
        'y': hist_expense,
        'gdp_growth': hist_gdp,
        'cpi': hist_cpi,
        'interest_spread': hist_spread
    })
    
    # ----------------------------------------------------
    # 2. 初始化並訓練 Prophet 模型，加入外生變數 (Regressors)
    # ----------------------------------------------------
    model = Prophet(yearly_seasonality=True, weekly_seasonality=False, daily_seasonality=False)
    
    # 註冊總經外生變數
    model.add_regressor('gdp_growth')
    model.add_regressor('cpi')
    model.add_regressor('interest_spread')
    
    # 訓練模型
    model.fit(df_train)
    
    # ----------------------------------------------------
    # 3. 建立未來預測期的外生變數情境 (結合即時 market_data)
    # ----------------------------------------------------
    # 預測未來 1 個月或 1 季的開銷
    future = model.make_future_dataframe(periods=1, freq='MS')
    
    # 填入未來期的總經預估值（若 market_data 有提供則使用即時值，否則帶入預設值）
    future['gdp_growth'] = list(hist_gdp) + [float(market_data.get("gdp_growth", 0.032))]
    future['cpi'] = list(hist_cpi) + [float(market_data.get("cpi", 0.021))]
    future['interest_spread'] = list(hist_spread) + [float(market_data.get("interest_spread", 1.45))] # 假設利差擴大
    
    # 執行預測
    forecast = model.predict(future)
    
    # 取得當期（最後一筆）預測出的避險與營運開銷
    predicted_expense = forecast.iloc[-1]['yhat']
    lower_bound = forecast.iloc[-1]['yhat_lower']
    upper_bound = forecast.iloc[-1]['yhat_upper']
    
    # ----------------------------------------------------
    # 4. 預算黃紅燈與標準比對 (決定輸出種類)
    # ----------------------------------------------------
    current_spread = float(market_data.get("interest_spread", 1.45))
    
    if current_spread > 1.50 or predicted_expense > 22000000:
        budget_category = "投資部 - 紅燈警戒：台美利差擴大導致避險成本飆升，需立即調整外匯準備金與避險比例 (Output: Urgent Hedging Adjustment Plan)"
    elif current_spread > 1.20:
        budget_category = "投資部 - 黃燈注意：避險營運開銷上升，啟動動態避險檢視 (Output: Moderate Hedging Review)"
    else:
        budget_category = "投資部 - 綠燈正常：總經環境平穩，依常態編列預算 (Output: Standard Investment Budget)"
        
    return {
        "predicted_investment_expense": round(predicted_expense, 2),
        "prediction_confidence_interval": {
            "lower": round(lower_bound, 2),
            "upper": round(upper_bound, 2)
        },
        "budget_category": budget_category,
        "used_macro_variables": {
            "interest_spread": current_spread,
            "gdp_growth": market_data.get("gdp_growth", 0.032),
            "cpi": market_data.get("cpi", 0.021)
        }
    }