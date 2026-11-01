import io
import math
import zipfile
from datetime import datetime, timezone
from flask import (
    Flask,
    abort,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import pandas as pd
import scheduler
from scheduler import init_scheduler

# 1. 匯入五大部門的計算模組
from calculator_investment import calculate_investment_department_budget
from calculator_risk_actuarial import calculate_risk_actuarial_budget
from calculator_sales import calculate_sales_department_budget
from calculator_support import calculate_support_department_budget
from calculator_underwriting_claims import calculate_underwriting_claims_budget

# 2. 匯入 LLM 報告生成模組與背景排程器
from llm_report_generator import generate_executive_budget_report

# ==========================================
# 應用程式配置 (App Configurations)
# ==========================================
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

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
    department = db.Column(db.String(50), nullable=False)  # 例如: 'Sales', 'Investment', 'Risk', 'Support', 'Underwriting'
    item_name = db.Column(db.String(100), nullable=False)  # 會計科目項目
    category = db.Column(db.String(50), nullable=False)   # 支出種類標籤
    amount = db.Column(db.Float, nullable=False)          # 金額


class BudgetImportBatch(db.Model):
    """保留每次匯入的 Excel 版本與預覽狀態"""
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='preview')
    version = db.Column(db.Integer, nullable=True, unique=True)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    validation_errors = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class ImportedBudgetItem(db.Model):
    """單一匯入版本中的預算科目快照"""
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(
        db.Integer, db.ForeignKey('budget_import_batch.id'), nullable=False
    )
    department = db.Column(db.String(50), nullable=False)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    source_row = db.Column(db.Integer, nullable=False)
    __table_args__ = (
        db.UniqueConstraint(
            'batch_id', 'department', 'item_code',
            name='uq_import_batch_department_item_code',
        ),
    )


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

IMPORT_SHEETS = {
    'Sales': 'Sales',
    'Risk': 'Risk',
    'Investment': 'Investment',
    'Support': 'Support',
    'Underwriting': 'Underwriting',
}
IMPORT_COLUMNS = ('ItemCode', 'Item', 'Category', 'Amount')
MAX_IMPORT_ROWS = 50000

RESERVED_ITEM_NAMES = frozenset({
    'new_item_name',
    'new_item_category',
    'new_item_amount',
})

# 📌 各部門專屬的支出種類標籤下拉選單項目
DEPT_CATEGORIES = {
    'sales': ['業務變動成本', '業務營運指標', '通路費率規範', '獎金與激勵', '營運與培訓', '行銷與推廣'],
    'investment': ['資產規模', '投資收益', '營運與交易', '避險與交易成本', '外部經理人費'],
    'risk_actuarial': ['精算負債', '監理合規', '外部精算模型軟體費', '風管外包專案費', '系統開發與維護'],
    'support': ['法規合規', '系統維護', '人事費用', '行政與總務', '資訊資安'],
    'underwriting_claims': ['理賠準備金', '公證外包', '核保醫療體檢費', '再保險支出', '防阻詐欺與調查']
}

# ==========================================
# 初始化資料庫預設資料與排程器
# ==========================================
def init_db():
    """初始化資料庫表單，若無資料則匯入預設數據"""
    with app.app_context():
        db.create_all()
        removed_reserved_items = BudgetItemModel.query.filter(
            BudgetItemModel.item_name.in_(RESERVED_ITEM_NAMES)
        ).delete(synchronize_session=False)
        if removed_reserved_items:
            db.session.commit()

        if BudgetItemModel.query.count() == 0:
            default_records = [
                # 業務部門 (Sales)
                BudgetItemModel(department='Sales', item_name='保單商品佣金支出(收入)', category='業務變動成本', amount=150000000),
                BudgetItemModel(department='Sales', item_name='初年度保費FYP', category='業務營運指標', amount=300000000),
                BudgetItemModel(department='Sales', item_name='保單商品佣金率表fyc%', category='通路費率規範', amount=50.0),
                BudgetItemModel(department='Sales', item_name='業務競賽獎金與激勵活動支出', category='獎金與激勵', amount=12000000),
                BudgetItemModel(department='Sales', item_name='業務營運培訓與通訊運營費用', category='營運與培訓', amount=8000000),
                BudgetItemModel(department='Sales', item_name='業務通路常態行銷與推廣費用', category='行銷與推廣', amount=20000000),
                # 投資部門 (Investment)
                BudgetItemModel(department='Investment', item_name='常態資產庫存總額', category='資產規模', amount=1000000000),
                BudgetItemModel(department='Investment', item_name='常態資產收益明細', category='投資收益', amount=45000000),
                BudgetItemModel(department='Investment', item_name='投資例行性營運與交易費用', category='營運與交易', amount=5000000),
                # 風管部門 (Risk)
                BudgetItemModel(department='Risk', item_name='精算負債與資金成本曲線基數', category='精算負債', amount=250000000),
                BudgetItemModel(department='Risk', item_name='監理資本與投資限額上限(接軌ICS/IFRS17合規成本)', category='監理合規', amount=80000000),
                # 後勤部門 (Support)
                BudgetItemModel(department='Support', item_name='內控、稽核與合規費用', category='法規合規', amount=12000000),
                BudgetItemModel(department='Support', item_name='軟硬體維護費', category='系統維護', amount=18000000),
                BudgetItemModel(department='Support', item_name='人事費用', category='人事費用', amount=45000000),
                # 核保理賠部門 (Underwriting)
                BudgetItemModel(department='Underwriting', item_name='理賠金給付與險種賠款準備金', category='理賠準備金', amount=500000000),
                BudgetItemModel(department='Underwriting', item_name='外部醫療公證與理賠調查外包費用', category='公證外包', amount=25000000),
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
    return render_template('index.html', market_data=scheduler.DAILY_MARKET_DATA, depts=DEPT_NAMES)


@app.route('/imports')
def import_batches():
    batches = BudgetImportBatch.query.order_by(
        BudgetImportBatch.id.desc()
    ).limit(50).all()
    return render_template('imports.html', batches=batches)


@app.route('/imports/template')
def download_import_template():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name in IMPORT_SHEETS:
            pd.DataFrame(columns=IMPORT_COLUMNS).to_excel(
                writer, sheet_name=sheet_name, index=False
            )
    output.seek(0)
    return send_file(
        output,
        download_name='budget_import_template.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def _import_error(sheet, row, column, message):
    return {
        'sheet': sheet,
        'row': row,
        'column': column,
        'message': message,
    }


def _cell_text(value):
    if pd.isna(value):
        return ''
    return str(value).strip()


def _parse_import_amount(value):
    if pd.isna(value) or isinstance(value, bool):
        raise ValueError('金額不可空白，且必須是數字。')
    if isinstance(value, str):
        value = value.strip().replace(',', '')
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError('金額必須是有效數字。')
    if not math.isfinite(amount) or amount < 0:
        raise ValueError('金額必須是大於或等於 0 的有限數值。')
    return amount


@app.route('/imports/upload', methods=['POST'])
def upload_budget_workbook():
    uploaded_file = request.files.get('workbook')
    if not uploaded_file or not uploaded_file.filename:
        return render_template(
            'imports.html',
            batches=BudgetImportBatch.query.order_by(
                BudgetImportBatch.id.desc()
            ).limit(50).all(),
            upload_error='請選擇 Excel 檔案。',
        ), 400

    original_filename = secure_filename(uploaded_file.filename) or 'budget.xlsx'
    if not original_filename.lower().endswith('.xlsx'):
        return render_template(
            'imports.html',
            batches=BudgetImportBatch.query.order_by(
                BudgetImportBatch.id.desc()
            ).limit(50).all(),
            upload_error='目前只接受 .xlsx 格式。',
        ), 400

    workbook_bytes = uploaded_file.read()
    if not workbook_bytes:
        return render_template(
            'imports.html',
            batches=BudgetImportBatch.query.order_by(
                BudgetImportBatch.id.desc()
            ).limit(50).all(),
            upload_error='上傳的檔案是空的。',
        ), 400

    errors = []
    preview_rows = []
    import_rows = []
    try:
        if not zipfile.is_zipfile(io.BytesIO(workbook_bytes)):
            raise ValueError('檔案不是有效的 .xlsx 活頁簿。')
        workbook = pd.ExcelFile(
            io.BytesIO(workbook_bytes), engine='openpyxl'
        )
    except (ValueError, OSError, zipfile.BadZipFile) as error:
        return render_template(
            'imports.html',
            batches=BudgetImportBatch.query.order_by(
                BudgetImportBatch.id.desc()
            ).limit(50).all(),
            upload_error=f'無法讀取 Excel 檔案：{error}',
        ), 400

    expected_sheets = set(IMPORT_SHEETS)
    actual_sheets = set(workbook.sheet_names)
    for missing_sheet in sorted(expected_sheets - actual_sheets):
        errors.append(_import_error(
            missing_sheet, 1, '工作表',
            '缺少必要的部門工作表。',
        ))
    for unexpected_sheet in sorted(actual_sheets - expected_sheets):
        errors.append(_import_error(
            unexpected_sheet, 1, '工作表',
            '工作表名稱不在支援的部門清單中。',
        ))

    total_data_rows = 0
    row_limit_reached = False
    for sheet_name, department in IMPORT_SHEETS.items():
        if sheet_name not in actual_sheets:
            continue
        frame = pd.read_excel(
            workbook, sheet_name=sheet_name, dtype=object
        )
        frame.columns = [str(column).strip() for column in frame.columns]
        if len(set(frame.columns)) != len(frame.columns):
            errors.append(_import_error(
                sheet_name, 1, '欄位',
                '欄位名稱重複，請確認標題列。',
            ))
            continue

        missing_columns = set(IMPORT_COLUMNS) - set(frame.columns)
        for missing_column in sorted(missing_columns):
            errors.append(_import_error(
                sheet_name, 1, missing_column,
                f'缺少必要欄位 {missing_column}。',
            ))
        if missing_columns:
            continue

        seen_item_codes = set()
        for dataframe_row, values in frame.iterrows():
            excel_row = int(dataframe_row) + 2
            cells = {column: values[column] for column in IMPORT_COLUMNS}
            if all(pd.isna(value) or _cell_text(value) == '' for value in cells.values()):
                continue

            if total_data_rows >= MAX_IMPORT_ROWS:
                errors.append(_import_error(
                    sheet_name, excel_row, '資料列',
                    f'匯入資料不可超過 {MAX_IMPORT_ROWS} 列。',
                ))
                row_limit_reached = True
                break

            total_data_rows += 1
            row_errors = []
            item_code = _cell_text(cells['ItemCode'])
            item_name = _cell_text(cells['Item'])
            category = _cell_text(cells['Category'])
            if not item_code:
                row_errors.append(('ItemCode', '科目代碼不可空白。'))
            elif len(item_code) > 50:
                row_errors.append(('ItemCode', '科目代碼不可超過 50 個字元。'))
            elif item_code in seen_item_codes:
                row_errors.append(('ItemCode', '同一部門工作表中科目代碼重複。'))
            else:
                seen_item_codes.add(item_code)

            if not item_name:
                row_errors.append(('Item', '科目名稱不可空白。'))
            elif len(item_name) > 100:
                row_errors.append(('Item', '科目名稱不可超過 100 個字元。'))
            if not category:
                row_errors.append(('Category', '標籤不可空白。'))
            elif len(category) > 50:
                row_errors.append(('Category', '標籤不可超過 50 個字元。'))

            try:
                amount = _parse_import_amount(cells['Amount'])
            except ValueError as error:
                row_errors.append(('Amount', str(error)))

            for column, message in row_errors:
                errors.append(_import_error(
                    sheet_name, excel_row, column, message
                ))

            if not row_errors:
                item = {
                    'department': department,
                    'item_code': item_code,
                    'item_name': item_name,
                    'category': category,
                    'amount': amount,
                    'source_row': excel_row,
                }
                import_rows.append(item)
                if len(preview_rows) < 100:
                    preview_rows.append({
                        **item,
                        'department_name': next(
                            name for key, name in DEPT_NAMES.items()
                            if DEPT_CODES[key] == department
                        ),
                    })
        if row_limit_reached:
            break

    batch = BudgetImportBatch(
        original_filename=original_filename,
        status='preview',
        row_count=len(import_rows),
        error_count=len(errors),
        validation_errors=errors,
    )
    db.session.add(batch)
    db.session.flush()
    db.session.add_all(
        ImportedBudgetItem(batch_id=batch.id, **row)
        for row in import_rows
    )
    db.session.commit()

    return render_template(
        'imports.html',
        batches=BudgetImportBatch.query.order_by(
            BudgetImportBatch.id.desc()
        ).limit(50).all(),
        preview_batch=batch,
        preview_rows=preview_rows,
        preview_errors=errors[:100],
        omitted_error_count=max(0, len(errors) - 100),
    )


@app.route('/imports/<int:batch_id>')
def import_batch_detail(batch_id):
    batch = db.get_or_404(BudgetImportBatch, batch_id)
    preview_rows = ImportedBudgetItem.query.filter_by(
        batch_id=batch.id
    ).order_by(
        ImportedBudgetItem.department,
        ImportedBudgetItem.source_row,
    ).limit(100).all()
    return render_template(
        'imports.html',
        batches=BudgetImportBatch.query.order_by(
            BudgetImportBatch.id.desc()
        ).limit(50).all(),
        preview_batch=batch,
        preview_rows=preview_rows,
        preview_errors=batch.validation_errors[:100],
        omitted_error_count=max(0, batch.error_count - 100),
    )


@app.route('/imports/<int:batch_id>/confirm', methods=['POST'])
def confirm_import_batch(batch_id):
    batch = db.get_or_404(BudgetImportBatch, batch_id)
    if batch.status != 'preview':
        abort(409, '此匯入批次已確認或不可再變更。')
    if batch.error_count or not batch.row_count:
        abort(400, '匯入資料仍有錯誤，或沒有可匯入的資料列。')

    latest_version = db.session.query(
        db.func.max(BudgetImportBatch.version)
    ).scalar() or 0
    batch.version = latest_version + 1
    batch.status = 'confirmed'
    db.session.commit()
    return redirect(url_for('import_batch_detail', batch_id=batch.id))


@app.route('/dept/<dept_id>')
def department_home(dept_id):
    """部門主頁"""
    if dept_id not in DEPT_NAMES:
        return '找不到該部門', 404
    return render_template('department_home.html', dept_id=dept_id, dept_name=DEPT_NAMES[dept_id])


@app.route('/dept/<dept_id>/input', methods=['GET', 'POST'])
def department_input(dept_id):
    if dept_id not in DEPT_NAMES:
        return '找不到該部門', 404

    department_name = DEPT_NAMES[dept_id]
    db_code = DEPT_CODES[dept_id]
    available_categories = DEPT_CATEGORIES.get(dept_id, ['一般支出'])
    market_data_keys = {
        'sales': 'sales_data',
        'risk_actuarial': 'risk_data',
        'investment': 'investment_data',
        'support': 'support_data',
        'underwriting_claims': 'uw_data',
    }
    calculators = {
        'sales': calculate_sales_department_budget,
        'risk_actuarial': calculate_risk_actuarial_budget,
        'investment': calculate_investment_department_budget,
        'support': calculate_support_department_budget,
        'underwriting_claims': calculate_underwriting_claims_budget,
    }

    def render_input_form(
        base_budget=100000000.0, growth_rate=0.05, form_error=None
    ):
        records = BudgetItemModel.query.filter_by(department=db_code).all()
        internal_data = {
            record.item_name: {
                'category': record.category,
                'amount': record.amount,
            }
            for record in records
        }
        return render_template(
            'input_form.html',
            department_name=department_name,
            dept_id=dept_id,
            base_budget=base_budget,
            growth_rate=growth_rate,
            internal_data=internal_data,
            available_categories=available_categories,
            form_error=form_error,
        )

    def parse_non_negative_amount(value, label):
        try:
            amount = float(value)
        except (TypeError, ValueError):
            raise ValueError(f'{label}必須是有效數字。')
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f'{label}必須是大於或等於 0 的有限數值。')
        return amount

    if request.method == 'POST':
        records = BudgetItemModel.query.filter_by(department=db_code).all()
        try:
            base_budget = parse_non_negative_amount(
                request.form.get('base_budget'), '基準預算'
            )
            growth_rate = float(request.form.get('growth_rate', ''))
            if not math.isfinite(growth_rate) or growth_rate < -1:
                raise ValueError('預期成長率必須是大於或等於 -1 的有限數值。')

            amount_updates = {}
            category_updates = {}
            allowed_categories = set(available_categories)
            allowed_categories.add('一般支出')

            for record in records:
                if record.item_name in RESERVED_ITEM_NAMES:
                    continue

                if record.item_name in request.form:
                    amount_updates[record.id] = parse_non_negative_amount(
                        request.form.get(record.item_name),
                        f'「{record.item_name}」金額',
                    )

                category_key = f'category_{record.item_name}'
                if category_key in request.form:
                    category = request.form.get(category_key, '').strip()
                    if not category or (
                        category not in allowed_categories
                        and category != record.category
                    ):
                        raise ValueError(f'「{record.item_name}」的支出類別無效。')
                    if len(category) > 50:
                        raise ValueError(f'「{record.item_name}」的支出類別不可超過 50 個字元。')
                    category_updates[record.id] = category

            new_item_name = request.form.get('new_item_name', '').strip()
            new_item_category = request.form.get('new_item_category', '').strip()
            new_item_amount = request.form.get('new_item_amount', '').strip()
            if new_item_name:
                if len(new_item_name) > 100:
                    raise ValueError('新科目名稱不可超過 100 個字元。')
                if new_item_category and new_item_category not in allowed_categories:
                    raise ValueError('新科目的支出類別無效。')
                if len(new_item_category) > 50:
                    raise ValueError('新科目的支出類別不可超過 50 個字元。')
                new_item_amount_value = parse_non_negative_amount(
                    new_item_amount or '0', '新科目金額'
                )
        except ValueError as error:
            return render_input_form(
                request.form.get('base_budget', 100000000.0),
                request.form.get('growth_rate', 0.05),
                str(error),
            )

        for record in records:
            if record.id in amount_updates:
                record.amount = amount_updates[record.id]
            if record.id in category_updates:
                record.category = category_updates[record.id]

        if new_item_name:
            existing = BudgetItemModel.query.filter_by(
                department=db_code, item_name=new_item_name
            ).first()
            if existing:
                existing.amount = new_item_amount_value
                if new_item_category:
                    existing.category = new_item_category
            else:
                db.session.add(
                    BudgetItemModel(
                        department=db_code,
                        item_name=new_item_name,
                        category=new_item_category or available_categories[0],
                        amount=new_item_amount_value,
                    )
                )

        db.session.commit()

        updated_records = BudgetItemModel.query.filter_by(department=db_code).all()
        internal_data = {
            r.item_name: {'category': r.category, 'amount': r.amount}
            for r in updated_records
        }
        user_inputs = {
            'base_budget': base_budget,
            'growth_rate': growth_rate,
            'update_data': internal_data,
        }
        market_data = scheduler.DAILY_MARKET_DATA.get(
            market_data_keys[dept_id], {}
        )
        result = calculators[dept_id](user_inputs, market_data)

        ai_report = generate_executive_budget_report(
            department=department_name,
            user_inputs=user_inputs,
            market_data=result.get('market_snapshot', market_data),
            calc_results=result,
        )

        return render_template(
            'result.html',
            dept_id=dept_id,
            dept_name=department_name,
            result=result,
            ai_report=ai_report,
        )

    return render_input_form()


@app.route('/dept/<dept_id>/export_excel')
def export_excel(dept_id):
    """匯出該部門預算科目至 Excel"""
    if dept_id not in DEPT_CODES:
        return '找不到該部門', 404

    db_code = DEPT_CODES[dept_id]
    records = BudgetItemModel.query.filter_by(department=db_code).all()

    data = [{'Item': r.item_name, 'Category': r.category, 'Amount': r.amount} for r in records]

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


@app.route('/dept/<dept_id>/delete_item', methods=['POST'])
def delete_department_item(dept_id):
    """刪除指定部門預算科目"""
    if dept_id not in DEPT_CODES:
        return '找不到該部門', 404

    db_code = DEPT_CODES[dept_id]
    item_name = request.form.get('item_name', '')
    record = BudgetItemModel.query.filter_by(department=db_code, item_name=item_name).first()

    if record:
        db.session.delete(record)
        db.session.commit()

    return redirect(url_for('department_input', dept_id=dept_id))


# ==========================================
# 主程式執行點
# ==========================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)