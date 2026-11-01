import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, g, abort, jsonify, make_response, send_file
)
import io
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

from database import (
    get_db, init_db, seed_db, create_notification,
    get_unread_notifications_count, get_user_notifications,
    mark_notification_read, mark_all_notifications_read,
    toggle_favorite_farmer, is_farmer_favorited, get_buyer_favorites,
    save_quality_inspection, get_farmer_quality_inspections,
    log_ai_chat, update_order_lifecycle, get_order_timeline,
    create_payment_record, confirm_payment_record, confirm_cod_order,
    request_payment_refund, process_admin_refund, get_buyer_payments,
    get_farmer_payments, get_admin_payments, get_payment_by_order_id,
    get_available_stock, reserve_listing_stock, get_market_prices,
    get_crop_benchmark_price, save_chat_message, get_conversation_messages,
    get_user_chat_threads, get_weather_alerts
)
from razorpay_gateway import (
    create_razorpay_order, verify_razorpay_signature,
    verify_webhook_signature, RAZORPAY_KEY_ID
)
from qr_generator import generate_qr_bytes
from translations import t, TRANSLATIONS
from ai_engine import (
    get_ai_rescue_advice, predict_freshness, recommend_smart_price,
    match_smart_buyers, grade_produce_quality, predict_market_demand,
    chat_with_farmfresh_ai, parse_voice_command, TN_DISTRICT_COORDINATES,
    calculate_haversine_distance, get_coordinates_for_location
)

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
        'predict_freshness': predict_freshness,
        'recommend_smart_price': recommend_smart_price,
        'is_farmer_favorited': lambda f_id: is_farmer_favorited(g.user['id'], f_id) if g.user and g.user['role'] == 'buyer' else False,
        'tn_districts': TN_DISTRICTS,
        'crop_categories': CROP_CATEGORIES,
        'crop_units': CROP_UNITS,
        'buyer_types': BUYER_TYPES,
        'tn_district_coordinates': TN_DISTRICT_COORDINATES,
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

    # AI Freshness Prediction
    freshness = predict_freshness(listing['crop_name'], listing['harvest_date'], listing['storage_condition'] or 'ambient')

    # AI Price Recommendation
    price_rec = recommend_smart_price(
        listing['crop_name'],
        listing['quantity'],
        freshness.get('freshness_score', 80),
        asking_price=listing['price_per_unit'],
        conn=conn
    )

    # Buyer distance calculation & favorite status
    buyer_distance_km = None
    is_favorited = False
    if g.user and g.user['role'] == 'buyer':
        is_favorited = is_farmer_favorited(g.user['id'], listing['farmer_id'], conn)
        user_keys = g.user.keys()
        buyer_lat = g.user['latitude'] if 'latitude' in user_keys else None
        buyer_lng = g.user['longitude'] if 'longitude' in user_keys else None
        if not buyer_lat and g.user['location']:
            user_dist = g.user['district'] if 'district' in user_keys else ''
            b_coords = get_coordinates_for_location(g.user['location'], user_dist or '')
            if b_coords:
                buyer_lat, buyer_lng = b_coords[0], b_coords[1]
        
        listing_lat = listing['latitude']
        listing_lng = listing['longitude']
        if not listing_lat:
            l_coords = get_coordinates_for_location(listing['village_town'], listing['district'])
            if l_coords:
                listing_lat, listing_lng = l_coords[0], l_coords[1]

        if buyer_lat and listing_lat:
            dist_res = calculate_haversine_distance(buyer_lat, buyer_lng, listing_lat, listing_lng)
            buyer_distance_km = dist_res['distance_km'] if isinstance(dist_res, dict) else dist_res

    conn.close()

    days_old, age_text = calculate_listing_age(listing['created_at'])
    urgency_info = get_listing_urgency_info(listing)
    available_stock = get_available_stock(listing_id)
    benchmark_price = get_crop_benchmark_price(listing['crop_name'], listing['district'])

    return render_template(
        'listing_detail.html',
        listing=listing,
        days_old=days_old,
        age_text=age_text,
        days_since_harvest=days_since_harvest,
        urgency_info=urgency_info,
        needs_attn=urgency_info['is_urgent'],
        related_listings=related_listings,
        freshness=freshness,
        price_rec=price_rec,
        buyer_distance_km=buyer_distance_km,
        is_favorited=is_favorited,
        available_stock=available_stock,
        benchmark_price=benchmark_price
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

        storage_condition = request.form.get('storage_condition', 'Ambient / Room Temperature').strip()
        custom_suggested_price = request.form.get('suggested_price', '').strip()

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

        # AI Calculations: Freshness, Price & Coordinates
        lat_val, lng_val, _ = get_coordinates_for_location(village_town, district)
        freshness_res = predict_freshness(crop_name, harvest_date, qty_val, unit, storage_condition)
        freshness_score_val = freshness_res['freshness_score']
        freshness_grade_val = freshness_res['freshness_grade']

        price_res = recommend_smart_price(crop_name, qty_val, freshness_grade_val, location=district, current_price=price_val, db_conn=conn)
        suggested_price_val = float(custom_suggested_price) if custom_suggested_price else price_res['suggested_price']

        # AI Quality Grading if image present
        quality_grade_val = 'Grade A'
        quality_conf_val = 88.0
        quality_analysis_val = 'Initial fresh harvest submission'
        if photo_filename:
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], photo_filename)
            grading_res = grade_produce_quality(img_path, crop_name)
            quality_grade_val = grading_res.get('quality_grade', 'Grade A')
            quality_conf_val = grading_res.get('confidence', 88.0)
            quality_analysis_val = grading_res.get('freshness_assessment', '')
            save_quality_inspection(
                g.user['id'], crop_name, photo_filename, quality_grade_val,
                quality_conf_val, grading_res.get('color_score'), grading_res.get('defect_score'),
                quality_analysis_val, json.dumps(grading_res.get('target_buyers', [])),
                source=grading_res.get('source', 'AI Visual Inspection')
            )

        cursor.execute('''
            INSERT INTO listings (
                farmer_id, crop_name, category, photo, quantity, unit, price_per_unit,
                original_price, harvest_date, estimated_freshness_date, village_town,
                district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
                description, urgency_level, status, rescued_from_waste,
                storage_condition, freshness_score, freshness_grade,
                quality_grade, quality_confidence, quality_analysis,
                suggested_price, latitude, longitude,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            g.user['id'], crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, estimated_freshness_date, village_town,
            district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
            description, urgency_level,
            storage_condition, freshness_score_val, freshness_grade_val,
            quality_grade_val, quality_conf_val, quality_analysis_val,
            suggested_price_val, lat_val, lng_val,
            now_str, now_str
        ))
        conn.commit()
        new_listing_id = cursor.lastrowid

        # AI Smart Buyer Matching & Notifications
        new_listing_dict = {
            'id': new_listing_id,
            'crop_name': crop_name,
            'category': category,
            'quantity': qty_val,
            'unit': unit,
            'price_per_unit': price_val,
            'village_town': village_town,
            'district': district
        }
        matching_buyers = match_smart_buyers(new_listing_dict, top_n=6, db_conn=conn)
        for b in matching_buyers:
            if b.get('match_percentage', 0) >= 60:
                create_notification(
                    b['buyer_id'],
                    f"⚡ New Matching Produce ({b['match_percentage']}% Match): {crop_name}",
                    f"{qty_val} {unit} of {crop_name} listed in {district} (~{b['distance_km']} km away) at ₹{price_val}/{unit}.",
                    "alert",
                    url_for('listing_detail', listing_id=new_listing_id)
                )

        conn.close()

        log_activity("Listing Added", f"Produce listed: {crop_name} ({qty_val} {unit}) at ₹{price_val}/{unit} in {district} [AI Grade: {quality_grade_val}]")
        flash(f"Success! '{crop_name}' has been listed with AI Freshness ({freshness_grade_val}) and Quality ({quality_grade_val}). Matching buyers have been alerted.", "success")
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

        storage_condition = request.form.get('storage_condition', listing['storage_condition'] or 'ambient').strip()
        freshness_info = predict_freshness(crop_name, harvest_date, storage_condition)
        freshness_score = freshness_info.get('freshness_score', 80)
        freshness_grade = freshness_info.get('status', 'Moderate')

        price_rec = recommend_smart_price(crop_name, qty_val, freshness_score, asking_price=price_val, conn=conn)
        suggested_price = price_rec.get('suggested_price', price_val)

        coords = get_coordinates_for_location(village_town, district)
        lat = coords[0] if coords else listing['latitude']
        lng = coords[1] if coords else listing['longitude']

        cursor.execute('''
            UPDATE listings SET
                crop_name = ?, category = ?, photo = ?, quantity = ?, unit = ?,
                price_per_unit = ?, original_price = ?, harvest_date = ?,
                estimated_freshness_date = ?, village_town = ?, district = ?, state = ?,
                pin_code = ?, farmer_name = ?, farmer_phone = ?, whatsapp_number = ?,
                description = ?, urgency_level = ?, status = ?, rescued_from_waste = ?,
                storage_condition = ?, freshness_score = ?, freshness_grade = ?,
                suggested_price = ?, latitude = ?, longitude = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, estimated_freshness_date, village_town,
            district, state, pin_code, farmer_name, farmer_phone, whatsapp_number,
            description, urgency_level, status, rescued_flag,
            storage_condition, freshness_score, freshness_grade,
            suggested_price, lat, lng,
            now_str, listing_id
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
# FarmFresh AI 2.0 Feature Endpoints
# ==========================================

# 1. Freshness Prediction API
@app.route('/api/ai/freshness-predict', methods=['GET', 'POST'])
def api_freshness_predict():
    data = request.get_json(silent=True) or request.args or request.form
    crop_name = data.get('crop_name', 'Tomatoes').strip()
    harvest_date = data.get('harvest_date')
    quantity = float(data.get('quantity') or 100)
    unit = data.get('unit', 'kg')
    storage_condition = data.get('storage_condition', 'Ambient / Room Temperature')
    
    result = predict_freshness(crop_name, harvest_date, quantity, unit, storage_condition)
    return jsonify(result)

# 2. Smart Price Recommendation API
@app.route('/api/ai/price-recommend', methods=['GET', 'POST'])
def api_price_recommend():
    data = request.get_json(silent=True) or request.args or request.form
    crop_name = data.get('crop_name', 'Tomatoes').strip()
    quantity = float(data.get('quantity') or 100)
    freshness_grade = data.get('freshness_grade', 'Fresh')
    location = data.get('location') or data.get('district')
    current_price = data.get('current_price')
    
    conn = get_db()
    result = recommend_smart_price(crop_name, quantity, freshness_grade, location, current_price, db_conn=conn)
    conn.close()
    return jsonify(result)

# 3. Smart Buyer Matching API
@app.route('/api/ai/match-buyers/<int:listing_id>', methods=['GET'])
def api_match_buyers(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()
    if not listing:
        conn.close()
        return jsonify({'error': 'Listing not found'}), 404
        
    matches = match_smart_buyers(dict(listing), top_n=6, db_conn=conn)
    conn.close()
    return jsonify({'listing_id': listing_id, 'matches': matches})

# 4. Send Produce Alert to Buyer
@app.route('/api/ai/notify-buyer', methods=['POST'])
@login_required
def api_notify_buyer():
    data = request.get_json(silent=True) or request.form
    listing_id = data.get('listing_id')
    buyer_id = data.get('buyer_id')
    
    if not listing_id or not buyer_id:
        return jsonify({'error': 'Listing and buyer IDs are required'}), 400
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()
    if not listing:
        conn.close()
        return jsonify({'error': 'Listing not found'}), 404
        
    farmer_name = g.user['name'] if g.user else listing['farmer_name']
    create_notification(
        int(buyer_id),
        f"⚡ Direct Produce Alert from Farmer {farmer_name}",
        f"{listing['quantity']} {listing['unit']} of {listing['crop_name']} in {listing['district']} available at ₹{listing['price_per_unit']}/{listing['unit']}.",
        "alert",
        url_for('listing_detail', listing_id=listing['id'])
    )
    conn.close()
    return jsonify({'success': True, 'message': 'Notification sent to buyer successfully'})

# 5. Multilingual AI Voice Assistant Page & API
@app.route('/voice-assistant')
def voice_assistant():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT crop_name, unit, price_per_unit, district FROM listings 
        WHERE status = 'Available' ORDER BY created_at DESC LIMIT 6
    """)
    recent_produce = cursor.fetchall()
    conn.close()
    return render_template('voice_assistant.html', recent_produce=recent_produce)

@app.route('/api/ai/voice-command', methods=['POST'])
def api_voice_command():
    data = request.get_json(silent=True) or request.form
    speech_text = data.get('speech_text', '').strip()
    lang = data.get('lang', session.get('lang', 'ta'))
    
    user_context = None
    if g.user:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM enquiries e JOIN listings l ON e.listing_id = l.id WHERE l.farmer_id = ? AND e.status = 'Pending'", (g.user['id'],))
        pending_cnt = cursor.fetchone()[0]
        conn.close()
        user_context = {
            'id': g.user['id'],
            'name': g.user['name'],
            'role': g.user['role'],
            'pending_orders_count': pending_cnt
        }
    
    conn = get_db()
    res = parse_voice_command(speech_text, lang=lang, user_context=user_context, db_conn=conn)
    conn.close()
    return jsonify(res)

# 6. AI Produce Quality Grading Page & API
@app.route('/quality-grading', methods=['GET', 'POST'])
def quality_grading():
    grading_result = None
    crop_name = request.form.get('crop_name', '').strip() if request.method == 'POST' else ''
    
    if request.method == 'POST' and 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename != '':
            saved_name = validate_and_save_image(file)
            if saved_name:
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
                grading_result = grade_produce_quality(img_path, crop_name or 'Produce')
                grading_result['photo_filename'] = saved_name
                
                # Persist inspection if user is logged in
                if g.user and g.user['role'] == 'farmer':
                    save_quality_inspection(
                        g.user['id'], crop_name or 'Produce', saved_name,
                        grading_result['quality_grade'], grading_result['confidence'],
                        grading_result.get('color_score'), grading_result.get('defect_score'),
                        grading_result.get('freshness_assessment'),
                        json.dumps(grading_result.get('target_buyers', [])),
                        source=grading_result.get('source', 'AI Visual Inspection')
                    )
            else:
                flash("Please upload a valid image file (PNG, JPG, WEBP).", "danger")

    recent_inspections = []
    if g.user and g.user['role'] == 'farmer':
        recent_inspections = get_farmer_quality_inspections(g.user['id'], limit=6)

    return render_template('quality_grading.html', grading_result=grading_result,
                           crop_name=crop_name, recent_inspections=recent_inspections)

@app.route('/api/ai/grade-produce', methods=['POST'])
def api_grade_produce():
    if 'photo' not in request.files:
        return jsonify({'error': 'Photo file is required'}), 400
    file = request.files['photo']
    crop_name = request.form.get('crop_name', 'Produce').strip()
    saved_name = validate_and_save_image(file)
    if not saved_name:
        return jsonify({'error': 'Invalid image format'}), 400
        
    img_path = os.path.join(app.config['UPLOAD_FOLDER'], saved_name)
    grading = grade_produce_quality(img_path, crop_name)
    grading['photo_filename'] = saved_name
    return jsonify(grading)

# 7. AI Demand Prediction Page & API
@app.route('/demand-prediction')
def demand_prediction():
    conn = get_db()
    demand_data = predict_market_demand(conn)
    conn.close()
    return render_template('demand_prediction.html', demand=demand_data)

@app.route('/api/ai/demand-prediction')
def api_demand_prediction():
    conn = get_db()
    demand_data = predict_market_demand(conn)
    conn.close()
    return jsonify(demand_data)

# 8. Smart Delivery Tracking & Map Page
@app.route('/order/track/<int:order_id>')
@login_required
def track_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.crop_name, l.quantity as stock_qty, l.unit, l.price_per_unit,
               l.village_town as farm_village, l.district as farm_district,
               l.farmer_name, l.farmer_phone, l.whatsapp_number, l.photo as crop_photo,
               l.farmer_id
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    order = cursor.fetchone()
    
    if not order:
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for('index'))
        
    is_farmer = (order['farmer_id'] == g.user['id'])
    is_buyer = (order['buyer_id'] == g.user['id'] or order['buyer_email'] == g.user['email'])
    is_admin = (g.user['role'] == 'admin')
    if not (is_farmer or is_buyer or is_admin):
        conn.close()
        flash("Unauthorized to view this order tracking.", "danger")
        return redirect(url_for('index'))

    # Calculate coordinates
    f_lat, f_lng, f_hub = get_coordinates_for_location(order['farm_village'], order['farm_district'])
    b_district = order['farm_district']
    cursor.execute("SELECT location FROM users WHERE id = ?", (order['buyer_id'],))
    b_user = cursor.fetchone()
    if b_user and b_user['location']:
        b_district = b_user['location']
    b_lat, b_lng, b_hub = get_coordinates_for_location(b_district)

    distance_info = calculate_haversine_distance(f_lat, f_lng, b_lat, b_lng)
    timeline = get_order_timeline(order_id)
    conn.close()

    return render_template(
        'order_tracking.html',
        order=order,
        f_lat=f_lat, f_lng=f_lng, f_hub=f_hub,
        b_lat=b_lat, b_lng=b_lng, b_hub=b_hub,
        distance_info=distance_info,
        timeline=timeline,
        is_farmer=is_farmer,
        is_buyer=is_buyer
    )

@app.route('/api/order/timeline/<int:order_id>')
def api_order_timeline(order_id):
    timeline = get_order_timeline(order_id)
    return jsonify({'order_id': order_id, 'timeline': timeline, 'success': True})

@app.route('/api/order/update-location/<int:order_id>', methods=['POST'])
@login_required
def api_order_update_location(order_id):
    data = request.get_json(silent=True) or request.form
    lat = data.get('lat')
    lng = data.get('lng')
    status = data.get('status')
    note = data.get('note')
    
    success, msg = update_order_lifecycle(
        order_id, status or 'Shipped',
        note=note or 'Delivery vehicle location updated',
        delivery_lat=lat, delivery_lng=lng
    )
    return jsonify({'success': success, 'message': msg})

# 9. Contextual Floating AI Chatbot API
@app.route('/api/ai/chatbot', methods=['POST'])
def api_chatbot():
    data = request.get_json(silent=True) or request.form
    message = data.get('message', '').strip()
    lang = data.get('lang', session.get('lang', 'en'))
    session_id = session.get('_id', 'guest_session')
    
    user_context = None
    if g.user:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM listings WHERE farmer_id = ? AND status = 'Available'", (g.user['id'],))
        active_listings = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM enquiries e JOIN listings l ON e.listing_id = l.id WHERE l.farmer_id = ? AND e.status = 'Pending'", (g.user['id'],))
        pending_orders = cursor.fetchone()[0]
        conn.close()
        user_context = {
            'id': g.user['id'],
            'name': g.user['name'],
            'role': g.user['role'],
            'active_listings_count': active_listings,
            'pending_orders_count': pending_orders
        }
        
    chat_res = chat_with_farmfresh_ai(message, user_context=user_context, lang=lang)
    log_ai_chat(g.user['id'] if g.user else None, session_id, message, chat_res['reply'], lang)
    return jsonify(chat_res)

# 10. Favorite Farmer Toggle API
@app.route('/api/buyer/favorite-farmer/<int:farmer_id>', methods=['POST'])
@login_required
def api_favorite_farmer(farmer_id):
    if g.user['role'] not in ['buyer', 'admin']:
        return jsonify({'error': 'Only registered buyers can save favorite farmers'}), 403
    res = toggle_favorite_farmer(g.user['id'], farmer_id)
    return jsonify(res)

# 11. Download Sales & Profit Analytics CSV
@app.route('/analytics/export-csv')
def export_analytics_csv():
    conn = get_db()
    cursor = conn.cursor()
    is_farmer = bool(g.user and g.user['role'] == 'farmer')
    
    if is_farmer:
        cursor.execute("""
            SELECT e.id, e.created_at, l.crop_name, e.buyer_name, e.buyer_phone,
                   e.requested_quantity, l.unit, e.offered_price, e.total_price, e.status
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE l.farmer_id = ?
            ORDER BY e.created_at DESC
        """, (g.user['id'],))
    else:
        cursor.execute("""
            SELECT e.id, e.created_at, l.crop_name, e.buyer_name, e.buyer_phone,
                   e.requested_quantity, l.unit, e.offered_price, e.total_price, e.status
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            ORDER BY e.created_at DESC
        """)
    orders = cursor.fetchall()
    conn.close()

    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Order ID', 'Date', 'Crop Name', 'Buyer Name', 'Buyer Phone', 'Quantity', 'Unit', 'Price per Unit (Rs)', 'Total Price (Rs)', 'Status'])
    for o in orders:
        writer.writerow([o['id'], o['created_at'], o['crop_name'], o['buyer_name'], o['buyer_phone'], o['requested_quantity'], o['unit'], o['offered_price'], o['total_price'], o['status']])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=farmfresh_sales_report_{datetime.now().strftime("%Y%m%d")}.csv'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response

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
    data = request.get_json(silent=True) or request.form
    new_status = data.get('status', '').strip()
    status_note = data.get('note', '').strip()
    valid_statuses = [
        # Official 9 Lifecycle Statuses (Section 4):
        'Order Placed', 'Order Accepted', 'Order Rejected', 'Processing',
        'Packed', 'Ready for Pickup', 'Out for Delivery', 'Delivered', 'Cancelled',
        # Backward-compatibility aliases:
        'Pending', 'Accepted', 'Rejected', 'Declined', 'Ready for Collection',
        'Shipped', 'Completed'
    ]
    
    is_json = request.is_json or request.headers.get('Accept') == 'application/json'

    if new_status not in valid_statuses:
        if is_json:
            return jsonify({'error': 'Invalid order status transition'}), 400
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
        if is_json:
            return jsonify({'error': 'Order record not found'}), 404
        flash("Order record not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    is_farmer = (order['farmer_id'] == g.user['id'])
    is_buyer = (order['buyer_id'] == g.user['id'] or order['buyer_email'] == g.user['email'])
    is_admin = (g.user['role'] == 'admin')

    if not (is_farmer or is_buyer or is_admin):
        conn.close()
        if is_json:
            return jsonify({'error': 'Unauthorized action on this order'}), 403
        flash("Unauthorized action on this order.", "danger")
        return redirect(url_for('index'))

    # Only buyer, farmer or admin can Cancel
    if new_status == 'Cancelled' and not (is_buyer or is_admin or is_farmer):
        conn.close()
        if is_json:
            return jsonify({'error': 'Only buyer or farmer can cancel this request'}), 403
        flash("Only the buyer or admin can cancel this request.", "danger")
        return redirect(request.referrer or url_for('index'))

    # Handle completion & delivery inventory updates
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if new_status in ['Completed', 'Delivered'] and order['status'] not in ['Completed', 'Delivered']:
        # Deduct ordered quantity from listing
        req_qty = float(order['requested_quantity'] or 0.0)
        curr_stock = float(order['current_stock'] or 0.0)
        new_qty = max(0.0, curr_stock - req_qty)
        new_listing_status = 'Sold' if new_qty <= 0 else 'Available'
        
        cursor.execute("""
            UPDATE listings SET quantity = ?, status = ?, rescued_from_waste = 1, updated_at = ?
            WHERE id = ?
        """, (new_qty, new_listing_status, now_str, order['listing_id']))

        # Low stock notification to farmer (Section 3)
        if new_qty > 0 and (new_qty <= 50.0 or (curr_stock > 0 and (new_qty / curr_stock) <= 0.20)):
            create_notification(
                order['farmer_id'],
                f"⚠️ Low Stock Alert: {order['crop_name']}",
                f"Remaining stock for {order['crop_name']} is down to {new_qty:.0f} {order['unit']}.",
                "alert",
                url_for('farmer_dashboard')
            )
        elif new_qty <= 0:
            create_notification(
                order['farmer_id'],
                f"🎉 Produce Sold Out: {order['crop_name']}",
                f"All {order['crop_name']} stock has been successfully cleared and marked Sold.",
                "info",
                url_for('farmer_dashboard')
            )

    conn.commit()
    conn.close()

    # Append to status timeline and update status in database
    update_order_lifecycle(actual_order_id, new_status, note=status_note or f"Order marked as {new_status}")

    # Send Notification to counterpart
    target_user_id = order['buyer_id'] if is_farmer else order['farmer_id']
    if new_status in ['Order Accepted', 'Accepted']:
        notif_title = f"✅ Order #{actual_order_id} Accepted"
        status_msg = f"Farmer {order['farmer_name']} confirmed your order for {order['crop_name']} ({order['requested_quantity']} {order['unit']})."
    elif new_status in ['Order Rejected', 'Rejected', 'Declined']:
        notif_title = f"❌ Order #{actual_order_id} Declined"
        status_msg = f"Farmer was unable to accept order #{actual_order_id} for {order['crop_name']}."
    elif new_status in ['Processing', 'Packed', 'Ready for Pickup', 'Ready for Collection']:
        notif_title = f"📦 Order #{actual_order_id} Packed & Ready"
        status_msg = f"Your order #{actual_order_id} ({order['crop_name']}) has been crated and is ready for pickup/dispatch."
    elif new_status in ['Out for Delivery', 'Shipped']:
        notif_title = f"🚚 Order #{actual_order_id} Out for Delivery"
        status_msg = f"Your produce #{actual_order_id} is in transit! Follow the delivery route live."
    elif new_status in ['Delivered', 'Completed']:
        notif_title = f"🌱 Order #{actual_order_id} Delivered & Rescued"
        status_msg = f"Order #{actual_order_id} ({order['crop_name']}) has been delivered and recorded in platform waste prevention stats."
    elif new_status == 'Cancelled':
        notif_title = f"🚫 Order #{actual_order_id} Cancelled"
        status_msg = f"Order #{actual_order_id} for {order['crop_name']} has been cancelled."
    else:
        notif_title = f"Order #{actual_order_id} Update: {new_status}"
        status_msg = f"Order #{actual_order_id} for {order['crop_name']} is now: {new_status}."

    create_notification(
        target_user_id,
        notif_title,
        status_msg,
        "status_change",
        url_for('buyer_dashboard') if is_farmer else url_for('farmer_dashboard')
    )

    log_activity("Order Status Updated", f"Order #{actual_order_id} ({order['crop_name']}) status changed to {new_status} by {g.user['email']}")

    if is_json:
        return jsonify({
            'success': True,
            'order_id': actual_order_id,
            'new_status': new_status,
            'message': f"Order #{actual_order_id} marked as '{new_status}'."
        })

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

    user_keys = g.user.keys()
    default_btype = g.user['user_type'] if 'user_type' in user_keys and g.user['user_type'] else 'Supermarkets'
    default_loc = g.user['location'] if 'location' in user_keys and g.user['location'] else ''

    crop_name = request.form.get('crop_name', '').strip()
    category = request.form.get('category', 'Vegetables').strip()
    business_type = request.form.get('business_type', default_btype).strip()
    required_quantity = request.form.get('required_quantity', '').strip()
    unit = request.form.get('unit', 'kg').strip()
    target_price = request.form.get('target_price', '').strip()
    village_town = request.form.get('village_town', default_loc).strip()
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
def analytics_view():
    """
    Role-aware & Public Waste Reduction Analytics:
    - Guests/Visitors: Public platform waste reduction statistics without login barrier
    - Farmers: Farmer-specific produce waste metrics + platform benchmarks
    - Buyers: Buyer-specific purchase & rescued produce contribution + platform benchmarks
    - Admins: Complete platform metrics & management KPIs
    """
    timeframe = request.args.get('timeframe', 'all') # 'all', 'month', 'week'
    conn = get_db()
    cursor = conn.cursor()

    user_role = g.user['role'] if g.user else 'guest'
    is_farmer = (user_role == 'farmer')
    is_buyer = (user_role == 'buyer')
    is_admin = (user_role == 'admin')

    # Time filter clause
    time_clause = ""
    if timeframe == 'month':
        time_clause = " AND (julianday('now') - julianday(created_at)) <= 30"
    elif timeframe == 'week':
        time_clause = " AND (julianday('now') - julianday(created_at)) <= 7"

    # ==========================================
    # 1. Platform-Wide Baseline Aggregates
    # ==========================================
    cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings WHERE 1=1 {time_clause}")
    total_qty_listed = cursor.fetchone()[0]

    cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings WHERE status = 'Available' {time_clause}")
    available_qty = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0),
               COALESCE(SUM(e.requested_quantity), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.status IN ('Completed', 'Delivered')
    """)
    completed_orders_data = cursor.fetchone()
    completed_orders_count = completed_orders_data[0]
    total_sales_revenue = completed_orders_data[1]
    total_qty_sold = completed_orders_data[2]

    cursor.execute(f"""
        SELECT COALESCE(SUM(quantity), 0) FROM listings 
        WHERE (status = 'Sold' OR rescued_from_waste = 1) {time_clause}
    """)
    confirmed_rescued_kg = cursor.fetchone()[0]
    if confirmed_rescued_kg == 0 and total_qty_sold > 0:
        confirmed_rescued_kg = total_qty_sold

    cursor.execute(f"""
        SELECT category, COUNT(*) as count, COALESCE(SUM(quantity), 0) as total_kg
        FROM listings WHERE 1=1 {time_clause}
        GROUP BY category
    """)
    category_breakdown = cursor.fetchall()

    cursor.execute(f"""
        SELECT crop_name, category, COALESCE(SUM(quantity), 0) as total_kg,
               COALESCE(SUM(quantity * price_per_unit), 0) as est_value
        FROM listings WHERE 1=1 {time_clause}
        GROUP BY crop_name, category
        ORDER BY total_kg DESC LIMIT 6
    """)
    top_crops = cursor.fetchall()

    # ==========================================
    # 2. Role-Specific Metric Calculations
    # ==========================================
    farmer_metrics = None
    buyer_metrics = None
    admin_metrics = None

    if is_farmer:
        f_id = g.user['id']
        cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings WHERE farmer_id = ? {time_clause}", (f_id,))
        f_listed = cursor.fetchone()[0]

        cursor.execute(f"SELECT COALESCE(SUM(quantity), 0) FROM listings WHERE farmer_id = ? AND status = 'Available' {time_clause}", (f_id,))
        f_avail = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*), COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0),
                   COALESCE(SUM(e.requested_quantity), 0)
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE l.farmer_id = ? AND e.status IN ('Completed', 'Delivered')
        """, (f_id,))
        f_sales = cursor.fetchone()
        f_orders_count = f_sales[0]
        f_revenue = f_sales[1]
        f_sold = f_sales[2]

        f_waste_pct = (f_sold / f_listed * 100) if f_listed > 0 else 0.0

        farmer_metrics = {
            'total_listed': f_listed,
            'total_sold': f_sold,
            'remaining_stock': f_avail,
            'total_earnings': f_revenue,
            'rescued_kg': f_sold,
            'waste_reduction_pct': f_waste_pct,
            'orders_count': f_orders_count
        }

    elif is_buyer:
        b_id = g.user['id']
        b_email = g.user['email'] if (g.user and 'email' in g.user.keys()) else ''
        cursor.execute("""
            SELECT COUNT(*),
                   COALESCE(SUM(e.requested_quantity), 0),
                   COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0)
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE (e.buyer_id = ? OR e.buyer_email = ?)
              AND e.status IN ('Completed', 'Delivered', 'Paid', 'Accepted', 'Order Accepted', 'Processing', 'Packed', 'Ready for Pickup', 'Out for Delivery')
        """, (b_id, b_email))
        b_data = cursor.fetchone()
        b_orders = b_data[0]
        b_purchased_qty = b_data[1]
        b_spent = b_data[2]

        cursor.execute("""
            SELECT COALESCE(SUM(e.requested_quantity), 0)
            FROM enquiries e
            WHERE (e.buyer_id = ? OR e.buyer_email = ?)
              AND e.status IN ('Completed', 'Delivered')
        """, (b_id, b_email))
        b_rescued = cursor.fetchone()[0]

        # Estimated savings vs market prices (~15% below mandi markups)
        b_saved = b_spent * 0.15

        buyer_metrics = {
            'orders_count': b_orders,
            'purchased_qty': b_purchased_qty,
            'total_spending': b_spent,
            'rescued_kg': b_rescued,
            'money_saved': b_saved
        }

    elif is_admin:
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'farmer' AND is_active = 1")
        adm_farmers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer' AND is_active = 1")
        adm_buyers = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM listings")
        adm_listings = cursor.fetchone()[0]

        admin_metrics = {
            'total_farmers': adm_farmers,
            'total_buyers': adm_buyers,
            'total_listings': adm_listings,
            'completed_orders': completed_orders_count,
            'total_rescued_kg': confirmed_rescued_kg,
            'platform_revenue': total_sales_revenue
        }

    conn.close()

    # Environmental impact calculations based on FAO agri-waste benchmarks:
    # ~1.9 kg CO2e prevented per kg agricultural produce rescued from landfill decomposition
    # ~230 liters embedded water conserved per kg horticultural produce
    co2e_prevented = confirmed_rescued_kg * 1.9
    water_saved_liters = confirmed_rescued_kg * 230

    return render_template(
        'analytics.html',
        timeframe=timeframe,
        total_qty_listed=total_qty_listed,
        available_qty=available_qty,
        total_qty_sold=total_qty_sold,
        completed_orders_count=completed_orders_count,
        total_sales_revenue=total_sales_revenue,
        confirmed_rescued_kg=confirmed_rescued_kg,
        co2e_prevented=co2e_prevented,
        water_saved_liters=water_saved_liters,
        category_breakdown=category_breakdown,
        top_crops=top_crops,
        user_role=user_role,
        is_farmer=is_farmer,
        is_buyer=is_buyer,
        is_admin=is_admin,
        farmer_metrics=farmer_metrics,
        buyer_metrics=buyer_metrics,
        admin_metrics=admin_metrics
    )

# ==========================================
# Role-Specific Dashboards
# ==========================================

@app.route('/farmer/dashboard')
@login_required
@role_required(['farmer', 'admin'])
def farmer_dashboard():
    """
    Farmer Dashboard AI 2.0 with real calculated metrics:
    1. Total Products Listed
    2. Available Produce Quantity (kg)
    3. Pending Orders
    4. Completed Sales
    5. Produce at Risk (kg)
    6. Total Sales Revenue (₹)
    Plus AI Freshness Queue, Price Suggestions, Matching Buyers, and Waste Impact.
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
        WHERE l.farmer_id = ? AND e.status IN ('Completed', 'Delivered')
    """, (farmer_id,))
    completed_sales_count = cursor.fetchone()[0]

    # 5. Produce at Risk (kg)
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) FROM listings 
        WHERE farmer_id = ? AND status = 'Available' 
        AND ((julianday('now') - julianday(created_at)) >= 3 OR urgency_level = 'Urgent Sale' OR freshness_grade = 'Urgent')
    """, (farmer_id,))
    produce_at_risk_qty = cursor.fetchone()[0]

    # 6. Total Sales Revenue (₹)
    cursor.execute("""
        SELECT COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status IN ('Completed', 'Delivered')
    """, (farmer_id,))
    total_sales_revenue = cursor.fetchone()[0]

    # Pending Payments (Accepted / Packed / Shipped awaiting settlement)
    cursor.execute("""
        SELECT COALESCE(SUM(COALESCE(e.total_price, e.requested_quantity * l.price_per_unit)), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status IN ('Accepted', 'Packed', 'Shipped', 'Ready for Collection')
    """, (farmer_id,))
    pending_payments = cursor.fetchone()[0]

    # Farmer's listings
    cursor.execute("""
        SELECT * FROM listings 
        WHERE farmer_id = ? 
        ORDER BY created_at DESC
    """, (farmer_id,))
    my_listings = cursor.fetchall()

    # Enquiries / Orders received for farmer's listings
    cursor.execute("""
        SELECT e.*, l.crop_name, l.unit, l.price_per_unit, l.status as listing_status, l.photo
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ?
        ORDER BY e.created_at DESC
    """, (farmer_id,))
    received_orders = cursor.fetchall()

    # Attention & Status counts
    attention_count = sum(1 for item in my_listings if is_needs_attention(item))
    active_count = sum(1 for item in my_listings if item['status'] == 'Available')
    sold_count = sum(1 for item in my_listings if item['status'] == 'Sold')

    # Unsold Produce Value at Risk
    unsold_produce_value = sum(
        (float(item['quantity']) * float(item['price_per_unit']))
        for item in my_listings if item['status'] == 'Available'
    )
    estimated_profit = round(total_sales_revenue * 0.40, 2)

    # Food Waste Reduction Impact for this farmer
    cursor.execute("""
        SELECT COALESCE(SUM(e.requested_quantity), 0)
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ? AND e.status IN ('Completed', 'Delivered')
    """, (farmer_id,))
    rescued_produce_kg = cursor.fetchone()[0]
    co2_saved_kg = round(rescued_produce_kg * 1.9, 1)
    water_saved_liters = int(rescued_produce_kg * 250)

    # AI Freshness Prediction & Priority Clearance Queue
    freshness_queue = []
    recommended_buyers = []
    seen_buyer_ids = set()

    for item in my_listings:
        if item['status'] == 'Available':
            f_eval = predict_freshness(
                item['crop_name'],
                item['harvest_date'],
                item['quantity'],
                item['unit'],
                item['storage_condition'] if 'storage_condition' in item.keys() else 'Ambient / Room Temperature'
            )
            price_eval = recommend_smart_price(
                item['crop_name'],
                item['quantity'],
                f_eval['freshness_grade'],
                location=item['district'],
                current_price=item['price_per_unit'],
                db_conn=conn
            )
            freshness_queue.append({
                'listing': item,
                'freshness': f_eval,
                'price_rec': price_eval
            })

            # Match buyers for this listing
            item_buyers = match_smart_buyers(dict(item), top_n=3, db_conn=conn)
            for b in item_buyers:
                if b['buyer_id'] not in seen_buyer_ids:
                    b['for_crop'] = item['crop_name']
                    b['for_listing_id'] = item['id']
                    recommended_buyers.append(b)
                    seen_buyer_ids.add(b['buyer_id'])

    # Sort clearance queue: Priority Rank 1 (Urgent) first, then lowest remaining hours
    freshness_queue.sort(key=lambda x: (x['freshness']['priority_rank'], x['freshness']['remaining_hours']))
    recommended_buyers.sort(key=lambda b: b['match_percentage'], reverse=True)

    conn.close()

    # Farmer payments and transaction history
    farmer_payments = get_farmer_payments(farmer_id)
    farmer_weather_alerts = get_weather_alerts()
    paid_orders_revenue = sum(float(p['amount']) for p in farmer_payments if p['payment_status'] == 'Paid')
    cod_pending_revenue = sum(float(p['amount']) for p in farmer_payments if p['payment_status'] == 'COD Pending')

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
        pending_payments=pending_payments,
        unsold_produce_value=unsold_produce_value,
        estimated_profit=estimated_profit,
        attention_count=attention_count,
        active_count=active_count,
        sold_count=sold_count,
        pending_enquiries_count=pending_orders_count,
        rescued_produce_kg=rescued_produce_kg,
        co2_saved_kg=co2_saved_kg,
        water_saved_liters=water_saved_liters,
        freshness_queue=freshness_queue,
        recommended_buyers=recommended_buyers[:6],
        payments=farmer_payments,
        weather_alerts=farmer_weather_alerts[:3],
        paid_orders_revenue=paid_orders_revenue,
        cod_pending_revenue=cod_pending_revenue
    )

@app.route('/buyer/dashboard')
@login_required
@role_required(['buyer', 'admin'])
def buyer_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Enquiries sent by this buyer
    cursor.execute("""
        SELECT e.*, l.farmer_id, l.crop_name, l.unit, l.price_per_unit, l.village_town, l.district, 
               l.farmer_name, l.farmer_phone, l.whatsapp_number, l.status as listing_status, l.photo,
               l.freshness_grade, l.quality_grade
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

    # Favorite Farmers
    my_favorites = get_buyer_favorites(g.user['id'])

    # Coordinates of this buyer
    b_lat, b_lng, b_dist = get_coordinates_for_location(g.user['location'])

    # Available Produce nearby with Haversine distance
    cursor.execute("""
        SELECT l.*, u.phone as farmer_user_phone
        FROM listings l
        JOIN users u ON l.farmer_id = u.id
        WHERE l.status = 'Available'
        ORDER BY l.created_at DESC
        LIMIT 25
    """)
    all_available = cursor.fetchall()

    nearby_produce = []
    for item in all_available:
        item_dict = dict(item)
        f_lat, f_lng, _ = get_coordinates_for_location(item['village_town'], item['district'])
        dist_info = calculate_haversine_distance(f_lat, f_lng, b_lat, b_lng)
        item_dict['distance_km'] = dist_info['distance_km']
        item_dict['transit_text'] = dist_info['transit_text']
        item_dict['is_favorited'] = is_farmer_favorited(g.user['id'], item['farmer_id'])
        nearby_produce.append(item_dict)

    nearby_produce.sort(key=lambda x: x['distance_km'])

    # AI Recommended Produce based on buyer business type
    user_type = (g.user['user_type'] or '').lower()
    recommended_produce = []
    for item in nearby_produce:
        crop_low = item['crop_name'].lower()
        if 'hotel' in user_type or 'restaurant' in user_type:
            if any(k in crop_low for k in ['tomato', 'shallot', 'onion', 'chilli', 'potato', 'rice', 'ginger', 'brinjal']):
                recommended_produce.append(item)
        elif 'supermarket' in user_type:
            if 'quality_grade' in item.keys() and item['quality_grade'] in ['Grade A', 'Grade B']:
                recommended_produce.append(item)
        elif 'processing' in user_type:
            if any(k in crop_low for k in ['tomato', 'mango', 'chilli', 'onion']):
                recommended_produce.append(item)
        else:
            recommended_produce.append(item)

    if not recommended_produce:
        recommended_produce = nearby_produce[:6]

    # Active Orders needing live tracking
    active_orders = [o for o in my_orders if o['status'] in ['Pending', 'Accepted', 'Packed', 'Shipped', 'Ready for Collection', 'Order Placed', 'Order Accepted', 'Processing', 'Ready for Pickup', 'Out for Delivery']]

    # Buyer payments and transaction history
    buyer_payments = get_buyer_payments(g.user['id'])

    # Calculated KPIs for Buyer Portal
    total_orders = len(my_orders)
    total_purchased_qty = sum(
        float(o['requested_quantity'] or 0.0)
        for o in my_orders
        if o['status'] in ['Completed', 'Delivered', 'Paid', 'Accepted', 'Order Accepted', 'Processing', 'Packed', 'Ready for Pickup', 'Out for Delivery', 'Shipped', 'Ready for Collection']
    )
    total_spending = sum(
        float(o['total_price'] or (float(o['requested_quantity'] or 0.0) * float(o['price_per_unit'] or 0.0)))
        for o in my_orders
        if o['status'] in ['Completed', 'Delivered', 'Paid']
    )
    buyer_rescued_kg = sum(
        float(o['requested_quantity'] or 0.0)
        for o in my_orders
        if o['status'] in ['Completed', 'Delivered']
    )

    conn.close()

    return render_template(
        'buyer_dashboard.html',
        orders=my_orders,
        enquiries=my_orders,  # backward compatibility
        requirements=my_requirements,
        my_favorites=my_favorites,
        nearby_produce=nearby_produce[:8],
        recommended_produce=recommended_produce[:6],
        active_orders=active_orders,
        payments=buyer_payments,
        total_orders=total_orders,
        total_purchased_qty=total_purchased_qty,
        total_spending=total_spending,
        buyer_rescued_kg=buyer_rescued_kg
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
        WHERE e.status IN ('Completed', 'Delivered')
    """)
    platform_revenue = cursor.fetchone()[0]

    # Total Rescued kg verified
    cursor.execute("""
        SELECT COALESCE(SUM(e.requested_quantity), 0)
        FROM enquiries e
        WHERE e.status IN ('Completed', 'Delivered')
    """)
    total_rescued_kg = cursor.fetchone()[0]

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

    # AI Demand Prediction data
    demand_summary = predict_market_demand(conn)

    # Payments & Transactions Audit
    admin_payments = get_admin_payments(limit=100)
    paid_payments_count = len([p for p in admin_payments if p['payment_status'] == 'Paid'])
    pending_payments_count = len([p for p in admin_payments if p['payment_status'] in ('Pending', 'COD Pending')])
    failed_payments_count = len([p for p in admin_payments if p['payment_status'] in ('Failed', 'Cancelled')])
    total_payment_volume = sum(float(p['amount']) for p in admin_payments if p['payment_status'] == 'Paid')
    refund_requests = [p for p in admin_payments if p['refund_status'] == 'Requested']

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
        total_rescued_kg=total_rescued_kg,
        demo_listings_count=demo_listings_count,
        users=all_users,
        listings=all_listings,
        enquiries=all_enquiries,
        logs=recent_logs,
        demand_summary=demand_summary,
        payments=admin_payments,
        paid_payments_count=paid_payments_count,
        pending_payments_count=pending_payments_count,
        failed_payments_count=failed_payments_count,
        total_payment_volume=total_payment_volume,
        refund_requests=refund_requests
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

# Convenience routes for direct navigation
@app.route('/my-orders')
@app.route('/my-enquiries')
def my_orders_enquiries():
    if not g.user:
        return redirect(url_for('login', next=request.path))
    user_role = g.user['role'] if 'role' in g.user.keys() else None
    if user_role == 'farmer':
        return redirect(url_for('farmer_dashboard') + '#enquiriesTable')
    elif user_role == 'buyer':
        return redirect(url_for('buyer_dashboard') + '#ordersTable')
    elif user_role == 'admin':
        return redirect(url_for('admin_dashboard') + '#enquiries-section')
    return redirect(url_for('index'))

@app.route('/add-listing')
def add_listing_redirect():
    return redirect(url_for('add_listing'))

# ==========================================
# Real-Time Payments & Checkout Workflows
# ==========================================

@app.route('/checkout/<int:order_id>')
@login_required
def checkout_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.crop_name, l.category, l.unit, l.price_per_unit, l.photo,
               l.village_town, l.district, l.harvest_date, l.farmer_name, l.farmer_id,
               l.quantity as listing_qty
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for('buyer_dashboard'))

    # Security check: only buyer or admin can checkout
    if g.user['role'] != 'admin' and order['buyer_id'] != g.user['id']:
        flash("Unauthorized access to checkout.", "danger")
        return redirect(url_for('buyer_dashboard'))

    available_stock = get_available_stock(order['listing_id'])
    subtotal = float(order['total_price'] or (order['requested_quantity'] * order['price_per_unit']))
    delivery_mode = 'delivery' if order['delivery_preference'] and 'Delivery' in order['delivery_preference'] else 'pickup'
    delivery_charges = float(order['delivery_charges'] or (60.0 if delivery_mode == 'delivery' else 0.0))
    total_amount = subtotal + delivery_charges

    return render_template(
        'checkout.html',
        order=order,
        listing=order,
        available_stock=available_stock,
        subtotal=subtotal,
        delivery_charges=delivery_charges,
        delivery_mode=delivery_mode,
        total_amount=total_amount
    )

@app.route('/checkout/direct/<int:listing_id>', methods=['GET', 'POST'])
@login_required
@role_required(['buyer', 'admin'])
def checkout_direct(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()
    if not listing:
        conn.close()
        flash("Produce listing not found.", "danger")
        return redirect(url_for('browse_listings'))

    available_stock = get_available_stock(listing_id)
    if available_stock <= 0:
        conn.close()
        flash("This produce is currently sold out.", "warning")
        return redirect(url_for('listing_detail', listing_id=listing_id))

    qty = float(request.values.get('quantity') or min(50.0, available_stock))
    if qty > available_stock:
        qty = available_stock

    subtotal = qty * float(listing['price_per_unit'])
    delivery_pref = request.values.get('delivery_preference', 'Agri-Logistics Delivery')
    delivery_charges = 60.0 if 'Delivery' in delivery_pref else 0.0
    delivery_addr = request.values.get('delivery_address', g.user['location'] or '')

    cursor.execute("""
        INSERT INTO enquiries (
            listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
            offered_price, requested_quantity, delivery_preference,
            total_price, delivery_charges, delivery_address, message,
            status, payment_status, payment_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', 'Unpaid', 'Online')
    """, (
        listing['id'], g.user['id'], g.user['name'], g.user['phone'], g.user['email'],
        listing['price_per_unit'], qty, delivery_pref,
        subtotal, delivery_charges, delivery_addr,
        f"Direct purchase initiated for {qty} {listing['unit']} of {listing['crop_name']}."
    ))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return redirect(url_for('checkout_order', order_id=order_id))

@app.route('/api/payment/create-order', methods=['POST'])
@login_required
def api_create_payment_order():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    if not order_id:
        return jsonify({'success': False, 'error': 'Missing order_id'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.price_per_unit, l.farmer_id, l.quantity as listing_qty
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    if g.user['role'] != 'admin' and order['buyer_id'] != g.user['id']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    avail = get_available_stock(order['listing_id'])
    if float(order['requested_quantity']) > avail:
        return jsonify({'success': False, 'error': f"Only {avail:.1f} kg available in stock"}), 400

    delivery_charges = float(data.get('delivery_charges', order['delivery_charges'] or 0))
    subtotal = float(order['total_price'] or (order['requested_quantity'] * order['price_per_unit']))
    total_amount = subtotal + delivery_charges

    rzp_res = create_razorpay_order(
        amount_in_rupees=total_amount,
        receipt_id=f"rec_ord_{order_id}",
        notes={'order_id': order_id, 'buyer_id': order['buyer_id']}
    )

    if not rzp_res['success']:
        return jsonify(rzp_res), 500

    rec_res = create_payment_record(
        order_id=order['id'],
        listing_id=order['listing_id'],
        buyer_id=order['buyer_id'],
        farmer_id=order['farmer_id'],
        amount=total_amount,
        subtotal=subtotal,
        delivery_charges=delivery_charges,
        payment_method='Online',
        razorpay_order_id=rzp_res['order_id']
    )

    return jsonify({
        'success': True,
        'razorpay_order_id': rzp_res['order_id'],
        'key_id': rzp_res['key_id'],
        'amount': rzp_res['amount'],
        'amount_rupees': total_amount,
        'currency': rzp_res['currency'],
        'transaction_id': rec_res.get('transaction_id'),
        'is_mock': rzp_res.get('is_mock', False)
    })

@app.route('/api/payment/verify', methods=['POST'])
@login_required
def api_verify_payment():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    transaction_id = data.get('transaction_id')
    rzp_order_id = data.get('razorpay_order_id')
    rzp_payment_id = data.get('razorpay_payment_id')
    rzp_signature = data.get('razorpay_signature')
    method = data.get('payment_method', 'Razorpay Online')

    if not rzp_order_id or not rzp_payment_id:
        return jsonify({'success': False, 'error': 'Missing payment credentials'}), 400

    is_valid, reason = verify_razorpay_signature(rzp_order_id, rzp_payment_id, rzp_signature)
    if not is_valid:
        return jsonify({'success': False, 'error': f"Signature verification failed: {reason}"}), 400

    success, txn_or_err = confirm_payment_record(
        transaction_id=transaction_id or rzp_order_id,
        razorpay_payment_id=rzp_payment_id,
        razorpay_signature=rzp_signature,
        payment_method=method
    )

    if not success:
        return jsonify({'success': False, 'error': txn_or_err}), 500

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.crop_name, l.farmer_id
        FROM enquiries e JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    ord_info = cursor.fetchone()
    conn.close()

    if ord_info:
        create_notification(
            user_id=ord_info['farmer_id'],
            title="💰 Payment Confirmed for Your Produce!",
            message=f"Buyer {ord_info['buyer_name']} has completed payment for {ord_info['requested_quantity']} kg of {ord_info['crop_name']}. Please pack for handover.",
            notif_type='order',
            link=url_for('farmer_dashboard')
        )
        create_notification(
            user_id=ord_info['buyer_id'],
            title="✓ Payment Successful & Order Confirmed",
            message=f"Your payment for {ord_info['requested_quantity']} kg of {ord_info['crop_name']} has been cleared. Invoice #{txn_or_err} generated.",
            notif_type='order',
            link=url_for('view_invoice', order_id=order_id)
        )

    return jsonify({
        'success': True,
        'transaction_id': txn_or_err,
        'redirect_url': url_for('view_invoice', order_id=order_id)
    })

@app.route('/api/payment/cod', methods=['POST'])
@login_required
def api_confirm_cod():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    delivery_charges = float(data.get('delivery_charges', 0))
    delivery_address = data.get('delivery_address')

    if not order_id:
        return jsonify({'success': False, 'error': 'Missing order_id'}), 400

    if delivery_address:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE enquiries SET delivery_address = ? WHERE id = ?", (delivery_address, order_id))
        conn.commit()
        conn.close()

    success, txn_or_err = confirm_cod_order(order_id, delivery_charges)
    if not success:
        return jsonify({'success': False, 'error': txn_or_err}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT e.*, l.crop_name, l.farmer_id
        FROM enquiries e JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (order_id,))
    ord_info = cursor.fetchone()
    conn.close()

    if ord_info:
        create_notification(
            user_id=ord_info['farmer_id'],
            title="📦 New Cash on Delivery (COD) Order Placed",
            message=f"Buyer {ord_info['buyer_name']} has placed a COD order for {ord_info['requested_quantity']} kg of {ord_info['crop_name']}. Collect cash upon delivery.",
            notif_type='order',
            link=url_for('farmer_dashboard')
        )
        create_notification(
            user_id=ord_info['buyer_id'],
            title="✓ COD Order Confirmed",
            message=f"Your COD order for {ord_info['crop_name']} is confirmed. Pay cash upon physical handover.",
            notif_type='order',
            link=url_for('view_invoice', order_id=order_id)
        )

    return jsonify({
        'success': True,
        'transaction_id': txn_or_err,
        'redirect_url': url_for('view_invoice', order_id=order_id)
    })

@app.route('/order/<int:order_id>/invoice')
@login_required
def view_invoice(order_id):
    payment = get_payment_by_order_id(order_id)
    if not payment:
        flash("No invoice or payment record found for this order.", "warning")
        return redirect(url_for('buyer_dashboard'))

    if g.user['role'] != 'admin' and g.user['id'] not in (payment['buyer_id'], payment['farmer_id']):
        flash("Unauthorized invoice access.", "danger")
        return redirect(url_for('index'))

    return render_template('invoice.html', payment=payment)

@app.route('/api/payment/refund-request', methods=['POST'])
@login_required
def api_request_refund():
    data = request.get_json() or {}
    payment_id = data.get('payment_id')
    if not payment_id and data.get('order_id'):
        p_row = get_payment_by_order_id(data.get('order_id'))
        if p_row:
            payment_id = p_row['id']
    reason = data.get('reason', 'Quality deviation or delivery failure')

    if not payment_id:
        return jsonify({'success': False, 'error': 'Missing payment_id'}), 400

    success, msg = request_payment_refund(payment_id, g.user['id'], reason)
    if not success:
        return jsonify({'success': False, 'error': msg}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE role = 'admin'")
    admins = cursor.fetchall()
    conn.close()
    for a in admins:
        create_notification(
            user_id=a['id'],
            title="⚠️ Refund Request Submitted",
            message=f"Buyer #{g.user['name']} has requested a refund for Payment #{payment_id}. Reason: {reason}",
            notif_type='alert',
            link=url_for('admin_dashboard') + '#payments-section'
        )

    return jsonify({'success': True, 'message': msg})

@app.route('/api/admin/refund/<int:payment_id>', methods=['POST'])
@login_required
@role_required('admin')
def api_admin_process_refund(payment_id):
    if request.is_json:
        data = request.get_json(silent=True) or {}
    else:
        data = request.form or {}

    action = (data.get('decision') or data.get('action') or 'Approved').strip()
    if action.lower() in ['approve', 'approved']:
        decision = 'Approved'
    else:
        decision = 'Rejected'
    notes = data.get('notes', '')

    success, msg = process_admin_refund(payment_id, decision, notes)
    if not request.is_json:
        if success:
            flash(f"Refund {decision.lower()} successfully.", "success")
        else:
            flash(f"Error processing refund: {msg}", "danger")
        return redirect(url_for('admin_dashboard'))

    if not success:
        return jsonify({'success': False, 'error': msg}), 400

    return jsonify({'success': True, 'message': msg})

# ==========================================
# Live Market Prices & Interactive Map Routes
# ==========================================

@app.route('/market-prices')
def live_market_prices():
    crop_name = request.args.get('crop_name', '').strip()
    district = request.args.get('district', '').strip()
    prices = get_market_prices(crop_name=crop_name, district=district, limit=50)

    districts = sorted(list(set(TN_DISTRICT_COORDINATES.keys())))

    return render_template(
        'market_prices.html',
        market_prices=prices,
        districts=districts
    )

@app.route('/live-map')
def live_map_view():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT l.id, l.farmer_id, l.crop_name, l.category, l.quantity, l.unit,
               l.price_per_unit, l.urgency_level, l.village_town, l.district,
               l.farmer_name
        FROM listings l
        WHERE l.status = 'Available'
        ORDER BY l.created_at DESC
        LIMIT 60
    """)
    listings = cursor.fetchall()

    farmer_markers = []
    for item in listings:
        f_dict = dict(item)
        lat, lng, _ = get_coordinates_for_location(item['village_town'], item['district'])
        f_dict['lat'] = lat
        f_dict['lng'] = lng
        farmer_markers.append(f_dict)

    cursor.execute("""
        SELECT u.id, u.name, u.role, u.location, u.district, u.user_type,
               (SELECT crop_name FROM buyer_requirements WHERE buyer_id = u.id AND status = 'Active' LIMIT 1) AS requirement_crop,
               (SELECT required_quantity || ' ' || unit FROM buyer_requirements WHERE buyer_id = u.id AND status = 'Active' LIMIT 1) AS requirement_qty
        FROM users u
        WHERE u.role = 'buyer' AND u.is_active = 1
        LIMIT 40
    """)
    buyers = cursor.fetchall()
    conn.close()

    buyer_markers = []
    for b in buyers:
        b_dict = dict(b)
        b_lat, b_lng, _ = get_coordinates_for_location(b['location'], b['district'])
        b_dict['lat'] = b_lat
        b_dict['lng'] = b_lng
        buyer_markers.append(b_dict)

    map_data = {
        'farmers': farmer_markers,
        'buyers': buyer_markers
    }

    districts = sorted(list(set(TN_DISTRICT_COORDINATES.keys())))

    return render_template(
        'live_map.html',
        map_data_json=json.dumps(map_data),
        districts=districts
    )

# ==========================================
# Farmer & Buyer Live Chat Routes
# ==========================================

@app.route('/chat')
@app.route('/chat/<int:recipient_id>')
@login_required
def chat_conversation(recipient_id=None):
    threads = get_user_chat_threads(g.user['id'])
    recipient = None

    if recipient_id:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, role, phone, email, location FROM users WHERE id = ?", (recipient_id,))
        recipient = cursor.fetchone()
        conn.close()

    order_id = request.args.get('order_id', type=int)
    listing_id = request.args.get('listing_id', type=int)

    return render_template(
        'chat.html',
        threads=threads,
        recipient=recipient,
        order_id=order_id,
        listing_id=listing_id
    )

@app.route('/api/chat/messages/<int:recipient_id>')
@login_required
def api_chat_messages(recipient_id):
    order_id = request.args.get('order_id', type=int)
    msgs = get_conversation_messages(g.user['id'], recipient_id, order_id=order_id, limit=60)
    msg_list = [dict(m) for m in msgs]
    return jsonify({'success': True, 'messages': msg_list})

@app.route('/api/chat/upload-image', methods=['POST'])
@login_required
def api_chat_upload_image():
    if 'photo' not in request.files:
        return jsonify({'success': False, 'error': 'No image file uploaded'}), 400
    file = request.files['photo']
    saved_filename = save_uploaded_image(file)
    if not saved_filename:
        return jsonify({'success': False, 'error': 'Invalid image format or size (must be under 3MB PNG, JPG, WEBP)'}), 400
    return jsonify({
        'success': True,
        'filename': saved_filename,
        'url': url_for('static', filename='uploads/' + saved_filename)
    })

@app.route('/api/chat/send', methods=['POST'])
@login_required
def api_chat_send():
    data = request.get_json() or {}
    receiver_id = data.get('receiver_id') or data.get('recipient_id')
    message = (data.get('message') or data.get('message_text') or '').strip()
    image_filename = data.get('image_filename')
    order_id = data.get('order_id')
    listing_id = data.get('listing_id')
    offer_price = data.get('offer_price')
    offer_qty = data.get('offer_quantity')

    if not receiver_id or (not message and not image_filename):
        return jsonify({'success': False, 'error': 'Missing receiver or message content'}), 400

    if not message and image_filename:
        message = '📷 Attached Produce Photo'

    res = save_chat_message(
        sender_id=g.user['id'],
        receiver_id=receiver_id,
        message=message,
        order_id=order_id,
        listing_id=listing_id,
        image_filename=image_filename,
        offer_price=offer_price,
        offer_quantity=offer_qty
    )

    if res['success']:
        create_notification(
            user_id=receiver_id,
            title=f"💬 New message from {g.user['name']}",
            message=message[:80] + ("..." if len(message) > 80 else ""),
            notif_type='info',
            link=url_for('chat_conversation', recipient_id=g.user['id'])
        )

    return jsonify(res)

# ==========================================
# Agro-Weather Alerts & Traceability QR
# ==========================================

@app.route('/weather-alerts')
def weather_alerts_view():
    alerts = get_weather_alerts()
    return render_template('weather_alerts.html', weather_alerts=alerts)

@app.route('/trace/<int:listing_id>', endpoint='trace_produce')
@app.route('/trace/<int:listing_id>', endpoint='trace_passport')
def trace_passport(listing_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT l.*, u.name as grower_name, u.phone as grower_phone, u.location as grower_loc
        FROM listings l
        JOIN users u ON l.farmer_id = u.id
        WHERE l.id = ?
    """, (listing_id,))
    listing = cursor.fetchone()
    conn.close()

    if not listing:
        flash("Traceability certificate not found.", "warning")
        return redirect(url_for('browse_listings'))

    return render_template('trace_passport.html', listing=listing)

@app.route('/qr/<int:listing_id>')
def generate_qr_code(listing_id):
    trace_url = url_for('trace_passport', listing_id=listing_id, _external=True)
    img_bytes = generate_qr_bytes(trace_url)
    return send_file(io.BytesIO(img_bytes), mimetype='image/png')

@app.route('/api/notifications/poll')
@login_required
def api_notifications_poll():
    unread_count = get_unread_notifications_count(g.user['id'])
    notifs = get_user_notifications(g.user['id'], limit=5)
    return jsonify({
        'unread_count': unread_count,
        'notifications': [dict(n) for n in notifs]
    })

@app.route('/api/order/<int:order_id>/status', methods=['POST'])
@login_required
def api_update_order_status(order_id):
    data = request.get_json() or {}
    new_status = data.get('status')
    note = data.get('note')

    if not new_status:
        return jsonify({'success': False, 'error': 'Missing status'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT e.*, l.farmer_id, l.crop_name FROM enquiries e JOIN listings l ON e.listing_id = l.id WHERE e.id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()

    if not order:
        return jsonify({'success': False, 'error': 'Order not found'}), 404

    # Farmer or admin permission
    if g.user['role'] != 'admin' and order['farmer_id'] != g.user['id']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    success, msg = update_order_lifecycle(order_id, new_status, note=note)
    if not success:
        return jsonify({'success': False, 'error': msg}), 500

    # If status is delivered on COD, mark payment as Paid
    if new_status in ('Delivered', 'Completed'):
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE payments SET payment_status = 'Paid', payout_status = 'Processing' WHERE order_id = ? AND payment_status = 'COD Pending'", (order_id,))
        conn.commit()
        conn.close()

    create_notification(
        user_id=order['buyer_id'],
        title=f"🚚 Order Status Updated: {new_status}",
        message=f"Your order for {order['requested_quantity']} kg of {order['crop_name']} is now: {new_status}.",
        notif_type='order',
        link=url_for('buyer_dashboard') + '#ordersTable'
    )

    return jsonify({'success': True, 'message': f"Order status updated to {new_status}"})

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
