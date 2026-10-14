from flask import Flask, render_template, request
from scheduler import init_scheduler, DAILY_MARKET_DATA

# 匯入五大部門的計算模組
from calculator_sales import calculate_sales_department_budget
from calculator_risk_actuarial import calculate_risk_actuarial_budget
from calculator_investment import calculate_investment_department_budget
from calculator_support import calculate_support_department_budget
from calculator_underwriting_claims import calculate_underwriting_claims_budget

app = Flask(__name__)

# 啟動時初始化排程器
init_scheduler()

@app.route('/')
def index():
    """首頁：讓使用者選擇要分析的部門類別"""
    return render_template('index.html')

@app.route('/input', methods=['POST'])
def input_page():
    """第二頁：根據選擇的部門動態載入對應的輸入表單欄位"""
    department = request.form.get('department')
    return render_template('input_form.html', department=department)

@app.route('/calculate', methods=['POST'])
def calculate_result():
    """後端計算分派與標準比對"""
    department = request.form.get('department')
    user_inputs = request.form.to_dict()
    
    result = {}
    
    # 根據不同部門分派到對應的計算模組
    if department == 'sales':
        result = calculate_sales_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif department == 'risk_actuarial':
        result = calculate_risk_actuarial_budget(user_inputs, DAILY_MARKET_DATA)
    elif department == 'investment':
        result = calculate_investment_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif department == 'support':
        result = calculate_support_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif department == 'underwriting_claims':
        result = calculate_underwriting_claims_budget(user_inputs, DAILY_MARKET_DATA)
        
    return render_template('result.html', result=result, department=department)

if __name__ == '__main__':
    app.run(debug=True, port=5000)