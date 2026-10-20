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
        unit TEXT NOT NULL,
        price_per_unit REAL NOT NULL,
        original_price REAL,
        harvest_date DATE NOT NULL,
        village_town TEXT NOT NULL,
        district TEXT NOT NULL,
        pin_code TEXT NOT NULL,
        farmer_name TEXT NOT NULL,
        farmer_phone TEXT NOT NULL,
        whatsapp_number TEXT,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Sold', 'Inactive')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Buyer Enquiries Table
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
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Accepted', 'Declined', 'Completed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
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

    conn.commit()
    conn.close()

def seed_db():
    conn = get_db()
    cursor = conn.cursor()

    # Check if users already exist
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] > 0:
        conn.close()
        return

    # Seed Users
    # Password for all demo accounts is role + '123' (e.g., admin123, farmer123, buyer123)
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
        ("Saravana Bhavan Procurement", "saravana.hotel@gmail.com", buyer_pw, "buyer", "9840012345", "Madurai City", "625001", "Restaurant / Hotel"),
        ("Kumar Daily Fresh Mart", "kumar.mart@gmail.com", buyer_pw, "buyer", "9841122334", "RS Puram, Coimbatore", "641002", "Retail Supermarket"),
        ("Annapoorna Catering Services", "annapoorna.caterers@gmail.com", buyer_pw, "buyer", "9894455667", "Tirupur", "641601", "Catering & Events")
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
            "Rayakottai",
            "Krishnagiri",
            "635116",
            "Selvi Shanmugam",
            "9443256789",
            "9443256789",
            "Firm, naturally ripened farm-fresh red country tomatoes. 850 kg available in 34 wooden crates. Needs swift buyer clearance due to bumper harvest. Perfect for hotels, restaurants, sauce makers, and vegetable retailers.",
            "Available",
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
            "Ottanchathiram",
            "Dindigul",
            "624619",
            "Muthuvel Karuppan",
            "9842112345",
            "9842112345",
            "Top-grade pungent small onions dried and sorted into 40kg gunny bags. High shelf life if kept dry. Price discounted for bulk wholesale buyers to prevent storage loss.",
            "Available",
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
            "Ketti Valley",
            "The Nilgiris",
            "643215",
            "Ramanathan K.",
            "9789012345",
            "9789012345",
            "Sweet, crunchy high-altitude Ooty carrots washed and crated straight from the mountain slopes. Suitable for supermarkets, hotels, and cold-pressed juice shops.",
            "Available",
            one_day_ago,
            one_day_ago
        ),
        # Listing 4: 3 days old -> Needs Attention!
        (
            user_map['kandasamy.coconuts@gmail.com'],
            "Pollachi Grade-A Tender Coconuts (Elaneer)",
            "Fruits",
            "",
            1500.0,
            "Pieces",
            32.0,
            45.0,
            harvest_3d,
            "Anamalai",
            "Coimbatore",
            "642104",
            "Kandasamy P.",
            "9488123456",
            "9488123456",
            "Sweet coconut water, tender jelly pulp, freshly cut bunches from 20-year old native palm trees. Ready for direct bulk pickup or dispatch across Tamil Nadu.",
            "Available",
            three_days_ago,
            three_days_ago
        ),
        # Listing 5: Today -> New Listing!
        (
            user_map['muthu.farmer@gmail.com'],
            "Madurai Fragrant Malli (Jasmine Buds)",
            "Flowers",
            "",
            60.0,
            "kg",
            380.0,
            550.0,
            harvest_today,
            "Thiruparankundram",
            "Madurai",
            "625005",
            "Muthuvel Karuppan",
            "9842112345",
            "9842112345",
            "Intense aroma Madurai Malli buds plucked in early morning cool hours. Best for garland makers, temple trusts, and event decorators.",
            "Available",
            today_str,
            today_str
        ),
        # Listing 6: Sold Produce -> Demo Sold state & rescue metrics
        (
            user_map['selvi.farms@gmail.com'],
            "Thanjavur Ponni Raw Rice (Deluxe Harvest)",
            "Grains & Pulses",
            "",
            40.0,
            "Bags (25kg)",
            1350.0,
            1600.0,
            harvest_20d,
            "Kumbakonam",
            "Thanjavur",
            "612001",
            "Selvi Shanmugam",
            "9443256789",
            "9443256789",
            "Traditional Kaveri delta Ponni rice, double-boiled and cleaned. Successfully rescued and sold in bulk.",
            "Sold",
            five_days_ago,
            today_str
        )
    ]

    cursor.executemany('''
        INSERT INTO listings (
            farmer_id, crop_name, category, photo, quantity, unit, price_per_unit, original_price,
            harvest_date, village_town, district, pin_code, farmer_name, farmer_phone, whatsapp_number,
            description, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', listings_data)

    conn.commit()

    # Seed Sample Enquiries
    cursor.execute("SELECT id, crop_name FROM listings WHERE crop_name LIKE '%Tomatoes%'")
    tomato_listing = cursor.fetchone()

    cursor.execute("SELECT id, crop_name FROM listings WHERE crop_name LIKE '%Small Onions%'")
    onion_listing = cursor.fetchone()

    cursor.execute("SELECT id, crop_name FROM listings WHERE crop_name LIKE '%Ponni%'")
    rice_listing = cursor.fetchone()

    enquiries_data = [
        (
            tomato_listing['id'],
            user_map['saravana.hotel@gmail.com'],
            "Saravana Bhavan Procurement",
            "9840012345",
            "saravana.hotel@gmail.com",
            17.0,
            400.0,
            "Hello Selvi ji, We can take 400 kg immediately for our Madurai branches if you can arrange delivery to the bypass junction. Please confirm.",
            "Pending",
            two_days_ago := (now - timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        ),
        (
            onion_listing['id'],
            user_map['kumar.mart@gmail.com'],
            "Kumar Daily Fresh Mart",
            "9841122334",
            "kumar.mart@gmail.com",
            40.0,
            1200.0,
            "We have transport arriving near Ottanchathiram tomorrow morning. We can lift the entire 1200 kg batch at ₹40/kg instant cash payment.",
            "Accepted",
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
            "40 bags received and verified in our central warehouse. Payment cleared via NEFT. Thank you!",
            "Completed",
            four_days_ago
        )
    ]

    cursor.executemany('''
        INSERT INTO enquiries (
            listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
            offered_price, requested_quantity, message, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    seed_db()
    print("Database initialized and seeded successfully.")
