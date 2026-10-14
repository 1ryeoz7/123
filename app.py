from flask import Flask, render_template, request
from scheduler import init_scheduler, DAILY_MARKET_DATA
from calculator import process_calculation

app = Flask(__name__)

# 啟動時初始化排程器
init_scheduler()

@app.route('/')
def index():
    """第一頁：選擇類別"""
    return render_template('index.html')

@app.route('/input', methods=['POST'])
def input_page():
    """第二頁：動態載入輸入表單"""
    category = request.form.get('category')
    return render_template('input_form.html', category=category)

@app.route('/calculate', methods=['POST'])
def calculate_result():
    """後端計算與標準比對"""
    category = request.form.get('category')
    user_inputs = request.form.to_dict()
    
    result = process_calculation(category, user_inputs, DAILY_MARKET_DATA)
    
    return render_template('result.html', result=result, category=category)

if __name__ == '__main__':
    app.run(debug=True, port=5000)