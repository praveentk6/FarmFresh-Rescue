import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, g, abort, jsonify, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

from database import (
    get_db, init_db, seed_db, create_notification,
    get_unread_notifications_count, get_user_notifications,
    mark_notification_read, mark_all_notifications_read
)
from translations import t, TRANSLATIONS
from ai_engine import get_ai_rescue_advice

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'farmfresh-rescue-tamilnadu-secure-key-2026')

# Upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 3 * 1024 * 1024  # 3MB
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Ensure database tables and initial seed data exist
try:
    init_db()
    seed_db()
except Exception as _e:
    print(f"Database initialization notice: {_e}")

# Tamil Nadu Districts List for unified filtering and dropdowns
TN_DISTRICTS = [
    "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri",
    "Dindigul", "Erode", "Kallakurichi", "Kanchipuram", "Kanyakumari", "Karur",
    "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal", "Nilgiris",
    "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga",
    "Tenkasi", "Thanjavur", "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli",
    "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai", "Tiruvarur", "Vellore",
    "Viluppuram", "Virudhunagar"
]

CROP_CATEGORIES = [
    "Vegetables", "Fruits", "Grains & Pulses", "Spices & Herbs", "Flowers", "Plantation & Cash Crops"
]

CROP_UNITS = [
    "kg", "Quintal", "Tonne", "Crats (Approx 25kg)", "Bags (25kg)", "Bags (50kg)", "Pieces / Bunches"
]

BUYER_TYPES = [
    "Vegetable Shops", "Supermarkets", "Hotels and Restaurants",
    "Wholesalers", "Food Processing Companies", "Individual Consumers"
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_and_save_image(file_storage):
    """Safely validate, resize, and save an uploaded image file."""
    if not file_storage or file_storage.filename == '':
        return None
    
    if not allowed_file(file_storage.filename):
        return None

    try:
        ext = file_storage.filename.rsplit('.', 1)[1].lower()
        unique_name = f"produce_{int(datetime.now().timestamp())}_{secure_filename(file_storage.filename)}"
        target_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

        img = Image.open(file_storage)
        img.verify()

        file_storage.seek(0)
        img = Image.open(file_storage)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        max_dim = 1200
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        img.save(target_path, optimize=True, quality=85)
        return unique_name
    except Exception as e:
        app.logger.error(f"Image upload validation error: {e}")
        return None

# ==========================================
# Helpers & Context Processors
# ==========================================

def get_current_user():
    """Retrieve current logged in user from session."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, role, phone, location, pin_code, user_type, is_active 
        FROM users WHERE id = ?
    """, (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user and user['is_active'] == 0:
        session.clear()
        return None
    return user

@app.before_request
def load_request_state():
    # Language resolution: session -> cookie -> default 'en'
    if 'lang' not in session:
        session['lang'] = request.cookies.get('farmfresh_lang', 'en')
    if session['lang'] not in ['en', 'ta']:
        session['lang'] = 'en'
    g.lang = session['lang']
    g.user = get_current_user()

def calculate_listing_age(created_at_val):
    """Calculate days since listing was posted."""
    if not created_at_val:
        return 0, "Today"
    try:
        if isinstance(created_at_val, str):
            if ' ' in created_at_val:
                dt = datetime.strptime(created_at_val.split('.')[0], '%Y-%m-%d %H:%M:%S')
            else:
                dt = datetime.strptime(created_at_val, '%Y-%m-%d')
        else:
            dt = created_at_val

        diff_days = (datetime.now() - dt).days
        if diff_days <= 0:
            return 0, "Today"
        elif diff_days == 1:
            return 1, "1 day ago"
        else:
            return diff_days, f"{diff_days} days ago"
    except Exception:
        return 0, "Recently"

def get_listing_urgency_info(listing):
    """
    Computes transparent urgency classification based on:
    - Listing status (Available / Sold)
    - Stored urgency level
    - Harvest date & shelf life
    - Estimated freshness date (if provided)
    - Days since posted
    """
    if listing['status'] != 'Available':
        return {
            'level': 'Sold Out',
            'badge_class': 'badge-sold',
            'is_urgent': False,
            'reason': 'Sold'
        }

    # If explicit urgency set
    stored_urgency = listing.get('urgency_level') if isinstance(listing, dict) else listing['urgency_level']
    if stored_urgency == 'Urgent Sale':
        return {
            'level': 'Urgent Sale',
            'badge_class': 'badge-urgent-sale',
            'is_urgent': True,
            'reason': 'Immediate clearance requested by farmer'
        }

    # Check estimated freshness date
    freshness_date = listing.get('estimated_freshness_date') if isinstance(listing, dict) else listing['estimated_freshness_date']
    if freshness_date:
        try:
            f_dt = datetime.strptime(str(freshness_date).split()[0], '%Y-%m-%d').date()
            days_left = (f_dt - date.today()).days
            if days_left <= 1:
                return {
                    'level': 'Urgent Sale',
                    'badge_class': 'badge-urgent-sale',
                    'is_urgent': True,
                    'reason': 'Estimated freshness window ending in <= 24 hrs'
                }
            elif days_left <= 3:
                return {
                    'level': 'Needs Attention',
                    'badge_class': 'badge-needs-attention',
                    'is_urgent': True,
                    'reason': f'Estimated freshness window ends in {days_left} days'
                }
        except Exception:
            pass

    # Check listing age (>= 3 days unsold)
    days_old, _ = calculate_listing_age(listing['created_at'])
    if days_old >= 4:
        return {
            'level': 'Urgent Sale',
            'badge_class': 'badge-urgent-sale',
            'is_urgent': True,
            'reason': f'Unsold for {days_old} days. Swift clearance recommended'
        }
    elif days_old >= 3:
        return {
            'level': 'Needs Attention',
            'badge_class': 'badge-needs-attention',
            'is_urgent': True,
            'reason': f'Unsold for {days_old} days'
        }

    # Check days since harvest
    try:
        h_date = datetime.strptime(str(listing['harvest_date']).split()[0], '%Y-%m-%d').date()
        days_harvest = (date.today() - h_date).days
        category = listing['category']
        if category in ['Vegetables', 'Flowers'] and days_harvest >= 4:
            return {
                'level': 'Needs Attention',
                'badge_class': 'badge-needs-attention',
                'is_urgent': True,
                'reason': f'Harvested {days_harvest} days ago'
            }
    except Exception:
        pass

    return {
        'level': 'Available',
        'badge_class': 'badge-available',
        'is_urgent': False,
        'reason': 'Fresh harvest'
    }

def is_needs_attention(listing):
    info = get_listing_urgency_info(listing)
    return info['is_urgent']

def log_activity(action, details, email=None):
    """Log platform actions for admin oversight."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (action, details, user_email) VALUES (?, ?, ?)",
            (action, details, email or (g.user['email'] if g.user else 'System'))
        )
        conn.commit()
        conn.close()
    except Exception as e:
        app.logger.error(f"Error logging activity: {e}")

@app.context_processor
def inject_global_template_vars():
    """Inject globally useful values and helper functions into all templates."""
    current_lang = session.get('lang', 'en')
    unread_count = 0
    if g.user:
        unread_count = get_unread_notifications_count(g.user['id'])

    return {
        'current_user': g.user,
        'lang': current_lang,
        't': lambda k: t(k, current_lang),
        '_t': lambda k: t(k, current_lang),
        'unread_count': unread_count,
        'calculate_listing_age': calculate_listing_age,
        'get_listing_urgency_info': get_listing_urgency_info,
        'is_needs_attention': is_needs_attention,
        'tn_districts': TN_DISTRICTS,
        'crop_categories': CROP_CATEGORIES,
        'crop_units': CROP_UNITS,
        'buyer_types': BUYER_TYPES,
        'translations_json': json.dumps(TRANSLATIONS.get(current_lang, TRANSLATIONS['en'])),
        'now_year': datetime.now().year
    }

# ==========================================
# Decorators for Authentication & Roles
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.user:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not g.user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for('login', next=request.url))
            if g.user['role'] not in allowed_roles:
                flash("Access denied. You do not have permissions for this page.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==========================================
# Language Switcher Route
# ==========================================

@app.route('/set-language/<lang_code>')
def set_language(lang_code):
    if lang_code in ['en', 'ta']:
        session['lang'] = lang_code
    next_url = request.referrer or url_for('index')
    # Prevent open redirect loops
    if '/set-language/' in next_url:
        next_url = url_for('index')
    resp = make_response(redirect(next_url))
    resp.set_cookie('farmfresh_lang', session['lang'], max_age=60*60*24*365)
    return resp

# ==========================================
# Public Routes
# ==========================================

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()

    # Statistics for impact counters
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    available_count = cursor.fetchone()[0]

    # Needs attention count (Available and >= 3 days old or urgent)
    cursor.execute("""
        SELECT COUNT(*) FROM listings 
        WHERE status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
    """)
    needs_attention_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    total_users_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Sold'")
    rescued_sold_count = cursor.fetchone()[0]

    # Total quantity sold/rescued in kg
    cursor.execute("SELECT COALESCE(SUM(quantity), 0) FROM listings WHERE status = 'Sold'")
    total_qty_rescued = cursor.fetchone()[0]

    # High-priority Urgent / Needs Attention produce
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
        ORDER BY (CASE WHEN urgency_level = 'Urgent Sale' THEN 0 ELSE 1 END), created_at ASC 
        LIMIT 6
    """)
    urgent_listings = cursor.fetchall()

    # Fresh listings (latest harvests)
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        ORDER BY created_at DESC 
        LIMIT 6
    """)
    recent_listings = cursor.fetchall()

    conn.close()

    return render_template(
        'index.html',
        available_count=available_count,
        needs_attention_count=needs_attention_count,
        total_users_count=total_users_count,
        rescued_sold_count=rescued_sold_count,
        total_qty_rescued=total_qty_rescued,
        urgent_listings=urgent_listings,
        recent_listings=recent_listings
    )

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/listings')
def browse_listings():
    conn = get_db()
    cursor = conn.cursor()

    # Query parameters
    search_q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    district = request.args.get('district', '').strip()
    village = request.args.get('village', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    min_qty = request.args.get('min_qty', '').strip()
    max_qty = request.args.get('max_qty', '').strip()
    urgency = request.args.get('urgency', '').strip()  # 'urgent_only'
    status_filter = request.args.get('status', 'Available').strip()
    sort_by = request.args.get('sort', 'urgent').strip()

    # Base query
    query = "SELECT * FROM listings WHERE 1=1"
    params = []

    # Status filter
    if status_filter and status_filter != 'All':
        query += " AND status = ?"
        params.append(status_filter)

    # Keyword search across crop_name, village_town, district, farmer_name, description
    if search_q:
        query += """ AND (
            crop_name LIKE ? OR 
            village_town LIKE ? OR 
            district LIKE ? OR 
            pin_code LIKE ? OR 
            farmer_name LIKE ? OR 
            description LIKE ?
        )"""
        search_param = f"%{search_q}%"
        params.extend([search_param] * 6)

    # Category filter
    if category:
        query += " AND category = ?"
        params.append(category)

    # District filter
    if district:
        query += " AND district = ?"
        params.append(district)

    # Village filter
    if village:
        query += " AND village_town LIKE ?"
        params.append(f"%{village}%")

    # Price filters
    if min_price:
        try:
            query += " AND price_per_unit >= ?"
            params.append(float(min_price))
        except ValueError:
            pass

    if max_price:
        try:
            query += " AND price_per_unit <= ?"
            params.append(float(max_price))
        except ValueError:
            pass

    # Quantity filters
    if min_qty:
        try:
            query += " AND quantity >= ?"
            params.append(float(min_qty))
        except ValueError:
            pass

    if max_qty:
        try:
            query += " AND quantity <= ?"
            params.append(float(max_qty))
        except ValueError:
            pass

    # Urgency filter: listings unsold >= 3 days or marked urgent
    if urgency == 'urgent_only':
        query += " AND status = 'Available' AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')"

    # Sorting
    if sort_by == 'price_low':
        query += " ORDER BY price_per_unit ASC"
    elif sort_by == 'price_high':
        query += " ORDER BY price_per_unit DESC"
    elif sort_by == 'newest':
        query += " ORDER BY created_at DESC"
    elif sort_by == 'harvest_recent':
        query += " ORDER BY harvest_date DESC"
    elif sort_by == 'urgent':
        # Prioritize Urgent Sale and 3+ days old listings first to prevent waste, then newest
        query += """ ORDER BY 
            (CASE 
                WHEN status = 'Available' AND urgency_level = 'Urgent Sale' THEN 0 
                WHEN status = 'Available' AND (julianday('now') - julianday(created_at)) >= 3 THEN 1 
                ELSE 2 
            END), created_at ASC"""
    else:
        query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    listings = cursor.fetchall()

    # Dedicated Rescue section listings (urgent / needs attention)
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
        ORDER BY (CASE WHEN urgency_level = 'Urgent Sale' THEN 0 ELSE 1 END), created_at ASC
        LIMIT 4
    """)
    urgent_spotlight = cursor.fetchall()

    # Pre-calculate counts for quick tabs
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    total_available = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM listings 
        WHERE status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
    """)
    total_urgent = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'listings.html',
        listings=listings,
        urgent_spotlight=urgent_spotlight,
        search_q=search_q,
        category=category,
        district=district,
        village=village,
        min_price=min_price,
        max_price=max_price,
        min_qty=min_qty,
        max_qty=max_qty,
        urgency=urgency,
        status_filter=status_filter,
        sort_by=sort_by,
        total_available=total_available,
        total_urgent=total_urgent
    )

@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.*, u.email as farmer_email, u.user_type as farmer_type, u.created_at as farmer_joined
        FROM listings l
        JOIN users u ON l.farmer_id = u.id
        WHERE l.id = ?
    """, (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        flash("The requested produce listing was not found.", "danger")
        return redirect(url_for('browse_listings'))

    days_since_harvest = None
    try:
        h_date = datetime.strptime(str(listing['harvest_date']).split()[0], '%Y-%m-%d').date()
        days_since_harvest = (date.today() - h_date).days
    except Exception:
        pass

    cursor.execute("""
        SELECT * FROM listings 
        WHERE category = ? AND id != ? AND status = 'Available'
        ORDER BY created_at DESC LIMIT 3
    """, (listing['category'], listing_id))
    related_listings = cursor.fetchall()

    conn.close()

    days_old, age_text = calculate_listing_age(listing['created_at'])
    urgency_info = get_listing_urgency_info(listing)

    return render_template(
        'listing_detail.html',
        listing=listing,
        days_old=days_old,
        age_text=age_text,
        days_since_harvest=days_since_harvest,
        urgency_info=urgency_info,
        needs_attn=urgency_info['is_urgent'],
        related_listings=related_listings
    )

# ==========================================
# Authentication Routes
# ==========================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.user:
        flash("You are already logged in.", "info")
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'farmer').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        pin_code = request.form.get('pin_code', '').strip()
        user_type = request.form.get('user_type', '').strip()

        errors = []
        if not name or len(name) < 2:
            errors.append("Please enter your full name (minimum 2 characters).")
        if not email or '@' not in email or '.' not in email:
            errors.append("Please enter a valid email address.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if role not in ['farmer', 'buyer', 'admin']:
            errors.append("Invalid user role selected.")
        if not phone or len(phone) < 10:
            errors.append("Please provide a valid 10-digit contact phone number.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('register.html', **request.form)

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email address already exists. Please login instead.", "warning")
            return redirect(url_for('login'))

        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (name, email, password_hash, role, phone, location, pin_code, user_type))
        conn.commit()

        user_id = cursor.lastrowid
        conn.close()

        # Send welcome notification
        create_notification(
            user_id,
            "Welcome to FarmFresh Rescue!",
            "Explore direct farm produce trade in Tamil Nadu and prevent agricultural waste.",
            "info",
            url_for('farmer_dashboard') if role == 'farmer' else url_for('browse_listings')
        )

        log_activity("User Registered", f"New {role} registered: {name} ({email})", email)

        session['user_id'] = user_id
        session['user_name'] = name
        session['user_role'] = role

        flash(f"Welcome to FarmFresh Rescue, {name}! Your {role.capitalize()} account has been created successfully.", "success")
        
        if role == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif role == 'buyer':
            return redirect(url_for('buyer_dashboard'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    initial_role = request.args.get('role', 'farmer')
    return render_template('register.html', initial_role=initial_role)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        flash("You are already logged in.", "info")
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        next_url = request.args.get('next')

        if not email or not password:
            flash("Please enter both email address and password.", "danger")
            return render_template('login.html', email=email)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            if user['is_active'] == 0:
                flash("Your account has been deactivated by administrator. Please contact support.", "danger")
                return render_template('login.html', email=email)

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']

            log_activity("User Logged In", f"{user['role'].capitalize()} logged in: {user['email']}", user['email'])
            flash(f"Welcome back, {user['name']}!", "success")

            if next_url:
                return redirect(next_url)

            if user['role'] == 'farmer':
                return redirect(url_for('farmer_dashboard'))
            elif user['role'] == 'buyer':
                return redirect(url_for('buyer_dashboard'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password. Please check your credentials.", "danger")
            return render_template('login.html', email=email)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out. Have a productive day!", "info")
    return redirect(url_for('index'))

# ==========================================
# Farmer Listings CRUD Routes
# ==========================================

@app.route('/listing/add', methods=['GET', 'POST'])
@login_required
def add_listing():
    if g.user['role'] not in ['farmer', 'admin']:
        flash("Only registered farmers can list agricultural produce.", "warning")
        return redirect(url_for('index'))

    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        category = request.form.get('category', 'Vegetables').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', 'kg').strip()
        price_per_unit = request.form.get('price_per_unit', '').strip()
        original_price = request.form.get('original_price', '').strip()
        harvest_date = request.form.get('harvest_date', '').strip()
        estimated_freshness_date = request.form.get('estimated_freshness_date', '').strip() or None
        village_town = request.form.get('village_town', '').strip()
        district = request.form.get('district', '').strip()
        state = request.form.get('state', 'Tamil Nadu').strip()
        pin_code = request.form.get('pin_code', '').strip()
        farmer_name = request.form.get('farmer_name', g.user['name']).strip()
        farmer_phone = request.form.get('farmer_phone', g.user['phone']).strip()
        whatsapp_number = request.form.get('whatsapp_number', farmer_phone).strip()
        description = request.form.get('description', '').strip()
        urgency_level = request.form.get('urgency_level', 'Normal').strip()
        if urgency_level not in ['Normal', 'Needs Attention', 'Urgent Sale']:
            urgency_level = 'Normal'

        errors = []
        if not crop_name:
            errors.append("Produce / Crop name is required.")
        try:
            qty_val = float(quantity)
            if qty_val <= 0:
                errors.append("Available quantity must be greater than 0.")
        except ValueError:
            errors.append("Please enter a valid numeric quantity.")

        try:
            price_val = float(price_per_unit)
            if price_val <= 0:
                errors.append("Asking price per unit must be greater than 0.")
        except ValueError:
            errors.append("Please enter a valid numeric price.")

        orig_price_val = None
        if original_price:
            try:
                orig_price_val = float(original_price)
                if orig_price_val < 0:
                    errors.append("Original price cannot be negative.")
            except ValueError:
                pass

        if not harvest_date:
            errors.append("Harvest date is required.")
        else:
            try:
                h_dt = datetime.strptime(harvest_date, '%Y-%m-%d').date()
                if h_dt > date.today() + timedelta(days=1):
                    errors.append("Harvest date cannot be in the distant future.")
            except ValueError:
                errors.append("Invalid harvest date format.")

        if estimated_freshness_date:
            try:
                datetime.strptime(estimated_freshness_date, '%Y-%m-%d')
            except ValueError:
                errors.append("Invalid estimated freshness date format.")

        if not village_town or not district:
            errors.append("Village/Town and District location are required.")
        if not pin_code or len(pin_code) < 6:
            errors.append("A valid 6-digit postal PIN code is required.")
        if not farmer_phone:
            errors.append("Farmer contact phone number is required.")

        photo_filename = ""
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                saved_filename = validate_and_save_image(file)
                if saved_filename:
                    photo_filename = saved_filename
                else:
                    errors.append("Uploaded file must be a valid image (PNG, JPG, JPEG, WEBP under 3MB).")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template('add_listing.html', form_data=request.form)

        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO listings (
                farmer_id, crop_name, category, photo, quantity, unit, price_per_unit,
                original_price, harvest_date, estimated_freshness_date, village_town,
                district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
                description, urgency_level, status, rescued_from_waste, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', 0, ?, ?)
        ''', (
            g.user['id'], crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, estimated_freshness_date, village_town,
            district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
            description, urgency_level, now_str, now_str
        ))
        conn.commit()
        new_listing_id = cursor.lastrowid

        # Notify nearby buyers who posted requirements in this district
        cursor.execute("""
            SELECT DISTINCT buyer_id FROM buyer_requirements 
            WHERE district = ? AND status = 'Active' AND category = ?
        """, (district, category))
        matching_buyers = cursor.fetchall()
        for b in matching_buyers:
            create_notification(
                b['buyer_id'],
                f"New Produce Available in {district}: {crop_name}",
                f"{qty_val} {unit} of {crop_name} listed by {farmer_name} at ₹{price_val}/{unit}.",
                "alert",
                url_for('listing_detail', listing_id=new_listing_id)
            )

        conn.close()

        log_activity("Listing Added", f"Produce listed: {crop_name} ({qty_val} {unit}) at ₹{price_val}/{unit} in {district}")
        flash(f"Success! '{crop_name}' has been listed. Buyers nearby can now discover your harvest.", "success")
        return redirect(url_for('farmer_dashboard'))

    default_date = date.today().strftime('%Y-%m-%d')
    return render_template('add_listing.html', default_date=default_date, form_data={})

@app.route('/listing/edit/<int:listing_id>', methods=['GET', 'POST'])
@login_required
def edit_listing(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        flash("Listing not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    if listing['farmer_id'] != g.user['id'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized! You can only edit your own produce listings.", "danger")
        return redirect(url_for('index'))

    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        category = request.form.get('category', 'Vegetables').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', 'kg').strip()
        price_per_unit = request.form.get('price_per_unit', '').strip()
        original_price = request.form.get('original_price', '').strip()
        harvest_date = request.form.get('harvest_date', '').strip()
        estimated_freshness_date = request.form.get('estimated_freshness_date', '').strip() or None
        village_town = request.form.get('village_town', '').strip()
        district = request.form.get('district', '').strip()
        state = request.form.get('state', 'Tamil Nadu').strip()
        pin_code = request.form.get('pin_code', '').strip()
        farmer_name = request.form.get('farmer_name', '').strip()
        farmer_phone = request.form.get('farmer_phone', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        description = request.form.get('description', '').strip()
        urgency_level = request.form.get('urgency_level', 'Normal').strip()
        status = request.form.get('status', 'Available').strip()

        errors = []
        if not crop_name:
            errors.append("Produce name cannot be empty.")
        try:
            qty_val = float(quantity)
            if qty_val < 0:
                errors.append("Quantity cannot be negative.")
        except ValueError:
            errors.append("Please enter a valid numeric quantity.")

        try:
            price_val = float(price_per_unit)
            if price_val <= 0:
                errors.append("Asking price must be greater than 0.")
        except ValueError:
            errors.append("Please enter a valid numeric price.")

        orig_price_val = None
        if original_price:
            try:
                orig_price_val = float(original_price)
            except ValueError:
                pass

        if status not in ['Available', 'Sold', 'Inactive']:
            errors.append("Invalid status selected.")

        photo_filename = listing['photo']
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename != '':
                saved_filename = validate_and_save_image(file)
                if saved_filename:
                    photo_filename = saved_filename
                else:
                    errors.append("Uploaded photo must be a valid image under 3MB.")

        if errors:
            conn.close()
            for err in errors:
                flash(err, "danger")
            return render_template('edit_listing.html', listing=listing)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rescued_flag = listing['rescued_from_waste']
        if status == 'Sold' and listing['status'] != 'Sold':
            rescued_flag = 1

        cursor.execute('''
            UPDATE listings SET
                crop_name = ?, category = ?, photo = ?, quantity = ?, unit = ?,
                price_per_unit = ?, original_price = ?, harvest_date = ?,
                estimated_freshness_date = ?, village_town = ?, district = ?, state = ?,
                pin_code = ?, farmer_name = ?, farmer_phone = ?, whatsapp_number = ?,
                description = ?, urgency_level = ?, status = ?, rescued_from_waste = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, estimated_freshness_date, village_town,
            district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
            description, urgency_level, status, rescued_flag, now_str, listing_id
        ))
        conn.commit()
        conn.close()

        log_activity("Listing Updated", f"Listing #{listing_id} ({crop_name}) updated by {g.user['email']}")
        flash(f"Produce listing '{crop_name}' updated successfully.", "success")
        return redirect(url_for('farmer_dashboard'))

    conn.close()
    return render_template('edit_listing.html', listing=listing)

@app.route('/listing/delete/<int:listing_id>', methods=['POST'])
@login_required
def delete_listing(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        flash("Listing not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    if listing['farmer_id'] != g.user['id'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized to delete this listing.", "danger")
        return redirect(url_for('index'))

    crop_name = listing['crop_name']
    cursor.execute("DELETE FROM listings WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()

    log_activity("Listing Deleted", f"Listing #{listing_id} ({crop_name}) deleted by {g.user['email']}")
    flash(f"Listing '{crop_name}' was removed successfully.", "info")

    if g.user['role'] == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('farmer_dashboard'))

@app.route('/listing/toggle-status/<int:listing_id>', methods=['POST'])
@login_required
def toggle_listing_status(listing_id):
    """Allows farmer or admin to toggle between 'Available' and 'Sold'."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        flash("Listing not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    if listing['farmer_id'] != g.user['id'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))

    new_status = 'Sold' if listing['status'] == 'Available' else 'Available'
    rescued = 1 if new_status == 'Sold' else listing['rescued_from_waste']

    cursor.execute("""
        UPDATE listings SET status = ?, rescued_from_waste = ?, updated_at = ? 
        WHERE id = ?
    """, (new_status, rescued, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), listing_id))
    conn.commit()
    conn.close()

    log_activity("Status Toggled", f"Listing #{listing_id} ({listing['crop_name']}) status marked as {new_status}")
    flash(f"Listing '{listing['crop_name']}' is now marked as {new_status}!", "success")

    if request.referrer and 'admin' in request.referrer:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('farmer_dashboard'))

# ==========================================
# Smart Buyer Matching Route (Section 6)
# ==========================================

@app.route('/nearby-buyers')
def nearby_buyers():
    """
    Helps farmers match with active buyers across Tamil Nadu.
    Matches by crop, category, district, and buyer business type.
    """
    district_filter = request.args.get('district', '').strip()
    buyer_type_filter = request.args.get('buyer_type', '').strip()
    category_filter = request.args.get('category', '').strip()
    search_q = request.args.get('q', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT r.*, u.name as registered_buyer_name, u.email as buyer_email, u.phone as buyer_phone_user
        FROM buyer_requirements r
        JOIN users u ON r.buyer_id = u.id
        WHERE r.status = 'Active' AND u.is_active = 1
    """
    params = []

    if district_filter:
        query += " AND r.district = ?"
        params.append(district_filter)

    if buyer_type_filter:
        query += " AND r.business_type = ?"
        params.append(buyer_type_filter)

    if category_filter:
        query += " AND r.category = ?"
        params.append(category_filter)

    if search_q:
        query += " AND (r.crop_name LIKE ? OR r.notes LIKE ? OR r.village_town LIKE ? OR r.buyer_name LIKE ?)"
        param_pattern = f"%{search_q}%"
        params.extend([param_pattern] * 4)

    query += " ORDER BY r.created_at DESC"

    cursor.execute(query, params)
    buyer_requirements = cursor.fetchall()

    # Pre-calculate counts by buyer category for quick badges
    cursor.execute("""
        SELECT business_type, COUNT(*) as count 
        FROM buyer_requirements WHERE status = 'Active' 
        GROUP BY business_type
    """)
    type_counts = {row['business_type']: row['count'] for row in cursor.fetchall()}

    conn.close()

    return render_template(
        'nearby_buyers.html',
        requirements=buyer_requirements,
        district_filter=district_filter,
        buyer_type_filter=buyer_type_filter,
        category_filter=category_filter,
        search_q=search_q,
        type_counts=type_counts
    )

# ==========================================
# AI-Based Produce Rescue Assistant (Section 7)
# ==========================================

@app.route('/ai-assistant', methods=['GET', 'POST'])
def ai_assistant():
    """Interactive page for AI-assisted shelf-life and selling strategy."""
    ai_result = None
    form_data = {}

    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        quantity = request.form.get('quantity', '100').strip()
        unit = request.form.get('unit', 'kg').strip()
        harvest_date = request.form.get('harvest_date', '').strip()
        freshness_obs = request.form.get('freshness_obs', '').strip()
        storage_condition = request.form.get('storage_condition', 'Ambient / Room Temperature').strip()
        location = request.form.get('location', 'Tamil Nadu').strip()
        urgency = request.form.get('urgency', 'Normal').strip()

        form_data = {
            'crop_name': crop_name,
            'quantity': quantity,
            'unit': unit,
            'harvest_date': harvest_date,
            'freshness_obs': freshness_obs,
            'storage_condition': storage_condition,
            'location': location,
            'urgency': urgency
        }

        if crop_name:
            ai_result = get_ai_rescue_advice(
                crop_name, quantity, unit, harvest_date, freshness_obs,
                storage_condition, location, urgency, lang=g.lang
            )
        else:
            flash("Please enter the name of the agricultural produce.", "warning")

    # If GET with query params from farmer dashboard or listing
    prefill_crop = request.args.get('crop', '')
    prefill_qty = request.args.get('qty', '')
    if prefill_crop and not form_data:
        form_data['crop_name'] = prefill_crop
        form_data['quantity'] = prefill_qty
        form_data['location'] = g.user['location'] if g.user and g.user['location'] else 'Tamil Nadu'

    return render_template('ai_assistant.html', ai_result=ai_result, form_data=form_data)

@app.route('/api/ai-rescue-advice', methods=['POST'])
def api_ai_rescue_advice():
    """Backend JSON endpoint for AI rescue assistant."""
    data = request.get_json(silent=True) or request.form
    crop_name = data.get('crop_name', '').strip()
    quantity = data.get('quantity', '100')
    unit = data.get('unit', 'kg')
    harvest_date = data.get('harvest_date', '')
    freshness_obs = data.get('freshness_obs', '')
    storage_condition = data.get('storage_condition', 'Ambient / Room Temperature')
    location = data.get('location', 'Tamil Nadu')
    urgency = data.get('urgency', 'Normal')

    if not crop_name:
        return jsonify({'error': 'Crop name is required'}), 400

    result = get_ai_rescue_advice(
        crop_name, quantity, unit, harvest_date, freshness_obs,
        storage_condition, location, urgency, lang=g.lang
    )
    return jsonify(result)

# ==========================================
# Buyer Orders / Enquiries Workflow (Section 10 & 11)
# ==========================================

@app.route('/order/submit', methods=['POST'])
@app.route('/enquiry/submit', methods=['POST'], endpoint='submit_enquiry')
def submit_order():
    """
    Submits a purchase request from a buyer with requested quantity,
    offered rate, and delivery preference.
    Validates available stock and calculates totals on backend.
    """
    listing_id = request.form.get('listing_id')
    buyer_name = request.form.get('buyer_name', '').strip()
    buyer_phone = request.form.get('buyer_phone', '').strip()
    buyer_email = request.form.get('buyer_email', '').strip().lower()
    offered_price = request.form.get('offered_price', '').strip()
    requested_quantity = request.form.get('requested_quantity', '').strip()
    delivery_preference = request.form.get('delivery_preference', 'Direct Pickup / Collection').strip()
    message = request.form.get('message', '').strip()

    buyer_id = g.user['id'] if g.user else None
    if g.user:
        buyer_name = buyer_name or g.user['name']
        buyer_email = buyer_email or g.user['email']
        buyer_phone = buyer_phone or g.user['phone']

    errors = []
    if not listing_id:
        errors.append("Invalid produce listing reference.")
    if not buyer_name:
        errors.append("Your name is required.")
    if not buyer_phone or len(buyer_phone) < 10:
        errors.append("A valid 10-digit contact phone number is required.")
    if not buyer_email or '@' not in buyer_email:
        errors.append("A valid email address is required.")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()

    if not listing:
        conn.close()
        flash("Listing not found.", "danger")
        return redirect(url_for('browse_listings'))

    if listing['status'] != 'Available':
        conn.close()
        flash("Sorry, this produce listing is no longer available.", "warning")
        return redirect(url_for('listing_detail', listing_id=listing_id))

    req_qty_val = 0.0
    try:
        req_qty_val = float(requested_quantity)
        if req_qty_val <= 0:
            errors.append("Requested quantity must be greater than zero.")
        elif req_qty_val > listing['quantity']:
            errors.append(f"Requested quantity ({req_qty_val} {listing['unit']}) exceeds available stock ({listing['quantity']} {listing['unit']}).")
    except (ValueError, TypeError):
        errors.append("Please specify a valid numeric requested quantity.")

    offered_price_val = listing['price_per_unit']
    if offered_price:
        try:
            p_val = float(offered_price)
            if p_val > 0:
                offered_price_val = p_val
            else:
                errors.append("Offered price must be positive.")
        except ValueError:
            pass

    if errors:
        conn.close()
        for err in errors:
            flash(err, "danger")
        return redirect(url_for('listing_detail', listing_id=listing_id))

    # Calculate total on backend
    total_price = req_qty_val * offered_price_val

    # Find or associate buyer_id
    if not buyer_id:
        cursor.execute("SELECT id FROM users WHERE email = ?", (buyer_email,))
        existing_user = cursor.fetchone()
        buyer_id = existing_user['id'] if existing_user else 1

    cursor.execute('''
        INSERT INTO enquiries (
            listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
            offered_price, requested_quantity, delivery_preference, total_price,
            message, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ''', (
        listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
        offered_price_val, req_qty_val, delivery_preference, total_price, message
    ))
    order_id = cursor.lastrowid
    conn.commit()

    # Create notification for farmer
    create_notification(
        listing['farmer_id'],
        f"New Purchase Request: {req_qty_val} {listing['unit']} of {listing['crop_name']}",
        f"Buyer {buyer_name} ({buyer_phone}) sent a request at ₹{offered_price_val}/{listing['unit']}.",
        "order",
        url_for('farmer_dashboard')
    )

    conn.close()

    log_activity("Purchase Request Sent", f"Order #{order_id} placed for {req_qty_val} {listing['unit']} {listing['crop_name']} by {buyer_name}", buyer_email)

    flash(f"Purchase request submitted successfully to farmer {listing['farmer_name']}! You can track this in your dashboard.", "success")
    if g.user and g.user['role'] == 'buyer':
        return redirect(url_for('buyer_dashboard'))
    return redirect(url_for('listing_detail', listing_id=listing_id))

@app.route('/order/update-status/<int:order_id>', methods=['POST'])
@app.route('/enquiry/update-status/<int:order_id>', methods=['POST'])
@app.route('/enquiry/update-status-compat/<int:enquiry_id>', methods=['POST'], endpoint='update_enquiry_status')
@login_required
def update_order_status(order_id=None, enquiry_id=None):
    """
    Validates status transitions:
    - Farmer: Pending -> Accepted / Rejected -> Ready for Collection -> Completed
    - Concurrency & Inventory: when Completed, deducts quantity from listing.
      If remaining quantity reaches 0, listing status becomes 'Sold'.
    """
    actual_order_id = order_id if order_id is not None else enquiry_id
    new_status = request.form.get('status', '').strip()
    valid_statuses = ['Pending', 'Accepted', 'Rejected', 'Declined', 'Ready for Collection', 'Completed', 'Cancelled']
    
    if new_status not in valid_statuses:
        flash("Invalid order status transition.", "danger")
        return redirect(request.referrer or url_for('farmer_dashboard'))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.*, l.farmer_id, l.crop_name, l.quantity as current_stock, l.unit, l.farmer_name
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (actual_order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order record not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    is_farmer = (order['farmer_id'] == g.user['id'])
    is_buyer = (order['buyer_id'] == g.user['id'] or order['buyer_email'] == g.user['email'])
    is_admin = (g.user['role'] == 'admin')

    if not (is_farmer or is_buyer or is_admin):
        conn.close()
        flash("Unauthorized action on this order.", "danger")
        return redirect(url_for('index'))

    # Only buyer or admin can Cancel a Pending order
    if new_status == 'Cancelled' and not (is_buyer or is_admin or is_farmer):
        conn.close()
        flash("Only the buyer or admin can cancel this request.", "danger")
        return redirect(request.referrer or url_for('index'))

    # Handle completion inventory update
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if new_status == 'Completed' and order['status'] != 'Completed':
        # Deduct ordered quantity from listing
        req_qty = order['requested_quantity'] or 0.0
        new_qty = max(0.0, float(order['current_stock']) - float(req_qty))
        new_listing_status = 'Sold' if new_qty <= 0 else 'Available'
        
        cursor.execute("""
            UPDATE listings SET quantity = ?, status = ?, rescued_from_waste = 1, updated_at = ?
            WHERE id = ?
        """, (new_qty, new_listing_status, now_str, order['listing_id']))

    cursor.execute("""
        UPDATE enquiries SET status = ?, updated_at = ? WHERE id = ?
    """, (new_status, now_str, actual_order_id))
    conn.commit()

    # Send Notification to counterpart
    target_user_id = order['buyer_id'] if is_farmer else order['farmer_id']
    status_msg = f"Order #{actual_order_id} for {order['crop_name']} status is now: {new_status}."
    create_notification(target_user_id, f"Order Update: {new_status}", status_msg, "status_change", url_for('buyer_dashboard') if is_farmer else url_for('farmer_dashboard'))

    conn.close()

    log_activity("Order Status Updated", f"Order #{actual_order_id} ({order['crop_name']}) status changed to {new_status} by {g.user['email']}")
    flash(f"Order #{actual_order_id} marked as '{new_status}'.", "info")

    if is_buyer and not is_admin:
        return redirect(url_for('buyer_dashboard'))
    return redirect(url_for('farmer_dashboard'))

@app.route('/order/cancel/<int:order_id>', methods=['POST'])
@app.route('/enquiry/cancel/<int:order_id>', methods=['POST'], endpoint='cancel_enquiry')
@login_required
def cancel_order(order_id):
    """Convenience endpoint for buyers to cancel their pending orders."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.farmer_id, l.crop_name 
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for('buyer_dashboard'))

    if order['buyer_id'] != g.user['id'] and order['buyer_email'] != g.user['email'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized action.", "danger")
        return redirect(url_for('buyer_dashboard'))

    if order['status'] not in ['Pending']:
        conn.close()
        flash("Only pending orders can be cancelled.", "warning")
        return redirect(url_for('buyer_dashboard'))

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE enquiries SET status = 'Cancelled', updated_at = ? WHERE id = ?", (now_str, order_id))
    conn.commit()

    # Notify farmer of cancellation
    create_notification(order['farmer_id'], "Order Cancelled", f"Buyer cancelled purchase request #{order_id} for {order['crop_name']}.", "status_change", url_for('farmer_dashboard'))
    conn.close()

    flash(f"Order #{order_id} for '{order['crop_name']}' has been cancelled.", "info")
    return redirect(url_for('buyer_dashboard'))

# ==========================================
# Buyer Procurement Requirements Posting
# ==========================================

@app.route('/buyer/requirement/add', methods=['POST'])
@login_required
def add_buyer_requirement():
    if g.user['role'] not in ['buyer', 'admin']:
        flash("Only registered buyers can post procurement requirements.", "warning")
        return redirect(url_for('index'))

    crop_name = request.form.get('crop_name', '').strip()
    category = request.form.get('category', 'Vegetables').strip()
    business_type = request.form.get('business_type', g.user.get('user_type') or 'Supermarkets').strip()
    required_quantity = request.form.get('required_quantity', '').strip()
    unit = request.form.get('unit', 'kg').strip()
    target_price = request.form.get('target_price', '').strip()
    village_town = request.form.get('village_town', g.user.get('location') or '').strip()
    district = request.form.get('district', '').strip()
    contact_phone = request.form.get('contact_phone', g.user['phone']).strip()
    notes = request.form.get('notes', '').strip()

    if not crop_name or not required_quantity or not district:
        flash("Please provide crop name, required quantity, and district.", "danger")
        return redirect(url_for('buyer_dashboard'))

    try:
        qty_val = float(required_quantity)
        if qty_val <= 0:
            flash("Required quantity must be positive.", "danger")
            return redirect(url_for('buyer_dashboard'))
    except ValueError:
        flash("Please enter a valid numeric quantity.", "danger")
        return redirect(url_for('buyer_dashboard'))

    target_price_val = None
    if target_price:
        try:
            target_price_val = float(target_price)
        except ValueError:
            pass

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO buyer_requirements (
            buyer_id, buyer_name, business_type, crop_name, category,
            required_quantity, unit, target_price, village_town, district,
            state, contact_phone, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Tamil Nadu', ?, ?, 'Active')
    ''', (
        g.user['id'], g.user['name'], business_type, crop_name, category,
        qty_val, unit, target_price_val, village_town, district, contact_phone, notes
    ))
    conn.commit()
    conn.close()

    log_activity("Buyer Requirement Posted", f"Requirement posted for {qty_val} {unit} of {crop_name} in {district} by {g.user['email']}")
    flash(f"Your buying requirement for '{crop_name}' has been posted! Farmers nearby can view and contact you.", "success")
    return redirect(url_for('buyer_dashboard'))

@app.route('/buyer/requirement/delete/<int:req_id>', methods=['POST'])
@login_required
def delete_buyer_requirement(req_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM buyer_requirements WHERE id = ?", (req_id,))
    req_item = cursor.fetchone()

    if not req_item:
        conn.close()
        flash("Requirement not found.", "danger")
        return redirect(url_for('buyer_dashboard'))

    if req_item['buyer_id'] != g.user['id'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized action.", "danger")
        return redirect(url_for('buyer_dashboard'))

    cursor.execute("DELETE FROM buyer_requirements WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()

    flash("Buying requirement removed.", "info")
    return redirect(url_for('buyer_dashboard'))

# ==========================================
# In-App Notifications Center (Section 12)
# ==========================================

@app.route('/notifications')
@login_required
def notifications_view():
    notifications = get_user_notifications(g.user['id'], limit=50)
    return render_template('notifications.html', notifications=notifications)

@app.route('/notification/read/<int:notif_id>')
@login_required
def read_notification(notif_id):
    mark_notification_read(notif_id, g.user['id'])
    next_url = request.args.get('next')
    if next_url:
        return redirect(next_url)
    return redirect(url_for('notifications_view'))

@app.route('/notification/read-all', methods=['POST'])
@login_required
def read_all_notifications():
    mark_all_notifications_read(g.user['id'])
    flash("All notifications marked as read.", "info")
    return redirect(url_for('notifications_view'))

@app.route('/api/notifications/unread-count')
def api_unread_notifications_count():
    if not g.user:
        return jsonify({'unread': 0})
    count = get_unread_notifications_count(g.user['id'])
    return jsonify({'unread': count})

# ==========================================
# Waste Reduction Analytics (Section 13)
# ==========================================

@app.route('/analytics')
@login_required
def analytics_view():
    """
    Analytics on produce listed, sold, remaining, revenue,
    and confirmed saved from food waste.
    """
    timeframe = request.args.get('timeframe', 'all') # 'all', 'month', 'week'
    conn = get_db()
    cursor = conn.cursor()

    is_farmer = (g.user['role'] == 'farmer')
    is_admin = (g.user['role'] == 'admin')

    farmer_clause = "WHERE farmer_id = ?" if is_farmer else "WHERE 1=1"
    farmer_params = [g.user['id']] if is_farmer else []

    # Time filter
    time_clause = ""
    if timeframe == 'month':
        time_clause = " AND (julianday('now') - julianday(created_at)) <= 30"
    elif timeframe == 'week':
        time_clause = " AND (julianday('now') - julianday(created_at)) <= 7"

    # 1. Total quantity listed
    cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings {farmer_clause} {time_clause}", farmer_params)
    total_qty_listed = cursor.fetchone()[0]

    # 2. Total quantity currently available
    cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings {farmer_clause} AND status = 'Available' {time_clause}", farmer_params)
    available_qty = cursor.fetchone()[0]

    # 3. Completed sales count & revenue from orders
    if is_farmer:
        cursor.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0),
                   COALESCE(SUM(e.requested_quantity), 0)
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE l.farmer_id = ? AND e.status = 'Completed'
        """, (g.user['id'],))
    else:
        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0),
                   COALESCE(SUM(e.requested_quantity), 0)
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE e.status = 'Completed'
        """)
    completed_orders_data = cursor.fetchone()
    completed_orders_count = completed_orders_data[0]
    total_sales_revenue = completed_orders_data[1]
    total_qty_sold = completed_orders_data[2]

    # 4. Confirmed saved from waste (Sold listings with rescued_from_waste = 1)
    cursor.execute(f"""
        SELECT COALESCE(SUM(quantity), 0) FROM listings 
        {farmer_clause} AND (status = 'Sold' OR rescued_from_waste = 1) {time_clause}
    """, farmer_params)
    confirmed_rescued_kg = cursor.fetchone()[0]

    # 5. Category distribution
    cursor.execute(f"""
        SELECT category, COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_kg
        FROM listings {farmer_clause} {time_clause}
        GROUP BY category
    """, farmer_params)
    category_breakdown = cursor.fetchall()

    conn.close()

    return render_template(
        'analytics.html',
        timeframe=timeframe,
        total_qty_listed=total_qty_listed,
        available_qty=available_qty,
        total_qty_sold=total_qty_sold,
        completed_orders_count=completed_orders_count,
        total_sales_revenue=total_sales_revenue,
        confirmed_rescued_kg=confirmed_rescued_kg,
        category_breakdown=category_breakdown,
        is_farmer=is_farmer
    )

# ==========================================
# Role-Specific Dashboards
# ==========================================

@app.route('/farmer/dashboard')
@login_required
@role_required(['farmer', 'admin'])
def farmer_dashboard():
    """
    Farmer Dashboard with real calculated metrics:
    1. Total Products Listed
    2. Available Produce Quantity (kg)
    3. Pending Orders
    4. Completed Sales
    5. Produce at Risk (kg)
    6. Total Sales Revenue (₹)
    Strictly calculates from DB, excluding cancelled/rejected orders.
    """
    conn = get_db()
    cursor = conn.cursor()
    farmer_id = g.user['id']

    # 1. Total Products Listed
    cursor.execute("SELECT COUNT(*) FROM listings WHERE farmer_id = ?", (farmer_id,))
    total_products_listed = cursor.fetchone()[0]

    # 2. Available Produce Quantity
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) FROM listings 
        WHERE farmer_id = ? AND status = 'Available'
    """, (farmer_id,))
    available_produce_qty = cursor.fetchone()[0]

    # 3. Pending Orders
    cursor.execute("""
        SELECT COUNT(*) FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status = 'Pending'
    """, (farmer_id,))
    pending_orders_count = cursor.fetchone()[0]

    # 4. Completed Sales
    cursor.execute("""
        SELECT COUNT(*) FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status = 'Completed'
    """, (farmer_id,))
    completed_sales_count = cursor.fetchone()[0]

    # 5. Produce at Risk (kg)
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) FROM listings 
        WHERE farmer_id = ? AND status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
    """, (farmer_id,))
    produce_at_risk_qty = cursor.fetchone()[0]

    # 6. Total Sales Revenue (₹)
    cursor.execute("""
        SELECT COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status = 'Completed'
    """, (farmer_id,))
    total_sales_revenue = cursor.fetchone()[0]

    # Farmer's recent listings
    cursor.execute("""
        SELECT * FROM listings 
        WHERE farmer_id = ? 
        ORDER BY created_at DESC
    """, (farmer_id,))
    my_listings = cursor.fetchall()

    # Enquiries / Orders received for farmer's listings
    cursor.execute("""
        SELECT e.*, l.crop_name, l.unit, l.price_per_unit, l.status as listing_status
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ?
        ORDER BY e.created_at DESC
    """, (farmer_id,))
    received_orders = cursor.fetchall()

    # Attention count
    attention_count = sum(1 for item in my_listings if is_needs_attention(item))
    active_count = sum(1 for item in my_listings if item['status'] == 'Available')
    sold_count = sum(1 for item in my_listings if item['status'] == 'Sold')

    conn.close()

    return render_template(
        'farmer_dashboard.html',
        listings=my_listings,
        orders=received_orders,
        enquiries=received_orders,  # backwards-compatibility
        total_products_listed=total_products_listed,
        available_produce_qty=available_produce_qty,
        pending_orders_count=pending_orders_count,
        completed_sales_count=completed_sales_count,
        produce_at_risk_qty=produce_at_risk_qty,
        total_sales_revenue=total_sales_revenue,
        attention_count=attention_count,
        active_count=active_count,
        sold_count=sold_count,
        pending_enquiries_count=pending_orders_count
    )

@app.route('/buyer/dashboard')
@login_required
@role_required(['buyer', 'admin'])
def buyer_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Enquiries sent by this buyer
    cursor.execute("""
        SELECT e.*, l.crop_name, l.unit, l.price_per_unit, l.village_town, l.district, 
               l.farmer_name, l.farmer_phone, l.whatsapp_number, l.status as listing_status, l.photo
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.buyer_id = ? OR e.buyer_email = ?
        ORDER BY e.created_at DESC
    """, (g.user['id'], g.user['email']))
    my_orders = cursor.fetchall()

    # Buyer's posted procurement requirements
    cursor.execute("""
        SELECT * FROM buyer_requirements 
        WHERE buyer_id = ? 
        ORDER BY created_at DESC
    """, (g.user['id'],))
    my_requirements = cursor.fetchall()

    # Urgently available listings buyer might want to rescue
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
        ORDER BY created_at ASC 
        LIMIT 4
    """)
    urgent_recommendations = cursor.fetchall()

    conn.close()

    return render_template(
        'buyer_dashboard.html',
        orders=my_orders,
        enquiries=my_orders,  # backward compatibility
        requirements=my_requirements,
        urgent_recommendations=urgent_recommendations
    )

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Platform Stats
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_active = 1")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'farmer' AND is_active = 1")
    total_farmers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer' AND is_active = 1")
    total_buyers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings")
    total_listings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    available_listings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Sold'")
    sold_listings = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM listings 
        WHERE status = 'Available' AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale')
    """)
    urgent_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM enquiries")
    total_enquiries = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.status = 'Completed'
    """)
    platform_revenue = cursor.fetchone()[0]

    # All Users
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    all_users = cursor.fetchall()

    # All Listings
    cursor.execute("""
        SELECT l.*, u.email as farmer_email 
        FROM listings l 
        JOIN users u ON l.farmer_id = u.id 
        ORDER BY l.created_at DESC
    """)
    all_listings = cursor.fetchall()

    # Recent Platform Enquiries / Orders
    cursor.execute("""
        SELECT e.*, l.crop_name, l.farmer_name
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        ORDER BY e.created_at DESC LIMIT 20
    """)
    all_enquiries = cursor.fetchall()

    # Activity Logs
    cursor.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 30")
    recent_logs = cursor.fetchall()

    # Demonstration Listings Count
    cursor.execute("SELECT COUNT(*) FROM listings WHERE farmer_name LIKE '[DEMO]%'")
    demo_listings_count = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        total_farmers=total_farmers,
        total_buyers=total_buyers,
        total_listings=total_listings,
        available_listings=available_listings,
        sold_listings=sold_listings,
        urgent_count=urgent_count,
        total_enquiries=total_enquiries,
        platform_revenue=platform_revenue,
        demo_listings_count=demo_listings_count,
        users=all_users,
        listings=all_listings,
        enquiries=all_enquiries,
        logs=recent_logs
    )

@app.route('/admin/toggle-user-status/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_toggle_user_status(user_id):
    if user_id == g.user['id']:
        flash("You cannot deactivate your own admin account.", "danger")
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, is_active FROM users WHERE id = ?", (user_id,))
    target = cursor.fetchone()

    if target:
        new_active = 0 if target['is_active'] == 1 else 1
        cursor.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_active, user_id))
        conn.commit()
        status_label = "Activated" if new_active == 1 else "Deactivated"
        log_activity(f"User {status_label}", f"Admin changed status of user #{user_id} ({target['name']}) to {status_label}")
        flash(f"User '{target['name']}' has been {status_label.lower()}.", "info")
    else:
        flash("User not found.", "warning")

    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@role_required('admin')
def admin_delete_user(user_id):
    if user_id == g.user['id']:
        flash("You cannot delete your own admin account.", "danger")
        return redirect(url_for('admin_dashboard'))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, email, role FROM users WHERE id = ?", (user_id,))
    target_user = cursor.fetchone()

    if target_user:
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        log_activity("User Deleted", f"Admin deleted {target_user['role']} {target_user['name']} ({target_user['email']})")
        flash(f"User '{target_user['name']}' has been removed from the platform.", "info")
    else:
        flash("User not found.", "warning")

    conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/sample-data/remove', methods=['POST'])
@login_required
@role_required('admin')
def admin_remove_sample_data():
    try:
        from seed_vegetables import remove_sample_data
        count = remove_sample_data()
        log_activity("Sample Data Removed", f"Admin removed {count} demonstration vegetable listings and sample accounts.")
        flash(f"Successfully removed {count} demonstration vegetable listings from the platform.", "info")
    except Exception as e:
        flash(f"Error removing sample data: {e}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/sample-data/reset', methods=['POST'])
@login_required
@role_required('admin')
def admin_reset_sample_data():
    try:
        from seed_vegetables import reset_sample_data
        removed, inserted = reset_sample_data()
        log_activity("Sample Data Reset", f"Admin reset demonstration vegetable listings (removed {removed}, seeded {inserted}).")
        flash(f"Successfully refreshed {inserted} demonstration vegetable listings with current dates and market rates.", "success")
    except Exception as e:
        flash(f"Error refreshing sample data: {e}", "danger")
    return redirect(url_for('admin_dashboard'))

# ==========================================
# Error Handlers
# ==========================================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(413)
def file_too_large(e):
    flash("Uploaded image is too large! Maximum allowed image size is 3 MB.", "danger")
    return redirect(request.url)

# ==========================================
# Run application
# ==========================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1')
    print(f"FarmFresh Rescue Platform starting on http://0.0.0.0:{port} ...")
    app.run(host='0.0.0.0', port=port, debug=debug)
