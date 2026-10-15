import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib
matplotlib.use('Agg') # 避免 Mac/Linux GUI 渲染報錯
import matplotlib.pyplot as plt

def calculate_sales_department_budget(user_inputs, market_data):
    """
    業務部門進階預算分析、AI 迴歸預測與執行建議模組
    """
    # ----------------------------------------------------
    #1. 解析內部與外部輸入資料
    # ----------------------------------------------------
    # 內部資料
    hist_activity_expense = float(user_inputs.get("hist_activity_expense", 5000000))
    operating_expense = float(user_inputs.get("operating_expense", 2000000))
    entry_policies = float(user_inputs.get("entry_policies", 1200)) # 進場保單件數
    avg_fyc_rate = float(user_inputs.get("avg_fyc_rate", 0.15))     # 平均佣金率
    est_fyp = float(user_inputs.get("est_fyp", 50000000))           # 預估 FYP
    
    # 外部資料（來自爬蟲或即時 market_data）
    market_fyp_growth = float(market_data.get("market_fyp_growth", 0.04)) # 壽險公會市場 FYP 增長率
    interest_spread = float(market_data.get("interest_spread", 1.35))     # 台美利差
    cpi_rate = float(market_data.get("cpi", 0.021))                       # CPI 通膨率

    # ----------------------------------------------------
    # 2. 內部驅動與線性迴歸預算計算
    # ----------------------------------------------------
    # 內部驅動：業務佣金 = 預估 FYP * 平均佣金率
    est_commission = est_fyp * avg_fyc_rate
    
    # 歷史訓練資料（結合外部總經與市場指標）
    historical_data = pd.DataFrame({
        'market_fyp_growth': [0.02, 0.05, -0.01, 0.08, 0.03],
        'interest_spread':   [1.20, 1.40,  0.90, 1.60, 1.30],
        'marketing_expense': [5000000, 6200000, 4100000, 7500000, 5800000]
    })
    
    X = historical_data[['market_fyp_growth', 'interest_spread']]
    Y = historical_data['marketing_expense']
    
    reg_model = LinearRegression()
    reg_model.fit(X, Y)
    
    # 預測當期行銷與競賽活動支出（受市場增長率與利差影響，並隨 CPI 微調）
    predicted_marketing = reg_model.predict([[market_fyp_growth, interest_spread]])[0] * (1 + cpi_rate)
    
    # 總業務預算 = 佣金 + 預測行銷支出 + 基礎運營費用
    total_sales_budget = est_commission + predicted_marketing + operating_expense
    
    # 當前預算實際使用率（假設部門編列額度為 15,000,000）
    budget_limit = 15000000
    utilization_rate = (total_sales_budget / budget_limit) * 100

    # ----------------------------------------------------
    # 3. AI 智慧執行建議生成引擎 (Actionable Insights)
    # ----------------------------------------------------
    ai_recommendations = []
    
    if utilization_rate > 100:
        ai_recommendations.append("【紅色警戒】預算使用率已超過 100% 上限！建議立即凍結非核心競賽專案，並針對高成本通路重新審視 FYC 佣金率結構。")
    elif utilization_rate > 85:
        ai_recommendations.append("【黃色注意】預算使用率逼近 85% 安全門檻。由於目前市場 FYP 增長率為動態成長，建議將行銷預算優先傾斜投遞至轉換率最高的精準保單。")
    else:
        ai_recommendations.append("【綠色穩健】預算使用率在安全範圍內，可維持現行業務推廣節奏。")
        
    if interest_spread > 1.4:
        ai_recommendations.append(f"【總經聯動提示】當前台美利差擴大 ({interest_spread}%)，資金成本上升，建議業務團隊多推行利變型或短年期商品以優化資金配置。")
        
    if market_fyp_growth < 0:
        ai_recommendations.append("【市場防禦提示】壽險公會市場 FYP 呈現負增長，AI 建議下個月酌減競賽活動支出，轉以內勤服務與現有保戶維繫為主。")
    else:
        ai_recommendations.append(f"【市場機會提示】市場正向成長 ({market_fyp_growth*100:.1f}%)，建議把握商機適度擴編業務行銷資源。")

    # ----------------------------------------------------
    # 4. 後端自動繪製圖表 (預算使用率 vs AI 預測線)
    # ----------------------------------------------------
    os.makedirs('static', exist_ok=True)
    chart_path = 'static/sales_budget_chart.png'
    
    plt.figure(figsize=(8, 4))
    months = ['Q1 (實際)', 'Q2 (實際)', 'Q3 (實際)', 'Q4 (AI 預測)']
    historical_trend = [11000000, 12500000, 13200000, total_sales_budget]
    ai_trend_line = [11500000, 12000000, 12800000, total_sales_budget * 0.98] # AI 基準預測線
    
    plt.plot(months, historical_trend, marker='o', color='royalblue', linewidth=2, label='部門預算使用趨勢')
    plt.plot(months, ai_trend_line, linestyle='--', color='crimson', linewidth=2, label='AI 基準預測線')
    plt.axhline(y=budget_limit, color='orange', linestyle=':', label='預算上限門檻 (1,500萬)')
    
    plt.title('業務部門預算使用率與 AI 預測趨勢對比')
    plt.ylabel('金額 (NTD)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    return {
        "est_commission": round(est_commission, 2),
        "predicted_marketing": round(predicted_marketing, 2),
        "total_sales_budget": round(total_sales_budget, 2),
        "utilization_rate_pct": round(utilization_rate, 2),
        "ai_recommendations": ai_recommendations,
        "chart_url": "/" + chart_path
    }