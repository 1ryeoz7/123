def process_calculation(category, user_inputs, market_data):
    """
    依據不同類別、使用者輸入與當日市場資料進行後端計算與標準比對
    """
    rate = market_data["interest_rate"]
    fx = market_data["exchange_rate"]
    
    result_score = 0
    
    if category == "finance_loan":
        amount = float(user_inputs.get("amount", 0))
        result_score = amount * (rate / 100) * fx
        
    elif category == "insurance_fyp":
        premium = float(user_inputs.get("premium", 0))
        result_score = premium / fx
        
    # 比對標準並決定輸出種類
    if result_score > 50000:
        output_type = "高級審查與VIP方案 (Category A)"
    elif result_score > 20000:
        output_type = "標準處理流程 (Category B)"
    else:
        output_type = "快速通關/簡易件 (Category C)"
        
    return {
        "score": round(result_score, 2),
        "output_type": output_type,
        "used_market_data": market_data
    }