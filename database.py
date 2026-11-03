import sqlite3
import os
from datetime import datetime, timedelta
import time
import uuid
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH, timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
    conn.execute("PRAGMA journal_mode = WAL")
    cursor = conn.cursor()

    # Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('farmer', 'buyer', 'admin')),
        phone TEXT NOT NULL,
        location TEXT,
        pin_code TEXT,
        user_type TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Produce Listings Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS listings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER NOT NULL,
        crop_name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Vegetables',
        photo TEXT,
        quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        price_per_unit REAL NOT NULL,
        original_price REAL,
        harvest_date DATE NOT NULL,
        estimated_freshness_date DATE,
        village_town TEXT NOT NULL,
        district TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'Tamil Nadu',
        pin_code TEXT NOT NULL,
        farmer_name TEXT NOT NULL,
        farmer_phone TEXT NOT NULL,
        whatsapp_number TEXT,
        description TEXT,
        urgency_level TEXT NOT NULL DEFAULT 'Normal' CHECK(urgency_level IN ('Normal', 'Needs Attention', 'Urgent Sale')),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Sold', 'Inactive')),
        rescued_from_waste INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Buyer Enquiries / Orders Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS enquiries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_phone TEXT NOT NULL,
        buyer_email TEXT NOT NULL,
        offered_price REAL,
        requested_quantity REAL,
        delivery_preference TEXT DEFAULT 'Direct Pickup / Collection',
        total_price REAL DEFAULT 0,
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Accepted', 'Rejected', 'Declined', 'Ready for Collection', 'Completed', 'Cancelled')),
        cancelled_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Buyer Procurement Requirements (for Smart Buyer Matching)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS buyer_requirements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        buyer_name TEXT NOT NULL,
        business_type TEXT NOT NULL,
        crop_name TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Vegetables',
        required_quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        target_price REAL,
        village_town TEXT,
        district TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'Tamil Nadu',
        contact_phone TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Fulfilled', 'Closed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Notifications Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'info' CHECK(type IN ('info', 'order', 'urgent_risk', 'status_change', 'alert')),
        link TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Activity Log Table for Admin monitoring
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        details TEXT NOT NULL,
        user_email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Favorite Farmers (for Buyer Dashboard)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS favorite_farmers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        buyer_id INTEGER NOT NULL,
        farmer_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(buyer_id, farmer_id),
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # AI Quality Inspections Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS quality_inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_id INTEGER,
        farmer_id INTEGER NOT NULL,
        crop_name TEXT NOT NULL,
        image_filename TEXT NOT NULL,
        quality_grade TEXT NOT NULL,
        confidence REAL NOT NULL,
        color_score REAL,
        defect_score REAL,
        freshness_assessment TEXT,
        target_buyers TEXT,
        source TEXT DEFAULT 'AI Visual Inspection',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # AI Chat Logs Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS ai_chat_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_id TEXT,
        user_message TEXT NOT NULL,
        bot_response TEXT NOT NULL,
        lang TEXT DEFAULT 'en',
        intent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Payments & Transactions Table (Razorpay & COD)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        listing_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        farmer_id INTEGER NOT NULL,
        transaction_id TEXT UNIQUE NOT NULL,
        razorpay_order_id TEXT,
        razorpay_payment_id TEXT,
        razorpay_signature TEXT,
        payment_method TEXT NOT NULL DEFAULT 'Online',
        amount REAL NOT NULL,
        currency TEXT DEFAULT 'INR',
        subtotal REAL NOT NULL,
        delivery_charges REAL DEFAULT 0,
        payment_status TEXT NOT NULL DEFAULT 'Pending' CHECK(payment_status IN ('Pending', 'Paid', 'Failed', 'Cancelled', 'Refunded', 'COD Pending')),
        payout_status TEXT NOT NULL DEFAULT 'Unsettled' CHECK(payout_status IN ('Unsettled', 'Processing', 'Settled')),
        payout_date TIMESTAMP,
        refund_status TEXT DEFAULT 'None' CHECK(refund_status IN ('None', 'Requested', 'Approved', 'Rejected', 'Processed')),
        refund_reason TEXT,
        refund_amount REAL DEFAULT 0,
        refund_tx_id TEXT,
        idempotency_key TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES enquiries(id) ON DELETE CASCADE,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Live Market Prices Benchmark Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS market_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        crop_name TEXT NOT NULL,
        category TEXT DEFAULT 'Vegetables',
        market_name TEXT NOT NULL,
        district TEXT NOT NULL,
        modal_price REAL NOT NULL,
        min_price REAL NOT NULL,
        max_price REAL NOT NULL,
        price_date DATE NOT NULL,
        trend TEXT DEFAULT 'stable' CHECK(trend IN ('up', 'down', 'stable')),
        unit TEXT DEFAULT 'kg',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Farmer-Buyer Live Chat Messages
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        order_id INTEGER,
        listing_id INTEGER,
        message TEXT NOT NULL,
        image_filename TEXT,
        offer_price REAL,
        offer_quantity REAL,
        offer_status TEXT DEFAULT 'None' CHECK(offer_status IN ('None', 'Pending', 'Accepted', 'Declined')),
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Weather Alerts Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weather_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        district TEXT NOT NULL,
        severity TEXT NOT NULL CHECK(severity IN ('Info', 'Advisory', 'Warning', 'Critical')),
        condition TEXT NOT NULL,
        temperature REAL,
        rainfall_prob INTEGER,
        title TEXT NOT NULL,
        advice TEXT NOT NULL,
        affected_crops TEXT,
        valid_until DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Safe Schema Migrations for existing database
    # 1. users migrations
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [r[1] for r in cursor.fetchall()]
    if 'is_active' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
    if 'latitude' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN latitude REAL")
    if 'longitude' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN longitude REAL")
    if 'district' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN district TEXT")

    # 2. listings migrations
    cursor.execute("PRAGMA table_info(listings)")
    listing_cols = [r[1] for r in cursor.fetchall()]
    if 'state' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN state TEXT NOT NULL DEFAULT 'Tamil Nadu'")
    if 'estimated_freshness_date' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN estimated_freshness_date DATE")
    if 'urgency_level' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN urgency_level TEXT NOT NULL DEFAULT 'Normal'")
    if 'rescued_from_waste' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN rescued_from_waste INTEGER DEFAULT 0")
    if 'storage_condition' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN storage_condition TEXT DEFAULT 'Ambient / Room Temperature'")
    if 'freshness_score' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN freshness_score REAL DEFAULT 85")
    if 'freshness_grade' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN freshness_grade TEXT DEFAULT 'Fresh'")
    if 'quality_grade' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN quality_grade TEXT DEFAULT 'Grade A'")
    if 'quality_confidence' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN quality_confidence REAL DEFAULT 90")
    if 'quality_analysis' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN quality_analysis TEXT")
    if 'suggested_price' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN suggested_price REAL")
    if 'latitude' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN latitude REAL")
    if 'longitude' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN longitude REAL")
    if 'reserved_quantity' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN reserved_quantity REAL DEFAULT 0")
    if 'shelf_life_days' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN shelf_life_days INTEGER DEFAULT 7")
    if 'qr_code_token' not in listing_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN qr_code_token TEXT")

    # 3. enquiries migrations (ensure new columns & status compatibility)
    cursor.execute("PRAGMA table_info(enquiries)")
    enquiry_cols = [r[1] for r in cursor.fetchall()]
    if 'delivery_preference' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_preference TEXT DEFAULT 'Direct Pickup / Collection'")
    if 'total_price' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN total_price REAL DEFAULT 0")
    if 'payment_method' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN payment_method TEXT DEFAULT 'COD'")
    if 'payment_status' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN payment_status TEXT DEFAULT 'Unpaid'")
    if 'delivery_charges' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_charges REAL DEFAULT 0")
    if 'updated_at' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN updated_at TIMESTAMP DEFAULT NULL")
    if 'cancelled_reason' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN cancelled_reason TEXT")
    if 'tracking_notes' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN tracking_notes TEXT")
    if 'delivery_address' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_address TEXT")
    if 'delivery_lat' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_lat REAL")
    if 'delivery_lng' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_lng REAL")
    if 'status_timeline' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN status_timeline TEXT")

    # Migrate enquiries CHECK constraint to include full 6-stage lifecycle
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='enquiries'")
        enq_sql_row = cursor.fetchone()
        if enq_sql_row and "'Packed'" not in enq_sql_row[0]:
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute('''
            CREATE TABLE enquiries_migrated (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                buyer_id INTEGER NOT NULL,
                buyer_name TEXT NOT NULL,
                buyer_phone TEXT NOT NULL,
                buyer_email TEXT NOT NULL,
                offered_price REAL,
                requested_quantity REAL,
                delivery_preference TEXT DEFAULT 'Direct Pickup / Collection',
                total_price REAL DEFAULT 0,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Accepted', 'Packed', 'Shipped', 'Delivered', 'Completed', 'Ready for Collection', 'Rejected', 'Declined', 'Cancelled')),
                cancelled_reason TEXT,
                tracking_notes TEXT,
                delivery_address TEXT,
                delivery_lat REAL,
                delivery_lng REAL,
                status_timeline TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
                FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
            )
            ''')
            cursor.execute('''
            INSERT INTO enquiries_migrated (
                id, listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
                offered_price, requested_quantity, delivery_preference, total_price,
                message, status, cancelled_reason, tracking_notes, delivery_address,
                delivery_lat, delivery_lng, status_timeline, created_at, updated_at
            )
            SELECT 
                id, listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
                offered_price, requested_quantity, 
                COALESCE(delivery_preference, 'Direct Pickup / Collection'),
                COALESCE(total_price, 0),
                message, status, cancelled_reason,
                NULL, NULL, NULL, NULL, NULL,
                created_at, 
                COALESCE(updated_at, created_at)
            FROM enquiries
            ''')
            cursor.execute("DROP TABLE enquiries")
            cursor.execute("ALTER TABLE enquiries_migrated RENAME TO enquiries")
            cursor.execute("PRAGMA foreign_keys = ON")
    except Exception as e:
        print(f"Enquiries migration note: {e}")

    try:
        seed_market_prices(conn)
        seed_weather_alerts(conn)
    except Exception as _e:
        pass

    conn.commit()
    conn.close()

def create_notification(user_id, title, message, notif_type='info', link=None):
    """Helper to store an in-app notification for a user."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, title, message, notif_type, link))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False

def get_unread_notifications_count(user_id):
    """Return count of unread notifications for user."""
    if not user_id:
        return 0
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0

def get_user_notifications(user_id, limit=20):
    """Fetch notifications for user ordered by newest first."""
    if not user_id:
        return []
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM notifications 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def mark_notification_read(notification_id, user_id=None):
    """Mark a single notification as read."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notification_id, user_id))
        else:
            cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

def mark_all_notifications_read(user_id):
    """Mark all notifications as read for a user."""
    if not user_id:
        return False
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False

# ==========================================
# AI 2.0 Helpers: Favorites, Quality & Orders
# ==========================================

def toggle_favorite_farmer(buyer_id, farmer_id):
    """Toggle a farmer in a buyer's favorite list."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM favorite_farmers WHERE buyer_id = ? AND farmer_id = ?", (buyer_id, farmer_id))
        row = cursor.fetchone()
        if row:
            cursor.execute("DELETE FROM favorite_farmers WHERE id = ?", (row['id'],))
            favorited = False
        else:
            cursor.execute("INSERT INTO favorite_farmers (buyer_id, farmer_id) VALUES (?, ?)", (buyer_id, farmer_id))
            favorited = True
        conn.commit()
        conn.close()
        return {'success': True, 'favorited': favorited}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def is_farmer_favorited(buyer_id, farmer_id, conn=None):
    """Check if farmer is favorited by buyer."""
    if not buyer_id or not farmer_id:
        return False
    close_conn = False
    try:
        if conn is None:
            conn = get_db()
            close_conn = True
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM favorite_farmers WHERE buyer_id = ? AND farmer_id = ?", (buyer_id, farmer_id))
        fav = cursor.fetchone() is not None
        if close_conn:
            conn.close()
        return fav
    except Exception:
        return False

def get_buyer_favorites(buyer_id):
    """Fetch all favorite farmers for a buyer with their active listings count."""
    if not buyer_id:
        return []
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.name, u.email, u.phone, u.location, u.pin_code,
                   COUNT(DISTINCT l.id) AS active_listings_count,
                   ff.created_at AS favorited_at
            FROM favorite_farmers ff
            JOIN users u ON ff.farmer_id = u.id
            LEFT JOIN listings l ON l.farmer_id = u.id AND l.status = 'Available'
            WHERE ff.buyer_id = ?
            GROUP BY u.id
            ORDER BY ff.created_at DESC
        ''', (buyer_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f"Error fetching favorites: {e}")
        return []

def save_quality_inspection(farmer_id, crop_name, image_filename, quality_grade,
                            confidence, color_score=None, defect_score=None,
                            freshness_assessment=None, target_buyers=None,
                            listing_id=None, source='AI Visual Inspection'):
    """Record a produce quality grading inspection."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO quality_inspections (
                listing_id, farmer_id, crop_name, image_filename,
                quality_grade, confidence, color_score, defect_score,
                freshness_assessment, target_buyers, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing_id, farmer_id, crop_name, image_filename,
            quality_grade, confidence, color_score, defect_score,
            freshness_assessment, target_buyers, source
        ))
        inspection_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return inspection_id
    except Exception as e:
        print(f"Error saving quality inspection: {e}")
        return None

def get_farmer_quality_inspections(farmer_id, limit=15):
    """Retrieve quality inspection history for farmer."""
    if not farmer_id:
        return []
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM quality_inspections
            WHERE farmer_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        ''', (farmer_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def log_ai_chat(user_id, session_id, user_message, bot_response, lang='en', intent=None):
    """Persist conversation snippet for contextual assistance."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO ai_chat_logs (user_id, session_id, user_message, bot_response, lang, intent)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, session_id, user_message, bot_response, lang, intent))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error logging AI chat: {e}")
        return False

def update_order_lifecycle(order_id, new_status, note=None, delivery_address=None,
                           delivery_lat=None, delivery_lng=None):
    """
    Update order status and append an entry to the status_timeline JSON.
    Supports: Pending -> Accepted -> Packed -> Shipped -> Delivered / Cancelled
    """
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status, status_timeline FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found"

        current_timeline = []
        if order['status_timeline']:
            try:
                current_timeline = json.loads(order['status_timeline'])
            except Exception:
                current_timeline = []

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timeline_entry = {
            'status': new_status,
            'timestamp': now_str,
            'note': note or f"Status changed from {order['status']} to {new_status}"
        }
        if delivery_lat and delivery_lng:
            timeline_entry['lat'] = delivery_lat
            timeline_entry['lng'] = delivery_lng

        current_timeline.append(timeline_entry)
        timeline_json = json.dumps(current_timeline)

        cursor.execute('''
            UPDATE enquiries
            SET status = ?,
                tracking_notes = COALESCE(?, tracking_notes),
                delivery_address = COALESCE(?, delivery_address),
                delivery_lat = COALESCE(?, delivery_lat),
                delivery_lng = COALESCE(?, delivery_lng),
                status_timeline = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            new_status, note, delivery_address,
            delivery_lat, delivery_lng, timeline_json,
            now_str, order_id
        ))
        conn.commit()
        conn.close()
        return True, "Order updated successfully"
    except Exception as e:
        return False, str(e)

def get_order_timeline(order_id):
    """Return parsed timeline list for an order."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status_timeline, created_at, status FROM enquiries WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return []
        if row['status_timeline']:
            try:
                return json.loads(row['status_timeline'])
            except Exception:
                pass
        return [{'status': row['status'], 'timestamp': str(row['created_at']), 'note': 'Order created'}]
    except Exception:
        return []

def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check if users already exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        # Still check and seed buyer_requirements and notifications if needed
        seed_buyer_requirements(conn)
        conn.close()
        return

    # Seed Users with bcrypt hashing
    admin_email = os.environ.get('ADMIN_EMAIL', 'Pp274142@gmail.com').strip().lower()
    admin_pw_plain = os.environ.get('ADMIN_PASSWORD', 'praveen16')
    try:
        import bcrypt
        admin_pw = bcrypt.hashpw(admin_pw_plain.encode('utf-8'), bcrypt.gensalt(12)).decode('utf-8')
        farmer_pw = bcrypt.hashpw(b"farmer123", bcrypt.gensalt(12)).decode('utf-8')
        buyer_pw = bcrypt.hashpw(b"buyer123", bcrypt.gensalt(12)).decode('utf-8')
    except Exception:
        admin_pw = generate_password_hash(admin_pw_plain)
        farmer_pw = generate_password_hash("farmer123")
        buyer_pw = generate_password_hash("buyer123")

    users_data = [
        # Exactly ONE Authorized Admin Account
        ("Platform Administrator", admin_email, admin_pw, "admin", "9842100001", "Chennai Head Office", "600001", "Platform Admin"),
        # Farmers
        ("Muthuvel Karuppan", "muthu.farmer@gmail.com", farmer_pw, "farmer", "9842112345", "Ottanchathiram", "624619", "Smallholder Farmer"),
        ("Selvi Shanmugam", "selvi.farms@gmail.com", farmer_pw, "farmer", "9443256789", "Rayakottai", "635116", "Vegetable Grower"),
        ("Ramanathan K.", "raman.ooty@gmail.com", farmer_pw, "farmer", "9789012345", "Ketti Valley", "643215", "Hill Produce Farmer"),
        ("Kandasamy P.", "kandasamy.coconuts@gmail.com", farmer_pw, "farmer", "9488123456", "Anamalai", "642104", "Coconut Grower"),
        # Buyers
        ("Saravana Bhavan Procurement", "saravana.hotel@gmail.com", buyer_pw, "buyer", "9840012345", "Madurai City", "625001", "Hotels and Restaurants"),
        ("Kumar Daily Fresh Mart", "kumar.mart@gmail.com", buyer_pw, "buyer", "9841122334", "RS Puram, Coimbatore", "641002", "Supermarkets"),
        ("Annapoorna Catering Services", "annapoorna.caterers@gmail.com", buyer_pw, "buyer", "9894455667", "Tirupur", "641601", "Hotels and Restaurants"),
        ("Sakthi Food Processing Ltd", "sakthi.processing@gmail.com", buyer_pw, "buyer", "9788001122", "Perundurai", "638052", "Food Processing Companies")
    ]

    cursor.executemany('''
        INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', users_data)

    conn.commit()

    # Get IDs of created users
    cursor.execute("SELECT id, email FROM users")
    user_map = {row['email']: row['id'] for row in cursor.fetchall()}

    now = datetime.now()
    four_days_ago = (now - timedelta(days=4)).strftime('%Y-%m-%d %H:%M:%S')
    five_days_ago = (now - timedelta(days=5)).strftime('%Y-%m-%d %H:%M:%S')
    three_days_ago = (now - timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
    one_day_ago = (now - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    today_str = now.strftime('%Y-%m-%d %H:%M:%S')

    harvest_4d = (now - timedelta(days=5)).strftime('%Y-%m-%d')
    harvest_5d = (now - timedelta(days=6)).strftime('%Y-%m-%d')
    harvest_3d = (now - timedelta(days=3)).strftime('%Y-%m-%d')
    harvest_1d = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    harvest_today = now.strftime('%Y-%m-%d')
    harvest_20d = (now - timedelta(days=20)).strftime('%Y-%m-%d')

    fresh_tomatoes = (now + timedelta(days=2)).strftime('%Y-%m-%d')
    fresh_onions = (now + timedelta(days=14)).strftime('%Y-%m-%d')
    fresh_carrots = (now + timedelta(days=5)).strftime('%Y-%m-%d')
    fresh_coconuts = (now + timedelta(days=10)).strftime('%Y-%m-%d')
    fresh_jasmine = (now + timedelta(days=1)).strftime('%Y-%m-%d')

    listings_data = [
        # Listing 1: 4 days old -> Needs Attention!
        (
            user_map['selvi.farms@gmail.com'],
            "Krishnagiri Hybrid Country Tomatoes",
            "Vegetables",
            "tomatoes.jpg",
            850.0,
            "kg",
            18.0,
            28.0,
            harvest_4d,
            fresh_tomatoes,
            "Rayakottai",
            "Krishnagiri",
            "Tamil Nadu",
            "635116",
            "Selvi Shanmugam",
            "9443256789",
            "9443256789",
            "Firm, naturally ripened farm-fresh red country tomatoes. 850 kg available in 34 wooden crates. Needs swift buyer clearance due to bumper harvest. Perfect for hotels, restaurants, sauce makers, and vegetable retailers.",
            "Needs Attention",
            "Available",
            0,
            four_days_ago,
            four_days_ago
        ),
        # Listing 2: 4 days old -> Needs Attention!
        (
            user_map['muthu.farmer@gmail.com'],
            "Dindigul Bellary Small Onions (Shallots / Chinna Vengayam)",
            "Vegetables",
            "shallots.jpg",
            1200.0,
            "kg",
            42.0,
            60.0,
            harvest_5d,
            fresh_onions,
            "Ottanchathiram",
            "Dindigul",
            "Tamil Nadu",
            "624619",
            "Muthuvel Karuppan",
            "9842112345",
            "9842112345",
            "Top-grade pungent small onions dried and sorted into 40kg gunny bags. High shelf life if kept dry. Price discounted for bulk wholesale buyers to prevent storage loss.",
            "Needs Attention",
            "Available",
            0,
            four_days_ago,
            four_days_ago
        ),
        # Listing 3: 1 day old -> Fresh Listing!
        (
            user_map['raman.ooty@gmail.com'],
            "Ooty Mountain Crispy Carrots",
            "Vegetables",
            "carrots.jpg",
            500.0,
            "kg",
            35.0,
            50.0,
            harvest_1d,
            fresh_carrots,
            "Ketti Valley",
            "Nilgiris",
            "Tamil Nadu",
            "643215",
            "Ramanathan K.",
            "9789012345",
            "9789012345",
            "Sweet, crunchy high-altitude Ooty carrots washed and crated straight from the mountain slopes. Suitable for supermarkets, hotels, and cold-pressed juice shops.",
            "Normal",
            "Available",
            0,
            one_day_ago,
            one_day_ago
        ),
        # Listing 4: 3 days old -> Urgent Sale!
        (
            user_map['kandasamy.coconuts@gmail.com'],
            "Pollachi Grade-A Tender Coconuts (Elaneer)",
            "Fruits",
            "coconuts.jpg",
            1500.0,
            "Pieces / Bunches",
            32.0,
            45.0,
            harvest_3d,
            fresh_coconuts,
            "Anamalai",
            "Coimbatore",
            "Tamil Nadu",
            "642104",
            "Kandasamy P.",
            "9488123456",
            "9488123456",
            "Sweet coconut water, tender jelly pulp, freshly cut bunches from 20-year old native palm trees. Ready for direct bulk pickup or dispatch across Tamil Nadu.",
            "Needs Attention",
            "Available",
            0,
            three_days_ago,
            three_days_ago
        ),
        # Listing 5: Today -> New Listing!
        (
            user_map['muthu.farmer@gmail.com'],
            "Madurai Fragrant Malli (Jasmine Buds)",
            "Flowers",
            "jasmine.jpg",
            60.0,
            "kg",
            380.0,
            550.0,
            harvest_today,
            fresh_jasmine,
            "Thiruparankundram",
            "Madurai",
            "Tamil Nadu",
            "625005",
            "Muthuvel Karuppan",
            "9842112345",
            "9842112345",
            "Intense aroma Madurai Malli buds plucked in early morning cool hours. Best for garland makers, temple trusts, and event decorators.",
            "Urgent Sale",
            "Available",
            0,
            today_str,
            today_str
        ),
        # Listing 6: Sold Produce -> Confirmed Rescued
        (
            user_map['selvi.farms@gmail.com'],
            "Thanjavur Ponni Raw Rice (Deluxe Harvest)",
            "Grains & Pulses",
            "rice.jpg",
            40.0,
            "Bags (25kg)",
            1350.0,
            1600.0,
            harvest_20d,
            None,
            "Kumbakonam",
            "Thanjavur",
            "Tamil Nadu",
            "612001",
            "Selvi Shanmugam",
            "9443256789",
            "9443256789",
            "Traditional Kaveri delta Ponni rice, double-boiled and cleaned. Successfully rescued and sold in bulk.",
            "Normal",
            "Sold",
            1,
            five_days_ago,
            today_str
        )
    ]

    cursor.executemany('''
        INSERT INTO listings (
            farmer_id, crop_name, category, photo, quantity, unit, price_per_unit, original_price,
            harvest_date, estimated_freshness_date, village_town, district, state, pin_code,
            farmer_name, farmer_phone, whatsapp_number, description, urgency_level, status,
            rescued_from_waste, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', listings_data)

    conn.commit()

    # Seed Sample Enquiries / Orders
    cursor.execute("SELECT id, crop_name, price_per_unit FROM listings WHERE crop_name LIKE '%Tomatoes%'")
    tomato_listing = cursor.fetchone()

    cursor.execute("SELECT id, crop_name, price_per_unit FROM listings WHERE crop_name LIKE '%Small Onions%'")
    onion_listing = cursor.fetchone()

    cursor.execute("SELECT id, crop_name, price_per_unit FROM listings WHERE crop_name LIKE '%Ponni%'")
    rice_listing = cursor.fetchone()

    two_days_ago = (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')

    enquiries_data = [
        (
            tomato_listing['id'],
            user_map['saravana.hotel@gmail.com'],
            "Saravana Bhavan Procurement",
            "9840012345",
            "saravana.hotel@gmail.com",
            17.0,
            400.0,
            "Direct Pickup / Collection",
            6800.0,
            "Hello Selvi ji, We can take 400 kg immediately for our Madurai branches if you can arrange delivery to the bypass junction. Please confirm.",
            "Pending",
            two_days_ago,
            two_days_ago
        ),
        (
            onion_listing['id'],
            user_map['kumar.mart@gmail.com'],
            "Kumar Daily Fresh Mart",
            "9841122334",
            "kumar.mart@gmail.com",
            40.0,
            1200.0,
            "Self Pickup",
            48000.0,
            "We have transport arriving near Ottanchathiram tomorrow morning. We can lift the entire 1200 kg batch at ₹40/kg instant cash payment.",
            "Accepted",
            one_day_ago,
            one_day_ago
        ),
        (
            rice_listing['id'],
            user_map['annapoorna.caterers@gmail.com'],
            "Annapoorna Catering Services",
            "9894455667",
            "annapoorna.caterers@gmail.com",
            1350.0,
            40.0,
            "Direct Pickup / Collection",
            54000.0,
            "40 bags received and verified in our central warehouse. Payment cleared via NEFT. Thank you!",
            "Completed",
            four_days_ago,
            today_str
        )
    ]

    cursor.executemany('''
        INSERT INTO enquiries (
            listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
            offered_price, requested_quantity, delivery_preference, total_price,
            message, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', enquiries_data)

    # Seed Activity Logs
    logs_data = [
        ("Listing Created", "Selvi Shanmugam listed 850 kg of Krishnagiri Hybrid Country Tomatoes", "selvi.farms@gmail.com"),
        ("Listing Created", "Muthuvel Karuppan listed 1200 kg of Dindigul Bellary Small Onions", "muthu.farmer@gmail.com"),
        ("Enquiry Sent", "Saravana Bhavan enquired for 400 kg Tomatoes", "saravana.hotel@gmail.com"),
        ("Produce Rescued", "40 Bags of Ponni Rice marked as SOLD to Annapoorna Catering", "selvi.farms@gmail.com")
    ]
    cursor.executemany('''
        INSERT INTO activity_logs (action, details, user_email)
        VALUES (?, ?, ?)
    ''', logs_data)

    seed_buyer_requirements(conn)

    conn.commit()
    conn.close()

    try:
        from seed_vegetables import seed_vegetables
        seed_vegetables()
    except Exception as _e:
        print(f"Demo vegetable seed note: {_e}")

def seed_buyer_requirements(conn):
    """Seed procurement requirements from verified Tamil Nadu buyers."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM buyer_requirements")
    if cursor.fetchone()[0] > 0:
        return

    cursor.execute("SELECT id, email FROM users WHERE role = 'buyer'")
    buyer_map = {row['email']: row['id'] for row in cursor.fetchall()}

    if not buyer_map:
        return

    requirements_data = [
        (
            buyer_map.get('saravana.hotel@gmail.com', 6),
            "Saravana Bhavan Procurement",
            "Hotels and Restaurants",
            "Country Tomatoes (Nattu Thakkali)",
            "Vegetables",
            500.0,
            "kg",
            20.0,
            "Madurai Central",
            "Madurai",
            "Tamil Nadu",
            "9840012345",
            "Requirement for daily kitchen consumption. Prefer firm red country tomatoes in 25kg crates. Same-day cash settlement upon delivery."
        ),
        (
            buyer_map.get('saravana.hotel@gmail.com', 6),
            "Saravana Bhavan Procurement",
            "Hotels and Restaurants",
            "Small Onions (Chinna Vengayam)",
            "Vegetables",
            300.0,
            "kg",
            45.0,
            "Madurai Central",
            "Madurai",
            "Tamil Nadu",
            "9840012345",
            "High pungency clean shallots needed for sambar preparation. Dried and graded batches preferred."
        ),
        (
            buyer_map.get('kumar.mart@gmail.com', 7),
            "Kumar Daily Fresh Mart",
            "Supermarkets",
            "Ooty Carrots",
            "Vegetables",
            400.0,
            "kg",
            38.0,
            "RS Puram",
            "Coimbatore",
            "Tamil Nadu",
            "9841122334",
            "Fresh washed carrots required for retail chain shelves. Daily morning pickup available across Nilgiris and Coimbatore."
        ),
        (
            buyer_map.get('kumar.mart@gmail.com', 7),
            "Kumar Daily Fresh Mart",
            "Supermarkets",
            "Pollachi Tender Coconuts",
            "Fruits",
            1000.0,
            "Pieces / Bunches",
            34.0,
            "RS Puram",
            "Coimbatore",
            "Tamil Nadu",
            "9841122334",
            "Looking for regular truckload supply directly from coconut orchards in Pollachi / Anamalai."
        ),
        (
            buyer_map.get('annapoorna.caterers@gmail.com', 8),
            "Annapoorna Catering Services",
            "Hotels and Restaurants",
            "Green Chillies & Ginger",
            "Spices & Herbs",
            150.0,
            "kg",
            60.0,
            "Avinashi Road",
            "Tiruppur",
            "Tamil Nadu",
            "9894455667",
            "Medium spicy green chillies and fresh hill ginger for weekly wedding banquet catering."
        ),
        (
            buyer_map.get('sakthi.processing@gmail.com', 9),
            "Sakthi Food Processing Ltd",
            "Food Processing Companies",
            "Bulk Ripe Tomatoes (for Sauce & Puree)",
            "Vegetables",
            2500.0,
            "kg",
            15.0,
            "Perundurai SIPCOT",
            "Erode",
            "Tamil Nadu",
            "9788001122",
            "Industrial procurement: We rescue high-volume surplus and bumper harvest tomatoes. Bulk tanker and crate lifting available at farmgate."
        )
    ]

    cursor.executemany('''
        INSERT INTO buyer_requirements (
            buyer_id, buyer_name, business_type, crop_name, category,
            required_quantity, unit, target_price, village_town, district,
            state, contact_phone, notes, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    ''', requirements_data)

    # Seed welcome notifications
    cursor.execute("SELECT id FROM users WHERE role = 'farmer'")
    farmers = cursor.fetchall()
    for f in farmers:
        cursor.execute('''
            INSERT INTO notifications (user_id, title, message, type, link)
            VALUES (?, 'Vanakkam to FarmFresh Rescue!', 'Post your farm harvests or discover nearby hotels, shops, and food processors in Tamil Nadu to sell before spoilage.', 'info', '/farmer/dashboard')
        ''', (f['id'],))

    seed_market_prices(conn)
    seed_weather_alerts(conn)

    conn.commit()

def seed_market_prices(conn):
    """Seed benchmark market prices for Tamil Nadu APMC mandis."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM market_prices")
    if cursor.fetchone()[0] > 0:
        return

    today = datetime.now().strftime('%Y-%m-%d')
    prices = [
        # Koyambedu Wholesale Market (Chennai)
        ("Tomatoes", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 24.0, 20.0, 28.0, today, "stable", "kg"),
        ("Country Tomatoes (Nattu Thakkali)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 22.0, 18.0, 26.0, today, "down", "kg"),
        ("Small Onions (Chinna Vengayam)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 55.0, 48.0, 62.0, today, "up", "kg"),
        ("Bellary Onions (Periya Vengayam)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 32.0, 28.0, 36.0, today, "stable", "kg"),
        ("Potatoes", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 30.0, 26.0, 34.0, today, "stable", "kg"),
        ("Ooty Carrots", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 48.0, 42.0, 55.0, today, "up", "kg"),
        ("Brinjal (Kathirikai)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 28.0, 22.0, 35.0, today, "down", "kg"),
        ("Green Chillies (Pachai Milagai)", "Spices & Herbs", "Koyambedu Wholesale Market", "Chennai", 65.0, 55.0, 75.0, today, "up", "kg"),
        ("Drumsticks (Murungakkai)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 40.0, 32.0, 50.0, today, "down", "kg"),
        ("Ladies Finger (Bhendi / Vendakkai)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 32.0, 26.0, 38.0, today, "stable", "kg"),
        ("Cabbage (Muttakose)", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 20.0, 16.0, 24.0, today, "stable", "kg"),
        ("Cauliflower", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 35.0, 28.0, 42.0, today, "down", "kg"),
        ("Beans", "Vegetables", "Koyambedu Wholesale Market", "Chennai", 52.0, 45.0, 60.0, today, "up", "kg"),
        # Ottanchathiram Vegetable Market (Dindigul)
        ("Tomatoes", "Vegetables", "Ottanchathiram Market", "Dindigul", 19.0, 16.0, 22.0, today, "down", "kg"),
        ("Small Onions (Chinna Vengayam)", "Vegetables", "Ottanchathiram Market", "Dindigul", 48.0, 42.0, 54.0, today, "stable", "kg"),
        ("Drumsticks (Murungakkai)", "Vegetables", "Ottanchathiram Market", "Dindigul", 35.0, 28.0, 42.0, today, "stable", "kg"),
        # Pollachi Coconut Market (Coimbatore)
        ("Tender Coconuts (Elaneer)", "Fruits", "Pollachi Regulated Market", "Coimbatore", 35.0, 30.0, 40.0, today, "stable", "piece"),
        # Madurai Flower Market
        ("Madurai Jasmine (Malli)", "Flowers", "Mattuthavani Flower Market", "Madurai", 420.0, 350.0, 500.0, today, "up", "kg"),
    ]
    cursor.executemany('''
        INSERT INTO market_prices (crop_name, category, market_name, district, modal_price, min_price, max_price, price_date, trend, unit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', prices)
    conn.commit()

def seed_weather_alerts(conn):
    """Seed real-time agro-climatic advisories for Tamil Nadu."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM weather_alerts")
    if cursor.fetchone()[0] > 0:
        return

    today = datetime.now().date()
    valid_until = (today + timedelta(days=5)).strftime('%Y-%m-%d')
    alerts = [
        ("Krishnagiri", "Warning", "Moderate to Heavy Rainfall", 28.5, 75,
         "Rainfall Alert for Tomato & Vegetable Farmers",
         "Forecast of 45-60mm precipitation over next 48 hours. Harvest ripe tomatoes immediately to prevent fruit cracking, fungal rot, and waterlogged soil damage.",
         "Tomatoes, Chillies, Beans", valid_until),
        ("Dindigul", "Advisory", "High Humidity & Intermittent Showers", 31.0, 60,
         "Shallot & Onion Curing Advisory",
         "High humidity may trigger fungal neck rot in harvested shallots. Shift all drying small onions to elevated ventilated crates under covered sheds.",
         "Small Onions, Drumsticks", valid_until),
        ("Nilgiris", "Info", "Cool Mountain Mist", 16.0, 25,
         "Favorable Hill Crop Conditions",
         "Crisp cool weather ideal for carrot, cabbage and beetroot harvesting. Root vegetables can be harvested in early morning hours for crisp shelf life.",
         "Carrots, Potatoes, Cabbage", valid_until),
        ("Coimbatore", "Advisory", "Breezy & Warm", 33.0, 20,
         "Coconut Orchard Hydration Advisory",
         "Dry warm weather with moderate wind speeds. Tender coconuts in high demand across urban retail chains.",
         "Tender Coconuts, Bananas", valid_until),
        ("Thanjavur", "Info", "Sunny Kaveri Basin", 34.0, 15,
         "Grain Storage Weather",
         "Dry sunny conditions ideal for grain sun-drying and direct warehouse dispatch.",
         "Paddy, Pulses", valid_until),
    ]
    cursor.executemany('''
        INSERT INTO weather_alerts (district, severity, condition, temperature, rainfall_prob, title, advice, affected_crops, valid_until)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', alerts)
    conn.commit()

# ==========================================
# Real-Time Payments, Transactions & Invoices
# ==========================================

def create_payment_record(order_id, listing_id, buyer_id, farmer_id, amount, subtotal,
                          delivery_charges=0, payment_method='Online', razorpay_order_id=None,
                          idempotency_key=None):
    """Create a new payment transaction record."""
    txn_id = f"TXN-FFR-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
    status = 'COD Pending' if payment_method == 'COD' else 'Pending'
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO payments (
                order_id, listing_id, buyer_id, farmer_id, transaction_id,
                razorpay_order_id, payment_method, amount, subtotal, delivery_charges,
                payment_status, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (order_id, listing_id, buyer_id, farmer_id, txn_id, razorpay_order_id,
              payment_method, amount, subtotal, delivery_charges, status, idempotency_key))
        payment_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {'success': True, 'payment_id': payment_id, 'transaction_id': txn_id, 'status': status}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def confirm_payment_record(transaction_id, razorpay_payment_id=None, razorpay_signature=None, payment_method=None):
    """Mark payment as Paid and update associated order & stock."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE transaction_id = ? OR razorpay_order_id = ?", (transaction_id, transaction_id))
        payment = cursor.fetchone()
        if not payment:
            conn.close()
            return False, "Payment record not found"
        
        # Idempotency check: if already paid, return success without double decrementing stock
        if payment['payment_status'] == 'Paid':
            conn.close()
            return True, payment['transaction_id']

        method = payment_method or payment['payment_method']
        cursor.execute('''
            UPDATE payments
            SET payment_status = 'Paid',
                razorpay_payment_id = COALESCE(?, razorpay_payment_id),
                razorpay_signature = COALESCE(?, razorpay_signature),
                payment_method = ?,
                updated_at = ?
            WHERE id = ?
        ''', (razorpay_payment_id, razorpay_signature, method, now_str, payment['id']))

        # Update order status to Accepted
        cursor.execute('''
            UPDATE enquiries
            SET payment_status = 'Paid',
                payment_method = ?,
                status = 'Accepted',
                updated_at = ?
            WHERE id = ?
        ''', (method, now_str, payment['order_id']))

        # Deduct stock from listing
        cursor.execute("SELECT requested_quantity FROM enquiries WHERE id = ?", (payment['order_id'],))
        enq = cursor.fetchone()
        qty = enq['requested_quantity'] if enq else 0

        cursor.execute("SELECT quantity, reserved_quantity FROM listings WHERE id = ?", (payment['listing_id'],))
        listing = cursor.fetchone()
        if listing:
            new_qty = max(0.0, float(listing['quantity']) - float(qty))
            new_res = max(0.0, float(listing['reserved_quantity'] or 0) - float(qty))
            new_status = 'Sold' if new_qty <= 0 else 'Available'
            cursor.execute('''
                UPDATE listings
                SET quantity = ?,
                    reserved_quantity = ?,
                    status = ?,
                    rescued_from_waste = CASE WHEN ? <= 0 THEN 1 ELSE rescued_from_waste END,
                    updated_at = ?
                WHERE id = ?
            ''', (new_qty, new_res, new_status, new_qty, now_str, payment['listing_id']))

        conn.commit()
        conn.close()
        return True, payment['transaction_id']
    except Exception as e:
        return False, str(e)

def confirm_cod_order(order_id, delivery_charges=0):
    """Confirm a Cash on Delivery order: marks COD Pending, updates stock, creates payment record."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found"
        
        cursor.execute("SELECT * FROM listings WHERE id = ?", (order['listing_id'],))
        listing = cursor.fetchone()
        if not listing:
            conn.close()
            return False, "Listing not found"

        subtotal = float(order['total_price'] or (order['requested_quantity'] * order['offered_price']))
        total_amount = subtotal + float(delivery_charges)
        txn_id = f"COD-FFR-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"

        cursor.execute('''
            INSERT INTO payments (
                order_id, listing_id, buyer_id, farmer_id, transaction_id,
                payment_method, amount, subtotal, delivery_charges,
                payment_status, payout_status
            ) VALUES (?, ?, ?, ?, ?, 'COD', ?, ?, ?, 'COD Pending', 'Unsettled')
        ''', (order['id'], listing['id'], order['buyer_id'], listing['farmer_id'], txn_id, total_amount, subtotal, delivery_charges))

        cursor.execute('''
            UPDATE enquiries
            SET payment_status = 'COD Pending',
                payment_method = 'COD',
                status = 'Accepted',
                delivery_charges = ?,
                updated_at = ?
            WHERE id = ?
        ''', (delivery_charges, now_str, order['id']))

        # Deduct / reserve stock
        qty = float(order['requested_quantity'])
        new_qty = max(0.0, float(listing['quantity']) - qty)
        new_status = 'Sold' if new_qty <= 0 else 'Available'
        cursor.execute('''
            UPDATE listings
            SET quantity = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        ''', (new_qty, new_status, now_str, listing['id']))

        conn.commit()
        conn.close()
        return True, txn_id
    except Exception as e:
        return False, str(e)

def request_payment_refund(payment_id, buyer_id, reason):
    """Buyer submits a refund request for an eligible transaction."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE id = ? AND buyer_id = ?", (payment_id, buyer_id))
        payment = cursor.fetchone()
        if not payment:
            conn.close()
            return False, "Payment record not found"
        if payment['payment_status'] != 'Paid':
            conn.close()
            return False, "Only completed paid orders are eligible for refunds"
        if payment['refund_status'] in ('Requested', 'Approved', 'Processed'):
            conn.close()
            return False, "Refund has already been requested or processed"

        cursor.execute('''
            UPDATE payments
            SET refund_status = 'Requested',
                refund_reason = ?,
                updated_at = ?
            WHERE id = ?
        ''', (reason, now_str, payment_id))
        conn.commit()
        conn.close()
        return True, "Refund request submitted for administrator review"
    except Exception as e:
        return False, str(e)

def process_admin_refund(payment_id, decision, notes=None):
    """Admin approves or rejects refund."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM payments WHERE id = ?", (payment_id,))
        payment = cursor.fetchone()
        if not payment:
            conn.close()
            return False, "Payment not found"

        if decision == 'Approved':
            ref_tx = f"REF-FFR-{int(time.time())}-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute('''
                UPDATE payments
                SET refund_status = 'Processed',
                    payment_status = 'Refunded',
                    refund_amount = amount,
                    refund_tx_id = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (ref_tx, now_str, payment_id))
            # Restore stock if order was cancelled
            cursor.execute("SELECT listing_id, requested_quantity FROM enquiries WHERE id = ?", (payment['order_id'],))
            enq = cursor.fetchone()
            if enq:
                cursor.execute('''
                    UPDATE listings
                    SET quantity = quantity + ?,
                        status = 'Available',
                        updated_at = ?
                    WHERE id = ?
                ''', (enq['requested_quantity'], now_str, enq['listing_id']))
                cursor.execute("UPDATE enquiries SET status = 'Cancelled', cancelled_reason = 'Refunded by Admin' WHERE id = ?", (payment['order_id'],))
        else:
            cursor.execute('''
                UPDATE payments
                SET refund_status = 'Rejected',
                    updated_at = ?
                WHERE id = ?
            ''', (now_str, payment_id))

        conn.commit()
        conn.close()
        return True, f"Refund {decision.lower()} successfully"
    except Exception as e:
        return False, str(e)

def get_buyer_payments(buyer_id):
    """Get all payments for buyer with order details."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, e.requested_quantity, e.status AS order_status,
                   l.crop_name, l.unit, l.photo, u.name AS farmer_name, u.phone AS farmer_phone
            FROM payments p
            JOIN enquiries e ON p.order_id = e.id
            JOIN listings l ON p.listing_id = l.id
            JOIN users u ON p.farmer_id = u.id
            WHERE p.buyer_id = ?
            ORDER BY p.created_at DESC
        ''', (buyer_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def get_farmer_payments(farmer_id):
    """Get payment transaction history and earnings summary for farmer."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, e.requested_quantity, e.status AS order_status,
                   l.crop_name, l.unit, u.name AS buyer_name, u.phone AS buyer_phone
            FROM payments p
            JOIN enquiries e ON p.order_id = e.id
            JOIN listings l ON p.listing_id = l.id
            JOIN users u ON p.buyer_id = u.id
            WHERE p.farmer_id = ?
            ORDER BY p.created_at DESC
        ''', (farmer_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def get_admin_payments(limit=100):
    """Get all transactions for Admin control center."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, l.crop_name,
                   b.name AS buyer_name, b.email AS buyer_email,
                   f.name AS farmer_name, f.email AS farmer_email
            FROM payments p
            JOIN listings l ON p.listing_id = l.id
            JOIN users b ON p.buyer_id = b.id
            JOIN users f ON p.farmer_id = f.id
            ORDER BY p.created_at DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def get_payment_by_order_id(order_id):
    """Retrieve payment record for an order."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, l.crop_name, l.unit, l.price_per_unit, l.photo, l.village_town, l.district,
                   b.name AS buyer_name, b.phone AS buyer_phone, b.email AS buyer_email,
                   f.name AS farmer_name, f.phone AS farmer_phone, f.email AS farmer_email,
                   e.requested_quantity, e.status AS order_status, e.delivery_address, e.delivery_preference,
                   e.created_at AS order_created_at
            FROM payments p
            JOIN listings l ON p.listing_id = l.id
            JOIN users b ON p.buyer_id = b.id
            JOIN users f ON p.farmer_id = f.id
            JOIN enquiries e ON p.order_id = e.id
            WHERE p.order_id = ?
            ORDER BY p.id DESC LIMIT 1
        ''', (order_id,))
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception:
        return None

# ==========================================
# Real-Time Stock Availability
# ==========================================

def get_available_stock(listing_id):
    """Return available quantity (quantity - reserved_quantity)."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, reserved_quantity, status FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        conn.close()
        if not row or row['status'] != 'Available':
            return 0.0
        avail = max(0.0, float(row['quantity']) - float(row['reserved_quantity'] or 0))
        return avail
    except Exception:
        return 0.0

def reserve_listing_stock(listing_id, requested_qty):
    """Safely reserve stock for pending checkout."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity, reserved_quantity FROM listings WHERE id = ?", (listing_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Produce not found"
        avail = float(row['quantity']) - float(row['reserved_quantity'] or 0)
        if requested_qty > avail:
            conn.close()
            return False, f"Only {avail:.1f} kg available in stock"
        cursor.execute('''
            UPDATE listings
            SET reserved_quantity = COALESCE(reserved_quantity, 0) + ?
            WHERE id = ?
        ''', (requested_qty, listing_id))
        conn.commit()
        conn.close()
        return True, "Stock reserved"
    except Exception as e:
        return False, str(e)

# ==========================================
# Live Market Prices & Trends
# ==========================================

def get_market_prices(crop_name=None, district=None, limit=30):
    """Fetch live agricultural market benchmark rates in Tamil Nadu."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        query = "SELECT * FROM market_prices WHERE 1=1"
        params = []
        if crop_name:
            query += " AND crop_name LIKE ?"
            params.append(f"%{crop_name}%")
        if district:
            query += " AND district = ?"
            params.append(district)
        query += " ORDER BY price_date DESC, crop_name ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

def get_crop_benchmark_price(crop_name, district=None):
    """Find closest benchmark price for a crop."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        base = crop_name.split()[0].replace(',', '').strip()
        if district:
            cursor.execute('''
                SELECT * FROM market_prices
                WHERE crop_name LIKE ? AND district = ?
                ORDER BY price_date DESC LIMIT 1
            ''', (f"%{base}%", district))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row
        cursor.execute('''
            SELECT * FROM market_prices
            WHERE crop_name LIKE ?
            ORDER BY price_date DESC LIMIT 1
        ''', (f"%{base}%",))
        row = cursor.fetchone()
        conn.close()
        return row
    except Exception:
        return None

# ==========================================
# Farmer-Buyer Live Chat & Messaging
# ==========================================

def save_chat_message(sender_id, receiver_id, message, order_id=None, listing_id=None,
                      image_filename=None, offer_price=None, offer_quantity=None):
    """Store real-time chat message between buyer and farmer."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_messages (
                sender_id, receiver_id, order_id, listing_id,
                message, image_filename, offer_price, offer_quantity,
                offer_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sender_id, receiver_id, order_id, listing_id,
            message, image_filename, offer_price, offer_quantity,
            'Pending' if offer_price else 'None'
        ))
        msg_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return {'success': True, 'message_id': msg_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_conversation_messages(user_1_id, user_2_id, order_id=None, limit=60):
    """Fetch chronological message exchange between two users."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        query = '''
            SELECT cm.*,
                   s.name AS sender_name, s.role AS sender_role,
                   r.name AS receiver_name, r.role AS receiver_role
            FROM chat_messages cm
            JOIN users s ON cm.sender_id = s.id
            JOIN users r ON cm.receiver_id = r.id
            WHERE ((cm.sender_id = ? AND cm.receiver_id = ?)
                OR (cm.sender_id = ? AND cm.receiver_id = ?))
        '''
        params = [user_1_id, user_2_id, user_2_id, user_1_id]
        if order_id:
            query += " AND (cm.order_id = ? OR cm.order_id IS NULL)"
            params.append(order_id)
        query += " ORDER BY cm.created_at ASC LIMIT ?"
        params.append(limit)
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        cursor.execute('''
            UPDATE chat_messages SET is_read = 1
            WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
        ''', (user_2_id, user_1_id))
        conn.commit()
        conn.close()
        return rows
    except Exception:
        return []

def get_user_chat_threads(user_id):
    """Retrieve all active conversations for a user."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                CASE WHEN cm.sender_id = ? THEN cm.receiver_id ELSE cm.sender_id END AS other_user_id,
                u.name AS other_user_name, u.role AS other_user_role, u.phone AS other_user_phone,
                cm.message AS last_message, cm.created_at AS last_message_at,
                cm.order_id,
                SUM(CASE WHEN cm.receiver_id = ? AND cm.is_read = 0 THEN 1 ELSE 0 END) AS unread_count
            FROM chat_messages cm
            JOIN users u ON u.id = (CASE WHEN cm.sender_id = ? THEN cm.receiver_id ELSE cm.sender_id END)
            WHERE cm.sender_id = ? OR cm.receiver_id = ?
            GROUP BY other_user_id
            ORDER BY last_message_at DESC
        ''', (user_id, user_id, user_id, user_id, user_id))
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

# ==========================================
# Agro-Climatic Weather Alerts
# ==========================================

def get_weather_alerts(district=None):
    """Fetch active agro-climatic advisories."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        if district:
            cursor.execute("SELECT * FROM weather_alerts WHERE district = ? ORDER BY id DESC", (district,))
            rows = cursor.fetchall()
            if rows:
                conn.close()
                return rows
        cursor.execute("SELECT * FROM weather_alerts ORDER BY id DESC")
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception:
        return []

if __name__ == '__main__':
    init_db()
    seed_db()
    print("Database initialized and updated successfully.")
