from flask import Blueprint, jsonify, request, current_app, session, Response
from flask_login import current_user, login_required
from datetime import datetime, date
from bson import ObjectId
from pymongo import errors
from utils import get_mongo_db, requires_role, logger, clean_currency, check_ficore_credit_balance, is_admin, format_date, format_currency
from translations import trans
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from contextlib import nullcontext
import traceback

grocery_bp = Blueprint('grocery', __name__, url_prefix='/grocery')

def deduct_ficore_credits(db, user_id, amount, action, item_id=None, mongo_session=None):
    try:
        if amount <= 0:
            logger.error(f"Invalid deduction amount {amount} for user {user_id}, action: {action}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return False
        
        user = db.users.find_one({'_id': user_id}, session=mongo_session)
        if not user:
            logger.error(f"User {user_id} not found for credit deduction, action: {action}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return False
        
        current_balance = user.get('ficore_credit_balance', 0)
        if current_balance < amount:
            logger.warning(f"Insufficient credits for user {user_id}: required {amount}, available {current_balance}, action: {action}", 
                         extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return False
        
        session_to_use = mongo_session if mongo_session else db.client.start_session()
        owns_session = not mongo_session
        
        try:
            with session_to_use.start_transaction() if not mongo_session else nullcontext():
                result = db.users.update_one(
                    {'_id': user_id},
                    {'$inc': {'ficore_credit_balance': -amount}},
                    session=session_to_use
                )
                if result.modified_count == 0:
                    logger.error(f"Failed to deduct {amount} credits for user {user_id}, action: {action}: No documents modified", 
                                extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    raise ValueError(f"Failed to update user balance for {user_id}")
                
                transaction = {
                    '_id': ObjectId(),
                    'user_id': user_id,
                    'action': action,
                    'amount': -amount,
                    'item_id': str(item_id) if item_id else None,
                    'timestamp': datetime.utcnow(),
                    'session_id': session.get('sid', 'no-session-id'),
                    'status': 'completed'
                }
                db.ficore_credit_transactions.insert_one(transaction, session=session_to_use)
                
            logger.info(f"Deducted {amount} Ficore Credits for {action} by user {user_id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return True
        except (ValueError, errors.PyMongoError) as e:
            logger.error(f"Transaction aborted for user {user_id}, action: {action}: {str(e)}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
            return False
        finally:
            if owns_session:
                session_to_use.end_session()
    except Exception as e:
        logger.error(f"Unexpected error deducting {amount} Ficore Credits for {action} by user {user_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return False

def auto_categorize_item(item_name):
    item_name = item_name.lower().strip()
    categories = {
        'fruits': ['apple', 'banana', 'orange', 'mango', 'pineapple', 'berry', 'grape'],
        'vegetables': ['carrot', 'potato', 'tomato', 'onion', 'spinach', 'lettuce'],
        'dairy': ['milk', 'cheese', 'yogurt', 'butter', 'cream'],
        'meat': ['chicken', 'beef', 'pork', 'fish', 'egg'],
        'grains': ['rice', 'bread', 'pasta', 'flour', 'cereal'],
        'beverages': ['juice', 'soda', 'water', 'tea', 'coffee'],
        'household': ['detergent', 'soap', 'tissue', 'paper towel'],
        'other': []
    }
    for category, keywords in categories.items():
        if any(keyword in item_name for keyword in keywords):
            return category
    return 'other'

def get_predictive_suggestions(user_id, db):
    suggestions = []
    items = db.grocery_items.find({'user_id': str(user_id), 'status': 'bought'}).sort('updated_at', -1)
    today = date.today()
    for item in items:
        item_name = item.get('name', '').lower()
        last_bought = item.get('updated_at', datetime.utcnow()).date()
        frequency = item.get('frequency', 7)
        if (today - last_bought).days >= frequency:
            suggestions.append({
                'name': item.get('name'),
                'category': item.get('category', 'other'),
                'suggested_quantity': item.get('quantity', 1),
                'estimated_price': float(item.get('price', 0))
            })
    return suggestions[:5]

@grocery_bp.route('/', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def index():
    try:
        db = get_mongo_db()
        lists = db.grocery_lists.find({'user_id': str(current_user.id)}).sort('updated_at', -1).limit(5)
        suggestions = get_predictive_suggestions(current_user.id, db)
        summary = {
            'recent_lists': [{
                'id': str(l['_id']),
                'name': l.get('name'),
                'budget': float(l.get('budget', 0)),
                'total_spent': float(l.get('total_spent', 0)),
                'status': l.get('status', 'active')
            } for l in lists],
            'suggestions': suggestions
        }
        logger.info(f"Fetched grocery summary for user {current_user.id}", 
                   extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify(summary), 200
    except Exception as e:
        logger.error(f"Error fetching grocery summary for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_error', default='Error fetching grocery summary. Please try again later.')}), 500

@grocery_bp.route('/lists', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_lists():
    db = get_mongo_db()
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('budget'):
                return jsonify({'error': trans('grocery_invalid_input', default='Invalid or missing list data. Please provide name and budget.')}), 400
            budget = clean_currency(data.get('budget', '0'))
            if budget <= 0:
                return jsonify({'error': trans('grocery_invalid_budget', default='Budget must be a positive number.')}), 400
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                    logger.warning(f"Insufficient Ficore Credits for creating grocery list by user {current_user.id}", 
                                 extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to create a list. Please purchase more credits.')}), 403
            list_data = {
                'name': data.get('name'),
                'user_id': str(current_user.id),
                'budget': float(budget),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'collaborators': data.get('collaborators', []),
                'items': [],
                'total_spent': 0.0,
                'status': 'active'
            }
            with db.client.start_session() as mongo_session:
                with mongo_session.start_transaction():
                    result = db.grocery_lists.insert_one(list_data, session=mongo_session)
                    if current_user.is_authenticated and not is_admin():
                        if not deduct_ficore_credits(db, current_user.id, 0.5, 'create_grocery_list', str(result.inserted_id), mongo_session):
                            logger.error(f"Failed to deduct 0.5 Ficore Credits for creating grocery list {result.inserted_id} by user {current_user.id}", 
                                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                            raise ValueError(f"Failed to deduct Ficore Credits for creating list {result.inserted_id}")
            logger.info(f"Created grocery list {result.inserted_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'list_id': str(result.inserted_id), 'message': trans('grocery_list_created', default='Grocery list created successfully')}), 201
        lists = db.grocery_lists.find({'user_id': str(current_user.id)}).sort('updated_at', -1)
        return jsonify([{
            'id': str(l['_id']),
            'name': l.get('name'),
            'budget': float(l.get('budget', 0)),
            'total_spent': float(l.get('total_spent', 0)),
            'status': l.get('status', 'active'),
            'created_at': l.get('created_at').isoformat(),
            'collaborators': l.get('collaborators', [])
        } for l in lists]), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for creating grocery list by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_credit_deduction_failed', default='Failed to deduct Ficore Credits for creating list. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error during grocery list creation for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error managing grocery lists. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error managing grocery lists for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error managing grocery lists. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/save', methods=['PUT'])
@login_required
@requires_role(['personal', 'admin'])
def save_list(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        if grocery_list.get('status') == 'saved':
            return jsonify({'error': trans('grocery_list_already_saved', default='Grocery list is already saved.')}), 400
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                logger.warning(f"Insufficient Ficore Credits for saving list {list_id} by user {current_user.id}", 
                             extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to save a list. Please purchase more credits.')}), 403
        with db.clientLp.start_session() as mongo_session:
            with mongo_session.start_transaction():
                result = db.grocery_lists.update_one(
                    {'_id': ObjectId(list_id)},
                    {'$set': {'status': 'saved', 'updated_at': datetime.utcnow()}},
                    session=mongo_session
                )
                if result.modified_count == 0:
                    logger.error(f"Failed to save grocery list {list_id} for user {current_user.id}: No documents modified", 
                                extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    raise ValueError(f"Failed to save grocery list {list_id}")
                if current_user.is_authenticated and not is_admin():
                    if not deduct_ficore_credits(db, current_user.id, 0.5, 'save_grocery_list', list_id, mongo_session):
                        logger.error(f"Failed to deduct 0.5 Ficore Credits for saving list {list_id} by user {current_user.id}", 
                                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                        raise ValueError(f"Failed to deduct Ficore Credits for saving list {list_id}")
            logger.info(f"Saved grocery list {list_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_list_saved', default='Grocery list saved successfully')}), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for saving list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error saving grocery list. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error during saving of list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error saving grocery list due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error saving grocery list {list_id} for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error saving grocery list. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/export_pdf', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def export_list_pdf(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        if grocery_list.get('status') != 'saved':
            return jsonify({'error': trans('grocery_list_not_saved', default='Grocery list must be saved before exporting to PDF.')}), 400
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                logger.warning(f"Insufficient Ficore Credits for exporting list {list_id} to PDF by user {current_user.id}", 
                             extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to export list to PDF. Please purchase more credits.')}), 403
        items = db.grocery_items.find({'list_id': list_id}).sort('created_at', -1)
        grocery_data = {
            'lists': [{
                'name': grocery_list.get('name'),
                'budget': float(grocery_list.get('budget', 0)),
                'total_spent': float(grocery_list.get('total_spent', 0)),
                'collaborators': grocery_list.get('collaborators', []),
                'created_at': grocery_list.get('created_at')
            }],
            'items': [{
                'name': i.get('name'),
                'quantity': i.get('quantity', 1),
                'price': float(i.get('price', 0)),
                'category': i.get('category', 'other'),
                'status': i.get('status', 'to_buy'),
                'store': i.get('store', 'Unknown'),
                'created_at': i.get('created_at')
            } for i in items],
            'suggestions': []
        }
        with db.client.start_session() as mongo_session:
            with mongo_session.start_transaction():
                buffer = BytesIO()
                p = canvas.Canvas(buffer, pagesize=A4)
                header_height = 0.7
                extra_space = 0.2
                row_height = 0.3
                bottom_margin = 0.5
                max_y = 10.5
                title_y = max_y - header_height - extra_space
                page_height = (max_y - bottom_margin) * inch
                rows_per_page = int((page_height - (title_y - 0.6) * inch) / (row_height * inch))
                total_budget = float(grocery_data['lists'][0]['budget'])
                total_spent = float(grocery_data['lists'][0]['total_spent'])
                total_price = sum(float(item['price']) * item['quantity'] for item in grocery_data['items'])
                def draw_list_headers(y):
                    p.setFillColor(colors.black)
                    p.drawString(1 * inch, y * inch, trans('general_date', default='Date'))
                    p.drawString(2 * inch, y * inch, trans('general_list_name', default='List Name'))
                    p.drawString(3.5 * inch, y * inch, trans('general_budget', default='Budget'))
                    p.drawString(4.5 * inch, y * inch, trans('general_total_spent', default='Total Spent'))
                    p.drawString(5.5 * inch, y * inch, trans('general_collaborators', default='Collaborators'))
                    return y - row_height
                def draw_item_headers(y):
                    p.setFillColor(colors.black)
                    p.drawString(1 * inch, y * inch, trans('general_date', default='Date'))
                    p.drawString(2 * inch, y * inch, trans('general_item_name', default='Item Name'))
                    p.drawString(3 * inch, y * inch, trans('general_quantity', default='Quantity'))
                    p.drawString(3.8 * inch, y * inch, trans('general_price', default='Price'))
                    p.drawString(4.5 * inch, y * inch, trans('general_status', default='Status'))
                    p.drawString(5.2 * inch, y * inch, trans('general_category', default='Category'))
                    p.drawString(6 * inch, y * inch, trans('general_store', default='Store'))
                    return y - row_height
                draw_ficore_pdf_header(p, current_user, y_start=max_y)
                p.setFont("Helvetica", 12)
                p.drawString(1 * inch, title_y * inch, trans('grocery_list_report', default='Grocery List Report'))
                p.drawString(1 * inch, (title_y - 0.3) * inch, f"{trans('reports_generated_on', default='Generated on')}: {format_date(datetime.utcnow())}")
                y = title_y - 0.6
                p.setFont("Helvetica", 10)
                y = draw_list_headers(y)
                row_count = 0
                list_data = grocery_data['lists'][0]
                p.drawString(1 * inch, y * inch, format_date(list_data['created_at']))
                p.drawString(2 * inch, y * inch, list_data['name'])
                p.drawString(3.5 * inch, y * inch, format_currency(list_data['budget']))
                p.drawString(4.5 * inch, y * inch, format_currency(list_data['total_spent']))
                p.drawString(5.5 * inch, y * inch, ', '.join(list_data['collaborators']) or 'None')
                y -= row_height
                row_count += 1
                y -= 0.5
                p.drawString(1 * inch, y * inch, trans('grocery_items', default='Items'))
                y -= row_height
                y = draw_item_headers(y)
                for item in grocery_data['items']:
                    if row_count + 1 >= rows_per_page:
                        p.showPage()
                        draw_ficore_pdf_header(p, current_user, y_start=max_y)
                        y = title_y - 0.6
                        y = draw_item_headers(y)
                        row_count = 0
                    p.drawString(1 * inch, y * inch, format_date(item['created_at']))
                    p.drawString(2 * inch, y * inch, item['name'][:20])
                    p.drawString(3 * inch, y * inch, str(item['quantity']))
                    p.drawString(3.8 * inch, y * inch, format_currency(item['price']))
                    p.drawString(4.5 * inch, y * inch, trans(item['status'], default=item['status']))
                    p.drawString(5.2 * inch, y * inch, trans(item['category'], default=item['category']))
                    p.drawString(6 * inch, y * inch, item['store'][:15])
                    y -= row_height
                    row_count += 1
                if row_count + 3 <= rows_per_page:
                    y -= row_height
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_budget', default='Total Budget')}: {format_currency(total_budget)}")
                    y -= row_height
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_spent', default='Total Spent')}: {format_currency(total_spent)}")
                    y -= row_height
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_price', default='Total Price')}: {format_currency(total_price)}")
                else:
                    p.showPage()
                    draw_ficore_pdf_header(p, current_user, y_start=max_y)
                    y = title_y - 0.6
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_budget', default='Total Budget')}: {format_currency(total_budget)}")
                    y -= row_height
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_spent', default='Total Spent')}: {format_currency(total_spent)}")
                    y -= row_height
                    p.drawString(1 * inch, y * inch, f"{trans('reports_total_price', default='Total Price')}: {format_currency(total_price)}")
                p.save()
                buffer.seek(0)
                if current_user.is_authenticated and not is_admin():
                    if not deduct_ficore_credits(db, current_user.id, 0.5, 'export_grocery_list_pdf', list_id, mongo_session):
                        logger.error(f"Failed to deduct 0.5 Ficore Credits for exporting list {list_id} to PDF by user {current_user.id}", 
                                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                        raise ValueError(f"Failed to deduct Ficore Credits for exporting list {list_id} to PDF")
            logger.info(f"Exported grocery list {list_id} to PDF for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=grocery_list_{list_id}.pdf'})
    except ValueError as e:
        logger.error(f"Transaction aborted for exporting list {list_id} to PDF by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_export_error', default='Error exporting grocery list to PDF. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error exporting list {list_id} to PDF by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_export_error', default='Error exporting grocery list to PDF due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error exporting grocery list {list_id} to PDF: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_export_error', default='Error exporting grocery list to PDF. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>', methods=['DELETE'])
@login_required
@requires_role(['personal', 'admin'])
def delete_list(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=2.0, user_id=current_user.id):
                logger.warning(f"Insufficient Ficore Credits for deleting list {list_id} by user {current_user.id}", 
                             extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to delete a list. Please purchase more credits.')}), 403
        with db.client.start_session() as mongo_session:
            with mongo_session.start_transaction():
                db.grocery_items.delete_many({'list_id': list_id}, session=mongo_session)
                db.grocery_suggestions.delete_many({'list_id': list_id}, session=mongo_session)
                result = db.grocery_lists.delete_one({'_id': ObjectId(list_id)}, session=mongo_session)
                if result.deleted_count == 0:
                    logger.error(f"Failed to delete grocery list {list_id} for user {current_user.id}: No documents deleted", 
                                extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    raise ValueError(f"Failed to delete grocery list {list_id}")
                if current_user.is_authenticated and not is_admin():
                    if not deduct_ficore_credits(db, current_user.id, 2.0, 'delete_grocery_list', list_id, mongo_session):
                        logger.error(f"Failed to deduct 2.0 Ficore Credits for deleting list {list_id} by user {current_user.id}", 
                                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                        raise ValueError(f"Failed to deduct Ficore Credits for deleting list {list_id}")
            logger.info(f"Deleted grocery list {list_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_list_deleted', default='Grocery list deleted successfully')}), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for deleting list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error deleting grocery list. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error during deletion of list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error deleting grocery list due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting grocery list {list_id} for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_list_error', default='Error deleting grocery list. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/items', methods=['GET', 'POST', 'PUT'])
@login_required
@requires_role(['personal', 'admin'])
def manage_items(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity') or not data.get('price'):
                return jsonify({'error': trans('grocery_invalid_item', default='Invalid or missing item data. Please provide name, quantity, and price.')}), 400
            quantity = int(data.get('quantity', 1))
            price = clean_currency(data.get('price', '0'))
            if quantity <= 0 or price < 0:
                return jsonify({'error': trans('grocery_invalid_item_data', default='Invalid quantity or price. Quantity must be positive, and price cannot be negative.')}), 400
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                    logger.warning(f"Insufficient Ficore Credits for adding item to list {list_id} by user {current_user.id}", 
                                 extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to add an item. Please purchase more credits.')}), 403
            item_data = {
                'list_id': list_id,
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'quantity': quantity,
                'price': float(price),
                'category': auto_categorize_item(data.get('name')),
                'status': data.get('status', 'to_buy'),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'store': data.get('store', 'Unknown'),
                'frequency': int(data.get('frequency', 7))
            }
            with db.client.start_session() as mongo_session:
                with mongo_session.start_transaction():
                    result = db.grocery_items.insert_one(item_data, session=mongo_session)
                    db.grocery_lists.update_one(
                        {'_id': ObjectId(list_id)},
                        {'$inc': {'total_spent': float(price * quantity)}, '$set': {'updated_at': datetime.utcnow()}},
                        session=mongo_session
                    )
                    if current_user.is_authenticated and not is_admin():
                        if not deduct_ficore_credits(db, current_user.id, 0.5, 'add_grocery_item', str(result.inserted_id), mongo_session):
                            logger.error(f"Failed to deduct 0.5 Ficore Credits for adding item {result.inserted_id} to list {list_id} by user {current_user.id}", 
                                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                            raise ValueError(f"Failed to deduct Ficore Credits for adding item {result.inserted_id}")
            logger.info(f"Added item {result.inserted_id} to list {list_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'item_id': str(result.inserted_id), 'message': trans('grocery_item_added', default='Item added to list successfully')}), 201
        if request.method == 'PUT':
            data = request.get_json()
            item_id = data.get('item_id')
            item = db.grocery_items.find_one({'_id': ObjectId(item_id), 'list_id': list_id, 'user_id': str(current_user.id)})
            if not item:
                return jsonify({'error': trans('grocery_item_not_found', default='Item not found or you are not the owner.')}), 404
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                    logger.warning(f"Insufficient Ficore Credits for updating item {item_id} in list {list_id} by user {current_user.id}", 
                                 extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to update an item. Please purchase more credits.')}), 403
            original_item = item.copy()
            updates = {}
            if 'status' in data:
                updates['status'] = data['status']
            if 'quantity' in data:
                updates['quantity'] = int(data['quantity'])
            if 'price' in data:
                updates['price'] = float(clean_currency(data['price']))
            if updates:
                updates['updated_at'] = datetime.utcnow()
                with db.client.start_session() as mongo_session:
                    with mongo_session.start_transaction():
                        db.grocery_items.update_one({'_id': ObjectId(item_id)}, {'$set': updates}, session=mongo_session)
                        items = db.grocery_items.find({'list_id': list_id, 'status': 'bought'}, session=mongo_session)
                        total_spent = sum(float(item.get('price', 0)) * item.get('quantity', 1) for item in items)
                        db.grocery_lists.update_one(
                            {'_id': ObjectId(list_id)},
                            {'$set': {'total_spent': total_spent, 'updated_at': datetime.utcnow()}},
                            session=mongo_session
                        )
                        if current_user.is_authenticated and not is_admin():
                            if not deduct_ficore_credits(db, current_user.id, 0.5, 'update_grocery_item', item_id, mongo_session):
                                logger.error(f"Failed to deduct 0.5 Ficore Credits for updating item {item_id} in list {list_id} by user {current_user.id}", 
                                            extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                                raise ValueError(f"Failed to deduct Ficore Credits for updating item {item_id}")
            logger.info(f"Updated item {item_id} in list {list_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_item_updated', default='Item updated successfully')}), 200
        items = db.grocery_items.find({'list_id': list_id}).sort('created_at', -1)
        return jsonify([{
            'id': str(i['_id']),
            'name': i.get('name'),
            'quantity': i.get('quantity', 1),
            'price': float(i.get('price', 0)),
            'category': i.get('category', 'other'),
            'status': i.get('status', 'to_buy'),
            'store': i.get('store', 'Unknown'),
            'frequency': i.get('frequency', 7)
        } for i in items]), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for managing items in list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_item_error', default='Error managing items. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error managing items for list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_item_error', default='Error managing items due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error managing items for list {list_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_item_error', default='Error managing items. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/share', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def share_list(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        data = request.get_json()
        collaborator_email = data.get('email')
        if not collaborator_email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', collaborator_email):
            return jsonify({'error': trans('grocery_invalid_email', default='Invalid email address format.')}), 400
        collaborator = db.users.find_one({'email': collaborator_email})
        if not collaborator:
            return jsonify({'error': trans('grocery_user_not_found', default='User with this email not found.')}), 404
        db.grocery_lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$addToSet': {'collaborators': collaborator_email}, '$set': {'updated_at': datetime.utcnow()}}
        )
        logger.info(f"Shared list {list_id} with {collaborator_email} by user {current_user.id}", 
                   extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'message': trans('grocery_list_shared', default='List shared successfully')}), 200
    except Exception as e:
        logger.error(f"Error sharing list {list_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_share_error', default='Error sharing list. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/suggestions', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_suggestions(list_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id)})
        if not grocery_list or (str(current_user.id) not in [grocery_list['user_id']] + grocery_list.get('collaborators', [])):
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or access denied.')}), 404
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity'):
                return jsonify({'error': trans('grocery_invalid_suggestion', default='Invalid or missing suggestion data. Please provide name and quantity.')}), 400
            suggestion_data = {
                'list_id': list_id,
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'quantity': int(data.get('quantity', 1)),
                'price': float(clean_currency(data.get('price', '0'))),
                'category': auto_categorize_item(data.get('name')),
                'status': 'pending',
                'created_at': datetime.utcnow()
            }
            result = db.grocery_suggestions.insert_one(suggestion_data)
            logger.info(f"Added suggestion {result.inserted_id} to list {list_id} by user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'suggestion_id': str(result.inserted_id), 'message': trans('grocery_suggestion_added', default='Suggestion added successfully')}), 201
        suggestions = db.grocery_suggestions.find({'list_id': list_id}).sort('created_at', -1)
        return jsonify([{
            'id': str(s['_id']),
            'name': s.get('name'),
            'quantity': s.get('quantity', 1),
            'price': float(s.get('price', 0)),
            'category': s.get('category', 'other'),
            'status': s.get('status', 'pending'),
            'user_id': s.get('user_id')
        } for s in suggestions]), 200
    except Exception as e:
        logger.error(f"Error managing suggestions for list {list_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error managing suggestions. Please try again later.')}), 500

@grocery_bp.route('/lists/<list_id>/suggestions/<suggestion_id>/approve', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def approve_suggestion(list_id, suggestion_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(list_id):
            logger.error(f"Invalid list_id {list_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_list_id', default='Invalid list ID format.')}), 400
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or you are not the owner.')}), 404
        suggestion = db.grocery_suggestions.find_one({'_id': ObjectId(suggestion_id), 'list_id': list_id})
        if not suggestion:
            return jsonify({'error': trans('grocery_suggestion_not_found', default='Suggestion not found.')}), 404
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                logger.warning(f"Insufficient Ficore Credits for approving suggestion {suggestion_id} in list {list_id} by user {current_user.id}", 
                             extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to approve a suggestion. Please purchase more credits.')}), 403
        with db.client.start_session() as mongo_session:
            with mongo_session.start_transaction():
                item_data = {
                    'list_id': list_id,
                    'user_id': str(current_user.id),
                    'name': suggestion.get('name'),
                    'quantity': suggestion.get('quantity', 1),
                    'price': suggestion.get('price', 0),
                    'category': suggestion.get('category', 'other'),
                    'status': 'to_buy',
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                    'store': suggestion.get('store', 'Unknown'),
                    'frequency': suggestion.get('frequency', 7)
                }
                result = db.grocery_items.insert_one(item_data, session=mongo_session)
                db.grocery_suggestions.update_one(
                    {'_id': ObjectId(suggestion_id)},
                    {'$set': {'status': 'approved', 'updated_at': datetime.utcnow()}},
                    session=mongo_session
                )
                db.grocery_lists.update_one(
                    {'_id': ObjectId(list_id)},
                    {'$inc': {'total_spent': float(suggestion.get('price', 0) * suggestion.get('quantity', 1))},
                     '$set': {'updated_at': datetime.utcnow()}},
                    session=mongo_session
                )
                if current_user.is_authenticated and not is_admin():
                    if not deduct_ficore_credits(db, current_user.id, 0.5, 'approve_grocery_suggestion', str(result.inserted_id), mongo_session):
                        logger.error(f"Failed to deduct 0.5 Ficore Credits for approving suggestion {suggestion_id} in list {list_id} by user {current_user.id}", 
                                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                        raise ValueError(f"Failed to deduct Ficore Credits for approving suggestion {suggestion_id}")
            logger.info(f"Approved suggestion {suggestion_id} for list {list_id} by user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_suggestion_approved', default='Suggestion approved and added to list successfully')}), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for approving suggestion {suggestion_id} in list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error approving suggestion. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error approving suggestion {suggestion_id} for list {list_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error approving suggestion due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error approving suggestion {suggestion_id} for list {list_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error approving suggestion. Please try again later.')}), 500

@grocery_bp.route('/meal_plans', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_meal_plans():
    db = get_mongo_db()
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name'):
                return jsonify({'error': trans('grocery_invalid_meal_plan', default='Invalid or missing meal plan data. Please provide a name.')}), 400
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                    logger.warning(f"Insufficient Ficore Credits for creating meal plan by user {current_user.id}", 
                                 extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to create a meal plan. Please purchase more credits.')}), 403
            meal_plan = {
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'ingredients': [{
                    'name': i.get('name'),
                    'quantity': int(i.get('quantity', 1)),
                    'category': auto_categorize_item(i.get('name')),
                    'price': float(clean_currency(i.get('price', '0')))
                } for i in data.get('ingredients', [])],
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            with db.client.start_session() as mongo_session:
                with mongo_session.start_transaction():
                    result = db.meal_plans.insert_one(meal_plan, session=mongo_session)
                    if data.get('auto_generate_list'):
                        budget = float(clean_currency(data.get('budget', '0')))
                        list_data = {
                            'name': f"{data.get('name')} Grocery List",
                            'user_id': str(current_user.id),
                            'budget': budget,
                            'created_at': datetime.utcnow(),
                            'updated_at': datetime.utcnow(),
                            'collaborators': [],
                            'items': [],
                            'total_spent': 0.0,
                            'status': 'active'
                        }
                        list_result = db.grocery_lists.insert_one(list_data, session=mongo_session)
                        for ingredient in meal_plan['ingredients']:
                            item_result = db.grocery_items.insert_one({
                                'list_id': str(list_result.inserted_id),
                                'user_id': str(current_user.id),
                                'name': ingredient['name'],
                                'quantity': ingredient['quantity'],
                                'price': ingredient['price'],
                                'category': ingredient['category'],
                                'status': 'to_buy',
                                'created_at': datetime.utcnow(),
                                'updated_at': datetime.utcnow(),
                                'store': 'Unknown',
                                'frequency': 7
                            }, session=mongo_session)
                            if current_user.is_authenticated and not is_admin():
                                if not deduct_ficore_credits(db, current_user.id, 0.5, 'add_grocery_item_from_meal_plan', str(item_result.inserted_id), mongo_session):
                                    logger.error(f"Failed to deduct 0.5 Ficore Credits for adding item {item_result.inserted_id} to list {list_result.inserted_id} by user {current_user.id}", 
                                                extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                                    raise ValueError(f"Failed to deduct Ficore Credits for adding item {item_result.inserted_id}")
                        list_data['total_spent'] = sum(i['price'] * i['quantity'] for i in meal_plan['ingredients'])
                        db.grocery_lists.update_one(
                            {'_id': list_result.inserted_id},
                            {'$set': {'total_spent': list_data['total_spent'], 'updated_at': datetime.utcnow()}},
                            session=mongo_session
                        )
                    if current_user.is_authenticated and not is_admin():
                        if not deduct_ficore_credits(db, current_user.id, 0.5, 'create_meal_plan', str(result.inserted_id), mongo_session):
                            logger.error(f"Failed to deduct 0.5 Ficore Credits for creating meal plan {result.inserted_id} by user {current_user.id}", 
                                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                            raise ValueError(f"Failed to deduct Ficore Credits for creating meal plan {result.inserted_id}")
            logger.info(f"Created meal plan {result.inserted_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'meal_plan_id': str(result.inserted_id), 'message': trans('grocery_meal_plan_created', default='Meal plan created successfully')}), 201
        meal_plans = db.meal_plans.find({'user_id': str(current_user.id)}).sort('updated_at', -1)
        return jsonify([{
            'id': str(m['_id']),
            'name': m.get('name'),
            'ingredients': m.get('ingredients', []),
            'created_at': m.get('created_at').isoformat()
        } for m in meal_plans]), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for creating meal plan or grocery list by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_credit_deduction_failed', default='Failed to deduct Ficore Credits. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error during meal plan creation for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_meal_plan_error', default='Error managing meal plans due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error managing meal plans for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_meal_plan_error', default='Error managing meal plans. Please try again later.')}), 500

@grocery_bp.route('/meal_plans/<meal_plan_id>/ingredients', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def add_ingredient(meal_plan_id):
    db = get_mongo_db()
    try:
        if not ObjectId.is_valid(meal_plan_id):
            logger.error(f"Invalid meal_plan_id {meal_plan_id}: not a valid ObjectId", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'error': trans('grocery_invalid_meal_plan_id', default='Invalid meal plan ID format.')}), 400
        meal_plan = db.meal_plans.find_one({'_id': ObjectId(meal_plan_id), 'user_id': str(current_user.id)})
        if not meal_plan:
            return jsonify({'error': trans('grocery_meal_plan_not_found', default='Meal plan not found or you are not the owner.')}), 404
        data = request.get_json()
        if not data or not data.get('name') or not data.get('quantity') or not data.get('price'):
            return jsonify({'error': trans('grocery_invalid_ingredient', default='Invalid or missing ingredient data. Please provide name, quantity, and price.')}), 400
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=0.5, user_id=current_user.id):
                logger.warning(f"Insufficient Ficore Credits for adding ingredient to meal plan {meal_plan_id} by user {current_user.id}", 
                             extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits to add an ingredient. Please purchase more credits.')}), 403
        ingredient = {
            'name': data.get('name'),
            'quantity': int(data.get('quantity', 1)),
            'category': auto_categorize_item(data.get('name')),
            'price': float(clean_currency(data.get('price', '0')))
        }
        with db.client.start_session() as mongo_session:
            with mongo_session.start_transaction():
                result = db.meal_plans.update_one(
                    {'_id': ObjectId(meal_plan_id)},
                    {'$push': {'ingredients': ingredient}, '$set': {'updated_at': datetime.utcnow()}},
                    session=mongo_session
                )
                if result.modified_count == 0:
                    logger.error(f"Failed to add ingredient to meal plan {meal_plan_id} for user {current_user.id}: No documents modified", 
                                extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                    raise ValueError(f"Failed to add ingredient to meal plan {meal_plan_id}")
                if current_user.is_authenticated and not is_admin():
                    if not deduct_ficore_credits(db, current_user.id, 0.5, 'add_meal_plan_ingredient', str(meal_plan_id), mongo_session):
                        logger.error(f"Failed to deduct 0.5 Ficore Credits for adding ingredient to meal plan {meal_plan_id} by user {current_user.id}", 
                                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
                        raise ValueError(f"Failed to deduct Ficore Credits for adding ingredient to meal plan {meal_plan_id}")
            logger.info(f"Added ingredient to meal plan {meal_plan_id} for user {current_user.id}", 
                       extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_ingredient_added', default='Ingredient added to meal plan successfully')}), 200
    except ValueError as e:
        logger.error(f"Transaction aborted for adding ingredient to meal plan {meal_plan_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_ingredient_error', default='Error adding ingredient. Please try again.')}), 500
    except errors.PyMongoError as e:
        logger.error(f"MongoDB error adding ingredient to meal plan {meal_plan_id} by user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_ingredient_error', default='Error adding ingredient due to database issue. Please try again later.')}), 500
    except Exception as e:
        logger.error(f"Unexpected error adding ingredient to meal plan {meal_plan_id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_ingredient_error', default='Error adding ingredient. Please try again later.')}), 500

@grocery_bp.route('/price_history/<item_name>', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def price_history(item_name):
    db = get_mongo_db()
    try:
        items = db.grocery_items.find({
            'user_id': str(current_user.id),
            'name': {'$regex': f'^{item_name}$', '$options': 'i'},
            'status': 'bought'
        }).sort('updated_at', -1).limit(10)
        prices = [{'price': float(i.get('price', 0)), 'store': i.get('store', 'Unknown'), 'date': i.get('updated_at').isoformat()} for i in items]
        if prices:
            avg_price = sum(p['price'] for p in prices) / len(prices)
            return jsonify({'prices': prices, 'average_price': float(avg_price)}), 200
        return jsonify({'prices': [], 'average_price': 0.0}), 200
    except Exception as e:
        logger.error(f"Error fetching price history for item {item_name}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_price_history_error', default='Error fetching price history. Please try again later.')}), 500

@grocery_bp.route('/suggestions', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def predictive_suggestions():
    try:
        db = get_mongo_db()
        suggestions = get_predictive_suggestions(current_user.id, db)
        logger.info(f"Fetched {len(suggestions)} predictive suggestions for user {current_user.id}", 
                   extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify(suggestions), 200
    except Exception as e:
        logger.error(f"Error fetching predictive suggestions for user {current_user.id}: {str(e)}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr, 'stack_trace': traceback.format_exc()})
        return jsonify({'error': trans('grocery_suggestions_error', default='Error fetching suggestions. Please try again later.')}), 500

def init_app(app):
    try:
        app.register_blueprint(grocery_bp)
        current_app.logger.info("Initialized grocery blueprint", extra={'session_id': 'no-request-context'})
    except Exception as e:
        current_app.logger.error(f"Error initializing grocery blueprint: {str(e)}", 
                                extra={'session_id': 'no-request-context', 'stack_trace': traceback.format_exc()})
        raise
