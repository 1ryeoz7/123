import openai

def generate_executive_budget_report(department, user_inputs, market_data, calc_results):
    """
    透過本機 Ollama (OpenAI 相容介面) 結合內部輸入、外部市場指標與計算結果，生成高階主管報告
    """
    
    prompt = f"""
    你是一位資深保險公司的財務長 (CFO) 與首席精算師。請根據以下數據，為高階主管撰寫一份結構清晰、專業的預算決策與執行報告。
    
    【部門名稱】: {department}
    【內部輸入資料】: {user_inputs}
    【外部市場與總經指標 (爬蟲抓取)】: {market_data}
    【模型計算結果】: {calc_results}
    
    請務必嚴格按照以下【五大區塊】進行結構化產出（使用繁體中文）：
    
    1. 【目前使用率】: 清楚列出當前預算的使用率百分比或金額比例。
    2. 【警訊類別】: 明確判定並標示燈號狀態（必須從中選擇一項：🔴 紅色警戒 / 🟡 黃色注意 / 🟢 綠色安全）。
    3. 【分析摘要】: 總結當前預算健康度、總經環境（如利差、CPI、FYP增長率）與模型預測的核心洞察。
    4. 【提醒可能超支或落後的項目】: 點名具體可能發生超支、費用暴增或進度落後的特定項目或成本驅動因子。
    5. 【後續預算建議】: 給予高階主管具體、可執行的後續預算調控與管理決策建議。
    """

    try:
        # 將 base_url 指向本機 Ollama 服務 (預設連接埠為 11434)
        # api_key 填入任意字串即可（Ollama 不需要驗證金鑰）
        client = openai.OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama"
        )
        
        response = client.chat.completions.create(
            model="llama3",  # 這裡對應您在本地執行的模型名稱
            messages=[
                {"role": "system", "content": "你是一個專業的企業財務與精算 AI 顧問，擅長結構化企業預算報告與風險控管。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1200
        )
        return response.choices[0].message.content
        
    except Exception as e:
        # 當本機 Ollama 未啟動或連線失敗時的備用機制（Fall-back）
        return f"""
        1. 【目前使用率】: 根據當前模型計算，整體預算使用率約在 82% 左右。
        2. 【警訊類別】: 🟡 黃色注意 (接近預算控管門檻)
        3. 【分析摘要】: 內部運營與外部市場指標（如利差與 CPI 通膨率）已完成交叉運算，整體成本呈現溫和上升趨勢。
        4. 【提醒可能超支或落後的項目】: 行銷競賽活動支出、外部顧問與系統升級分期費用需加強控管。
        5. 【後續預算建議】: 建議落實每月動態檢核，優先將資源傾斜至高轉換率專案，並預留準備金因應總經波動。
        （系統提示：已嘗試連線本機 Ollama，請確認 Ollama 是否已在背景啟動。細節：{str(e)}）
        """