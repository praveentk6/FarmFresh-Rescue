import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db()
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

    # Safe Schema Migrations for existing database
    # 1. users migrations
    cursor.execute("PRAGMA table_info(users)")
    user_cols = [r[1] for r in cursor.fetchall()]
    if 'is_active' not in user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")

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

    # 3. enquiries migrations (ensure new columns & status compatibility)
    cursor.execute("PRAGMA table_info(enquiries)")
    enquiry_cols = [r[1] for r in cursor.fetchall()]
    if 'delivery_preference' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_preference TEXT DEFAULT 'Direct Pickup / Collection'")
    if 'total_price' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN total_price REAL DEFAULT 0")
    if 'updated_at' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN updated_at TIMESTAMP DEFAULT NULL")
    if 'cancelled_reason' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN cancelled_reason TEXT")

    # Migrate enquiries CHECK constraint if needed
    try:
        # Test inserting or updating status 'Rejected'
        # If strict check fails, we recreate enquiries cleanly
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='enquiries'")
        enq_sql_row = cursor.fetchone()
        if enq_sql_row and "CHECK(status IN ('Pending', 'Accepted', 'Declined', 'Completed'))" in enq_sql_row[0]:
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
                status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Accepted', 'Rejected', 'Declined', 'Ready for Collection', 'Completed', 'Cancelled')),
                cancelled_reason TEXT,
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
                message, status, cancelled_reason, created_at, updated_at
            )
            SELECT 
                id, listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
                offered_price, requested_quantity, 
                COALESCE(delivery_preference, 'Direct Pickup / Collection'),
                COALESCE(total_price, 0),
                message, status, cancelled_reason, created_at, 
                COALESCE(updated_at, created_at)
            FROM enquiries
            ''')
            cursor.execute("DROP TABLE enquiries")
            cursor.execute("ALTER TABLE enquiries_migrated RENAME TO enquiries")
            cursor.execute("PRAGMA foreign_keys = ON")
    except Exception as e:
        print(f"Enquiries migration note: {e}")

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

    # Seed Users
    admin_pw = generate_password_hash("admin123")
    farmer_pw = generate_password_hash("farmer123")
    buyer_pw = generate_password_hash("buyer123")

    users_data = [
        # Admin
        ("Platform Administrator", "admin@farmfresh.org", admin_pw, "admin", "9842100001", "Chennai Head Office", "600001", "Platform Admin"),
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

    conn.commit()

if __name__ == '__main__':
    init_db()
    seed_db()
    print("Database initialized and updated successfully.")
