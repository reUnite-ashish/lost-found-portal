from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import os
from datetime import datetime, timedelta
import re
import csv
import io
from flask_pymongo import PyMongo
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import json
import shutil
import zipfile

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your-app-password')
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_USERNAME', 'your-email@gmail.com')

# Explicit limiter backend avoids Flask-Limiter in-memory default warning.
app.config['RATELIMIT_STORAGE_URI'] = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')

# Initialize extensions
mail = Mail(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=app.config['RATELIMIT_STORAGE_URI']
)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# MongoDB configuration
app.config['MONGO_URI'] = 'mongodb+srv://Ashish-reunite:ASHish8r@cluster0.rhonu58.mongodb.net/reunite_db?retryWrites=true&w=majority&appName=Cluster0'
mongo = PyMongo(app)


# Ensure default admin user exists in MongoDB
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash

def ensure_admin_user():
    admin = mongo.db.users.find_one({'username': 'ashish&nitesh'})
    if not admin:
        mongo.db.users.insert_one({
            'username': 'ashish&nitesh',
            'email': 'ashishpaande@gmail.com',
            'password': generate_password_hash('mppg301'),
            'created_at': datetime.now(),
            'is_admin': True
        })
ensure_admin_user()

# Utility Functions
def send_email(to, subject, body):
    """Send email notification"""
    try:
        msg = Message(subject, recipients=[to])
        msg.body = body
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def log_admin_action(admin_id, action, details, target_type=None, target_id=None):
    """Log admin actions for audit trail"""
    mongo.db.admin_logs.insert_one({
        'admin_id': admin_id,
        'action': action,
        'details': details,
        'target_type': target_type,
        'target_id': target_id,
        'timestamp': datetime.now(),
        'ip_address': request.remote_addr
    })

def detect_spam(text):
    """Simple spam detection based on keywords and patterns"""
    spam_keywords = [
        'free money', 'lottery', 'winner', 'urgent', 'limited time',
        'buy now', 'discount', 'offer', 'prize', 'jackpot',
        'http://', 'https://', 'www.', '.com', '.net', '.org'
    ]
    text_lower = text.lower()
    spam_score = 0

    # Check for spam keywords
    for keyword in spam_keywords:
        if keyword in text_lower:
            spam_score += 1

    # Check for excessive caps
    caps_ratio = sum(1 for c in text if c.isupper()) / len(text) if text else 0
    if caps_ratio > 0.3:
        spam_score += 2

    return spam_score > 3

def create_backup():
    """Create a backup of key MongoDB collections and return the zip filename."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_dir = f'backup_{timestamp}'
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs('backups', exist_ok=True)

    collections = ['users', 'items', 'claims', 'admin_logs', 'spam_logs']
    for collection_name in collections:
        data = list(mongo.db[collection_name].find())
        with open(os.path.join(backup_dir, f'{collection_name}.json'), 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=2)

    zip_filename = f'backup_{timestamp}.zip'
    zip_path = os.path.join('backups', zip_filename)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_name = os.path.relpath(file_path, backup_dir)
                zipf.write(file_path, arc_name)

    shutil.rmtree(backup_dir)
    return zip_filename

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin', False):
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    lost_count = mongo.db.items.count_documents({'type': 'lost'})
    found_count = mongo.db.items.count_documents({'type': 'found'})
    match_count = mongo.db.found_matches.count_documents({})
    return render_template('index.html', lost_count=lost_count, found_count=found_count, match_count=match_count)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not username or not email or not password or not confirm_password:
            flash('All fields are required', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))
        
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': generate_password_hash(password),
            'created_at': datetime.now(),
            'is_admin': False
        })
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = mongo.db.users.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            if not user.get('is_active', True):
                flash('⛔ Your account has been banned. Please contact admin for assistance.', 'danger')
                return render_template('login.html', banned=True)
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('browse' if not user.get('is_admin') else 'admin_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('index'))

@app.route('/browse')
def browse():
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    query = {}
    if item_type:
        query['type'] = item_type
    if category:
        query['category'] = category
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    items = list(mongo.db.items.find(query))
    return render_template('browse.html', items=items, item_type=item_type, category=category, search=search)

@app.route('/api/items')
@limiter.limit("30 per minute")
def api_items():
    item_type = request.args.get('type', '')
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    query = {}
    if item_type:
        query['type'] = item_type
    if category:
        query['category'] = category
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    items = list(mongo.db.items.find(query))
    def item_json(item):
        return {
            'id': str(item['_id']),
            'name': item['name'],
            'type': item['type'],
            'category': item['category'],
            'location': item['location'],
            'description': item['description'],
            'image': item.get('image'),
            'reporter_name': item.get('reporter_name', 'Unknown'),
            'reporter_id': item.get('reporter_id', 0)
        }
    return jsonify([item_json(item) for item in items])

@app.route('/report', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
@login_required
def report():
    if request.method == 'POST':
        name = request.form.get('name')
        item_type = request.form.get('type')
        category = request.form.get('category')
        location = request.form.get('location')
        description = request.form.get('description')
        filename = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        if not all([name, item_type, category, location]):
            flash('All fields are required', 'danger')
            return redirect(url_for('report'))
        item_doc = {
            'name': name,
            'type': item_type,
            'category': category,
            'location': location,
            'description': description,
            'image': filename,
            'reporter_id': session['user_id'],
            'reporter_name': session['username'],
            'created_at': datetime.now(),
            'status': 'active'
        }
        item_id = mongo.db.items.insert_one(item_doc).inserted_id
        # Auto-create notifications for matching items
        opposite_type = 'found' if item_type == 'lost' else 'lost'
        matching_items = list(mongo.db.items.find({
            'type': opposite_type,
            'category': category,
            'status': 'active'
        }))
        if matching_items:
            for matched_item in matching_items:
                mongo.db.notifications.insert_one({
                    'user_id': matched_item['reporter_id'],
                    'message': f"🎉 A similar {item_type} item found! '{matched_item['name']}' matches your '{name}'. Check it out and raise a claim!",
                    'original_item_id': str(item_id),
                    'matched_item_id': str(matched_item['_id']),
                    'created_at': datetime.now(),
                    'read': False
                })
        flash('Item reported successfully!', 'success')
        return redirect(url_for('browse'))
    return render_template('report.html')

@app.route('/item/<item_id>')
def view_item(item_id):
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('browse'))
    return render_template('item_detail.html', item=item)

@app.route('/claim/<item_id>', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
@login_required
def claim_item(item_id):
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('browse'))
    
    if request.method == 'POST':
        proof = request.form.get('proof')
        
        if not proof:
            flash('Please provide proof of ownership', 'danger')
            return redirect(url_for('claim_item', item_id=item_id))
        
        mongo.db.claims.insert_one({
            'item_id': item_id,
            'claimant_id': session['user_id'],
            'claimant_name': session['username'],
            'proof': proof,
            'item_name': item['name'],
            'item_owner_name': item['reporter_name'],
            'item_owner_id': item['reporter_id'],
            'created_at': datetime.now(),
            'status': 'pending'
        })
        
        flash('Claim submitted! Admin will verify soon.', 'success')
        return redirect(url_for('browse'))
    
    return render_template('claim.html', item=item)

@app.route('/found-match/<item_id>', methods=['GET', 'POST'])
@limiter.limit("20 per hour")
@login_required
def found_match(item_id):
    """Route for when someone reports they FOUND a LOST item"""
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('browse'))
    
    if item['type'] != 'lost':
        flash('This feature only works with LOST items', 'danger')
        return redirect(url_for('browse'))
    
    if request.method == 'POST':
        location_found = request.form.get('location_found')
        description = request.form.get('description')
        contact_info = request.form.get('contact_info')
        
        if not all([location_found, description, contact_info]):
            flash('All fields are required', 'danger')
            return redirect(url_for('found_match', item_id=item_id))
        
        mongo.db.found_matches.insert_one({
            'lost_item_id': item_id,
            'finder_id': session['user_id'],
            'finder_name': session['username'],
            'finder_contact': contact_info,
            'location_found': location_found,
            'description': description,
            'created_at': datetime.now(),
            'status': 'pending'
        })
        
        flash('✅ Thank you! Your report has been sent to admin for verification. You\'ll be contacted if verified.', 'success')
        return redirect(url_for('browse'))
    
    return render_template('found_match.html', item=item)

@app.route('/admin')
@admin_required
def admin_dashboard():
    items = list(mongo.db.items.find())
    claims = list(mongo.db.claims.find())
    found_matches = list(mongo.db.found_matches.find())
    users = list(mongo.db.users.find())
    
    # Calculate statistics
    stats = {
        'lost_count': len([i for i in items if i['type'] == 'lost']),
        'found_count': len([i for i in items if i['type'] == 'found']),
        'active_count': len([i for i in items if i['status'] == 'active']),
        'resolved_count': len([i for i in items if i['status'] != 'active']),
        'active_users': len([u for u in users if u.get('is_active', True)]),
        'avg_items_per_user': len(items) / len(users) if users else 0,
        'success_rate': (len([i for i in items if i['status'] != 'active']) / len(items) * 100) if items else 0
    }
    
    # Add item count to users
    for user in users:
        user['item_count'] = len([i for i in items if i['reporter_id'] == user['_id']])
    
    # Get recent activity (last 10 items/claims/found_matches)
    recent_activity = []
    for item in items[-5:]:
        recent_activity.append({
            'description': f"New {item['type']} item reported: {item['name']}",
            'timestamp': item['created_at']
        })
    for claim in claims[-3:]:
        recent_activity.append({
            'description': f"Claim submitted for item {claim['item_id']}",
            'timestamp': claim['created_at']
        })
    for match in found_matches[-2:]:
        recent_activity.append({
            'description': f"Found report submitted for lost item {match['lost_item_id']}",
            'timestamp': match['created_at']
        })
    
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:10]
    
    return render_template('admin_dashboard.html',
                         items=items,
                         claims=claims,
                         found_matches=found_matches,
                         users=users,
                         stats=stats,
                         recent_activity=recent_activity)

@app.route('/admin/toggle-user-status/<user_id>', methods=['POST'])
@admin_required
def toggle_user_status(user_id):
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        user = None
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Prevent banning admin accounts
    if user.get('is_admin'):
        flash('Admin users cannot be banned.', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Toggle active status
    new_status = not user.get('is_active', True)
    mongo.db.users.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'is_active': new_status}}
    )
    
    action = 'banned' if not new_status else 'unbanned'
    flash(f'User {user["username"]} has been {action}', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/message-user/<user_id>', methods=['POST'])
@admin_required
def admin_message_user(user_id):
    try:
        target_user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    except Exception:
        target_user = None
    if not target_user:
        flash('User not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    admin_id = session['user_id']
    admin_name = session['username']
    target_id = str(target_user['_id'])

    # Reuse existing admin chat room if one already exists
    existing_room = mongo.db.chat_rooms.find_one({
        'type': 'admin_chat',
        'claimant_id': admin_id,
        'finder_id': target_id
    })
    if existing_room:
        return redirect(url_for('chat', room_id=str(existing_room['_id'])))

    # Create a new admin chat room
    room_id = mongo.db.chat_rooms.insert_one({
        'type': 'admin_chat',
        'claimant_id': admin_id,
        'claimant_name': admin_name,
        'finder_id': target_id,
        'finder_name': target_user['username'],
        'item_name': 'Admin Message',
        'created_at': datetime.now()
    }).inserted_id

    # Notify the user
    mongo.db.notifications.insert_one({
        'user_id': target_id,
        'type': 'admin_message',
        'message': f'📨 Admin has sent you a message. Click to open the chat.',
        'chat_room_id': str(room_id),
        'created_at': datetime.now(),
        'read': False
    })

    return redirect(url_for('chat', room_id=str(room_id)))

@app.route('/admin/delete-item/<item_id>', methods=['POST'])
@admin_required
def delete_item(item_id):
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Delete the item and related data
    mongo.db.items.delete_one({'_id': ObjectId(item_id)})
    mongo.db.claims.delete_many({'item_id': item_id})
    mongo.db.found_matches.delete_many({'lost_item_id': item_id})
    mongo.db.notifications.delete_many({'$or': [
        {'original_item_id': item_id},
        {'matched_item_id': item_id},
        {'item_id': item_id}
    ]})
    
    # Delete associated image file if it exists
    if item.get('image'):
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], item['image'])
        if os.path.exists(image_path):
            os.remove(image_path)
    
    flash(f'Item "{item["name"]}" and all related data have been deleted', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify-claim/<claim_id>', methods=['POST'])
@admin_required
def verify_claim(claim_id):
    try:
        claim = mongo.db.claims.find_one({'_id': ObjectId(claim_id)})
    except Exception:
        claim = None
    if not claim:
        return jsonify({'error': 'Claim not found'}), 404
    
    action = request.form.get('action')
    
    if action == 'approve':
        mongo.db.claims.update_one({'_id': ObjectId(claim_id)}, {'$set': {'status': 'verified'}})
        try:
            item = mongo.db.items.find_one({'_id': ObjectId(claim['item_id'])})
        except Exception:
            item = None
        if item:
            mongo.db.items.update_one({'_id': ObjectId(claim['item_id'])}, {'$set': {'status': 'claimed'}})
            mongo.db.claims.update_one({'_id': ObjectId(claim_id)}, {'$set': {
                'item_owner_name': item['reporter_name'],
                'item_owner_contact': item.get('reporter_contact', 'Not provided'),
                'item_name': item['name']
            }})

        # Create chat room between claimant (lost item owner) and finder (found item reporter)
        room_id = mongo.db.chat_rooms.insert_one({
            'claimant_id': claim['claimant_id'],
            'claimant_name': claim['claimant_name'],
            'finder_id': claim['item_owner_id'],
            'finder_name': claim.get('item_owner_name', 'Finder'),
            'item_id': claim['item_id'],
            'item_name': claim.get('item_name', 'Item'),
            'claim_id': claim_id,
            'created_at': datetime.now()
        }).inserted_id

        mongo.db.claims.update_one({'_id': ObjectId(claim_id)}, {'$set': {'chat_room_id': str(room_id)}})

        # Notify claimant (lost item owner)
        mongo.db.notifications.insert_one({
            'user_id': claim['claimant_id'],
            'type': 'claim_approved',
            'message': f'✅ Your claim for "{claim.get("item_name", "item")}" has been approved! You can now chat with the finder.',
            'chat_room_id': str(room_id),
            'item_id': claim['item_id'],
            'created_at': datetime.now(),
            'read': False
        })

        # Notify finder (found item reporter)
        mongo.db.notifications.insert_one({
            'user_id': claim['item_owner_id'],
            'type': 'claim_approved_finder',
            'message': f'✅ The claim for your found item "{claim.get("item_name", "item")}" has been approved! You can now chat with the owner.',
            'chat_room_id': str(room_id),
            'item_id': claim['item_id'],
            'created_at': datetime.now(),
            'read': False
        })

        flash('✅ Claim verified! Both parties can now connect via chat.', 'success')
    elif action == 'reject':
        mongo.db.claims.update_one({'_id': ObjectId(claim_id)}, {'$set': {'status': 'rejected'}})
        flash('❌ Claim rejected', 'info')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify-found-match/<match_id>', methods=['POST'])
@admin_required
def verify_found_match(match_id):
    """Admin verifies when someone reports they found a LOST item"""
    try:
        match = mongo.db.found_matches.find_one({'_id': ObjectId(match_id)})
    except Exception:
        match = None
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    
    action = request.form.get('action')
    
    if action == 'approve':
        mongo.db.found_matches.update_one({'_id': ObjectId(match_id)}, {'$set': {'status': 'verified'}})
        try:
            item = mongo.db.items.find_one({'_id': ObjectId(match['lost_item_id'])})
        except Exception:
            item = None
        if item:
            mongo.db.items.update_one({'_id': ObjectId(match['lost_item_id'])}, {'$set': {
                'status': 'matched',
                'finder_id': match['finder_id'],
                'finder_contact': match['finder_contact']
            }})
        
        flash('✅ Match verified! Both parties will be notified to connect.', 'success')
    elif action == 'reject':
        mongo.db.found_matches.update_one({'_id': ObjectId(match_id)}, {'$set': {'status': 'rejected'}})
        flash('Match report rejected', 'info')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/my-items')
@login_required
def my_items():
    user_items = list(mongo.db.items.find({'reporter_id': session['user_id']}))
    return render_template('my_items.html', items=user_items)


@app.route('/matches')
@login_required
def matches():
    user_items = list(mongo.db.items.find({'reporter_id': session['user_id']}))
    matches_list = []
    for user_item in user_items:
        opposite_type = 'found' if user_item['type'] == 'lost' else 'lost'
        other_items = list(mongo.db.items.find({'type': opposite_type, 'category': user_item['category']}))
        for other_item in other_items:
            score = 80 if user_item['name'].strip().lower() == other_item['name'].strip().lower() else 65
            if user_item['type'] == 'lost':
                matches_list.append({
                    'lost_item': user_item,
                    'found_item': other_item,
                    'score': score
                })
            else:
                matches_list.append({
                    'lost_item': other_item,
                    'found_item': user_item,
                    'score': score
                })
    return render_template('matches.html', matches_list=matches_list)

@app.route('/my-claims')
@login_required
def my_claims():
    user_claims = list(mongo.db.claims.find({'claimant_id': session['user_id']}))
    claims_with_items = []
    for claim in user_claims:
        try:
            item_info = mongo.db.items.find_one({'_id': ObjectId(claim['item_id'])})
        except Exception:
            item_info = None
        claims_with_items.append({
            'claim': claim, 
            'item': item_info
        })
    
    return render_template('my_claims.html', claims=claims_with_items)

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = list(mongo.db.notifications.find({'user_id': session['user_id']}).sort('created_at', -1))
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/send-contact-request/<item_id>', methods=['POST'])
@login_required
def send_contact_request(item_id):
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('browse'))
    
    message = request.form.get('message', '')
    if not message:
        flash('Message is required', 'danger')
        return redirect(url_for('view_item', item_id=item_id))
    
    mongo.db.contact_requests.insert_one({
        'from_user_id': session['user_id'],
        'from_username': session['username'],
        'to_user_id': item['reporter_id'],
        'to_username': item['reporter_name'],
        'item_id': item_id,
        'item_name': item['name'],
        'message': message,
        'created_at': datetime.now(),
        'status': 'pending'
    })
    
    flash('Contact request sent!', 'success')
    return redirect(url_for('browse'))

# VIEW CONTACT REQUESTS ROUTE
@app.route('/contact-requests')
@login_required
def contact_requests():
    # Requests I received
    received = list(mongo.db.contact_requests.find({'to_user_id': session['user_id']}))
    # Requests I sent
    sent = list(mongo.db.contact_requests.find({'from_user_id': session['user_id']}))
    
    received.sort(key=lambda x: x['created_at'], reverse=True)
    sent.sort(key=lambda x: x['created_at'], reverse=True)
    
    return render_template('contact_requests.html', received=received, sent=sent)

# RESPOND TO CONTACT REQUEST
@app.route('/contact-request/<request_id>/respond', methods=['POST'])
@login_required
def respond_contact_request(request_id):
    try:
        contact_req = mongo.db.contact_requests.find_one({'_id': ObjectId(request_id)})
    except Exception:
        contact_req = None
    if not contact_req:
        return jsonify({'error': 'Request not found'}), 404
    
    # Only receiver can respond
    if contact_req['to_user_id'] != session['user_id']:
        return jsonify({'error': 'Not authorized'}), 403
    
    action = request.form.get('action')
    
    if action == 'accept':
        mongo.db.contact_requests.update_one({'_id': ObjectId(request_id)}, {'$set': {'status': 'accepted'}})
        flash('Contact request accepted!', 'success')
    elif action == 'reject':
        mongo.db.contact_requests.update_one({'_id': ObjectId(request_id)}, {'$set': {'status': 'rejected'}})
        flash('Contact request rejected!', 'info')
    
    return redirect(url_for('contact_requests'))

# CONTACT OWNER WITH VERIFIED PROOF ROUTE
@app.route('/contact-owner-with-proof/<claim_id>', methods=['POST'])
@login_required
def contact_owner_with_proof(claim_id):
    try:
        claim = mongo.db.claims.find_one({'_id': ObjectId(claim_id)})
    except Exception:
        claim = None
    if not claim:
        flash('Claim not found', 'error')
        return redirect(url_for('my_claims'))
    
    # Only the claimant can contact owner
    if claim['claimant_id'] != session['user_id']:
        flash('Not authorized', 'error')
        return redirect(url_for('my_claims'))
    
    # Only verified claims can proceed
    if claim['status'] != 'verified':
        flash('Claim must be verified by admin first', 'error')
        return redirect(url_for('my_claims'))
    
    # Create contact request WITH PROOF
    mongo.db.contact_requests.insert_one({
        'from_user_id': claim['claimant_id'],
        'from_username': claim['claimant_name'],
        'to_user_id': claim['item_owner_id'],
        'to_username': claim['item_owner_name'],
        'item_id': claim['item_id'],
        'item_name': claim['item_name'],
        'message': f"I found your {claim['item_name']}. Proof: {claim['proof']}",
        'claim_id': claim_id,
        'created_at': datetime.now(),
        'status': 'pending'
    })
    
    # Create notification for item owner
    mongo.db.notifications.insert_one({
        'user_id': claim['item_owner_id'],
        'type': 'claim_verified',
        'title': f'Contact from {claim["claimant_name"]} about {claim["item_name"]}',
        'message': f'{claim["claimant_name"]} wants to contact you with proof they found your {claim["item_name"]}',
        'item_id': claim['item_id'],
        'created_at': datetime.now(),
        'read': False
    })
    
    flash('Contact request sent to item owner! They will respond with their contact information.', 'success')
    return redirect(url_for('my_claims'))

# USER PROFILE ROUTE

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
    except Exception:
        user = None
    if not user:
        session.clear()
        flash('Session expired. Please log in again.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        bio = request.form.get('bio')
        if not email:
            flash('Email is required', 'danger')
            return redirect(url_for('profile'))
        mongo.db.users.update_one({'_id': ObjectId(session['user_id'])}, {'$set': {
            'email': email,
            'phone': phone or '',
            'bio': bio or ''
        }})
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))
    user_items = list(mongo.db.items.find({'reporter_id': session['user_id']}))
    user_claims = list(mongo.db.claims.find({'claimant_id': session['user_id']}))
    user_matches = []
    for user_item in user_items:
        opposite_type = 'found' if user_item['type'] == 'lost' else 'lost'
        other_items = list(mongo.db.items.find({'type': opposite_type, 'category': user_item['category']}))
        for other_item in other_items:
            user_matches.append({'lost_item': user_item, 'found_item': other_item, 'score': 65})
    return render_template('profile.html', user=user, user_items=user_items, user_claims=user_claims, user_matches=user_matches)

# ADVANCED ADMIN FEATURES

@app.route('/admin/send-notification', methods=['POST'])
@admin_required
def send_notification():
    """Send email notification to users"""
    recipient_type = request.form.get('recipient_type')
    subject = request.form.get('subject')
    message = request.form.get('message')
    user_ids = request.form.getlist('user_ids')

    if not subject or not message:
        flash('Subject and message are required', 'danger')
        return redirect(url_for('admin_dashboard'))

    sent_count = 0
    if recipient_type == 'all':
        users = list(mongo.db.users.find({'is_active': {'$ne': False}}))
    elif recipient_type == 'selected' and user_ids:
        users = list(mongo.db.users.find({'_id': {'$in': [ObjectId(uid) for uid in user_ids]}}))
    else:
        flash('Invalid recipient selection', 'danger')
        return redirect(url_for('admin_dashboard'))

    for user in users:
        if send_email(user['email'], subject, message):
            sent_count += 1

    log_admin_action(session['user_id'], 'send_notification',
                    f'Sent notification to {sent_count} users: {subject}')

    flash(f'Notification sent to {sent_count} users', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/bulk-approve-claims', methods=['POST'])
@admin_required
def bulk_approve_claims():
    """Bulk approve multiple claims"""
    claim_ids = request.form.getlist('claim_ids')

    if not claim_ids:
        flash('No claims selected', 'danger')
        return redirect(url_for('admin_dashboard'))

    approved_count = 0
    for claim_id in claim_ids:
        try:
            claim = mongo.db.claims.find_one({'_id': ObjectId(claim_id)})
            if claim and claim['status'] == 'pending':
                # Update claim status
                mongo.db.claims.update_one({'_id': ObjectId(claim_id)}, {'$set': {'status': 'verified'}})

                # Update item status
                mongo.db.items.update_one({'_id': ObjectId(claim['item_id'])}, {'$set': {'status': 'claimed'}})

                # Create notification for claimant
                mongo.db.notifications.insert_one({
                    'user_id': claim['claimant_id'],
                    'message': f'🎉 Your claim for item has been approved! Contact details will be shared.',
                    'item_id': claim['item_id'],
                    'created_at': datetime.now(),
                    'read': False
                })

                # Send email notification
                claimant = mongo.db.users.find_one({'_id': ObjectId(claim['claimant_id'])})
                if claimant:
                    send_email(claimant['email'], 'Claim Approved',
                             f'Your claim has been approved! You will receive contact details soon.')

                approved_count += 1
        except Exception as e:
            print(f"Error approving claim {claim_id}: {e}")

    log_admin_action(session['user_id'], 'bulk_approve_claims',
                    f'Approved {approved_count} claims')

    flash(f'Successfully approved {approved_count} claims', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/search', methods=['GET'])
@admin_required
def admin_search():
    """Advanced search for users and items"""
    search_type = request.args.get('type', 'users')
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    status = request.args.get('status', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    results = []
    if search_type == 'users':
        mongo_query = {}
        if query:
            mongo_query['$or'] = [
                {'username': {'$regex': query, '$options': 'i'}},
                {'email': {'$regex': query, '$options': 'i'}}
            ]
        if status:
            mongo_query['is_active'] = status == 'active'
        results = list(mongo.db.users.find(mongo_query).limit(50))

    elif search_type == 'items':
        mongo_query = {}
        if query:
            mongo_query['$or'] = [
                {'name': {'$regex': query, '$options': 'i'}},
                {'description': {'$regex': query, '$options': 'i'}}
            ]
        if category:
            mongo_query['category'] = category
        if status:
            mongo_query['status'] = status
        results = list(mongo.db.items.find(mongo_query).limit(50))

    return render_template('admin_search.html',
                         search_type=search_type,
                         query=query,
                         category=category,
                         status=status,
                         results=results)

@app.route('/admin/export/<data_type>')
@admin_required
def export_data(data_type):
    """Export data as CSV or PDF"""
    export_format = request.args.get('format', 'csv')

    if data_type == 'users':
        data = list(mongo.db.users.find())
        if export_format == 'csv':
            return export_users_csv(data)
        else:
            return export_users_pdf(data)

    elif data_type == 'items':
        data = list(mongo.db.items.find())
        if export_format == 'csv':
            return export_items_csv(data)
        else:
            return export_items_pdf(data)

    elif data_type == 'claims':
        data = list(mongo.db.claims.find())
        if export_format == 'csv':
            return export_claims_csv(data)
        else:
            return export_claims_pdf(data)

    flash('Invalid export type', 'danger')
    return redirect(url_for('admin_dashboard'))

def export_users_csv(users):
    """Export users as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Username', 'Email', 'Role', 'Active', 'Joined', 'Items Count'])

    for user in users:
        writer.writerow([
            user.get('username', ''),
            user.get('email', ''),
            'Admin' if user.get('is_admin') else 'User',
            'Yes' if user.get('is_active', True) else 'No',
            user.get('created_at', '').strftime('%Y-%m-%d') if user.get('created_at') else '',
            len(list(mongo.db.items.find({'reporter_id': str(user['_id'])})))
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='users_export.csv'
    )

def export_items_csv(items):
    """Export items as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Name', 'Type', 'Category', 'Location', 'Status', 'Reporter', 'Date'])

    for item in items:
        reporter = mongo.db.users.find_one({'_id': ObjectId(item['reporter_id'])})
        writer.writerow([
            item.get('name', ''),
            item.get('type', ''),
            item.get('category', ''),
            item.get('location', ''),
            item.get('status', ''),
            reporter['username'] if reporter else 'Unknown',
            item.get('created_at', '').strftime('%Y-%m-%d') if item.get('created_at') else ''
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='items_export.csv'
    )

def export_claims_csv(claims):
    """Export claims as CSV"""
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Item', 'Claimant', 'Status', 'Proof', 'Date'])

    for claim in claims:
        item = mongo.db.items.find_one({'_id': ObjectId(claim['item_id'])})
        claimant = mongo.db.users.find_one({'_id': ObjectId(claim['claimant_id'])})
        writer.writerow([
            item['name'] if item else 'Unknown Item',
            claimant['username'] if claimant else 'Unknown',
            claim.get('status', ''),
            claim.get('proof', '')[:50] + '...' if len(claim.get('proof', '')) > 50 else claim.get('proof', ''),
            claim.get('created_at', '').strftime('%Y-%m-%d') if claim.get('created_at') else ''
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='claims_export.csv'
    )

def export_users_pdf(users):
    """Export users as PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Users Report", styles['Heading1']))
    elements.append(Spacer(1, 12))

    data = [['Username', 'Email', 'Role', 'Active', 'Joined', 'Items']]
    for user in users:
        data.append([
            user.get('username', ''),
            user.get('email', ''),
            'Admin' if user.get('is_admin') else 'User',
            'Yes' if user.get('is_active', True) else 'No',
            user.get('created_at', '').strftime('%Y-%m-%d') if user.get('created_at') else '',
            str(len(list(mongo.db.items.find({'reporter_id': str(user['_id'])}))))
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='users_report.pdf'
    )

def export_items_pdf(items):
    """Export items as PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Items Report", styles['Heading1']))
    elements.append(Spacer(1, 12))

    data = [['Name', 'Type', 'Category', 'Location', 'Status', 'Reporter']]
    for item in items:
        reporter = mongo.db.users.find_one({'_id': ObjectId(item['reporter_id'])})
        data.append([
            item.get('name', ''),
            item.get('type', ''),
            item.get('category', ''),
            item.get('location', ''),
            item.get('status', ''),
            reporter['username'] if reporter else 'Unknown'
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='items_report.pdf'
    )

def export_claims_pdf(claims):
    """Export claims as PDF"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("Claims Report", styles['Heading1']))
    elements.append(Spacer(1, 12))

    data = [['Item', 'Claimant', 'Status', 'Date']]
    for claim in claims:
        item = mongo.db.items.find_one({'_id': ObjectId(claim['item_id'])})
        claimant = mongo.db.users.find_one({'_id': ObjectId(claim['claimant_id'])})
        data.append([
            item['name'] if item else 'Unknown Item',
            claimant['username'] if claimant else 'Unknown',
            claim.get('status', ''),
            claim.get('created_at', '').strftime('%Y-%m-%d') if claim.get('created_at') else ''
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='claims_report.pdf'
    )

@app.route('/admin/backup')
@admin_required
def create_system_backup():
    """Create system backup"""
    try:
        backup_file = create_backup()
        log_admin_action(session['user_id'], 'create_backup',
                        f'Created backup: {backup_file}')
        flash(f'Backup created successfully: {backup_file}', 'success')
    except Exception as e:
        flash(f'Backup failed: {str(e)}', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/audit-logs')
@admin_required
def audit_logs():
    """View admin audit logs"""
    page = int(request.args.get('page', 1))
    per_page = 50
    skip = (page - 1) * per_page

    logs = list(mongo.db.admin_logs.find()
               .sort('timestamp', -1)
               .skip(skip)
               .limit(per_page))

    total_logs = mongo.db.admin_logs.count_documents({})

    # Get admin usernames for display (skip malformed IDs safely)
    admin_ids = set(str(log.get('admin_id', '')) for log in logs if log.get('admin_id'))
    valid_object_ids = []
    for aid in admin_ids:
        try:
            valid_object_ids.append(ObjectId(aid))
        except Exception:
            continue

    admins = {}
    if valid_object_ids:
        admins = {
            str(admin['_id']): admin.get('username', 'Unknown')
            for admin in mongo.db.users.find({'_id': {'$in': valid_object_ids}})
        }

    for log in logs:
        log['admin_username'] = admins.get(str(log.get('admin_id', '')), 'Unknown')

    return render_template('admin_audit.html',
                         logs=logs,
                         page=page,
                         total_pages=(total_logs + per_page - 1) // per_page)

@app.route('/admin/user-analytics/<user_id>')
@admin_required
def user_analytics(user_id):
    """View detailed analytics for a specific user"""
    try:
        user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    except:
        flash('User not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    # Get user's items
    user_items = list(mongo.db.items.find({'reporter_id': user_id}))
    lost_items = [i for i in user_items if i['type'] == 'lost']
    found_items = [i for i in user_items if i['type'] == 'found']

    # Get user's claims
    user_claims = list(mongo.db.claims.find({'claimant_id': user_id}))
    approved_claims = [c for c in user_claims if c['status'] == 'verified']

    # Get user's notifications
    user_notifications = list(mongo.db.notifications.find({'user_id': user_id}))

    # Calculate success rate
    total_claims = len(user_claims)
    success_rate = (len(approved_claims) / total_claims * 100) if total_claims > 0 else 0

    # Activity timeline (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_items = [i for i in user_items if i.get('created_at', datetime.min) > thirty_days_ago]
    recent_claims = [c for c in user_claims if c.get('created_at', datetime.min) > thirty_days_ago]

    analytics = {
        'total_items': len(user_items),
        'lost_items': len(lost_items),
        'found_items': len(found_items),
        'total_claims': total_claims,
        'approved_claims': len(approved_claims),
        'success_rate': success_rate,
        'unread_notifications': len([n for n in user_notifications if not n.get('read', False)]),
        'recent_activity': len(recent_items) + len(recent_claims),
        'account_age_days': (datetime.now() - user.get('created_at', datetime.now())).days
    }

    return render_template('admin_user_analytics.html',
                         user=user,
                         analytics=analytics,
                         recent_items=recent_items[-10:],
                         recent_claims=recent_claims[-10:])

@app.route('/admin/health')
@admin_required
def admin_health():
    """Basic admin health check for DB connectivity and core collections."""
    db_ok = True
    db_error = None
    counts = {}

    try:
        mongo.cx.admin.command('ping')
        counts = {
            'users': mongo.db.users.count_documents({}),
            'items': mongo.db.items.count_documents({}),
            'claims': mongo.db.claims.count_documents({}),
            'admin_logs': mongo.db.admin_logs.count_documents({})
        }
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    return jsonify({
        'status': 'ok' if db_ok else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'database': {
            'connected': db_ok,
            'error': db_error
        },
        'counts': counts
    }), (200 if db_ok else 503)

@app.route('/admin/health/routes')
@admin_required
def admin_health_routes():
    """Health check for required admin route registration."""
    required = [
        '/admin',
        '/admin/search',
        '/admin/audit-logs',
        '/admin/backup',
        '/admin/send-notification',
        '/admin/bulk-approve-claims'
    ]
    existing = {rule.rule for rule in app.url_map.iter_rules()}
    missing = [route for route in required if route not in existing]

    return jsonify({
        'status': 'ok' if not missing else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'required_routes': required,
        'missing_routes': missing
    }), (200 if not missing else 503)

# ── MY CHATS (replaces old messages) ────────────────────────

@app.route('/my-chats')
@login_required
def my_chats():
    user_id = session['user_id']
    rooms = list(mongo.db.chat_rooms.find({
        '$or': [{'claimant_id': user_id}, {'finder_id': user_id}]
    }).sort('created_at', -1))

    # Attach last message and unread count to each room
    for room in rooms:
        room_id = str(room['_id'])
        last_msg = mongo.db.chat_messages.find_one(
            {'room_id': room_id}, sort=[('timestamp', -1)])
        room['last_message'] = last_msg['message'] if last_msg else None
        room['last_time'] = last_msg['timestamp'] if last_msg else room.get('created_at')
        room['unread_count'] = mongo.db.chat_messages.count_documents({
            'room_id': room_id,
            'sender_id': {'$ne': user_id},
            'read': False
        })
        room['other_name'] = room['finder_name'] if user_id == room['claimant_id'] else room['claimant_name']

    return render_template('my_chats.html', rooms=rooms)


# ── CHAT ROUTES ──────────────────────────────────────────────

@app.route('/chat/<room_id>')
@login_required
def chat(room_id):
    try:
        room = mongo.db.chat_rooms.find_one({'_id': ObjectId(room_id)})
    except Exception:
        room = None
    if not room:
        flash('Chat room not found', 'danger')
        return redirect(url_for('my_claims'))

    user_id = session['user_id']
    if user_id not in [room['claimant_id'], room['finder_id']]:
        flash('You do not have access to this chat', 'danger')
        return redirect(url_for('browse'))

    messages = list(mongo.db.chat_messages.find({'room_id': room_id}).sort('timestamp', 1))

    # Mark incoming messages as read
    mongo.db.chat_messages.update_many(
        {'room_id': room_id, 'sender_id': {'$ne': user_id}, 'read': False},
        {'$set': {'read': True}}
    )

    if user_id == room['claimant_id']:
        other_user_name = room['finder_name']
    else:
        other_user_name = room['claimant_name']

    return render_template('chat.html', room=room, messages=messages,
                           room_id=room_id, other_user_name=other_user_name)


@app.route('/chat/<room_id>/send', methods=['POST'])
@login_required
def send_chat_message(room_id):
    try:
        room = mongo.db.chat_rooms.find_one({'_id': ObjectId(room_id)})
    except Exception:
        room = None
    if not room:
        flash('Chat room not found', 'danger')
        return redirect(url_for('my_claims'))

    user_id = session['user_id']
    if user_id not in [room['claimant_id'], room['finder_id']]:
        flash('Not authorized', 'danger')
        return redirect(url_for('browse'))

    message_text = request.form.get('message', '').strip()
    if not message_text:
        flash('Message cannot be empty', 'danger')
        return redirect(url_for('chat', room_id=room_id))

    mongo.db.chat_messages.insert_one({
        'room_id': room_id,
        'sender_id': user_id,
        'sender_name': session['username'],
        'message': message_text,
        'timestamp': datetime.now(),
        'read': False
    })
    return redirect(url_for('chat', room_id=room_id))


@app.route('/chat/<room_id>/messages')
@login_required
def get_chat_messages(room_id):
    """JSON endpoint for polling new messages"""
    try:
        room = mongo.db.chat_rooms.find_one({'_id': ObjectId(room_id)})
    except Exception:
        room = None
    if not room:
        return jsonify({'error': 'Room not found'}), 404

    user_id = session['user_id']
    if user_id not in [room['claimant_id'], room['finder_id']]:
        return jsonify({'error': 'Not authorized'}), 403

    messages = list(mongo.db.chat_messages.find({'room_id': room_id}).sort('timestamp', 1))
    mongo.db.chat_messages.update_many(
        {'room_id': room_id, 'sender_id': {'$ne': user_id}, 'read': False},
        {'$set': {'read': True}}
    )
    return jsonify([{
        'id': str(m['_id']),
        'sender_id': m['sender_id'],
        'sender_name': m['sender_name'],
        'message': m['message'],
        'timestamp': m['timestamp'].strftime('%d %b, %H:%M') if m.get('timestamp') else '',
        'is_mine': m['sender_id'] == user_id
    } for m in messages])


# ── MARK ITEM RESOLVED ───────────────────────────────────────

@app.route('/item/<item_id>/mark-resolved', methods=['POST'])
@login_required
def mark_resolved(item_id):
    try:
        item = mongo.db.items.find_one({'_id': ObjectId(item_id)})
    except Exception:
        item = None
    if not item:
        flash('Item not found', 'danger')
        return redirect(url_for('my_items'))

    if item['reporter_id'] != session['user_id']:
        flash('Not authorized', 'danger')
        return redirect(url_for('my_items'))

    resolution = request.form.get('resolution')
    if resolution not in ('found', 'returned'):
        flash('Invalid resolution type', 'danger')
        return redirect(url_for('my_items'))

    status_labels = {
        'found': 'recovered by owner',
        'returned': 'returned to owner'
    }
    mongo.db.items.update_one(
        {'_id': ObjectId(item_id)},
        {'$set': {'status': 'resolved', 'resolution': resolution}}
    )
    flash(f'✅ Item "{item["name"]}" marked as {status_labels[resolution]}!', 'success')
    return redirect(url_for('my_items'))


# ── CONTACT ADMIN (for banned users / general) ───────────────

@app.route('/contact-admin', methods=['GET', 'POST'])
def contact_admin():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()

        if not all([name, email, message]):
            flash('All fields are required', 'danger')
            return redirect(url_for('contact_admin'))

        mongo.db.admin_messages.insert_one({
            'name': name,
            'email': email,
            'message': message,
            'type': 'contact_admin',
            'user_id': session.get('user_id', None),
            'created_at': datetime.now(),
            'status': 'unread'
        })
        flash('✅ Your message has been sent to admin. We will contact you soon.', 'success')
        return redirect(url_for('login'))
    return render_template('contact_admin.html')


# ── ADMIN: VIEW CONTACT MESSAGES ─────────────────────────────

@app.route('/admin/messages')
@admin_required
def admin_messages():
    messages = list(mongo.db.admin_messages.find().sort('created_at', -1))
    unread = mongo.db.admin_messages.count_documents({'status': 'unread'})
    mongo.db.admin_messages.update_many({'status': 'unread'}, {'$set': {'status': 'read'}})
    return render_template('admin_messages.html', messages=messages, unread=unread)


# SPAM DETECTION MIDDLEWARE
@app.before_request
def check_spam():
    """Check for spam in form submissions"""
    if request.method == 'POST' and request.endpoint in ['report', 'claim_item', 'found_match']:
        text_fields = []
        for field in request.form:
            if isinstance(request.form[field], str) and len(request.form[field]) > 10:
                text_fields.append(request.form[field])

        for text in text_fields:
            if detect_spam(text):
                flash('Your submission contains potentially inappropriate content and has been flagged for review.', 'warning')
                # Log potential spam
                mongo.db.spam_logs.insert_one({
                    'endpoint': request.endpoint,
                    'form_data': dict(request.form),
                    'ip_address': request.remote_addr,
                    'timestamp': datetime.now(),
                    'flagged': True
                })
                return redirect(request.url)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
