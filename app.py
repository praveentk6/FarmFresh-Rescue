import os
import sqlite3
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, g, abort, jsonify
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image

from database import get_db, init_db, seed_db

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_and_save_image(file_storage):
    """Safely validate, resize, and save an uploaded image file."""
    if not file_storage or file_storage.filename == '':
        return None
    
    if not allowed_file(file_storage.filename):
        return None

    try:
        # Secure filename and add timestamp prefix to avoid name collisions
        ext = file_storage.filename.rsplit('.', 1)[1].lower()
        unique_name = f"produce_{int(datetime.now().timestamp())}_{secure_filename(file_storage.filename)}"
        target_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)

        # Open with PIL to verify integrity
        img = Image.open(file_storage)
        img.verify()  # verify that it is, in fact, an image

        # Re-open for resizing since verify closes some pointers
        file_storage.seek(0)
        img = Image.open(file_storage)

        # Convert RGBA/P to RGB if JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Resize large images down to max width 1200px preserving aspect ratio
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
    cursor.execute("SELECT id, name, email, role, phone, location, pin_code, user_type FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

@app.before_request
def load_logged_in_user():
    g.user = get_current_user()

def calculate_listing_age(created_at_val):
    """Calculate days since listing was posted."""
    if not created_at_val:
        return 0, "Today"
    try:
        if isinstance(created_at_val, str):
            # Parse 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD'
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

def is_needs_attention(listing):
    """
    Returns True if listing is available and has been unsold for 3 or more days.
    """
    if listing['status'] != 'Available':
        return False
    days, _ = calculate_listing_age(listing['created_at'])
    return days >= 3

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
    return {
        'current_user': g.user,
        'calculate_listing_age': calculate_listing_age,
        'is_needs_attention': is_needs_attention,
        'tn_districts': TN_DISTRICTS,
        'crop_categories': CROP_CATEGORIES,
        'crop_units': CROP_UNITS,
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
# Public Routes
# ==========================================

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()

    # Statistics for impact counters
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    available_count = cursor.fetchone()[0]

    # Needs attention count (Available and >= 3 days old)
    cursor.execute("""
        SELECT COUNT(*) FROM listings 
        WHERE status = 'Available' 
        AND (julianday('now') - julianday(created_at)) >= 3
    """)
    needs_attention_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Sold'")
    rescued_sold_count = cursor.fetchone()[0]

    # High-priority "Needs Attention" produce (urgency rescue carousel / spotlight)
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        AND (julianday('now') - julianday(created_at)) >= 3
        ORDER BY created_at ASC 
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
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    min_qty = request.args.get('min_qty', '').strip()
    urgency = request.args.get('urgency', '').strip() # 'urgent_only'
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

    # Quantity filter
    if min_qty:
        try:
            query += " AND quantity >= ?"
            params.append(float(min_qty))
        except ValueError:
            pass

    # Urgency filter: only listings unsold 3+ days
    if urgency == 'urgent_only':
        query += " AND status = 'Available' AND (julianday('now') - julianday(created_at)) >= 3"

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
        # Prioritize 3+ days old listings first to prevent waste, then newest
        query += " ORDER BY (CASE WHEN (julianday('now') - julianday(created_at)) >= 3 AND status='Available' THEN 0 ELSE 1 END), created_at ASC"
    else:
        query += " ORDER BY created_at DESC"

    cursor.execute(query, params)
    listings = cursor.fetchall()

    # Pre-calculate counts for quick tabs
    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    total_available = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available' AND (julianday('now') - julianday(created_at)) >= 3")
    total_urgent = cursor.fetchone()[0]

    conn.close()

    return render_template(
        'listings.html',
        listings=listings,
        search_q=search_q,
        category=category,
        district=district,
        min_price=min_price,
        max_price=max_price,
        min_qty=min_qty,
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

    # Calculate days since harvest
    days_since_harvest = None
    try:
        h_date = datetime.strptime(listing['harvest_date'], '%Y-%m-%d').date()
        days_since_harvest = (date.today() - h_date).days
    except Exception:
        pass

    # Similar produce recommendations in the same category or nearby
    cursor.execute("""
        SELECT * FROM listings 
        WHERE category = ? AND id != ? AND status = 'Available'
        ORDER BY created_at DESC LIMIT 3
    """, (listing['category'], listing_id))
    related_listings = cursor.fetchall()

    conn.close()

    days_old, age_text = calculate_listing_age(listing['created_at'])
    needs_attn = is_needs_attention(listing)

    return render_template(
        'listing_detail.html',
        listing=listing,
        days_old=days_old,
        age_text=age_text,
        days_since_harvest=days_since_harvest,
        needs_attn=needs_attn,
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

        # Input Validations
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

        # Check existing email
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            flash("An account with this email address already exists. Please login instead.", "warning")
            return redirect(url_for('login'))

        # Insert new user
        password_hash = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, password_hash, role, phone, location, pin_code, user_type))
        conn.commit()

        user_id = cursor.lastrowid
        conn.close()

        log_activity("User Registered", f"New {role} registered: {name} ({email})", email)

        # Automatically log in the registered user
        session['user_id'] = user_id
        session['user_name'] = name
        session['user_role'] = role

        flash(f"Welcome to FarmFresh Rescue, {name}! Your {role.capitalize()} account has been created successfully.", "success")
        
        if role == 'farmer':
            return redirect(url_for('farmer_dashboard'))
        elif role == 'buyer':
            return redirect(url_for('browse_listings'))
        elif role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('index'))

    # Pre-select role if passed in query param
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
                return redirect(url_for('browse_listings'))
            elif user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        else:
            flash("Invalid email or password. Please check your credentials.", "danger")
            return render_template('login.html', email=email)

    return render_template('login.html')

@app.route('/logout')
def logout():
    user_name = session.get('user_name', 'User')
    session.clear()
    flash(f"You have been successfully logged out. Have a productive day!", "info")
    return redirect(url_for('index'))

# ==========================================
# Farmer Listings CRUD Routes
# ==========================================

@app.route('/listing/add', methods=['GET', 'POST'])
@login_required
def add_listing():
    # Only farmers or admin can add produce
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
        village_town = request.form.get('village_town', '').strip()
        district = request.form.get('district', '').strip()
        pin_code = request.form.get('pin_code', '').strip()
        farmer_name = request.form.get('farmer_name', g.user['name']).strip()
        farmer_phone = request.form.get('farmer_phone', g.user['phone']).strip()
        whatsapp_number = request.form.get('whatsapp_number', farmer_phone).strip()
        description = request.form.get('description', '').strip()

        # Validation
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
            except ValueError:
                pass

        if not harvest_date:
            errors.append("Harvest date is required.")
        if not village_town or not district:
            errors.append("Village/Town and District location are required.")
        if not pin_code or len(pin_code) < 6:
            errors.append("A valid 6-digit postal PIN code is required.")
        if not farmer_phone:
            errors.append("Farmer contact phone number is required.")

        # Photo handling
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
                original_price, harvest_date, village_town, district, pin_code,
                farmer_name, farmer_phone, whatsapp_number, description, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', ?, ?)
        ''', (
            g.user['id'], crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, village_town, district, pin_code,
            farmer_name, farmer_phone, whatsapp_number, description,
            now_str, now_str
        ))
        conn.commit()
        new_listing_id = cursor.lastrowid
        conn.close()

        log_activity("Listing Added", f"Produce listed: {crop_name} ({qty_val} {unit}) at ₹{price_val}/{unit}")
        flash(f"Success! '{crop_name}' has been listed. Buyers nearby can now discover your harvest.", "success")
        return redirect(url_for('farmer_dashboard'))

    # Default today's date for harvest date
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

    # Verify ownership
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
        village_town = request.form.get('village_town', '').strip()
        district = request.form.get('district', '').strip()
        pin_code = request.form.get('pin_code', '').strip()
        farmer_name = request.form.get('farmer_name', '').strip()
        farmer_phone = request.form.get('farmer_phone', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'Available').strip()

        errors = []
        if not crop_name:
            errors.append("Produce name cannot be empty.")
        try:
            qty_val = float(quantity)
            if qty_val <= 0:
                errors.append("Available quantity must be greater than 0.")
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
        cursor.execute('''
            UPDATE listings SET
                crop_name = ?, category = ?, photo = ?, quantity = ?, unit = ?,
                price_per_unit = ?, original_price = ?, harvest_date = ?,
                village_town = ?, district = ?, pin_code = ?, farmer_name = ?,
                farmer_phone = ?, whatsapp_number = ?, description = ?, status = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            crop_name, category, photo_filename, qty_val, unit, price_val,
            orig_price_val, harvest_date, village_town, district, pin_code,
            farmer_name, farmer_phone, whatsapp_number, description, status,
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

    # Verify ownership or admin
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
    cursor.execute("UPDATE listings SET status = ?, updated_at = ? WHERE id = ?", 
                   (new_status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), listing_id))
    conn.commit()
    conn.close()

    log_activity("Status Toggled", f"Listing #{listing_id} ({listing['crop_name']}) status marked as {new_status}")
    flash(f"Listing '{listing['crop_name']}' is now marked as {new_status}!", "success")

    if request.referrer and 'admin' in request.referrer:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('farmer_dashboard'))

# ==========================================
# Buyer Enquiries Routes
# ==========================================

@app.route('/enquiry/submit', methods=['POST'])
def submit_enquiry():
    listing_id = request.form.get('listing_id')
    buyer_name = request.form.get('buyer_name', '').strip()
    buyer_phone = request.form.get('buyer_phone', '').strip()
    buyer_email = request.form.get('buyer_email', '').strip().lower()
    offered_price = request.form.get('offered_price', '').strip()
    requested_quantity = request.form.get('requested_quantity', '').strip()
    message = request.form.get('message', '').strip()

    # Pre-fill with logged-in user if available
    buyer_id = g.user['id'] if g.user else None
    if g.user:
        buyer_name = buyer_name or g.user['name']
        buyer_email = buyer_email or g.user['email']
        buyer_phone = buyer_phone or g.user['phone']

    errors = []
    if not listing_id:
        errors.append("Invalid listing reference.")
    if not buyer_name:
        errors.append("Your name is required.")
    if not buyer_phone or len(buyer_phone) < 10:
        errors.append("A valid 10-digit contact phone number is required.")
    if not buyer_email or '@' not in buyer_email:
        errors.append("A valid email address is required.")
    if not message:
        errors.append("Please include a brief message or offer note.")

    offered_price_val = None
    if offered_price:
        try:
            offered_price_val = float(offered_price)
        except ValueError:
            pass

    req_qty_val = None
    if requested_quantity:
        try:
            req_qty_val = float(requested_quantity)
        except ValueError:
            pass

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for('listing_detail', listing_id=listing_id))

    conn = get_db()
    cursor = conn.cursor()

    # Verify listing exists and is available
    cursor.execute("SELECT crop_name, farmer_name, farmer_phone, status FROM listings WHERE id = ?", (listing_id,))
    listing = cursor.fetchone()
    if not listing:
        conn.close()
        flash("Listing not found.", "danger")
        return redirect(url_for('browse_listings'))

    # If anonymous buyer, we can link or create or store with buyer_id nullable
    # If buyer not logged in, find or set buyer_id to 0 or first buyer
    if not buyer_id:
        cursor.execute("SELECT id FROM users WHERE email = ?", (buyer_email,))
        existing_user = cursor.fetchone()
        buyer_id = existing_user['id'] if existing_user else 1 # fallback to system / first user

    cursor.execute('''
        INSERT INTO enquiries (
            listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
            offered_price, requested_quantity, message, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    ''', (listing_id, buyer_id, buyer_name, buyer_phone, buyer_email, offered_price_val, req_qty_val, message))

    conn.commit()
    conn.close()

    log_activity("Enquiry Sent", f"Enquiry sent for listing #{listing_id} ({listing['crop_name']}) by {buyer_name}", buyer_email)

    flash(f"Your enquiry has been sent to farmer {listing['farmer_name']}! They can reach you directly on {buyer_phone}.", "success")
    return redirect(url_for('listing_detail', listing_id=listing_id))

@app.route('/enquiry/update-status/<int:enquiry_id>', methods=['POST'])
@login_required
def update_enquiry_status(enquiry_id):
    new_status = request.form.get('status', 'Pending').strip()
    if new_status not in ['Pending', 'Accepted', 'Declined', 'Completed']:
        flash("Invalid status.", "danger")
        return redirect(url_for('farmer_dashboard'))

    conn = get_db()
    cursor = conn.cursor()

    # Check if this enquiry belongs to a listing of the logged-in farmer (or admin)
    cursor.execute("""
        SELECT e.*, l.farmer_id, l.crop_name 
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE e.id = ?
    """, (enquiry_id,))
    enquiry = cursor.fetchone()

    if not enquiry:
        conn.close()
        flash("Enquiry not found.", "danger")
        return redirect(url_for('farmer_dashboard'))

    if enquiry['farmer_id'] != g.user['id'] and g.user['role'] != 'admin':
        conn.close()
        flash("Unauthorized action.", "danger")
        return redirect(url_for('index'))

    cursor.execute("UPDATE enquiries SET status = ? WHERE id = ?", (new_status, enquiry_id))
    conn.commit()
    conn.close()

    log_activity("Enquiry Status Changed", f"Enquiry #{enquiry_id} for '{enquiry['crop_name']}' updated to {new_status}")
    flash(f"Enquiry marked as '{new_status}'.", "info")
    return redirect(url_for('farmer_dashboard'))

# ==========================================
# Role-Specific Dashboards
# ==========================================

@app.route('/farmer/dashboard')
@login_required
@role_required(['farmer', 'admin'])
def farmer_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Farmer's listings
    cursor.execute("""
        SELECT * FROM listings 
        WHERE farmer_id = ? 
        ORDER BY created_at DESC
    """, (g.user['id'],))
    my_listings = cursor.fetchall()

    # Enquiries received for farmer's listings
    cursor.execute("""
        SELECT e.*, l.crop_name, l.unit, l.price_per_unit, l.status as listing_status
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        WHERE l.farmer_id = ?
        ORDER BY e.created_at DESC
    """, (g.user['id'],))
    received_enquiries = cursor.fetchall()

    # Statistics
    active_count = sum(1 for item in my_listings if item['status'] == 'Available')
    sold_count = sum(1 for item in my_listings if item['status'] == 'Sold')
    attention_count = sum(1 for item in my_listings if is_needs_attention(item))
    pending_enquiries_count = sum(1 for e in received_enquiries if e['status'] == 'Pending')

    conn.close()

    return render_template(
        'farmer_dashboard.html',
        listings=my_listings,
        enquiries=received_enquiries,
        active_count=active_count,
        sold_count=sold_count,
        attention_count=attention_count,
        pending_enquiries_count=pending_enquiries_count
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
    my_enquiries = cursor.fetchall()

    # Urgently available listings buyer might want to rescue
    cursor.execute("""
        SELECT * FROM listings 
        WHERE status = 'Available' 
        AND (julianday('now') - julianday(created_at)) >= 3
        ORDER BY created_at ASC 
        LIMIT 4
    """)
    urgent_recommendations = cursor.fetchall()

    conn.close()

    return render_template(
        'buyer_dashboard.html',
        enquiries=my_enquiries,
        urgent_recommendations=urgent_recommendations
    )

@app.route('/admin/dashboard')
@login_required
@role_required('admin')
def admin_dashboard():
    conn = get_db()
    cursor = conn.cursor()

    # Platform Stats
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'farmer'")
    total_farmers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'buyer'")
    total_buyers = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings")
    total_listings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Available'")
    available_listings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM listings WHERE status = 'Sold'")
    sold_listings = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM listings 
        WHERE status = 'Available' AND (julianday('now') - julianday(created_at)) >= 3
    """)
    urgent_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM enquiries")
    total_enquiries = cursor.fetchone()[0]

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

    # Recent Platform Enquiries
    cursor.execute("""
        SELECT e.*, l.crop_name, l.farmer_name
        FROM enquiries e
        JOIN listings l ON e.listing_id = l.id
        ORDER BY e.created_at DESC LIMIT 15
    """)
    all_enquiries = cursor.fetchall()

    # Activity Logs
    cursor.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 25")
    recent_logs = cursor.fetchall()

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
        users=all_users,
        listings=all_listings,
        enquiries=all_enquiries,
        logs=recent_logs
    )

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
