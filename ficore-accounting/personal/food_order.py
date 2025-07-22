from flask import Blueprint, jsonify, current_app, request, session, render_template, flash, redirect, url_for
from flask_login import current_user, login_required
from pymongo import errors
from bson import ObjectId
from utils import requires_role, get_mongo_db, check_ficore_credit_balance, is_admin
from translations import trans
import logging
from datetime import datetime, timedelta
import uuid
import geocoder

# Configure logging
logging.basicConfig(level=logging.DEBUG)

food_order_bp = Blueprint('food_order', __name__, url_prefix='/food_order', template_folder='templates/personal/FOOD_ORDER')

def deduct_ficore_credits(db, user_id, amount, action, order_id=None):
    """Deduct Ficore Credits from user balance and log the transaction using MongoDB transaction."""
    try:
        if amount <= 0:
            current_app.logger.error(f"Invalid deduction amount {amount} for user {user_id}, action: {action}")
            return False

        client = db.client
        user = db.users.find_one({'_id': user_id})
        if not user:
            current_app.logger.error(f"User {user_id} not found for credit deduction, action: {action}", extra={'session_id': session.get('sid', 'unknown')})
            return False
        current_balance = user.get('ficore_credit_balance', 0)
        if current_balance < amount:
            current_app.logger.warning(f"Insufficient credits for user {user_id}: required {amount}, available {current_balance}, action: {action}", extra={'session_id': session.get('sid', 'unknown')})
            return False

        with client.start_session() as mongo_session:
            with mongo_session.start_transaction():
                result = db.users.update_one(
                    {'_id': user_id},
                    {'$inc': {'ficore_credit_balance': -amount}},
                    session=mongo_session
                )
                if result.modified_count == 0:
                    current_app.logger.error(f"Failed to deduct {amount} credits for user {user_id}, action: {action}", extra={'session_id': session.get('sid', 'unknown')})
                    raise ValueError(f"Failed to update user balance for {user_id}")

                transaction = {
                    '_id': ObjectId(),
                    'user_id': user_id,
                    'action': action,
                    'amount': -amount,
                    'order_id': str(order_id) if order_id else None,
                    'timestamp': datetime.utcnow(),
                    'session_id': session.get('sid', 'unknown'),
                    'status': 'completed'
                }
                db.ficore_credit_transactions.insert_one(transaction, session=mongo_session)
        
        current_app.logger.info(f"Deducted {amount} Ficore Credits for {action} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
        return True
    except (ValueError, errors.PyMongoError) as e:
        current_app.logger.error(f"Transaction aborted for user {user_id}, action: {action}: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return False
    except Exception as e:
        current_app.logger.error(f"Error deducting {amount} Ficore Credits for {action} by user {user_id}: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return False
    finally:
        if 'mongo_session' in locals():
            mongo_session.end_session()

def format_currency(value):
    """Format a numeric value with comma separation, no currency symbol."""
    try:
        numeric_value = float(value)
        formatted = f"{numeric_value:,.2f}"
        current_app.logger.debug(f"Formatted value: input={value}, output={formatted}", extra={'session_id': session.get('sid', 'unknown')})
        return formatted
    except (ValueError, TypeError) as e:
        current_app.logger.warning(f"Format Error: input={value}, error={str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return "0.00"

@food_order_bp.route('/index', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def index():
    """Render the food order management interface."""
    try:
        db = get_mongo_db()
        user_id = str(current_user.id)
        orders = list(db.FoodOrder.find({'user_id': user_id}, {'_id': 0}).sort('created_at', -1).limit(10))
        
        # Format order data for template
        orders_data = []
        for order in orders:
            order_data = {
                'id': order['id'],
                'name': order.get('name', ''),
                'vendor': order.get('vendor', ''),
                'phone': order.get('phone', ''),
                'location': order.get('location', ''),
                'total_cost': format_currency(order.get('total_cost', 0.0)),
                'total_cost_raw': float(order.get('total_cost', 0.0)),
                'created_at': order.get('created_at').strftime('%Y-%m-%d %H:%M:%S'),
                'status': order.get('status', 'submitted'),
                'items': order.get('items', [])
            }
            orders_data.append(order_data)
        
        # Calculate summary statistics
        total_orders = len(orders_data)
        total_spent = sum(order['total_cost_raw'] for order in orders_data)
        pending_orders = sum(1 for order in orders_data if order['status'] == 'submitted')
        
        current_app.logger.info(f"Rendering food order index for user {user_id}, fetched {total_orders} orders", extra={'session_id': session.get('sid', 'unknown')})
        
        return render_template(
            'personal/FOOD_ORDER/food_order_main.html',
            title=trans('food_order_title', default='Food Order Manager'),
            orders_data=orders_data,
            total_orders=total_orders,
            total_spent=format_currency(total_spent),
            pending_orders=pending_orders,
            is_admin=is_admin(),
            is_anonymous=False
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering food order index: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        flash(trans('general_error', default='An error occurred while loading the food order dashboard'), 'danger')
        return render_template(
            'personal/FOOD_ORDER/error.html',
            title=trans('food_order_title', default='Food Order Manager'),
            error_message=trans('general_error', default='An error occurred while loading the food order dashboard'),
            is_admin=is_admin()
        ), 500

@food_order_bp.route('/get_nearest_vendor', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def get_nearest_vendor():
    """Get the nearest vendor based on user location."""
    try:
        location = request.args.get('location')
        if not location:
            return jsonify({'error': trans('food_order_missing_location', default='Location required')}), 400

        # Parse location (assuming format: latitude,longitude)
        try:
            lat, lng = map(float, location.split(','))
        except ValueError:
            current_app.logger.error(f"Invalid location format: {location}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_invalid_location', default='Invalid location format')}), 400

        # Mock vendor lookup (replace with actual vendor database query)
        db = get_mongo_db()
        vendors = db.vendors.find()  # Assume vendors collection with {name, location: {lat, lng}}
        nearest_vendor = None
        min_distance = float('inf')

        for vendor in vendors:
            vendor_loc = vendor.get('location', {})
            if 'lat' not in vendor_loc or 'lng' not in vendor_loc:
                continue
            distance = ((lat - vendor_loc['lat'])**2 + (lng - vendor_loc['lng'])**2)**0.5
            if distance < min_distance:
                min_distance = distance
                nearest_vendor = vendor['name']

        if nearest_vendor:
            return jsonify({'vendor': nearest_vendor})
        else:
            return jsonify({'error': trans('food_order_no_vendors', default='No vendors found nearby')}), 404

    except Exception as e:
        current_app.logger.error(f"Error finding nearest vendor: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

@food_order_bp.route('/manage_orders', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_orders():
    """Manage food orders: list all orders (GET) or create a new order (POST)."""
    try:
        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        if request.method == 'GET':
            orders = list(collection.find({'user_id': user_id}, {'_id': 0}))
            current_app.logger.info(f"Retrieved {len(orders)} food orders for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(orders)

        elif request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('vendor') or not data.get('phone') or not data.get('location'):
                current_app.logger.warning(f"Invalid order data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_data', default='Invalid order data')}), 400

            # Check for recent orders to prevent duplicates
            recent_order = collection.find_one({
                'user_id': user_id,
                'created_at': {'$gte': datetime.utcnow() - timedelta(minutes=5)}
            })
            if recent_order:
                current_app.logger.warning(f"Duplicate order attempt by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_duplicate', default='Please wait 5 minutes before creating another order')}), 429

            # Check Ficore Credits for authenticated non-admin users
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.1, user_id=current_user.id):
                    current_app.logger.warning(f"Insufficient Ficore Credits for creating order by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_insufficient_credits', default='Insufficient Ficore Credits to create an order. Please purchase more credits.')}), 403

            order = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'name': data['name'],
                'vendor': data['vendor'],
                'phone': data['phone'],
                'location': data['location'],
                'total_cost': 0.0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'shared_with': [],  # For future sharing functionality
                'items': [],
                'status': 'submitted'  # For future vendor confirmation
            }
            result = collection.insert_one(order)

            # Deduct Ficore Credits
            if current_user.is_authenticated and not is_admin():
                if not deduct_ficore_credits(db, current_user.id, 0.1, 'create_food_order', order['id']):
                    collection.delete_one({'id': order['id']})
                    current_app.logger.error(f"Failed to deduct 0.1 Ficore Credits for creating order {order['id']} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_credit_deduction_failed', default='Failed to deduct Ficore Credits for creating order.')}), 500

            # Send order to vendor (mock implementation)
            send_order_to_vendor(order)

            current_app.logger.info(f"Created food order {order['id']} for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({k: v for k, v in order.items() if k != '_id'})

    except Exception as e:
        current_app.logger.error(f"Error in manage_orders: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

@food_order_bp.route('/manage_orders/<order_id>', methods=['DELETE'])
@login_required
@requires_role(['personal', 'admin'])
def delete_order(order_id):
    """Delete a food order."""
    try:
        # Validate order_id as a valid UUID
        try:
            uuid.UUID(order_id)
        except ValueError:
            current_app.logger.error(f"Invalid order_id {order_id}: not a valid UUID", 
                                     extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_invalid_order_id', default='Invalid order ID')}), 400

        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        # Verify order exists and belongs to user
        order = collection.find_one({'id': order_id, 'user_id': user_id})
        if not order:
            current_app.logger.warning(f"Order {order_id} not found for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_not_found', default='Order not found')}), 404

        result = collection.delete_one({'id': order_id})
        if result.deleted_count == 0:
            current_app.logger.error(f"Failed to delete order {order_id} for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_delete_failed', default='Failed to delete order')}), 500

        current_app.logger.info(f"Deleted order {order_id} for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'success': True})

    except Exception as e:
        current_app.logger.error(f"Error deleting order {order_id}: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

@food_order_bp.route('/manage_items/<order_id>', methods=['GET', 'POST', 'PUT'])
@login_required
@requires_role(['personal', 'admin'])
def manage_items(order_id):
    """Manage items in a food order: list items (GET), add item (POST), update item (PUT)."""
    try:
        # Validate order_id as a valid UUID
        try:
            uuid.UUID(order_id)
        except ValueError:
            current_app.logger.error(f"Invalid order_id {order_id}: not a valid UUID", 
                                     extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_invalid_order_id', default='Invalid order ID')}), 400

        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        # Verify order exists and belongs to user
        order = collection.find_one({'id': order_id, 'user_id': user_id})
        if not order:
            current_app.logger.warning(f"Order {order_id} not found for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_not_found', default='Order not found')}), 404

        if request.method == 'GET':
            items = order.get('items', [])
            current_app.logger.info(f"Retrieved {len(items)} items for order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(items)

        elif request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity') or not data.get('price'):
                current_app.logger.warning(f"Invalid item data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_item_data', default='Invalid item data')}), 400

            # Check Ficore Credits for authenticated non-admin users
            if current_user.is_authenticated and not is_admin():
                if not check_ficore_credit_balance(required_amount=0.1, user_id=current_user.id):
                    current_app.logger.warning(f"Insufficient Ficore Credits for adding item to order {order_id} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_insufficient_credits', default='Insufficient Ficore Credits to add an item. Please purchase more credits.')}), 403

            item = {
                'item_id': str(uuid.uuid4()),
                'name': data['name'],
                'quantity': int(data['quantity']),
                'price': float(data['price']),
                'notes': data.get('notes', ''),
                'category': data.get('category', 'Uncategorized')
            }
            result = collection.update_one(
                {'id': order_id},
                {
                    '$push': {'items': item},
                    '$set': {
                        'total_cost': order['total_cost'] + (item['quantity'] * item['price']),
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            # Deduct Ficore Credits
            if current_user.is_authenticated and not is_admin():
                if not deduct_ficore_credits(db, current_user.id, 0.1, 'add_food_order_item', item['item_id']):
                    # Roll back by removing the item
                    collection.update_one(
                        {'id': order_id},
                        {
                            '$pull': {'items': {'item_id': item['item_id']}},
                            '$set': {'updated_at': datetime.utcnow()}
                        }
                    )
                    current_app.logger.error(f"Failed to deduct 0.1 Ficore Credits for adding item {item['item_id']} to order {order_id} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_credit_deduction_failed', default='Failed to deduct Ficore Credits for adding item.')}), 500

            # Notify vendor of updated order
            updated_order = collection.find_one({'id': order_id})
            send_order_to_vendor(updated_order)

            current_app.logger.info(f"Added item {item['item_id']} to order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(item)

        elif request.method == 'PUT':
            data = request.get_json()
            if not data or not data.get('item_id') or not data.get('field') or data.get('field') not in ['quantity', 'price', 'notes']:
                current_app.logger.warning(f"Invalid update data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_update_data', default='Invalid update data')}), 400

            item_id = data['item_id']
            field = data['field']
            value = data[field]

            # Check Ficore Credits for authenticated non-admin users (except for notes updates)
            if current_user.is_authenticated and not is_admin() and field != 'notes':
                if not check_ficore_credit_balance(required_amount=0.1, user_id=current_user.id):
                    current_app.logger.warning(f"Insufficient Ficore Credits for updating item {item_id} in order {order_id} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_insufficient_credits', default='Insufficient Ficore Credits to update an item. Please purchase more credits.')}), 403

            # Find the item
            items = order.get('items', [])
            item_index = next((i for i, item in enumerate(items) if item['item_id'] == item_id), None)
            if item_index is None:
                current_app.logger.warning(f"Item {item_id} not found in order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_item_not_found', default='Item not found')}), 404

            # Store original item for potential rollback
            original_item = items[item_index].copy()

            # Update item
            items[item_index][field] = int(value) if field == 'quantity' else float(value) if field == 'price' else value
            total_cost = sum(item['quantity'] * item['price'] for item in items)
            result = collection.update_one(
                {'id': order_id},
                {
                    '$set': {
                        'items': items,
                        'total_cost': total_cost,
                        'updated_at': datetime.utcnow()
                    }
                }
            )

            # Deduct Ficore Credits (except for notes updates)
            if current_user.is_authenticated and not is_admin() and field != 'notes':
                if not deduct_ficore_credits(db, current_user.id, 0.1, 'update_food_order_item', item_id):
                    # Roll back by restoring the original item
                    items[item_index] = original_item
                    total_cost = sum(item['quantity'] * item['price'] for item in items)
                    collection.update_one(
                        {'id': order_id},
                        {
                            '$set': {
                                'items': items,
                                'total_cost': total_cost,
                                'updated_at': datetime.utcnow()
                            }
                        }
                    )
                    current_app.logger.error(f"Failed to deduct 0.1 Ficore Credits for updating item {item_id} in order {order_id} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                    return jsonify({'error': trans('food_order_credit_deduction_failed', default='Failed to deduct Ficore Credits for updating item.')}), 500

            # Notify vendor of updated order
            updated_order = collection.find_one({'id': order_id})
            send_order_to_vendor(updated_order)

            current_app.logger.info(f"Updated item {item_id} in order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'success': True})

    except Exception as e:
        current_app.logger.error(f"Error in manage_items: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

@food_order_bp.route('/reorder/<order_id>', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def reorder(order_id):
    """Reorder a previous food order."""
    try:
        # Validate order_id as a valid UUID
        try:
            uuid.UUID(order_id)
        except ValueError:
            current_app.logger.error(f"Invalid order_id {order_id}: not a valid UUID", 
                                     extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_invalid_order_id', default='Invalid order ID')}), 400

        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        # Verify order exists and belongs to user
        order = collection.find_one({'id': order_id, 'user_id': user_id})
        if not order:
            current_app.logger.warning(f"Order {order_id} not found for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_not_found', default='Order not found')}), 404

        # Check for recent orders to prevent duplicates
        recent_order = collection.find_one({
            'user_id': user_id,
            'created_at': {'$gte': datetime.utcnow() - timedelta(minutes=5)}
        })
        if recent_order:
            current_app.logger.warning(f"Duplicate order attempt by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_duplicate', default='Please wait 5 minutes before creating another order')}), 429

        # Check Ficore Credits for authenticated non-admin users
        if current_user.is_authenticated and not is_admin():
            if not check_ficore_credit_balance(required_amount=0.1, user_id=current_user.id):
                current_app.logger.warning(f"Insufficient Ficore Credits for reordering order {order_id} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_insufficient_credits', default='Insufficient Ficore Credits to reorder. Please purchase more credits.')}), 403

        # Create new order with same details
        new_order = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'name': order['name'],
            'vendor': order['vendor'],
            'phone': order['phone'],
            'location': order['location'],
            'total_cost': order['total_cost'],
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'shared_with': [],
            'items': order['items'],
            'status': 'submitted'
        }
        result = collection.insert_one(new_order)

        # Deduct Ficore Credits
        if current_user.is_authenticated and not is_admin():
            if not deduct_ficore_credits(db, current_user.id, 0.1, 'reorder_food_order', new_order['id']):
                collection.delete_one({'id': new_order['id']})
                current_app.logger.error(f"Failed to deduct 0.1 Ficore Credits for reordering order {new_order['id']} by user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_credit_deduction_failed', default='Failed to deduct Ficore Credits for reordering.')}), 500

        # Send order to vendor
        send_order_to_vendor(new_order)

        current_app.logger.info(f"Reordered order {order_id} as new order {new_order['id']} for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({k: v for k, v in new_order.items() if k != '_id'})

    except Exception as e:
        current_app.logger.error(f"Error in reorder: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

def send_order_to_vendor(order):
    """Mock function to send order to vendor (email, SMS, or dashboard)."""
    try:
        # Implement actual vendor notification logic here (e.g., email, SMS, or dashboard update)
        current_app.logger.info(f"Order {order['id']} sent to vendor {order['vendor']}: {order}")
    except Exception as e:
        current_app.logger.error(f"Error sending order {order['id']} to vendor: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})

def init_app(app):
    """Initialize the food order blueprint."""
    try:
        app.config['API_URLS']['getNearestVendor'] = '/food_order/get_nearest_vendor'
        app.config['API_URLS']['manageFoodOrders'] = '/food_order/manage_orders'
        app.config['API_URLS']['manageFoodOrderItems'] = '/food_order/manage_items/<order_id>'
        app.config['API_URLS']['reorderFoodOrder'] = '/food_order/reorder/<order_id>'
        current_app.logger.info("Food order blueprint initialized successfully", extra={'session_id': 'no-request-context'})
    except Exception as e:
        current_app.logger.error(f"Error initializing food order blueprint: {str(e)}", extra={'session_id': 'no-request-context'})
        raise
