import numpy as np
import pandas as pd
import xgboost as xgb
import statsmodels.api as sm

def calculate_risk_actuarial_budget(user_inputs, market_data):
    """
    風管與精算部門預算與 IFRS 17 / ICS 法規衝擊預測模組
    
    參數:
    - user_inputs: 包含專案期程、合約分期等資料
    - market_data: 即時市場資訊（利率、股市報酬率、信用利差等）
    """
    
    # ----------------------------------------------------
    # 1. 專案導向與階段性成本 (Step-fixed costs)
    # ----------------------------------------------------
    # 判斷當前季度或法規期限逼近程度（例如 Q4 為法規接軌高峰期）
    is_regulatory_peak = user_inputs.get("is_regulatory_peak", True) # 是否面臨接軌大限
    project_phase = user_inputs.get("project_phase", "Phase_3_Implementation") # 專案階段
    
    base_fixed_budget = 3000000  # 部門基礎常態營運預算
    
    consultant_cost = 0
    system_upgrade_cost = 0
    
    if is_regulatory_peak:
        # 當 IFRS 17 / ICS 期限逼近，自動依合約分期與歷史顧問時數認列大筆外部費用
        consultant_cost = 8500000  # 外部精算/會計顧問費
        system_upgrade_cost = 5000000 # 系統升級與模型驗證費
        
    total_project_budget = base_fixed_budget + consultant_cost + system_upgrade_cost

    # ----------------------------------------------------
    # 2. IFRS 17 / ICS 機器學習代理模型 (XGBoost Surrogate Model)
    # ----------------------------------------------------
    # 模擬歷史精算系統 (如 lifelib) 跑出來的大型矩陣訓練資料
    # X: [利率 (Interest Rate), 股市報酬率 (Stock Return), 信用利差 (Credit Spread)]
    # Y1: ICS 資本適足率變動數值, Y2: IFRS 負債變動金額
    np.random.seed(42)
    n_samples = 200
    
    hist_X = pd.DataFrame({
        'interest_rate': np.random.normal(0.025, 0.005, n_samples),
        'stock_return': np.random.normal(0.08, 0.15, n_samples),
        'credit_spread': np.random.normal(0.015, 0.003, n_samples)
    })
    
    # 假設精算系統真實算出的 ICS 資本適足率與負債反應
    hist_Y_ics = 200 + (hist_X['interest_rate'] * 500) + (hist_X['stock_return'] * 50) - (hist_X['credit_spread'] * 200)
    hist_Y_liab = 1000000 - (hist_X['interest_rate'] * 200000) + (hist_X['credit_spread'] * 50000)
    
    # 訓練 XGBoost 代理模型來擬合精算系統
    model_ics = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42)
    model_ics.fit(hist_X, hist_Y_ics)
    
    model_liab = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1, random_state=42)
    model_liab.fit(hist_X, hist_Y_liab)
    
    # 取得即時市場資訊 (X)
    current_market_features = pd.DataFrame([{
        'interest_rate': float(market_data.get("interest_rate", 0.028)),
        'stock_return': float(market_data.get("stock_return", 0.10)),
        'credit_spread': float(market_data.get("credit_spread", 0.016))
    }])
    
    # AI 代理模型在 0.1 秒內即時預測衝擊
    predicted_ics_ratio = model_ics.predict(current_market_features)[0]
    predicted_liab_change = model_liab.predict(current_market_features)[0]
    
    # ----------------------------------------------------
    # 3. 資本適足與衝擊標準比對 (決定輸出報告種類)
    # ----------------------------------------------------
    if predicted_ics_ratio < 180:
        impact_category = "風管級別 - 紅色警戒：ICS 接近監理紅線，需啟動資本增資或避險專案 (Output: High-Risk Capital Plan)"
    elif predicted_ics_ratio < 200:
        impact_category = "風管級別 - 黃色注意：需加強資產負債配管 (ALM) 與敏感度監控 (Output: Moderate Risk Report)"
    else:
        impact_category = "風管級別 - 綠色安全：資本結構穩健，依計畫執行專案 (Output: Standard Compliance Report)"
        
    return {
        "step_costs": {
            "base_fixed_budget": base_fixed_budget,
            "consultant_cost": consultant_cost,
            "system_upgrade_cost": system_upgrade_cost,
            "total_project_budget": total_project_budget
        },
        "regulatory_impact_forecast": {
            "predicted_ics_ratio": round(predicted_ics_ratio, 2),
            "predicted_liab_change": round(predicted_liab_change, 2),
            "impact_category": impact_category
        }
    }