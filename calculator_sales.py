import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

def calculate_sales_department_budget(user_inputs, market_data):
    """
    業務部門預算分析與預測函數
    
    參數:
    - user_inputs: 包含使用者輸入的字典，例如預估 FYP、歷史訓練資料等
    - market_data: 包含當日市場指標（如利率、台美利差、市場 FYP 增長率等）
    """
    
    # ----------------------------------------------------
    # 1. 內部驅動因子法：預估業務佣金 (Commission)
    # ----------------------------------------------------
    est_fyp = float(user_inputs.get("est_fyp", 0))          # 預估新契約保費 (FYP)
    avg_fyc_rate = float(user_inputs.get("avg_fyc_rate", 0.15)) # 平均佣金率 (預設 15%)
    
    est_commission = est_fyp * avg_fyc_rate
    
    # ----------------------------------------------------
    # 2. 外部與歷史連動：彈性預算迴歸預測行銷與競賽支出 (Y)
    # ----------------------------------------------------
    # 假設我們有一組歷史訓練數據 (X: [市場FYP增長率, 台美利差], Y: 實際行銷活動支出)
    # 實務上這些歷史資料可以從公司的資料庫或 Excel 讀取
    historical_data = pd.DataFrame({
        'market_fyp_growth': [0.02, 0.05, -0.01, 0.08, 0.03], # 歷史市場 FYP 增長率
        'interest_spread':   [1.20, 1.40,  0.90, 1.60, 1.30], # 歷史台美利差 (%)
        'marketing_expense': [5000, 6200,  4100, 7500, 5800]  # 歷史行銷與競賽支出 (萬元)
    })
    
    # 準備訓練特徵 (X) 與目標變數 (Y)
    X = historical_data[['market_fyp_growth', 'interest_spread']]
    Y = historical_data['marketing_expense']
    
    # 建立並訓練線性迴歸模型
    reg_model = LinearRegression()
    reg_model.fit(X, Y)
    
    # 取得當前大環境的自變數（從 market_data 或使用者輸入中取得）
    current_market_growth = float(market_data.get("market_fyp_growth", 0.04)) # 當前市場增長率預估
    current_spread = float(market_data.get("interest_spread", 1.35))          # 當前台美利差
    
    # 預測當期的行銷與競賽支出
    predicted_features = np.array([[current_market_growth, current_spread]])
    est_marketing_expense = reg_model.predict(predicted_features)[0]
    
    # ----------------------------------------------------
    # 3. 總預算加總與標準比對 (決定輸出種類)
    # ----------------------------------------------------
    total_sales_budget = est_commission + est_marketing_expense
    
    # 範例標準比對邏輯
    if total_sales_budget > 100000:
        budget_category = "業務部 - A級專案：大型擴展與高額獎金方案 (需總經理由)"
    elif total_sales_budget > 50000:
        budget_category = "業務部 - B級專案：標準常態營運預算 (部門主管核決)"
    else:
        budget_category = "業務部 - C級專案：精簡型防守預算"
        
    return {
        "est_commission": round(est_commission, 2),
        "est_marketing_expense": round(est_marketing_expense, 2),
        "total_sales_budget": round(total_sales_budget, 2),
        "budget_category": budget_category,
        "regression_coefficients": {
            "coef": list(reg_model.coef_),
            "intercept": reg_model.intercept_
        }
    }