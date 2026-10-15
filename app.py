from flask import Flask, render_template, request
from scheduler import init_scheduler, DAILY_MARKET_DATA

# 1. 匯入五大部門的計算模組
from calculator_sales import calculate_sales_department_budget
from calculator_risk_actuarial import calculate_risk_actuarial_budget
from calculator_investment import calculate_investment_department_budget
from calculator_support import calculate_support_department_budget
from calculator_underwriting_claims import calculate_underwriting_claims_budget

# 2. 匯入 LLM 報告生成模組
from llm_report_generator import generate_executive_budget_report

app = Flask(__name__)
init_scheduler()

# 部門名稱對照字典
DEPT_NAMES = {
    'sales': '業務部門',
    'risk_actuarial': '風管與精算部門',
    'investment': '投資管理部門',
    'support': '內控與後勤部門',
    'underwriting_claims': '核保與理賠部門'
}

@app.route('/')
def index():
    """頁面 1：首頁 (顯示外部重要資訊 + 全局預算使用率概覽與 Menu)"""
    return render_template('index.html', market_data=DAILY_MARKET_DATA, depts=DEPT_NAMES)

@app.route('/dept/<dept_id>')
def department_home(dept_id):
    """頁面 2 (2-1 ~ 2-5)：各部門專屬首頁與說明"""
    if dept_id not in DEPT_NAMES:
        return "找不到該部門", 404
    return render_template('department_home.html', dept_id=dept_id, dept_name=DEPT_NAMES[dept_id])

@app.route('/dept/<dept_id>/input')
def department_input(dept_id):
    """頁面 3 (3-1 ~ 3-5)：分別輸入內部資料與參數"""
    if dept_id not in DEPT_NAMES:
        return "找不到該部門", 404
    return render_template('input_form.html', dept_id=dept_id, dept_name=DEPT_NAMES[dept_id])

@app.route('/dept/<dept_id>/calculate', methods=['POST'])
def department_calculate(dept_id):
    """頁面 4 (4-1 ~ 4-5)：結合外部資料、AI 模型計算與生成五大區塊決策報告"""
    if dept_id not in DEPT_NAMES:
        return "找不到該部門", 404
        
    user_inputs = request.form.to_dict()
    result = {}
    
    # 根據不同部門呼叫對應的計算邏輯（正確縮排在路由內）
    if dept_id == 'sales':
        result = calculate_sales_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif dept_id == 'risk_actuarial':
        result = calculate_risk_actuarial_budget(user_inputs, DAILY_MARKET_DATA)
    elif dept_id == 'investment':
        result = calculate_investment_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif dept_id == 'support':
        result = calculate_support_department_budget(user_inputs, DAILY_MARKET_DATA)
    elif dept_id == 'underwriting_claims':
        result = calculate_underwriting_claims_budget(user_inputs, DAILY_MARKET_DATA)
        
    # 呼叫 LLM 生成符合要求的五大區塊決策報告
    executive_report = generate_executive_budget_report(
        department=DEPT_NAMES[dept_id],
        user_inputs=user_inputs,
        market_data=DAILY_MARKET_DATA,
        calc_results=result
    )
    
    return render_template('result.html', dept_id=dept_id, dept_name=DEPT_NAMES[dept_id], result=result, report=executive_report)

if __name__ == '__main__':
    app.run(debug=True, port=5000)