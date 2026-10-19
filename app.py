import io
from datetime import datetime

from calculator_investment import calculate_investment_department_budget
from calculator_risk_actuarial import calculate_risk_actuarial_budget

# 1. 匯入五大部門的計算模組
from calculator_sales import calculate_sales_department_budget
from calculator_support import calculate_support_department_budget
from calculator_underwriting_claims import (
    calculate_underwriting_claims_budget,
)
from flask import Flask, redirect, render_template, request, send_file, url_for
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

# 2. 匯入 LLM 報告生成模組與排程器
from llm_report_generator import generate_executive_budget_report
from scheduler import DAILY_MARKET_DATA, init_scheduler

# ==========================================
# 應用程式配置 (App Configurations)
# ==========================================
app = Flask(__name__)

# 設定 SQLite 資料庫
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


# ==========================================
# 資料庫模型 (Database Models)
# ==========================================
class BudgetItemModel(db.Model):
    """儲存各部門預算項目、標籤與金額"""

    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(
        db.String(50), nullable=False
    )  # 例如: 'Sales', 'Investment', 'Risk', 'Support', 'Underwriting'
    item_name = db.Column(db.String(100), nullable=False)  # 會計科目項目
    category = db.Column(db.String(50), nullable=False)  # 支出種類標籤
    amount = db.Column(db.Float, nullable=False)  # 金額


# ==========================================
# 常數與對照表 (Constants & Mappings)
# ==========================================
DEPT_NAMES = {
    'sales': '業務部門',
    'risk_actuarial': '風險管理部門',
    'investment': '投資管理部門',
    'support': '內控與後勤部門',
    'underwriting_claims': '核保與理賠部門',
}

DEPT_CODES = {
    'sales': 'Sales',
    'risk_actuarial': 'Risk',
    'investment': 'Investment',
    'support': 'Support',
    'underwriting_claims': 'Underwriting',
}


# ==========================================
# 初始化資料庫預設資料與排程器
# ==========================================
def init_db():
    """初始化資料庫表單，若無資料則匯入預設數據"""
    with app.app_context():
        db.create_all()
        if BudgetItemModel.query.count() == 0:
            default_records = [
                # 業務部門 (Sales)
                BudgetItemModel(
                    department='Sales',
                    item_name='保單商品佣金支出(收入)',
                    category='業務變動成本',
                    amount=150000000,
                ),
                BudgetItemModel(
                    department='Sales',
                    item_name='初年度保費FYP',
                    category='業務營運指標',
                    amount=300000000,
                ),
                BudgetItemModel(
                    department='Sales',
                    item_name='保單商品佣金率表fyc%',
                    category='通路費率規範',
                    amount=50.0,
                ),
                BudgetItemModel(
                    department='Sales',
                    item_name='業務競賽獎金與激勵活動支出',
                    category='獎金與激勵',
                    amount=12000000,
                ),
                BudgetItemModel(
                    department='Sales',
                    item_name='業務營運培訓與通訊運營費用',
                    category='營運與培訓',
                    amount=8000000,
                ),
                BudgetItemModel(
                    department='Sales',
                    item_name='業務通路常態行銷與推廣費用',
                    category='行銷與推廣',
                    amount=20000000,
                ),
                # 投資部門 (Investment)
                BudgetItemModel(
                    department='Investment',
                    item_name='常態資產庫存總額',
                    category='資產規模',
                    amount=1000000000,
                ),
                BudgetItemModel(
                    department='Investment',
                    item_name='常態資產收益明細',
                    category='投資收益',
                    amount=45000000,
                ),
                BudgetItemModel(
                    department='Investment',
                    item_name='投資例行性營運與交易費用',
                    category='營運與交易',
                    amount=5000000,
                ),
                # 風管部門 (Risk)
                BudgetItemModel(
                    department='Risk',
                    item_name='精算負債與資金成本曲線基數',
                    category='精算負債',
                    amount=250000000,
                ),
                BudgetItemModel(
                    department='Risk',
                    item_name='監理資本與投資限額上限(接軌ICS/IFRS17合規成本)',
                    category='監理合規',
                    amount=80000000,
                ),
                # 後勤部門 (Support)
                BudgetItemModel(
                    department='Support',
                    item_name='內控、稽核與合規費用',
                    category='法規合規',
                    amount=12000000,
                ),
                BudgetItemModel(
                    department='Support',
                    item_name='軟硬體維護費',
                    category='系統維護',
                    amount=18000000,
                ),
                BudgetItemModel(
                    department='Support',
                    item_name='人事費用',
                    category='人事費用',
                    amount=45000000,
                ),
                # 核保理賠部門 (Underwriting)
                BudgetItemModel(
                    department='Underwriting',
                    item_name='理賠金給付與險種賠款準備金',
                    category='理賠準備金',
                    amount=500000000,
                ),
                BudgetItemModel(
                    department='Underwriting',
                    item_name='外部醫療公證與理賠調查外包費用',
                    category='公證外包',
                    amount=25000000,
                ),
            ]
            db.session.add_all(default_records)
            db.session.commit()


# 執行初始化
init_db()
init_scheduler()


# ==========================================
# 路由設計 (Routes)
# ==========================================
@app.route('/')
def index():
    """首頁"""
    return render_template(
        'index.html', market_data=DAILY_MARKET_DATA, depts=DEPT_NAMES
    )


@app.route('/dept/<dept_id>')
def department_home(dept_id):
    """部門主頁"""
    if dept_id not in DEPT_NAMES:
        return '找不到該部門', 404
    return render_template(
        'department_home.html',
        dept_id=dept_id,
        dept_name=DEPT_NAMES[dept_id],
    )

@app.route('/dept/<dept_id>/input', methods=['GET', 'POST'])
def department_input(dept_id):
  # 驗證部門是否存在
  if dept_id not in DEPT_NAMES:
    return '找不到該部門', 404

  department_name = DEPT_NAMES[dept_id]
  db_code = DEPT_CODES[dept_id]

  if request.method == 'POST':
    # --- A. 接收並更新現有科目金額與新增自訂科目 ---
    base_budget = float(request.form.get('base_budget', 0))
    growth_rate = float(request.form.get('growth_rate', 0))

    # 更新資料庫中的現行科目金額
    records = BudgetItemModel.query.filter_by(department=db_code).all()
    for record in records:
      if record.item_name in request.form:
        try:
          record.amount = float(request.form.get(record.item_name))
        except ValueError:
          pass

    # 處理新寫入的自訂科目與標籤
    new_item_name = request.form.get('new_item_name', '').strip()
    new_item_category = request.form.get('new_item_category', '').strip()
    new_item_amount = request.form.get('new_item_amount', '').strip()

    if new_item_name:
      try:
        amt = float(new_item_amount) if new_item_amount else 0.0
        existing = BudgetItemModel.query.filter_by(
            department=db_code, item_name=new_item_name
        ).first()
        if existing:
          existing.amount = amt
          if new_item_category:
            existing.category = new_item_category
        else:
          new_rec = BudgetItemModel(
              department=db_code,
              item_name=new_item_name,
              category=new_item_category or '一般支出',
              amount=amt,
          )
          db.session.add(new_rec)
      except ValueError:
        pass

    db.session.commit()

    # --- B. 重新載入最新資料並進行模組計算 ---
    updated_records = BudgetItemModel.query.filter_by(department=db_code).all()
    internal_data = {
        r.item_name: {'category': r.category, 'amount': r.amount}
        for r in updated_records
    }

    user_inputs = {
        'base_budget': base_budget,
        'growth_rate': growth_rate,
        'update_data': internal_data
    }

    # 根據部門代碼呼叫對應的計算器
    result = {}
    if dept_id == 'sales':
      market_arg = DAILY_MARKET_DATA.get('sales_data', DAILY_MARKET_DATA)
      result = calculate_sales_department_budget(user_inputs, market_arg)
    elif dept_id == 'risk_actuarial':
      market_arg = DAILY_MARKET_DATA.get('risk_data', DAILY_MARKET_DATA)
      result = calculate_risk_actuarial_budget(user_inputs, market_arg)
    elif dept_id == 'investment':
      market_arg = DAILY_MARKET_DATA.get('investment_data', DAILY_MARKET_DATA)
      result = calculate_investment_department_budget(user_inputs, market_arg)
    elif dept_id == 'support':
      market_arg = DAILY_MARKET_DATA.get('support_data', DAILY_MARKET_DATA)
      result = calculate_support_department_budget(user_inputs, market_arg)
    elif dept_id == 'underwriting_claims':
      market_arg = DAILY_MARKET_DATA.get('uw_data', DAILY_MARKET_DATA)
      result = calculate_underwriting_claims_budget(user_inputs, market_arg)

    # --- C. 呼叫本機 LLM 生成 AI 決策報告 ---
    ai_report = generate_executive_budget_report(
        department=department_name,
        user_inputs=user_inputs,
        market_data=DAILY_MARKET_DATA,
        calc_results=result,
    )

    # --- D. 雙向相容變數封裝，導向 result.html ---
    return render_template(
        'result.html',
        dept_id=dept_id,
        dept_name=department_name,
        result=result,
        result_data=result,
        report=ai_report,
        ai_report=ai_report
    )

  # --- GET 請求：讀取資料庫並渲染輸入表單網頁 ---
  records = BudgetItemModel.query.filter_by(department=db_code).all()
  internal_data = {
      r.item_name: {'category': r.category, 'amount': r.amount}
      for r in records
  }

  return render_template(
      'input_form.html',
      department_name=department_name,
      dept_id=dept_id,
      base_budget=100000000.0,
      growth_rate=0.05,
      internal_data=internal_data,
  )

@app.route('/dept/<dept_id>/calculate', methods=['POST'])
def department_calculate(dept_id):
    """接收前端修改資料，自動更新並永久寫入 SQLite 資料庫，隨後進行專業模型計算"""
    if dept_id not in DEPT_NAMES:
        return '找不到該部門', 404

    db_code = DEPT_CODES[dept_id]
    form_data = request.form.to_dict()
    user_inputs = {}
    update_data_dict = {}

    # 解析表單一般數據與現有科目
    for key, val in form_data.items():
        if key in ['growth_rate', 'base_budget']:
            try:
                user_inputs[key] = float(val)
            except ValueError:
                user_inputs[key] = val
        elif not key.startswith('category_') and key not in [
            'new_item_name',
            'new_item_category',
            'new_item_amount',
        ]:
            item_name = key
            cat_name = form_data.get(f'category_{item_name}', '一般支出')
            try:
                amt_val = float(val) if '.' in str(val) else int(val)
            except ValueError:
                amt_val = 0.0

            update_data_dict[item_name] = {
                'amount': amt_val,
                'category': cat_name,
            }

            # 同步更新資料庫紀錄
            record = BudgetItemModel.query.filter_by(
                department=db_code, item_name=item_name
            ).first()
            if record:
                record.amount = amt_val
                record.category = cat_name
            else:
                new_rec = BudgetItemModel(
                    department=db_code,
                    item_name=item_name,
                    category=cat_name,
                    amount=amt_val,
                )
                db.session.add(new_rec)

    # 處理前端新增的自訂科目數據
    new_name = form_data.get('new_item_name')
    new_cat = form_data.get('new_item_category', '自訂支出')
    new_amt = form_data.get('new_item_amount')

    if new_name and new_amt:
        try:
            amt_val = float(new_amt) if '.' in str(new_amt) else int(new_amt)
            existing_rec = BudgetItemModel.query.filter_by(
                department=db_code, item_name=new_name
            ).first()
            if existing_rec:
                existing_rec.amount = amt_val
                existing_rec.category = new_cat
            else:
                new_rec = BudgetItemModel(
                    department=db_code,
                    item_name=new_name,
                    category=new_cat,
                    amount=amt_val,
                )
                db.session.add(new_rec)
            update_data_dict[new_name] = {
                'amount': amt_val,
                'category': new_cat,
            }
        except ValueError:
            pass

    db.session.commit()

    if update_data_dict:
        user_inputs['update_data'] = update_data_dict

    # 根據不同部門呼叫相對應的試算模組
    result = {}
    if dept_id == 'sales':
        market_arg = DAILY_MARKET_DATA.get('sales_data', DAILY_MARKET_DATA)
        result = calculate_sales_department_budget(user_inputs, market_arg)
    elif dept_id == 'risk_actuarial':
        market_arg = DAILY_MARKET_DATA.get('risk_data', DAILY_MARKET_DATA)
        result = calculate_risk_actuarial_budget(user_inputs, market_arg)
    elif dept_id == 'investment':
        market_arg = DAILY_MARKET_DATA.get('investment_data', DAILY_MARKET_DATA)
        result = calculate_investment_department_budget(
            user_inputs, market_arg
        )
    elif dept_id == 'support':
        market_arg = DAILY_MARKET_DATA.get('support_data', DAILY_MARKET_DATA)
        result = calculate_support_department_budget(user_inputs, market_arg)
    elif dept_id == 'underwriting_claims':
        market_arg = DAILY_MARKET_DATA.get('uw_data', DAILY_MARKET_DATA)
        result = calculate_underwriting_claims_budget(user_inputs, market_arg)

    # 產出 AI 高階分析報告
    executive_report = generate_executive_budget_report(
        department=DEPT_NAMES[dept_id],
        user_inputs=user_inputs,
        market_data=DAILY_MARKET_DATA,
        calc_results=result,
    )

    return render_template(
        'result.html',
        dept_id=dept_id,
        dept_name=DEPT_NAMES[dept_id],
        result=result,
        report=executive_report,
    )


@app.route('/dept/<dept_id>/export_excel')
def export_excel(dept_id):
    """匯出該部門預算科目至 Excel"""
    if dept_id not in DEPT_CODES:
        return '找不到該部門', 404

    db_code = DEPT_CODES[dept_id]
    records = BudgetItemModel.query.filter_by(department=db_code).all()

    data = [
        {'Item': r.item_name, 'Category': r.category, 'Amount': r.amount}
        for r in records
    ]

    df = pd.DataFrame(data)
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=db_code, index=False)

    output.seek(0)
    return send_file(
        output,
        download_name=f'{dept_id}_budget_report.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


@app.route('/dept/<dept_id>/delete_item/<item_name>', methods=['POST'])
def delete_department_item(dept_id, item_name):
    """刪除指定部門預算科目"""
    if dept_id not in DEPT_CODES:
        return '找不到該部門', 404

    db_code = DEPT_CODES[dept_id]
    record = BudgetItemModel.query.filter_by(
        department=db_code, item_name=item_name
    ).first()

    if record:
        db.session.delete(record)
        db.session.commit()

    return redirect(url_for('department_input', dept_id=dept_id))


# ==========================================
# 主程式執行點
# ==========================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)