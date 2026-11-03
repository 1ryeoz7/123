from __future__ import annotations

import io
import json
import math
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import pandas as pd
from flask import (
    Flask, abort, flash, redirect, render_template, request, send_file,
    session, url_for,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from budget_calculator import convert_to_reporting_currency, evaluate_traffic_light, apply_market_context
from llm_report_generator import generate_executive_budget_report
from market_scheduler import get_market_data, init_scheduler

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY"),
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", "sqlite:///budget_system_v17.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)
if not app.config["SECRET_KEY"]:
    raise RuntimeError("未設定 SECRET_KEY；請依 OVERWRITE_README.md 設定環境變數。")

db = SQLAlchemy(app)
FX_BUDGET_BASE = float(os.environ.get("FX_BUDGET_BASE", "31.0"))
DEPT_NAMES = {
    "sales": "業務部門",
    "risk_actuarial": "風險管理部門",
    "investment": "投資管理部門",
    "support": "內控與後勤部門",
    "underwriting_claims": "核保與理賠部門",
}
DEPT_CODES = {
    "sales": "Sales", "risk_actuarial": "Risk", "investment": "Investment",
    "support": "Support", "underwriting_claims": "Underwriting",
}
IMPORT_SHEETS = ["Sales", "Risk", "Investment", "Support", "Underwriting"]
IMPORT_COLUMNS = (
    "Year", "Period", "ItemCode", "Item", "Category", "B_Annual", "B_Period",
    "A_Actual", "F0_Forecast", "Currency", "Locked_Ratio", "A_Trans",
    "D_NewDemand", "H_Hist", "IsSchedule", "Reason",
)
VALID_PERIODS = ["Q1", "Q2", "Q3", "Q4", "YTD"]
DEPT_CATEGORIES = {
    "sales": ["業務變動成本", "獎金與激勵"],
    "investment": ["營運與交易", "避險與交易成本"],
    "risk_actuarial": ["軟硬體維護", "風管外包專案費"],
    "support": ["行政耗材", "軟硬體維護"],
    "underwriting_claims": ["公證外包", "系統雲端運算費"],
}


class BudgetItemModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    period = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    is_schedule = db.Column(db.Boolean, default=False, nullable=False)
    b_annual_budget = db.Column(db.Float, nullable=False, default=0)
    b_period_budget = db.Column(db.Float, nullable=False, default=0)
    a_actual = db.Column(db.Float, nullable=False)
    f_0_forecast = db.Column(db.Float, nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="TWD")
    locked_ratio = db.Column(db.Float, nullable=False, default=0)
    a_transmission = db.Column(db.Float, nullable=False, default=1)
    d_new_demand = db.Column(db.Float, nullable=False, default=0)
    h_historical = db.Column(db.Float, nullable=True)
    overrun_reason = db.Column(db.String(255), nullable=True)
    __table_args__ = (db.UniqueConstraint("year", "period", "department", "item_code", name="uq_budget_item_v18"),)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    year = db.Column(db.Integer, nullable=False)
    period = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    api_tx_id = db.Column(db.String(100), nullable=True)
    __table_args__ = (db.UniqueConstraint("year", "period", "department", "event_type", name="uq_audit_event_v18"),)


class BudgetImportBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="preview")
    row_count = db.Column(db.Integer, nullable=False, default=0)
    error_count = db.Column(db.Integer, nullable=False, default=0)
    validation_errors = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class ImportedBudgetItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("budget_import_batch.id"), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    period = db.Column(db.String(10), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    item_code = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    is_schedule = db.Column(db.Boolean, default=False, nullable=False)
    b_annual_budget = db.Column(db.Float, nullable=False)
    b_period_budget = db.Column(db.Float, nullable=False)
    a_actual = db.Column(db.Float, nullable=False)
    f_0_forecast = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    locked_ratio = db.Column(db.Float, nullable=False)
    a_transmission = db.Column(db.Float, nullable=False)
    d_new_demand = db.Column(db.Float, nullable=False)
    h_historical = db.Column(db.Float, nullable=True)
    overrun_reason = db.Column(db.String(255), nullable=True)
    source_row = db.Column(db.Integer, nullable=False)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="department")
    department = db.Column(db.String(50), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)


class NotificationOutbox(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.Integer, db.ForeignKey("audit_log.id"), unique=True, nullable=False)
    event_key = db.Column(db.String(255), unique=True, nullable=False)
    department = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    provider_tx_id = db.Column(db.String(120), nullable=True)
    last_error = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def _parse_float(value, field_name="欄位", min_val=0.0, max_val=None, allow_blank=False):
    if value is None or str(value).strip() == "":
        if allow_blank:
            return None
        raise ValueError(f"{field_name}不可空白")
    try:
        number = float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        raise ValueError(f"{field_name}格式錯誤")
    if not math.isfinite(number):
        raise ValueError(f"{field_name}必須是有限數字")
    if min_val is not None and number < min_val:
        raise ValueError(f"{field_name}不可小於 {min_val}")
    if max_val is not None and number > max_val:
        raise ValueError(f"{field_name}不可大於 {max_val}")
    return number


def _parse_optional(value):
    if value is None or str(value).strip() == "":
        return None
    return _parse_float(value, "歷史金額", 0)


def _bootstrap_users():
    """Create/update accounts from APP_USERS_JSON; never ships default credentials."""
    raw = os.environ.get("APP_USERS_JSON", "").strip()
    if not raw:
        return
    try:
        accounts = json.loads(raw)
        if not isinstance(accounts, list):
            raise ValueError("APP_USERS_JSON 必須是 JSON 陣列")
        for record in accounts:
            username = str(record.get("username", "")).strip()
            password = str(record.get("password", ""))
            role = str(record.get("role", "department")).strip()
            department = record.get("department")
            if not username or len(password) < 12 or role not in {"admin", "department"}:
                raise ValueError("使用者需有名稱、至少 12 字元密碼及有效角色")
            if role == "department" and department not in DEPT_CODES:
                raise ValueError(f"部門帳號 {username} 的 department 不正確")
            user = User.query.filter_by(username=username).first()
            if user is None:
                db.session.add(User(username=username, password_hash=generate_password_hash(password), role=role, department=department))
            else:
                user.password_hash = generate_password_hash(password)
                user.role, user.department, user.active = role, department, True
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("APP_USERS_JSON 設定無效，帳號未更新")
        raise


def _current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None


@app.before_request
def protect_requests():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        submitted = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
        if not secrets.compare_digest(str(session.get("csrf_token", "")), str(submitted)):
            abort(400, "CSRF 驗證失敗，請重新載入頁面後再試。")
    if request.endpoint not in {"login", "static"} and request.endpoint is not None:
        if not session.get("user_id"):
            return redirect(url_for("login", next=request.path))


@app.context_processor
def inject_common_template_values():
    return {"csrf_token": session.get("csrf_token", ""), "logged_user": _current_user(), "FX_BUDGET_BASE": FX_BUDGET_BASE}


def admin_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        user = _current_user()
        if user is None or user.role != "admin":
            abort(403)
        return func(*args, **kwargs)
    return wrapped


def department_required(func):
    @wraps(func)
    def wrapped(dept_id, *args, **kwargs):
        user = _current_user()
        if user is None or (user.role != "admin" and user.department != dept_id):
            abort(403)
        return func(dept_id, *args, **kwargs)
    return wrapped


def _period():
    year = session.get("curr_year", datetime.now().year)
    period = session.get("curr_period", "YTD")
    if not isinstance(year, int) or not 2000 <= year <= 2100:
        year = datetime.now().year
    if period not in VALID_PERIODS:
        period = "YTD"
    return year, period


def _market_values():
    data = get_market_data()
    defaults = {
        "USD_TWD_Spot": 32.0,
        "USD_TWD_Forward_1Y": 31.5,
        "市場通膨指數 (CPI)": 100.0,
        "預算基準通膨 (CPI Base)": 100.0,
        "醫療公證費用指數 (Medical Index)": 100.0,
        "預算基準醫療指數 (Medical Base)": 100.0,
    }
    for key, value in defaults.items():
        data.setdefault(key, {"value": value, "source": "預設備援", "fetch_time": "無資料", "data_type": "unavailable_fallback", "is_cached": True, "note": "尚無有效市場值"})
    return data


def _value(market, key, fallback):
    try:
        number = float(market.get(key, {}).get("value", fallback))
        return number if math.isfinite(number) else fallback
    except (TypeError, ValueError):
        return fallback


def _metric_is_usable(market, key, max_age_hours=48):
    item = market.get(key, {})
    if item.get("data_type") in {"static_simulation", "unavailable_fallback"}:
        return False
    if item.get("is_cached"):
        return False
    stamp = item.get("fetch_time")
    try:
        fetched = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - fetched.astimezone(timezone.utc)).total_seconds() / 3600
        return 0 <= age <= max_age_hours
    except (TypeError, ValueError):
        return False


def _record_alert(department, event_type, message, year, period, triggers):
    triggers.append(message)
    if AuditLog.query.filter_by(department=department, event_type=event_type, year=year, period=period).first():
        return
    event_key = f"{year}:{period}:{department}:{event_type}"
    try:
        audit = AuditLog(department=department, event_type=event_type, message=message, api_tx_id="PENDING", year=year, period=period)
        db.session.add(audit)
        db.session.flush()
        outbox = NotificationOutbox(
            audit_id=audit.id, event_key=event_key, department=department, message=message,
            status="pending" if os.environ.get("ENTERPRISE_NOTIFY_API_URL") else "demo_only",
        )
        db.session.add(outbox)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return
    if outbox.status == "pending":
        _deliver_notification(outbox.id)


def _deliver_notification(outbox_id):
    outbox = db.session.get(NotificationOutbox, outbox_id)
    if outbox is None or outbox.status == "sent" or outbox.attempts >= 5:
        return
    endpoint = os.environ.get("ENTERPRISE_NOTIFY_API_URL", "").strip()
    if not endpoint:
        outbox.status = "demo_only"
        db.session.commit()
        return
    token = os.environ.get("ENTERPRISE_NOTIFY_API_TOKEN", "").strip()
    headers = {"Content-Type": "application/json", "Idempotency-Key": outbox.event_key}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps({"department": outbox.department, "message": outbox.message, "event_key": outbox.event_key}).encode("utf-8")
    outbox.attempts += 1
    try:
        req = Request(endpoint, data=body, headers=headers, method="POST")
        with urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8") or "{}")
            if response.status < 200 or response.status >= 300:
                raise ValueError(f"通知端點回應 HTTP {response.status}")
        outbox.status = "sent"
        outbox.provider_tx_id = str(payload.get("tx_id", "accepted"))[:120]
        audit = db.session.get(AuditLog, outbox.audit_id)
        if audit:
            audit.api_tx_id = outbox.provider_tx_id
        outbox.last_error = None
    except Exception as exc:
        outbox.status = "failed"
        outbox.last_error = str(exc)[:500]
        app.logger.exception("Enterprise notification delivery failed")
    db.session.commit()


def _build_department_triggers(dept_id, year, period, market):
    triggers = []
    code = DEPT_CODES[dept_id]
    if dept_id == "investment":
        if _metric_is_usable(market, "USD_TWD_Spot") and _metric_is_usable(market, "USD_TWD_Forward_1Y"):
            spot = _value(market, "USD_TWD_Spot", 32.0)
            forward = _value(market, "USD_TWD_Forward_1Y", 31.5)
            delta = (spot - forward) / spot if spot else 0
            if abs(delta - 0.02) >= 0.015:
                _record_alert(code, "FX_Hedging_Alert", f"避險成本偏離基準：{delta:.1%}。", year, period, triggers)
    elif dept_id == "risk_actuarial":
        if _metric_is_usable(market, "金融市場波動 (VIX)") and _value(market, "金融市場波動 (VIX)", 0) >= 35:
            _record_alert(code, "Risk_Auth_Alert", "VIX 觸及警戒，建議精算覆核。", year, period, triggers)
        if _metric_is_usable(market, "公司_RBC_資本適足率") and _value(market, "公司_RBC_資本適足率", 0) < 200:
            _record_alert(code, "Capital_Alert", "RBC 低於 200% 警戒門檻。", year, period, triggers)
    elif dept_id == "sales":
        if all(_metric_is_usable(market, k) for k in ("同業_FYP_平均成長率", "本公司_FYP_成長率")):
            industry = _value(market, "同業_FYP_平均成長率", 0)
            company = _value(market, "本公司_FYP_成長率", 0)
            if industry - company >= 0.05:
                _record_alert(code, "Sales_Divergence", "本公司 FYP 成長落後同業達警戒差距。", year, period, triggers)
    elif dept_id == "underwriting_claims":
        if _metric_is_usable(market, "醫療險理賠通報頻率_MoM") and _value(market, "醫療險理賠通報頻率_MoM", 0) >= 0.05:
            _record_alert(code, "Claims_Alert", "理賠通報頻率達警戒，建議覆核。", year, period, triggers)
    return triggers


def _convert_record(record, dept_id, market):
    spot = _value(market, "USD_TWD_Spot", 32.0)
    cpi_ratio = _value(market, "市場通膨指數 (CPI)", 100) / max(_value(market, "預算基準通膨 (CPI Base)", 100), 1e-9)
    medical_ratio = _value(market, "醫療公證費用指數 (Medical Index)", 100) / max(_value(market, "預算基準醫療指數 (Medical Base)", 100), 1e-9)
    idx_ratio = cpi_ratio if dept_id == "support" else medical_ratio
    fx = apply_market_context(dept_id, record.category, record.f_0_forecast, idx_ratio, record.a_transmission, record.currency, record.locked_ratio, spot, FX_BUDGET_BASE)
    b = convert_to_reporting_currency(record.b_annual_budget, record.currency, spot)
    b_period = convert_to_reporting_currency(record.b_period_budget, record.currency, spot)
    actual = convert_to_reporting_currency(record.a_actual, record.currency, spot)
    f0 = convert_to_reporting_currency(record.f_0_forecast, record.currency, spot)
    demand = convert_to_reporting_currency(record.d_new_demand, record.currency, spot)
    hist = convert_to_reporting_currency(record.h_historical, record.currency, spot) if record.h_historical is not None else None
    light, rate, forecast, diff = evaluate_traffic_light(b, b_period, actual, fx, demand, record.is_schedule)
    return {
        "item_name": record.item_name, "item_code": record.item_code, "category": record.category,
        "currency": record.currency, "locked": record.locked_ratio,
        "B": b, "B_period": b_period, "A": actual, "F0": f0, "Fx": fx, "D": demand, "H": hist,
        "baseline_forecast": actual + f0, "market_forecast": actual + fx,
        "final_forecast": forecast, "diff": diff, "diff_rate": rate,
        "light": light, "reason": record.overrun_reason,
    }


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username, active=True).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session["user_id"] = user.id
            session["csrf_token"] = secrets.token_urlsafe(32)
            destination = request.args.get("next", "")
            if not destination.startswith("/") or destination.startswith("//") or "\\" in destination or urlsplit(destination).netloc:
                destination = url_for("index")
            return redirect(destination)
        flash("帳號或密碼錯誤。", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/set_period", methods=["POST"])
def set_period():
    try:
        year = int(request.form.get("year", datetime.now().year))
        period = request.form.get("period", "YTD").strip().upper()
        if not 2000 <= year <= 2100 or period not in VALID_PERIODS:
            raise ValueError
        session["curr_year"], session["curr_period"] = year, period
    except (TypeError, ValueError):
        flash("年度或期間格式無效。", "warning")
    return redirect(url_for("index"))


@app.route("/")
def index():
    year, period = _period()
    user = _current_user()
    departments = {user.department: DEPT_NAMES[user.department]} if user.role != "admin" else DEPT_NAMES
    return render_template("index.html", market_data=_market_values(), depts=departments, curr_year=year, curr_period=period)


@app.route("/summary")
@admin_required
def company_summary():
    year, period = _period()
    records = BudgetItemModel.query.filter_by(year=year, period=period).all()
    market = _market_values()
    grouped, triggers = {}, []
    spot = _value(market, "USD_TWD_Spot", 32.0)
    cpi = _value(market, "市場通膨指數 (CPI)", 100) / max(_value(market, "預算基準通膨 (CPI Base)", 100), 1e-9)
    medical = _value(market, "醫療公證費用指數 (Medical Index)", 100) / max(_value(market, "預算基準醫療指數 (Medical Base)", 100), 1e-9)
    for record in records:
        dept_id = next((key for key, val in DEPT_CODES.items() if val == record.department), None)
        if not dept_id:
            continue
        name = DEPT_NAMES[dept_id]
        data = grouped.setdefault(name, {"B": 0, "A": 0, "F0": 0, "Fx": 0, "D": 0, "H": 0, "Forecast": 0, "item_count": 0, "h_missing_count": 0})
        row = _convert_record(record, dept_id, market)
        data["item_count"] += 1
        for key in ("B", "A", "F0", "Fx", "D"):
            data[key] += row[key]
        data["Forecast"] += row["final_forecast"] or 0
        if row["H"] is None:
            data["h_missing_count"] += 1
        else:
            data["H"] += row["H"]
        if row["B"] == 0 and (row["final_forecast"] or 0) > 0:
            triggers.append(f"{name}：未編預算但有預期支出，科目「{record.item_name}」。")
    total_b = sum(x["B"] for x in grouped.values())
    total_a = sum(x["A"] for x in grouped.values())
    total_f = sum(x["Forecast"] for x in grouped.values())
    for name, data in grouped.items():
        if data["h_missing_count"] == data["item_count"]:
            data["H_display"] = "缺漏無資料"
        elif data["h_missing_count"]:
            data["H_display"] = f"{data['H']:,.0f} (部分缺漏 {data['h_missing_count']}/{data['item_count']} 筆)"
        else:
            data["H_display"] = f"{data['H']:,.0f}"
        if data["B"] > 0 and (data["Forecast"] - data["B"]) / data["B"] >= 0.10:
            triggers.append(f"{name}：部門預估超支達 10% 以上。")
    ai_report = generate_executive_budget_report("全公司", grouped, triggers, market, is_global=True)
    return render_template("summary.html", summary_data=grouped, total_b=total_b, total_a=total_a, total_f=total_f,
                           total_diff=total_f-total_b, usage_rate=total_a/total_b if total_b else "n.a.", ai_report=ai_report,
                           triggers=triggers, market_data=market)


@app.route("/dept/<dept_id>/input", methods=["GET", "POST"])
@department_required
def department_input(dept_id):
    if dept_id not in DEPT_NAMES:
        abort(404)
    department = DEPT_CODES[dept_id]
    name = DEPT_NAMES[dept_id]
    year, period = _period()
    categories = DEPT_CATEGORIES[dept_id]
    market = _market_values()
    triggers = _build_department_triggers(dept_id, year, period, market)
    records = BudgetItemModel.query.filter_by(department=department, year=year, period=period).all()

    if request.method == "POST":
        errors = []
        form = request.form
        codes = set()
        try:
            for record in records:
                prefix = str(record.id)
                category = form.get(f"category_{prefix}", record.category)
                currency = form.get(f"currency_{prefix}", "TWD").upper()
                if category not in categories or currency not in {"TWD", "USD"}:
                    raise ValueError(f"{record.item_name}：類別或幣別無效")
                values = {
                    "b": _parse_float(form.get(f"b_{prefix}"), f"{record.item_name} 年預算"),
                    "b_period": _parse_float(form.get(f"b_per_{prefix}"), f"{record.item_name} 同期預算"),
                    "actual": _parse_float(form.get(f"a_{prefix}"), f"{record.item_name} 實際"),
                    "f0": _parse_float(form.get(f"f0_{prefix}"), f"{record.item_name} F0"),
                    "locked": _parse_float(form.get(f"locked_{prefix}"), f"{record.item_name} 鎖定比例", 0, 1),
                    "trans": _parse_float(form.get(f"a_trans_{prefix}"), f"{record.item_name} 傳導係數", 0, 1),
                    "d": _parse_float(form.get(f"d_{prefix}"), f"{record.item_name} 新增需求"),
                }
                schedule_value = form.get(f"is_schedule_{prefix}", "FALSE").upper()
                if schedule_value not in {"TRUE", "FALSE"}:
                    raise ValueError(f"{record.item_name} 的排程欄位只能是 TRUE 或 FALSE")
                idx = _value(market, "市場通膨指數 (CPI)", 100) / max(_value(market, "預算基準通膨 (CPI Base)", 100), 1e-9) if dept_id == "support" else _value(market, "醫療公證費用指數 (Medical Index)", 100) / max(_value(market, "預算基準醫療指數 (Medical Base)", 100), 1e-9)
                fx = apply_market_context(dept_id, category, values["f0"], idx, values["trans"], currency, values["locked"], _value(market, "USD_TWD_Spot", 32), FX_BUDGET_BASE)
                spot = _value(market, "USD_TWD_Spot", 32)
                light = evaluate_traffic_light(convert_to_reporting_currency(values["b"], currency, spot), convert_to_reporting_currency(values["b_period"], currency, spot), convert_to_reporting_currency(values["actual"], currency, spot), fx, convert_to_reporting_currency(values["d"], currency, spot), schedule_value == "TRUE")[0]
                reason = form.get(f"reason_{prefix}", "").strip()
                if "🔴" in light and not reason:
                    raise ValueError(f"{record.item_name} 為紅燈，請填寫超支說明")
                record.item_name = record.item_name.strip()
                record.category = category
                record.b_annual_budget, record.b_period_budget = values["b"], values["b_period"]
                record.a_actual, record.f_0_forecast = values["actual"], values["f0"]
                record.currency, record.locked_ratio = currency, values["locked"]
                record.a_transmission, record.d_new_demand = values["trans"], values["d"]
                record.h_historical = _parse_optional(form.get(f"h_{prefix}"))
                record.overrun_reason = reason[:255] or None
                record.is_schedule = schedule_value == "TRUE"
                codes.add(record.item_code)

            names = form.getlist("new_item_name[]")
            for i, raw_name in enumerate(names):
                item_name = raw_name.strip()
                if not item_name:
                    continue
                item_code = (form.getlist("new_item_code[]")[i] if i < len(form.getlist("new_item_code[]")) else "").strip()
                item_code = item_code or f"NEW_{uuid.uuid4().hex[:12]}"
                if item_code in codes or BudgetItemModel.query.filter_by(year=year, period=period, department=department, item_code=item_code).first():
                    raise ValueError(f"科目代碼 {item_code} 重複")
                category = form.getlist("new_item_category[]")[i] if i < len(form.getlist("new_item_category[]")) else categories[0]
                currency = form.getlist("new_currency[]")[i] if i < len(form.getlist("new_currency[]")) else "TWD"
                if category not in categories or currency not in {"TWD", "USD"}:
                    raise ValueError(f"{item_name}：類別或幣別無效")
                def listed(field):
                    items = form.getlist(field)
                    return items[i] if i < len(items) else ""
                b = _parse_float(listed("new_b[]"), f"{item_name} 年預算")
                b_period = _parse_float(listed("new_b_per[]"), f"{item_name} 同期預算")
                actual = _parse_float(listed("new_a[]"), f"{item_name} 實際")
                f0 = _parse_float(listed("new_f0[]"), f"{item_name} F0")
                locked = _parse_float(listed("new_locked[]"), f"{item_name} 鎖定比例", 0, 1)
                trans = _parse_float(listed("new_a_trans[]"), f"{item_name} 傳導係數", 0, 1)
                demand = _parse_float(listed("new_d[]"), f"{item_name} 新增需求")
                schedule_text = listed("new_is_schedule[]").upper()
                if schedule_text not in {"TRUE", "FALSE"}:
                    raise ValueError(f"{item_name} 的排程欄位只能是 TRUE 或 FALSE")
                scheduled = schedule_text == "TRUE"
                index_ratio = _value(market, "市場通膨指數 (CPI)", 100) / max(_value(market, "預算基準通膨 (CPI Base)", 100), 1e-9) if dept_id == "support" else _value(market, "醫療公證費用指數 (Medical Index)", 100) / max(_value(market, "預算基準醫療指數 (Medical Base)", 100), 1e-9)
                spot = _value(market, "USD_TWD_Spot", 32)
                fx = apply_market_context(dept_id, category, f0, index_ratio, trans, currency, locked, spot, FX_BUDGET_BASE)
                light = evaluate_traffic_light(convert_to_reporting_currency(b, currency, spot), convert_to_reporting_currency(b_period, currency, spot), convert_to_reporting_currency(actual, currency, spot), fx, convert_to_reporting_currency(demand, currency, spot), scheduled)[0]
                reason = listed("new_reason[]").strip()
                if "🔴" in light and not reason:
                    raise ValueError(f"{item_name} 為紅燈，請填寫超支說明")
                db.session.add(BudgetItemModel(
                    year=year, period=period, department=department, item_code=item_code, item_name=item_name[:100], category=category,
                    is_schedule=scheduled, b_annual_budget=b, b_period_budget=b_period, a_actual=actual, f_0_forecast=f0,
                    currency=currency, locked_ratio=locked, a_transmission=trans, d_new_demand=demand,
                    h_historical=_parse_optional(listed("new_h[]")), overrun_reason=reason[:255] or None,
                ))
                codes.add(item_code)
            db.session.commit()
            records = BudgetItemModel.query.filter_by(department=department, year=year, period=period).all()
            rows = [_convert_record(record, dept_id, market) for record in records]
            report = generate_executive_budget_report(name, rows, triggers, market)
            return render_template("result.html", dept_id=dept_id, dept_name=name, results=rows, triggers=triggers, ai_report=report, market_data=market)
        except (ValueError, IndexError) as exc:
            db.session.rollback()
            flash(str(exc), "danger")
        except IntegrityError:
            db.session.rollback()
            flash("資料庫資料衝突；請重新載入並確認代碼後再試。", "danger")
        except Exception:
            db.session.rollback()
            app.logger.exception("Department budget save failed")
            flash("資料儲存失敗，變更已取消；請稍後重試或聯絡管理者。", "danger")

    return render_template("input_form.html", dept_id=dept_id, dept_name=name, records=records, available_categories=categories, form_data=request.form if request.method == "POST" else {})


@app.route("/imports/template")
@admin_required
def download_import_template():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for sheet in IMPORT_SHEETS:
            pd.DataFrame(columns=IMPORT_COLUMNS).to_excel(writer, sheet_name=sheet, index=False)
    output.seek(0)
    return send_file(output, download_name="budget_import_v18.xlsx", as_attachment=True)


@app.route("/imports")
@admin_required
def import_batches():
    batches = BudgetImportBatch.query.order_by(BudgetImportBatch.id.desc()).limit(50).all()
    return render_template("imports.html", batches=batches)


@app.route("/notifications")
@admin_required
def notification_status():
    deliveries = NotificationOutbox.query.order_by(NotificationOutbox.id.desc()).limit(100).all()
    return render_template("notifications.html", deliveries=deliveries)


@app.route("/notifications/retry", methods=["POST"])
@admin_required
def retry_notifications():
    pending = NotificationOutbox.query.filter(
        NotificationOutbox.status.in_(["pending", "failed", "demo_only"]),
        NotificationOutbox.attempts < 5,
    ).order_by(NotificationOutbox.id.asc()).all()
    for item in pending:
        _deliver_notification(item.id)
    flash(f"已處理 {len(pending)} 筆待送／失敗通知。未設定通知端點的項目仍標示為示範。", "info")
    return redirect(url_for("notification_status"))


@app.route("/imports/upload", methods=["POST"])
@admin_required
def upload_budget_workbook():
    file = request.files.get("workbook")
    if not file or not file.filename or not file.filename.lower().endswith(".xlsx"):
        flash("請選擇 .xlsx 活頁簿。", "danger")
        return redirect(url_for("import_batches"))
    try:
        workbook = pd.ExcelFile(io.BytesIO(file.read()), engine="openpyxl")
    except Exception:
        flash("無法解析活頁簿，請確認是有效的 XLSX 檔案。", "danger")
        return redirect(url_for("import_batches"))
    missing = [sheet for sheet in IMPORT_SHEETS if sheet not in workbook.sheet_names]
    if missing:
        flash("缺少必要工作表：" + ", ".join(missing), "danger")
        return redirect(url_for("import_batches"))

    market = _market_values()
    spot = _value(market, "USD_TWD_Spot", 32)
    cpi = _value(market, "市場通膨指數 (CPI)", 100) / max(_value(market, "預算基準通膨 (CPI Base)", 100), 1e-9)
    medical = _value(market, "醫療公證費用指數 (Medical Index)", 100) / max(_value(market, "預算基準醫療指數 (Medical Base)", 100), 1e-9)
    allowed = {DEPT_CODES[key]: (key, DEPT_CATEGORIES[key]) for key in DEPT_NAMES}
    errors, valid_rows, preview_rows, seen = [], [], [], set()
    for sheet in IMPORT_SHEETS:
        dept, (dept_id, categories) = sheet, allowed[sheet]
        frame = pd.read_excel(workbook, sheet_name=sheet, dtype=object)
        frame.columns = [str(col).strip() for col in frame.columns]
        missing_cols = [col for col in IMPORT_COLUMNS if col not in frame.columns]
        if missing_cols:
            errors.append({"sheet": sheet, "row": 1, "column": "欄位", "message": "缺少欄位：" + ", ".join(missing_cols)})
            continue
        for idx, raw in frame.iterrows():
            cells = raw.to_dict()
            if all(pd.isna(cells.get(col)) or str(cells.get(col)).strip() == "" for col in IMPORT_COLUMNS):
                continue
            row_no = int(idx) + 2
            try:
                year_number = float(cells["Year"])
                if not math.isfinite(year_number) or not year_number.is_integer():
                    raise ValueError("Year 必須是整數")
                year = int(year_number)
                if not 2000 <= year <= 2100:
                    raise ValueError("Year 須介於 2000 至 2100")
                period = str(cells["Period"]).strip().upper()
                if period not in VALID_PERIODS:
                    raise ValueError("Period 格式無效")
                code = str(cells["ItemCode"]).strip()
                name = str(cells["Item"]).strip()
                if not code or not name:
                    raise ValueError("科目代碼與科目名稱必填")
                if len(name) > 100 or len(code) > 50:
                    raise ValueError("科目代碼或名稱超過欄位長度")
                unique = (year, period, dept, code)
                if unique in seen:
                    raise ValueError(f"批次內重複科目代碼：{code}")
                seen.add(unique)
                category = str(cells["Category"]).strip()
                currency = str(cells["Currency"]).strip().upper()
                if category not in categories or currency not in {"TWD", "USD"}:
                    raise ValueError("類別或幣別無效")
                b = _parse_float(cells["B_Annual"], "年度預算")
                bp = _parse_float(cells["B_Period"], "同期預算")
                actual = _parse_float(cells["A_Actual"], "實際支出")
                f0 = _parse_float(cells["F0_Forecast"], "基準預測")
                locked = _parse_float(cells["Locked_Ratio"], "鎖定比例", 0, 1)
                trans = _parse_float(cells["A_Trans"], "傳導係數", 0, 1)
                demand = _parse_float(cells["D_NewDemand"], "新增需求")
                sched_raw = str(cells["IsSchedule"]).strip().upper()
                if sched_raw not in {"TRUE", "FALSE"}:
                    raise ValueError("IsSchedule 只能填 TRUE 或 FALSE")
                index_ratio = cpi if dept_id == "support" else medical
                fx = apply_market_context(dept_id, category, f0, index_ratio, trans, currency, locked, spot, FX_BUDGET_BASE)
                light = evaluate_traffic_light(convert_to_reporting_currency(b, currency, spot), convert_to_reporting_currency(bp, currency, spot), convert_to_reporting_currency(actual, currency, spot), fx, convert_to_reporting_currency(demand, currency, spot), sched_raw == "TRUE")[0]
                reason = str(cells.get("Reason", "") or "").strip()
                if "🔴" in light and not reason:
                    raise ValueError("紅燈資料必須填寫 Reason")
                row = {
                    "year": year, "period": period, "department": dept, "item_code": code,
                    "item_name": name, "category": category, "is_schedule": sched_raw == "TRUE",
                    "b_annual_budget": b, "b_period_budget": bp, "a_actual": actual, "f_0_forecast": f0,
                    "currency": currency, "locked_ratio": locked, "a_transmission": trans,
                    "d_new_demand": demand, "h_historical": _parse_optional(cells.get("H_Hist")),
                    "overrun_reason": reason[:255] or None, "source_row": row_no,
                }
                valid_rows.append(row)
                if len(preview_rows) < 100:
                    preview_rows.append(row)
            except Exception as exc:
                errors.append({"sheet": sheet, "row": row_no, "column": "資料驗證", "message": str(exc)[:300]})
    if not valid_rows and not errors:
        errors.append({"sheet": "全部", "row": 0, "column": "資料", "message": "活頁簿沒有任何預算資料列"})
    if errors:
        valid_rows = []

    batch = BudgetImportBatch(
        original_filename=secure_filename(file.filename)[:255] or "budget.xlsx",
        row_count=len(valid_rows), error_count=len(errors), validation_errors=errors,
    )
    try:
        db.session.add(batch)
        db.session.flush()
        db.session.add_all(ImportedBudgetItem(batch_id=batch.id, **row) for row in valid_rows)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("匯入預覽無法保存，請檢查資料庫狀態。", "danger")
        return redirect(url_for("import_batches"))
    return render_template("imports.html", batches=BudgetImportBatch.query.order_by(BudgetImportBatch.id.desc()).limit(50).all(), preview_batch=batch, preview_rows=preview_rows, preview_errors=errors[:100])


@app.route("/imports/<int:batch_id>/confirm", methods=["POST"])
@admin_required
def confirm_import_batch(batch_id):
    batch = db.get_or_404(BudgetImportBatch, batch_id)
    if batch.status != "preview" or batch.error_count or batch.row_count <= 0:
        abort(400)
    items = ImportedBudgetItem.query.filter_by(batch_id=batch.id).all()
    try:
        for item in items:
            current = BudgetItemModel.query.filter_by(year=item.year, period=item.period, department=item.department, item_code=item.item_code).first()
            fields = (
                "item_name", "category", "is_schedule", "b_annual_budget", "b_period_budget", "a_actual",
                "f_0_forecast", "currency", "locked_ratio", "a_transmission", "d_new_demand", "h_historical", "overrun_reason",
            )
            if current:
                for field in fields:
                    setattr(current, field, getattr(item, field))
            else:
                db.session.add(BudgetItemModel(
                    year=item.year, period=item.period, department=item.department, item_code=item.item_code,
                    **{field: getattr(item, field) for field in fields},
                ))
        batch.status = "confirmed"
        db.session.commit()
        flash("匯入已完成。", "success")
    except Exception:
        db.session.rollback()
        app.logger.exception("Budget import transaction rolled back")
        flash("匯入未完成，所有變更已取消；請檢查資料衝突後重試。", "danger")
    return redirect(url_for("import_batches"))


@app.errorhandler(400)
def bad_request(error):
    return render_template("message.html", title="請求無效", message=getattr(error, "description", "請求格式錯誤")), 400


@app.errorhandler(403)
def forbidden(error):
    return render_template("message.html", title="沒有存取權", message="此頁面只開放給授權帳號。"), 403


@app.errorhandler(404)
def not_found(error):
    return render_template("message.html", title="找不到頁面", message="請確認網址或返回首頁。"), 404


def init_db():
    with app.app_context():
        db.create_all()
        _bootstrap_users()


init_db()
if os.environ.get("ENTERPRISE_NOTIFY_API_URL"):
    with app.app_context():
        pending_notifications = NotificationOutbox.query.filter_by(status="pending").filter(NotificationOutbox.attempts < 5).all()
        for pending_notification in pending_notifications:
            _deliver_notification(pending_notification.id)
if os.environ.get("ENABLE_MARKET_SCHEDULER", "true").lower() == "true":
    init_scheduler()

if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5000")), debug=False)
