from flask import Blueprint, session, request, render_template, redirect, url_for, flash, jsonify, current_app, Response
from flask_login import login_required, current_user
from translations import trans
import utils
from bson import ObjectId
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from flask_wtf import FlaskForm
from wtforms import DateField, StringField, SubmitField, SelectField
from wtforms.validators import Optional
import csv
import logging

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

class ReportForm(FlaskForm):
    start_date = DateField(trans('reports_start_date', default='Start Date'), validators=[Optional()])
    end_date = DateField(trans('reports_end_date', default='End Date'), validators=[Optional()])
    submit = SubmitField(trans('reports_generate_report', default='Generate Report'))

class CustomerReportForm(FlaskForm):
    role = SelectField('User Role', choices=[('', 'All'), ('personal', 'Personal'), ('trader', 'Trader'), ('agent', 'Agent'), ('admin', 'Admin')], validators=[Optional()])
    format = SelectField('Format', choices=[('html', 'HTML'), ('pdf', 'PDF'), ('csv', 'CSV')], default='html')
    submit = SubmitField('Generate Report')

class DebtorsCreditorsReportForm(FlaskForm):
    start_date = DateField(trans('reports_start_date', default='Start Date'), validators=[Optional()])
    end_date = DateField(trans('reports_end_date', default='End Date'), validators=[Optional()])
    record_type = SelectField('Record Type', choices=[('', 'All'), ('debtor', 'Debtor'), ('creditor', 'Creditor')], validators=[Optional()])
    submit = SubmitField(trans('reports_generate_report', default='Generate Report'))

class TaxObligationsReportForm(FlaskForm):
    start_date = DateField(trans('reports_start_date', default='Start Date'), validators=[Optional()])
    end_date = DateField(trans('reports_end_date', default='End Date'), validators=[Optional()])
    status = SelectField('Status', choices=[('', 'All'), ('pending', 'Pending'), ('paid', 'Paid'), ('overdue', 'Overdue')], validators=[Optional()])
    submit = SubmitField(trans('reports_generate_report', default='Generate Report'))

class BudgetPerformanceReportForm(FlaskForm):
    start_date = DateField(trans('reports_start_date', default='Start Date'), validators=[Optional()])
    end_date = DateField(trans('reports_end_date', default='End Date'), validators=[Optional()])
    submit = SubmitField(trans('reports_generate_report', default='Generate Report'))

def to_dict_budget(record):
    if not record:
        return {'surplus_deficit': None, 'savings_goal': None}
    return {
        'id': str(record.get('_id', '')),
        'income': record.get('income', 0),
        'fixed_expenses': record.get('fixed_expenses', 0),
        'variable_expenses': record.get('variable_expenses', 0),
        'savings_goal': record.get('savings_goal', 0),
        'surplus_deficit': record.get('surplus_deficit', 0),
        'housing': record.get('housing', 0),
        'food': record.get('food', 0),
        'transport': record.get('transport', 0),
        'dependents': record.get('dependents', 0),
        'miscellaneous': record.get('miscellaneous', 0),
        'others': record.get('others', 0),
        'created_at': utils.format_date(record.get('created_at'), format_type='iso')
    }

def to_dict_bill(record):
    if not record:
        return {'amount': None, 'status': None}
    return {
        'id': str(record.get('_id', '')),
        'bill_name': record.get('bill_name', ''),
        'amount': record.get('amount', 0),
        'due_date': utils.format_date(record.get('due_date'), format_type='iso'),
        'frequency': record.get('frequency', ''),
        'category': record.get('category', ''),
        'status': record.get('status', ''),
        'send_email': record.get('send_email', False),
        'reminder_days': record.get('reminder_days'),
        'user_email': record.get('user_email', ''),
        'first_name': record.get('first_name', '')
    }

def to_dict_tax_reminder(record):
    if not record:
        return {'tax_type': None, 'amount': None}
    return {
        'id': str(record.get('_id', '')),
        'user_id': record.get('user_id', ''),
        'tax_type': record.get('tax_type', ''),
        'due_date': utils.format_date(record.get('due_date'), format_type='iso'),
        'amount': record.get('amount', 0),
        'status': record.get('status', ''),
        'created_at': utils.format_date(record.get('created_at'), format_type='iso'),
        'notification_id': record.get('notification_id'),
        'sent_at': utils.format_date(record.get('sent_at'), format_type='iso') if record.get('sent_at') else None,
        'payment_location_id': record.get('payment_location_id')
    }

def to_dict_record(record):
    if not record:
        return {'name': None, 'amount_owed': None}
    return {
        'id': str(record.get('_id', '')),
        'user_id': record.get('user_id', ''),
        'type': record.get('type', ''),
        'name': record.get('name', ''),
        'contact': record.get('contact', ''),
        'amount_owed': record.get('amount_owed', 0),
        'description': record.get('description', ''),
        'reminder_count': record.get('reminder_count', 0),
        'created_at': utils.format_date(record.get('created_at'), format_type='iso'),
        'updated_at': utils.format_date(record.get('updated_at'), format_type='iso') if record.get('updated_at') else None
    }

def to_dict_cashflow(record):
    if not record:
        return {'party_name': None, 'amount': None}
    result = {
        'id': str(record.get('_id', '')),
        'user_id': record.get('user_id', ''),
        'type': record.get('type', ''),
        'party_name': record.get('party_name', ''),
        'amount': record.get('amount', 0),
        'method': record.get('method', ''),
        'created_at': utils.format_date(record.get('created_at'), format_type='iso'),
        'updated_at': utils.format_date(record.get('updated_at'), format_type='iso') if record.get('updated_at') else None
    }
    # Convert datetime.date to datetime.datetime for BSON compatibility
    for key, value in result.items():
        if isinstance(value, date) and not isinstance(value, datetime):
            result[key] = datetime.combine(value, datetime.min.time())
    return result

@reports_bp.route('/')
@login_required
@utils.requires_role('trader')
def index():
    """Display report selection page."""
    try:
        return render_template(
            'reports/index.html',
            title=utils.trans('reports_index', default='Reports', lang=session.get('lang', 'en'))
        )
    except Exception as e:
        logger.error(f"Error loading reports index for user {current_user.id}: {str(e)}", exc_info=True)
        flash(trans('reports_load_error', default='An error occurred'), 'danger')
        return redirect(url_for('dashboard.index'))

@reports_bp.route('/profit_loss', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def profit_loss():
    """Generate profit/loss report with filters."""
    form = ReportForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate a report. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    cashflows = []
    query = {} if utils.is_admin() else {'user_id': str(current_user.id)}
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            if form.start_date.data:
                query['created_at'] = {'$gte': form.start_date.data}
            if form.end_date.data:
                query['created_at'] = query.get('created_at', {}) | {'$lte': form.end_date.data}
            cashflows = [to_dict_cashflow(cf) for cf in db.cashflows.find(query).sort('created_at', -1)]
            output_format = request.form.get('format', 'html')
            if output_format == 'pdf':
                return generate_profit_loss_pdf(cashflows)
            elif output_format == 'csv':
                return generate_profit_loss_csv(cashflows)
            if not utils.is_admin():
                user_query = utils.get_user_query(str(current_user.id))
                db.users.update_one(
                    user_query,
                    {'$inc': {'ficore_credit_balance': -1}}
                )
                db.ficore_ficore_credit_transactions.insert_one({
                    'user_id': str(current_user.id),
                    'amount': -1,
                    'type': 'spend',
                    'date': datetime.utcnow(),
                    'ref': 'Profit/Loss report generation (Ficore Credits)'
                })
        except Exception as e:
            logger.error(f"Error generating profit/loss report for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    else:
        try:
            db = utils.get_mongo_db()
            cashflows = [to_dict_cashflow(cf) for cf in db.cashflows.find(query).sort('created_at', -1)]
        except Exception as e:
            logger.error(f"Error fetching cashflows for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    return render_template(
        'reports/profit_loss.html',
        form=form,
        cashflows=cashflows,
        title=utils.trans('reports_profit_loss', default='Profit/Loss Report', lang=session.get('lang', 'en'))
    )

@reports_bp.route('/debtors_creditors', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def debtors_creditors():
    """Generate debtors/creditors report with filters."""
    form = DebtorsCreditorsReportForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate a report. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    records = []
    query = {} if utils.is_admin() else {'user_id': str(current_user.id)}
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            if form.start_date.data:
                query['created_at'] = {'$gte': form.start_date.data}
            if form.end_date.data:
                query['created_at'] = query.get('created_at', {}) | {'$lte': form.end_date.data}
            if form.record_type.data:
                query['type'] = form.record_type.data
            records = [to_dict_record(r) for r in db.records.find(query).sort('created_at', -1)]
            output_format = request.form.get('format', 'html')
            if output_format == 'pdf':
                return generate_debtors_creditors_pdf(records)
            elif output_format == 'csv':
                return generate_debtors_creditors_csv(records)
            if not utils.is_admin():
                user_query = utils.get_user_query(str(current_user.id))
                db.users.update_one(
                    user_query,
                    {'$inc': {'ficore_credit_balance': -1}}
                )
                db.ficore_ficore_credit_transactions.insert_one({
                    'user_id': str(current_user.id),
                    'amount': -1,
                    'type': 'spend',
                    'date': datetime.utcnow(),
                    'ref': 'Debtors/Creditors report generation (Ficore Credits)'
                })
        except Exception as e:
            logger.error(f"Error generating debtors/creditors report for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    else:
        try:
            db = utils.get_mongo_db()
            records = [to_dict_record(r) for r in db.records.find(query).sort('created_at', -1)]
        except Exception as e:
            logger.error(f"Error fetching records for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    return render_template(
        'reports/debtors_creditors.html',
        form=form,
        records=records,
        title=utils.trans('reports_debtors_creditors', default='Debtors/Creditors Report', lang=session.get('lang', 'en'))
    )

@reports_bp.route('/tax_obligations', methods=['GET', 'POST'])
@login_required
@utils.requires_role('trader')
def tax_obligations():
    """Generate tax obligations report with filters."""
    form = TaxObligationsReportForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate a report. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    tax_reminders = []
    query = {} if utils.is_admin() else {'user_id': str(current_user.id)}
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            if form.start_date.data:
                query['due_date'] = {'$gte': form.start_date.data}
            if form.end_date.data:
                query['due_date'] = query.get('due_date', {}) | {'$lte': form.end_date.data}
            if form.status.data:
                query['status'] = form.status.data
            tax_reminders = [to_dict_tax_reminder(tr) for tr in db.tax_reminders.find(query).sort('due_date', 1)]
            output_format = request.form.get('format', 'html')
            if output_format == 'pdf':
                return generate_tax_obligations_pdf(tax_reminders)
            elif output_format == 'csv':
                return generate_tax_obligations_csv(tax_reminders)
            if not utils.is_admin():
                user_query = utils.get_user_query(str(current_user.id))
                db.users.update_one(
                    user_query,
                    {'$inc': {'ficore_credit_balance': -1}}
                )
                db.ficore_ficore_credit_transactions.insert_one({
                    'user_id': str(current_user.id),
                    'amount': -1,
                    'type': 'spend',
                    'date': datetime.utcnow(),
                    'ref': 'Tax Obligations report generation (Ficore Credits)'
                })
        except Exception as e:
            logger.error(f"Error generating tax obligations report for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    else:
        try:
            db = utils.get_mongo_db()
            tax_reminders = [to_dict_tax_reminder(tr) for tr in db.tax_reminders.find(query).sort('due_date', 1)]
        except Exception as e:
            logger.error(f"Error fetching tax reminders for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    return render_template(
        'reports/tax_obligations.html',
        form=form,
        tax_reminders=tax_reminders,
        title=utils.trans('reports_tax_obligations', default='Tax Obligations Report', lang=session.get('lang', 'en'))
    )

@reports_bp.route('/budget_performance', methods=['GET', 'POST'])
@login_required
@utils.requires_role('personal')
def budget_performance():
    """Generate budget performance report with filters."""
    form = BudgetPerformanceReportForm()
    if not utils.is_admin() and not utils.check_ficore_credit_balance(1):
        flash(trans('debtors_insufficient_credits', default='Insufficient credits to generate a report. Request more credits.'), 'danger')
        return redirect(url_for('credits.request_credits'))
    budget_data = []
    query = {} if utils.is_admin() else {'user_id': str(current_user.id)}
    if form.validate_on_submit():
        try:
            db = utils.get_mongo_db()
            budget_query = query.copy()
            cashflow_query = query.copy()
            if form.start_date.data:
                budget_query['created_at'] = {'$gte': form.start_date.data}
                cashflow_query['created_at'] = {'$gte': form.start_date.data}
            if form.end_date.data:
                budget_query['created_at'] = budget_query.get('created_at', {}) | {'$lte': form.end_date.data}
                cashflow_query['created_at'] = cashflow_query.get('created_at', {}) | {'$lte': form.end_date.data}
            budgets = list(db.budgets.find(budget_query).sort('created_at', -1))
            cashflows = [to_dict_cashflow(cf) for cf in db.cashflows.find(cashflow_query).sort('created_at', -1)]
            for budget in budgets:
                budget_dict = to_dict_budget(budget)
                actual_income = sum(cf['amount'] for cf in cashflows if cf['type'] == 'receipt')
                actual_expenses = sum(cf['amount'] for cf in cashflows if cf['type'] == 'payment')
                budget_dict['actual_income'] = actual_income
                budget_dict['actual_expenses'] = actual_expenses
                budget_dict['income_variance'] = actual_income - budget_dict['income']
                budget_dict['expense_variance'] = actual_expenses - (budget_dict['fixed_expenses'] + budget_dict['variable_expenses'])
                budget_data.append(budget_dict)
            output_format = request.form.get('format', 'html')
            if output_format == 'pdf':
                return generate_budget_performance_pdf(budget_data)
            elif output_format == 'csv':
                return generate_budget_performance_csv(budget_data)
            if not utils.is_admin():
                user_query = utils.get_user_query(str(current_user.id))
                db.users.update_one(
                    user_query,
                    {'$inc': {'ficore_credit_balance': -1}}
                )
                db.ficore_ficore_credit_transactions.insert_one({
                    'user_id': str(current_user.id),
                    'amount': -1,
                    'type': 'spend',
                    'date': datetime.utcnow(),
                    'ref': 'Budget Performance report generation (Ficore Credits)'
                })
        except Exception as e:
            logger.error(f"Error generating budget performance report for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    else:
        try:
            db = utils.get_mongo_db()
            budgets = list(db.budgets.find(query).sort('created_at', -1))
            cashflows = [to_dict_cashflow(cf) for cf in db.cashflows.find(query).sort('created_at', -1)]
            for budget in budgets:
                budget_dict = to_dict_budget(budget)
                actual_income = sum(cf['amount'] for cf in cashflows if cf['type'] == 'receipt')
                actual_expenses = sum(cf['amount'] for cf in cashflows if cf['type'] == 'payment')
                budget_dict['actual_income'] = actual_income
                budget_dict['actual_expenses'] = actual_expenses
                budget_dict['income_variance'] = actual_income - budget_dict['income']
                budget_dict['expense_variance'] = actual_expenses - (budget_dict['fixed_expenses'] + budget_dict['variable_expenses'])
                budget_data.append(budget_dict)
        except Exception as e:
            logger.error(f"Error fetching budget data for user {current_user.id}: {str(e)}", exc_info=True)
            flash(trans('reports_generation_error', default='An error occurred'), 'danger')
    return render_template(
        'reports/budget_performance.html',
        form=form,
        budget_data=budget_data,
        title=utils.trans('reports_budget_performance', default='Budget Performance Report', lang=session.get('lang', 'en'))
    )

@reports_bp.route('/admin/customer-reports', methods=['GET', 'POST'])
@login_required
@utils.requires_role('admin')
def customer_reports():
    """Generate customer reports for admin."""
    form = CustomerReportForm()
    if form.validate_on_submit():
        role = form.role.data if form.role.data else None
        report_format = form.format.data
        try:
            db = utils.get_mongo_db()
            pipeline = [
                {'$match': {'role': role}} if role else {},
                {'$lookup': {
                    'from': 'budgets',
                    'let': {'user_id': '$_id'},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$user_id', '$$user_id']}}},
                        {'$sort': {'created_at': -1}},
                        {'$limit': 1}
                    ],
                    'as': 'latest_budget'
                }},
                {'$lookup': {
                    'from': 'bills',
                    'let': {'user_id': '$_id'},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$user_id', '$$user_id']}}},
                        {'$group': {
                            '_id': '$status',
                            'count': {'$sum': 1}
                        }}
                    ],
                    'as': 'bill_status_counts'
                }},
                {'$lookup': {
                    'from': 'learning_materials',
                    'let': {'user_id': '$_id'},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$user_id', '$$user_id']}}},
                        {'$group': {
                            '_id': None,
                            'total_lessons_completed': {'$sum': {'$size': '$lessons_completed'}}
                        }}
                    ],
                    'as': 'learning_progress'
                }},
                {'$lookup': {
                    'from': 'tax_reminders',
                    'let': {'user_id': '$_id'},
                    'pipeline': [
                        {'$match': {'$expr': {'$eq': ['$user_id', '$$user_id']}, 'due_date': {'$gte': datetime.utcnow()}}},
                        {'$sort': {'due_date': 1}},
                        {'$limit': 1}
                    ],
                    'as': 'next_tax_reminder'
                }},
            ]
            users = list(db.users.aggregate(pipeline))
            report_data = []
            for user in users:
                budget = to_dict_budget(user['latest_budget'][0] if user['latest_budget'] else None)
                bill_counts = {status['_id']: status['count'] for status in user['bill_status_counts']} if user['bill_status_counts'] else {'pending': 0, 'paid': 0, 'overdue': 0}
                learning_progress = user['learning_progress'][0]['total_lessons_completed'] if user['learning_progress'] else 0
                tax_reminder = to_dict_tax_reminder(user['next_tax_reminder'][0] if user['next_tax_reminder'] else None)
                data = {
                    'username': user['_id'],
                    'email': user.get('email', ''),
                    'role': user.get('role', ''),
                    'ficore_credit_balance': user.get('ficore_credit_balance', 0),
                    'language': user.get('language', 'en'),
                    'budget_income': budget['income'] if budget['income'] is not None else '-',
                    'budget_fixed_expenses': budget['fixed_expenses'] if budget['fixed_expenses'] is not None else '-',
                    'budget_variable_expenses': budget['variable_expenses'] if budget['variable_expenses'] is not None else '-',
                    'budget_surplus_deficit': budget['surplus_deficit'] if budget['surplus_deficit'] is not None else '-',
                    'pending_bills': bill_counts.get('pending', 0),
                    'paid_bills': bill_counts.get('paid', 0),
                    'overdue_bills': bill_counts.get('overdue', 0),
                    'lessons_completed': learning_progress,
                    'next_tax_due_date': utils.format_date(tax_reminder['due_date']) if tax_reminder['due_date'] else '-',
                    'next_tax_amount': tax_reminder['amount'] if tax_reminder['amount'] is not None else '-'
                }
                report_data.append(data)
            if report_format == 'html':
                return render_template('reports/customer_reports.html', report_data=report_data, title='Facore Credits')
            elif report_format == 'pdf':
                return generate_customer_report_pdf(report_data)
            elif report_format == 'csv':
                return generate_customer_report_csv(report_data)
        except Exception as e:
            logger.error(f"Error generating customer report: {str(e)}", exc_info=True)
            flash('An error occurred while generating the report', 'danger')
    return render_template('reports/customer_reports_form.html', form=form, title='Generate Customer Report')

def generate_profit_loss_pdf(cashflows):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, 10.5 * inch, trans('reports_profit_loss_report', default='Profit/Loss Report'))
    p.drawString(1 * inch, 10.2 * inch, f"{trans('reports_generated_on', default='Generated on')}: {utils.format_date(datetime.utcnow())}")
    y = 9.5 * inch
    p.setFillColor(colors.black)
    p.drawString(1 * inch, y, trans('general_date', default='Date'))
    p.drawString(2.5 * inch, y, trans('general_party_name', default='Party Name'))
    p.drawString(4 * inch, y, trans('general_type', default='Type'))
    p.drawString(5 * inch, y, trans('general_amount', default='Amount'))
    y -= 0.3 * inch
    total_income = 0
    total_expense = 0
    for t in cashflows:
        p.drawString(1 * inch, y, utils.format_date(t['created_at']))
        p.drawString(2.5 * inch, y, t['party_name'])
        p.drawString(4 * inch, y, trans(t['type'], default=t['type']))
        p.drawString(5 * inch, y, utils.format_currency(t['amount']))
        if t['type'] == 'receipt':
            total_income += t['amount']
        else:
            total_expense += t['amount']
        y -= 0.3 * inch
        if y < 1 * inch:
            p.showPage()
            y = 10.5 * inch
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_total_income', default='Total Income')}: {utils.format_currency(total_income)}")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_total_expense', default='Total Expense')}: {utils.format_currency(total_expense)}")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_net_profit', default='Net Profit')}: {utils.format_currency(total_income - total_expense)}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=profit_loss.pdf'})

def generate_profit_loss_csv(cashflows):
    output = []
    output.append([trans('general_date', default='Date'), trans('general_party_name', default='Party Name'), trans('general_type', default='Type'), trans('general_amount', default='Amount')])
    total_income = 0
    total_expense = 0
    for t in cashflows:
        output.append([utils.format_date(t['created_at']), t['party_name'], trans(t['type'], default=t['type']), utils.format_currency(t['amount'])])
        if t['type'] == 'receipt':
            total_income += t['amount']
        else:
            total_expense += t['amount']
    output.append(['', '', '', f"{trans('reports_total_income', default='Total Income')}: {utils.format_currency(total_income)}"])
    output.append(['', '', '', f"{trans('reports_total_expense', default='Total Expense')}: {utils.format_currency(total_expense)}"])
    output.append(['', '', '', f"{trans('reports_net_profit', default='Net Profit')}: {utils.format_currency(total_income - total_expense)}"])
    buffer = BytesIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerows(output)
    buffer.seek(0)
    return Response(buffer, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=profit_loss.csv'})

def generate_debtors_creditors_pdf(records):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, 10.5 * inch, trans('reports_debtors_creditors_report', default='Debtors/Creditors Report'))
    p.drawString(1 * inch, 10.2 * inch, f"{trans('reports_generated_on', default='Generated on')}: {utils.format_date(datetime.utcnow())}")
    y = 9.5 * inch
    p.setFillColor(colors.black)
    p.drawString(1 * inch, y, trans('general_date', default='Date'))
    p.drawString(2.5 * inch, y, trans('general_name', default='Name'))
    p.drawString(4 * inch, y, trans('general_type', default='Type'))
    p.drawString(5 * inch, y, trans('general_amount_owed', default='Amount Owed'))
    p.drawString(6.5 * inch, y, trans('general_description', default='Description'))
    y -= 0.3 * inch
    total_debtors = 0
    total_creditors = 0
    for r in records:
        p.drawString(1 * inch, y, utils.format_date(r['created_at']))
        p.drawString(2.5 * inch, y, r['name'])
        p.drawString(4 * inch, y, trans(r['type'], default=r['type']))
        p.drawString(5 * inch, y, utils.format_currency(r['amount_owed']))
        p.drawString(6.5 * inch, y, r.get('description', '')[:20])  # Truncate description
        if r['type'] == 'debtor':
            total_debtors += r['amount_owed']
        else:
            total_creditors += r['amount_owed']
        y -= 0.3 * inch
        if y < 1 * inch:
            p.showPage()
            y = 10.5 * inch
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_total_debtors', default='Total Debtors')}: {utils.format_currency(total_debtors)}")
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_total_creditors', default='Total Creditors')}: {utils.format_currency(total_creditors)}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=debtors_creditors.pdf'})

def generate_debtors_creditors_csv(records):
    output = []
    output.append([trans('general_date', default='Date'), trans('general_name', default='Name'), trans('general_type', default='Type'), trans('general_amount_owed', default='Amount Owed'), trans('general_description', default='Description')])
    total_debtors = 0
    total_creditors = 0
    for r in records:
        output.append([utils.format_date(r['created_at']), r['name'], trans(r['type'], default=r['type']), utils.format_currency(r['amount_owed']), r.get('description', '')])
        if r['type'] == 'debtor':
            total_debtors += r['amount_owed']
        else:
            total_creditors += r['amount_owed']
    output.append(['', '', '', f"{trans('reports_total_debtors', default='Total Debtors')}: {utils.format_currency(total_debtors)}", ''])
    output.append(['', '', '', f"{trans('reports_total_creditors', default='Total Creditors')}: {utils.format_currency(total_creditors)}", ''])
    buffer = BytesIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerows(output)
    buffer.seek(0)
    return Response(buffer, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=debtors_creditors.csv'})

def generate_tax_obligations_pdf(tax_reminders):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 12)
    p.drawString(1 * inch, 10.5 * inch, trans('reports_tax_obligations_report', default='Tax Obligations Report'))
    p.drawString(1 * inch, 10.2 * inch, f"{trans('reports_generated_on', default='Generated on')}: {utils.format_date(datetime.utcnow())}")
    y = 9.5 * inch
    p.setFillColor(colors.black)
    p.drawString(1 * inch, y, trans('general_due_date', default='Due Date'))
    p.drawString(2.5 * inch, y, trans('general_tax_type', default='Tax Type'))
    p.drawString(4 * inch, y, trans('general_amount', default='Amount'))
    p.drawString(5 * inch, y, trans('general_status', default='Status'))
    y -= 0.3 * inch
    total_amount = 0
    for tr in tax_reminders:
        p.drawString(1 * inch, y, utils.format_date(tr['due_date']))
        p.drawString(2.5 * inch, y, tr['tax_type'])
        p.drawString(4 * inch, y, utils.format_currency(tr['amount']))
        p.drawString(5 * inch, y, trans(tr['status'], default=tr['status']))
        total_amount += tr['amount']
        y -= 0.3 * inch
        if y < 1 * inch:
            p.showPage()
            y = 10.5 * inch
    y -= 0.3 * inch
    p.drawString(1 * inch, y, f"{trans('reports_total_tax_amount', default='Total Tax Amount')}: {utils.format_currency(total_amount)}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=tax_obligations.pdf'})

def generate_tax_obligations_csv(tax_reminders):
    output = []
    output.append([trans('general_due_date', default='Due Date'), trans('general_tax_type', default='Tax Type'), trans('general_amount', default='Amount'), trans('general_status', default='Status')])
    total_amount = 0
    for tr in tax_reminders:
        output.append([utils.format_date(tr['due_date']), tr['tax_type'], utils.format_currency(tr['amount']), trans(tr['status'], default=tr['status'])])
        total_amount += tr['amount']
    output.append(['', '', f"{trans('reports_total_tax_amount', default='Total Tax Amount')}: {utils.format_currency(total_amount)}", ''])
    buffer = BytesIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerows(output)
    buffer.seek(0)
    return Response(buffer, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=tax_obligations.csv'})

def generate_budget_performance_pdf(budget_data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 10)
    p.drawString(1 * inch, 10.5 * inch, trans('reports_budget_performance_report', default='Budget Performance Report'))
    p.drawString(1 * inch, 10.2 * inch, f"{trans('reports_generated_on', default='Generated on')}: {utils.format_date(datetime.utcnow())}")
    y = 9.5 * inch
    p.setFillColor(colors.black)
    headers = [
        trans('general_date', default='Date'),
        trans('general_income', default='Income'),
        trans('general_actual_income', default='Actual Income'),
        trans('general_income_variance', default='Income Variance'),
        trans('general_fixed_expenses', default='Fixed Expenses'),
        trans('general_variable_expenses', default='Variable Expenses'),
        trans('general_actual_expenses', default='Actual Expenses'),
        trans('general_expense_variance', default='Expense Variance')
    ]
    x_positions = [1 * inch + i * 0.9 * inch for i in range(len(headers))]
    for header, x in zip(headers, x_positions):
        p.drawString(x, y, header)
    y -= 0.3 * inch
    for bd in budget_data:
        values = [
            utils.format_date(bd['created_at']),
            utils.format_currency(bd['income']),
            utils.format_currency(bd['actual_income']),
            utils.format_currency(bd['income_variance']),
            utils.format_currency(bd['fixed_expenses']),
            utils.format_currency(bd['variable_expenses']),
            utils.format_currency(bd['actual_expenses']),
            utils.format_currency(bd['expense_variance'])
        ]
        for value, x in zip(values, x_positions):
            p.drawString(x, y, value)
        y -= 0.3 * inch
        if y < 1 * inch:
            p.showPage()
            y = 10.5 * inch
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=budget_performance.pdf'})

def generate_budget_performance_csv(budget_data):
    output = []
    output.append([
        trans('general_date', default='Date'),
        trans('general_income', default='Income'),
        trans('general_actual_income', default='Actual Income'),
        trans('general_income_variance', default='Income Variance'),
        trans('general_fixed_expenses', default='Fixed Expenses'),
        trans('general_variable_expenses', default='Variable Expenses'),
        trans('general_actual_expenses', default='Actual Expenses'),
        trans('general_expense_variance', default='Expense Variance')
    ])
    for bd in budget_data:
        output.append([
            utils.format_date(bd['created_at']),
            utils.format_currency(bd['income']),
            utils.format_currency(bd['actual_income']),
            utils.format_currency(bd['income_variance']),
            utils.format_currency(bd['fixed_expenses']),
            utils.format_currency(bd['variable_expenses']),
            utils.format_currency(bd['actual_expenses']),
            utils.format_currency(bd['expense_variance'])
        ])
    buffer = BytesIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerows(output)
    buffer.seek(0)
    return Response(buffer, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=budget_performance.csv'})

def generate_customer_report_pdf(report_data):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont("Helvetica", 8)
    p.drawString(0.5 * inch, 10.5 * inch, trans('reports_customer_report', default='Customer Report'))
    p.drawString(0.5 * inch, 10.2 * inch, f"{trans('reports_generated_on', default='Generated on')}: {utils.format_date(datetime.utcnow())}")
    y = 9.5 * inch
    headers = [
        'Username', 'Email', 'Role', 'Credits', 'Lang',
        'Income', 'Fixed Exp', 'Var Exp', 'Surplus',
        'Pending Bills', 'Paid Bills', 'Overdue Bills',
        'Lessons', 'Tax Due', 'Tax Amt'
    ]
    x_positions = [0.5 * inch + i * 0.3 * inch for i in range(len(headers))]
    for header, x in zip(headers, x_positions):
        p.drawString(x, y, header)
    y -= 0.2 * inch
    for data in report_data:
        values = [
            data['username'], data['email'], data['role'], str(data['ficore_credit_balance']), data['language'],
            str(data['budget_income']), str(data['budget_fixed_expenses']), str(data['budget_variable_expenses']), str(data['budget_surplus_deficit']),
            str(data['pending_bills']), str(data['paid_bills']), str(data['overdue_bills']),
            str(data['lessons_completed']), data['next_tax_due_date'], str(data['next_tax_amount'])
        ]
        for value, x in zip(values, x_positions):
            p.drawString(x, y, str(value)[:15])  # Truncate long values
        y -= 0.2 * inch
        if y < 0.5 * inch:
            p.showPage()
            y = 10.5 * inch
    p.showPage()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': 'attachment;filename=customer_report.pdf'})

def generate_customer_report_csv(report_data):
    output = []
    headers = [
        'Username', 'Email', 'Role', 'Ficore Credit Balance', 'Language',
        'Budget Income', 'Budget Fixed Expenses', 'Budget Variable Expenses', 'Budget Surplus/Deficit',
        'Pending Bills', 'Paid Bills', 'Overdue Bills',
        'Lessons Completed', 'Next Tax Due Date', 'Next Tax Amount'
    ]
    output.append(headers)
    for data in report_data:
        row = [
            data['username'], data['email'], data['role'], data['ficore_credit_balance'], data['language'],
            data['budget_income'], data['budget_fixed_expenses'], data['budget_variable_expenses'], data['budget_surplus_deficit'],
            data['pending_bills'], data['paid_bills'], data['overdue_bills'],
            data['lessons_completed'], data['next_tax_due_date'], data['next_tax_amount']
        ]
        output.append(row)
    buffer = BytesIO()
    writer = csv.writer(buffer, lineterminator='\n')
    writer.writerows(output)
    buffer.seek(0)
    return Response(buffer, mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=customer_report.csv'})
