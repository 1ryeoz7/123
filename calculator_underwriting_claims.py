import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

def calculate_underwriting_claims_budget(user_inputs, market_data):
    """
    核保與理賠部門預算與風險模擬模組 (Isolation Forest + Monte Carlo Simulation)
    
    參數:
    - user_inputs: 包含當月理賠營運開銷等輸入資料
    - market_data: 外部突發風險指標（如流感嚴重度、災害風險係數）
    """
    
    # ----------------------------------------------------
    # 1. 歷史理賠營運費用異常值偵測 (Isolation Forest)
    # ----------------------------------------------------
    np.random.seed(42)
    n_months = 36
    
    # 模擬歷史月理賠營運開銷（夾帶幾次突發性暴增的異常點，例如過去的疫情或大型天災）
    hist_expenses = np.random.normal(8000000, 500000, n_months)
    hist_expenses[12] = 13500000  # 假設第 13 個月發生突發異常暴增
    hist_expenses[25] = 14200000  # 假設第 26 個月發生突發異常暴增
    
    X_train = hist_expenses.reshape(-1, 1)
    
    # 訓練隔離森林模型來抓取異常值 (contamination 設定異常比例約 8%)
    iso_forest = IsolationForest(contamination=0.08, random_state=42)
    iso_forest.fit(X_train)
    
    # 取得當前輸入或測試的單月理賠營運費用
    current_month_expense = float(user_inputs.get("current_month_expense", 8500000))
    anomaly_pred = iso_forest.predict([[current_month_expense]])[0]
    is_anomaly = True if anomaly_pred == -1 else False
    
    # ----------------------------------------------------
    # 2. 蒙地卡羅模擬法 (Monte Carlo Simulation - 1,000 次模擬)
    # ----------------------------------------------------
    n_simulations = 1000
    # 外部突發風險係數（從 market_data 取得，若無則預設 1.05）
    env_shock_factor = float(market_data.get("disaster_risk_factor", 1.05))
    
    simulated_annual_costs = []
    for _ in range(n_simulations):
        # 模擬未來 12 個月的隨機變動總和（考量季節性疾病或突發事件機率）
        monthly_sim = np.random.normal(8200000 * env_shock_factor, 800000, 12)
        total_annual_cost = np.sum(monthly_sim)
        simulated_annual_costs.append(total_annual_cost)
        
    simulated_annual_costs = np.array(simulated_annual_costs)
    
    # 計算統計指標
    mean_cost = np.mean(simulated_annual_costs)
    percentile_95 = np.percentile(simulated_annual_costs, 95) # 95% 信賴水準下的極端值 (VaR 概念)
    
    # 設定年度理賠營運預算上限門檻，計算極端超支的機率分佈 (%)
    budget_limit = 105000000
    overspend_probability = np.mean(simulated_annual_costs > budget_limit) * 100
    
    # ----------------------------------------------------
    # 3. 風險與預算標準比對 (決定輸出種類)
    # ----------------------------------------------------
    if overspend_probability > 25.0 or is_anomaly:
        budget_category = "核保理賠部 - 紅色警戒：模擬顯示極端超支機率偏高，或偵測到理賠費用歷史異常暴增，需立即提撥特別準備金與調整外包合約 (Output: High-Risk Contingency Plan)"
    elif overspend_probability > 10.0:
        budget_category = "核保理賠部 - 黃色注意：季節性突發事件風險上升，理賠調查費波動加劇，需加強案件審查監控 (Output: Moderate Operations Alert)"
    else:
        budget_category = "核保理賠部 - 綠色安全：理賠與核保營運開銷經模擬後在可控範圍內 (Output: Standard Claims Budget)"
        
    return {
        "anomaly_detection": {
            "current_expense_tested": current_month_expense,
            "is_anomaly": is_anomaly,
            "status": "偵測到歷史異常暴增" if is_anomaly else "常態波動範圍內"
        },
        "monte_carlo_simulation": {
            "n_simulations": n_simulations,
            "expected_annual_mean": round(mean_cost, 2),
            "var_95_percentile": round(percentile_95, 2),
            "overspend_probability_pct": round(overspend_probability, 2)
        },
        "budget_category": budget_category
    }