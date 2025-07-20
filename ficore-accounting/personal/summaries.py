from flask import Blueprint, jsonify, current_app, session, request
from flask_login import current_user, login_required
from datetime import datetime, date
from models import get_budgets, get_bills
from utils import get_mongo_db, trans, requires_role, logger, is_admin
from bson import ObjectId

summaries_bp = Blueprint('summaries', __name__, url_prefix='/summaries')

# --- HELPER FUNCTION ---
def get_recent_activities(user_id=None, is_admin_user=False, db=None):
    if db is None:
        db = get_mongo_db()
    query = {} if is_admin_user else {'user_id': str(user_id)}
    activities = []

    # Fetch recent bills
    bills = db.bills.find(query).sort('created_at', -1).limit(5)
    for bill in bills:
        if not bill.get('created_at') or not bill.get('bill_name'):
            logger.warning(f"Skipping invalid bill record: {bill.get('_id')}", 
                           extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            continue
        activities.append({
            'type': 'bill',
            'description': trans('recent_activity_bill_added', default='Added bill: {name}', name=bill.get('bill_name', 'Unknown')),
            'timestamp': bill.get('created_at', datetime.utcnow()).isoformat(),
            'details': {
                'amount': bill.get('amount', 0),
                'due_date': bill.get('due_date', 'N/A'),
                'status': bill.get('status', 'Unknown')
            },
            'icon': 'bi-receipt'
        })

    # Fetch recent budgets
    budgets = db.budgets.find(query).sort('created_at', -1).limit(5)
    for budget in budgets:
        activities.append({
            'type': 'budget',
            'description': trans('recent_activity_budget_created', default='Created budget with income: {amount}', amount=budget.get('income', 0)),
            'timestamp': budget.get('created_at', datetime.utcnow()).isoformat(),
            'details': {
                'income': budget.get('income', 0),
                'surplus_deficit': budget.get('surplus_deficit', 0)
            },
            'icon': 'bi-cash-coin'
        })

    # Fetch recent grocery lists
    grocery_lists = db.grocery_lists.find(query).sort('created_at', -1).limit(5)
    for grocery_list in grocery_lists:
        activities.append({
            'type': 'grocery_list',
            'description': trans('recent_activity_grocery_list_created', default='Created grocery list: {name}', name=grocery_list.get('name', 'Unknown')),
            'timestamp': grocery_list.get('created_at', datetime.utcnow()).isoformat(),
            'details': {
                'budget': grocery_list.get('budget', 0),
                'total_spent': grocery_list.get('total_spent', 0)
            },
            'icon': 'bi-cart'
        })

    # Fetch recent grocery items
    grocery_items = db.grocery_items.find(query).sort('updated_at', -1).limit(5)
    for item in grocery_items:
        if item.get('status') == 'bought':
            activities.append({
                'type': 'grocery_item',
                'description': trans('recent_activity_grocery_item_bought', default='Bought item: {name}', name=item.get('name', 'Unknown')),
                'timestamp': item.get('updated_at', datetime.utcnow()).isoformat(),
                'details': {
                    'quantity': item.get('quantity', 1),
                    'price': item.get('price', 0),
                    'store': item.get('store', 'Unknown')
                },
                'icon': 'bi-check-circle'
            })

    # Fetch recent learning hub progress
    learning_hub_progress = db.learning_materials.find(query).sort('updated_at', -1).limit(5)
    for progress in learning_hub_progress:
        if progress.get('course_id'):
            activities.append({
                'type': 'learning_hub',
                'description': trans('recent_activity_learning_hub_progress', default='Progress in course: {course_id}', course_id=progress.get('course_id', 'N/A')),
                'timestamp': progress.get('updated_at', datetime.utcnow()).isoformat(),
                'details': {
                    'course_id': progress.get('course_id', 'N/A'),
                    'lessons_completed': len(progress.get('lessons_completed', [])),
                    'current_lesson': progress.get('current_lesson', 'N/A')
                },
                'icon': 'bi-book'
            })

    # Fetch recent Ficore Credits transactions
    ficore_transactions = db.ficore_credit_transactions.find(query).sort('timestamp', -1).limit(5)
    for transaction in ficore_transactions:
        activities.append({
            'type': 'ficore_credit',
            'description': trans('recent_activity_ficore_credit', default='{action}: {amount} credits', 
                                action=transaction.get('action', 'Transaction'), amount=abs(transaction.get('amount', 0))),
            'timestamp': transaction.get('timestamp', datetime.utcnow()).isoformat(),
            'details': {
                'amount': transaction.get('amount', 0),
                'action': transaction.get('action', 'Unknown')
            },
            'icon': 'bi-wallet2'
        })

    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return activities[:10]

# --- HELPER FUNCTION ---
def _get_recent_activities_data(user_id=None, is_admin_user=False, db=None):
    """Fetch recent activities across all personal finance tools for a user."""
    if db is None:
        db = get_mongo_db()
    return get_recent_activities(user_id, is_admin_user, db)

# --- HELPER FUNCTION FOR NOTIFICATIONS ---
def _get_notifications_data(user_id, is_admin_user, db):
    """Helper function to fetch recent notifications for a user from bill_reminders collection."""
    query = {} if is_admin_user else {'user_id': str(user_id)}
    notifications = db.bill_reminders.find(query).sort('sent_at', -1).limit(10)
    return [{
        'id': str(n.get('notification_id', ObjectId())),
        'message': n.get('message', 'No message'),
        'type': n.get('type', 'info'),
        'timestamp': n.get('sent_at', datetime.utcnow()).isoformat(),
        'read': n.get('read_status', False),
        'icon': get_notification_icon(n.get('type', 'info'))
    } for n in notifications]

# --- HELPER FUNCTION FOR NOTIFICATION ICONS ---
def get_notification_icon(notification_type):
    """Map notification types to Bootstrap Icons."""
    icons = {
        'info': 'bi-info-circle',
        'warning': 'bi-exclamation-triangle',
        'error': 'bi-x-circle',
        'success': 'bi-check-circle'
    }
    return icons.get(notification_type, 'bi-info-circle')

@summaries_bp.route('/budget/summary')
@login_required
@requires_role(['personal', 'admin'])
def budget_summary():
    """Fetch the latest budget summary for the authenticated user."""
    try:
        db = get_mongo_db()
        budgets = get_budgets(db, {'user_id': current_user.id})
        total_budget = 0
        if budgets:
            latest_budget = budgets[0]
            total_budget = (latest_budget.get('income', 0) - 
                           (latest_budget.get('fixed_expenses', 0) + 
                            latest_budget.get('variable_expenses', 0)))
        logger.info(f"Fetched budget summary for user {current_user.id}: {total_budget}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'totalBudget': float(total_budget)}), 200
    except Exception as e:
        logger.error(f"Error fetching budget summary for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('budget_summary_error', default='Error fetching budget summary')}), 500

@summaries_bp.route('/bill/summary')
@login_required
@requires_role(['personal', 'admin'])
def bill_summary():
    """Fetch the summary of bills for the authenticated user."""
    try:
        db = get_mongo_db()
        today = date.today()
        filter_criteria = {'user_id': current_user.id} if not is_admin() else {}
        bills = get_bills(db, filter_criteria)
        
        overdue_amount = 0
        pending_amount = 0
        unpaid_amount = 0
        
        for bill in bills:
            try:
                due_date = bill.get('due_date')
                if isinstance(due_date, str):
                    due_date = datetime.strptime(due_date, '%Y-%m-%d').date()
                amount = float(bill.get('amount', 0))
                status = bill.get('status', 'unpaid')
                
                if status == 'unpaid':
                    unpaid_amount += amount
                    if due_date < today:
                        overdue_amount += amount
                    elif due_date >= today:
                        pending_amount += amount
                elif status == 'pending':
                    pending_amount += amount
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid bill data for bill {bill.get('_id')}: {str(e)}", 
                              extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                continue

        logger.info(f"Fetched bill summary for user {current_user.id}: overdue={overdue_amount}, pending={pending_amount}, unpaid={unpaid_amount}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({
            'overdue_amount': float(overdue_amount),
            'pending_amount': float(pending_amount),
            'unpaid_amount': float(unpaid_amount)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching bill summary for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({
            'overdue_amount': 0.0,
            'pending_amount': 0.0,
            'unpaid_amount': 0.0,
            'error': trans('bill_summary_error', default='Error fetching bill summary')
        }), 500

@summaries_bp.route('/grocery/summary')
@login_required
@requires_role(['personal', 'admin'])
def grocery_summary():
    """Fetch the summary of active grocery lists for the authenticated user."""
    try:
        db = get_mongo_db()
        grocery_lists = db.grocery_lists.find({'user_id': str(current_user.id), 'status': 'active'}).sort('updated_at', -1)
        total_budget = 0
        total_spent = 0
        for grocery_list in grocery_lists:
            total_budget += float(grocery_list.get('budget', 0))
            total_spent += float(grocery_list.get('total_spent', 0))
        
        logger.info(f"Fetched grocery summary for user {current_user.id}: budget={total_budget}, spent={total_spent}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({
            'total_grocery_budget': float(total_budget),
            'total_grocery_spent': float(total_spent)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching grocery summary for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({
            'total_grocery_budget': 0.0,
            'total_grocery_spent': 0.0,
            'error': trans('grocery_summary_error', default='Error fetching grocery summary')
        }), 500

@summaries_bp.route('/ficore_balance')
@login_required
@requires_role(['personal', 'admin'])
def ficore_balance():
    """Fetch the Ficore Credits balance for the authenticated user."""
    try:
        db = get_mongo_db()
        user = db.users.find_one({'_id': current_user.id})
        balance = float(user.get('ficore_credit_balance', 0))
        logger.info(f"Fetched Ficore Credits balance for user {current_user.id}: {balance}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'balance': balance}), 200
    except Exception as e:
        logger.error(f"Error fetching Ficore Credits balance for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'balance': 0.0, 'error': trans('ficore_balance_error', default='Error fetching Ficore Credits balance')}), 500

@summaries_bp.route('/recent_activity')
@login_required
@requires_role(['personal', 'admin'])
def recent_activity():
    """Return recent activity across all personal finance tools for the current user."""
    try:
        activities = _get_recent_activities_data(user_id=current_user.id, is_admin_user=current_user.role == 'admin')
        logger.info(f"Fetched {len(activities)} recent activities for user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify(activities), 200
    except Exception as e:
        logger.error(f"Error in summaries.recent_activity: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch recent activity')}), 500

@summaries_bp.route('/notification_count')
@login_required
@requires_role(['personal', 'admin'])
def notification_count():
    """Return the count of unread notifications for the current user."""
    try:
        db = get_mongo_db()
        query = {} if current_user.role == 'admin' else {'user_id': str(current_user.id), 'read_status': False}
        count = db.bill_reminders.count_documents(query)
        logger.info(f"Fetched notification count {count} for user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'count': count}), 200
    except Exception as e:
        logger.error(f"Error fetching notification count: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch notification count')}), 500

@summaries_bp.route('/notifications')
@login_required
@requires_role(['personal', 'admin'])
def notifications():
    """Return the list of recent notifications for the current user."""
    try:
        db = get_mongo_db()
        query = {} if current_user.role == 'admin' else {'user_id': str(current_user.id)}
        notifications = list(db.bill_reminders.find(query).sort('sent_at', -1).limit(10))

        # Handle cases where notification_id or sent_at might be missing
        notification_ids = []
        for n in notifications:
            if 'notification_id' in n and not n.get('read_status', False):
                notification_ids.append(n['notification_id'])

        if notification_ids:
            db.bill_reminders.update_many(
                {'notification_id': {'$in': notification_ids}},
                {'$set': {'read_status': True}}
            )

        result = []
        for n in notifications:
            try:
                result.append({
                    'id': str(n.get('notification_id', ObjectId())),
                    'message': n.get('message', 'No message'),
                    'type': n.get('type', 'info'),
                    'timestamp': n.get('sent_at', datetime.utcnow()).isoformat(),
                    'read': n.get('read_status', False),
                    'icon': get_notification_icon(n.get('type', 'info'))
                })
            except Exception as e:
                logger.warning(f"Skipping invalid notification: {str(e)}", 
                               extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                continue

        logger.info(f"Fetched {len(result)} notifications for user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching notifications: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('general_something_went_wrong', default='Failed to fetch notifications')}), 500
