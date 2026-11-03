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

    # Farmer Offers Table (Section 2 & 3: Farmer Product Offer Workflow)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS farmer_offers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        offer_code TEXT UNIQUE NOT NULL,
        requirement_id INTEGER,
        farmer_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        listing_id INTEGER,
        crop_name TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        price_per_kg REAL NOT NULL,
        harvest_date DATE NOT NULL,
        quality_description TEXT,
        photo TEXT,
        delivery_preference TEXT DEFAULT 'Farmer Pickup',
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'Pending Buyer Review' 
            CHECK(status IN ('Pending Buyer Review', 'Accepted', 'Rejected', 'Counter Offered', 'Cancelled')),
        counter_price REAL,
        counter_quantity REAL,
        counter_notes TEXT,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requirement_id) REFERENCES buyer_requirements(id) ON DELETE SET NULL,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE SET NULL
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
    if 'order_code' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN order_code TEXT")
    if 'offer_id' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN offer_id INTEGER")
    if 'harvest_status' not in enq_cols if 'enq_cols' in locals() else 'order_code' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN harvest_status TEXT DEFAULT 'Harvest Pending'")
    if 'harvested_quantity' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN harvested_quantity REAL")
    if 'harvest_notes' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN harvest_notes TEXT")
    if 'fresh_product_image' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN fresh_product_image TEXT")
    if 'delivery_mode' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_mode TEXT DEFAULT 'Farmer Pickup'")
    if 'pickup_datetime' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN pickup_datetime TEXT")
    if 'delivery_partner' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_partner TEXT")
    if 'delivery_status' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivery_status TEXT DEFAULT 'Pending'")
    if 'handover_otp' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN handover_otp TEXT")
    if 'handover_qr_token' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN handover_qr_token TEXT")
    if 'handover_verified' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN handover_verified INTEGER DEFAULT 0")
    if 'handover_at' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN handover_at TIMESTAMP")
    if 'delivered_quantity' not in enquiry_cols:
        cursor.execute("ALTER TABLE enquiries ADD COLUMN delivered_quantity REAL")

    # 4. buyer_requirements migrations
    cursor.execute("PRAGMA table_info(buyer_requirements)")
    req_cols = [r[1] for r in cursor.fetchall()]
    if 'required_date' not in req_cols:
        cursor.execute("ALTER TABLE buyer_requirements ADD COLUMN required_date DATE")
    if 'is_verified' not in req_cols:
        cursor.execute("ALTER TABLE buyer_requirements ADD COLUMN is_verified INTEGER DEFAULT 1")
    if 'payment_terms' not in req_cols:
        cursor.execute("ALTER TABLE buyer_requirements ADD COLUMN payment_terms TEXT DEFAULT 'Payment on Delivery / Online'")

    cursor.execute("UPDATE buyer_requirements SET required_date = DATE('now', '+4 days') WHERE required_date IS NULL")
    cursor.execute("UPDATE buyer_requirements SET is_verified = 1 WHERE is_verified IS NULL")
    cursor.execute("UPDATE buyer_requirements SET payment_terms = 'Payment on Delivery / Online' WHERE payment_terms IS NULL")

    # Migrate enquiries CHECK constraint to include full lifecycle and Confirmed status
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='enquiries'")
        enq_sql_row = cursor.fetchone()
        if enq_sql_row and "'Confirmed'" not in enq_sql_row[0]:
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
                status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Accepted', 'Packed', 'Shipped', 'Ready for Pickup', 'In Transit', 'Out for Delivery', 'Delivered', 'Completed', 'Ready for Collection', 'Rejected', 'Declined', 'Cancelled', 'Processing', 'Order Placed', 'Order Accepted', 'Order Rejected')),
                cancelled_reason TEXT,
                tracking_notes TEXT,
                delivery_address TEXT,
                delivery_lat REAL,
                delivery_lng REAL,
                status_timeline TEXT,
                order_code TEXT,
                offer_id INTEGER,
                harvest_status TEXT DEFAULT 'Harvest Pending',
                harvested_quantity REAL,
                harvest_notes TEXT,
                fresh_product_image TEXT,
                delivery_mode TEXT DEFAULT 'Farmer Pickup',
                pickup_datetime TEXT,
                delivery_partner TEXT,
                delivery_status TEXT DEFAULT 'Pending',
                handover_otp TEXT,
                handover_qr_token TEXT,
                handover_verified INTEGER DEFAULT 0,
                handover_at TIMESTAMP,
                delivered_quantity REAL,
                payment_method TEXT DEFAULT 'COD',
                payment_status TEXT DEFAULT 'Unpaid',
                delivery_charges REAL DEFAULT 0,
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
                delivery_lat, delivery_lng, status_timeline, order_code, offer_id,
                harvest_status, harvested_quantity, harvest_notes, fresh_product_image,
                delivery_mode, pickup_datetime, delivery_partner, delivery_status,
                handover_otp, handover_qr_token, handover_verified, handover_at,
                delivered_quantity, payment_method, payment_status, delivery_charges,
                created_at, updated_at
            )
            SELECT 
                id, listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
                offered_price, requested_quantity, 
                COALESCE(delivery_preference, 'Direct Pickup / Collection'),
                COALESCE(total_price, 0),
                message, status, cancelled_reason, tracking_notes, delivery_address,
                delivery_lat, delivery_lng, status_timeline,
                COALESCE(order_code, 'ORD-2026-' || SUBSTR('0000' || id, -4)),
                offer_id,
                COALESCE(harvest_status, 'Harvest Pending'),
                harvested_quantity, harvest_notes, fresh_product_image,
                COALESCE(delivery_mode, 'Farmer Pickup'),
                pickup_datetime, delivery_partner,
                COALESCE(delivery_status, 'Pending'),
                COALESCE(handover_otp, PRINTF('%06d', ABS(RANDOM()) % 900000 + 100000)),
                COALESCE(handover_qr_token, HEX(RANDOMBLOB(16))),
                COALESCE(handover_verified, 0),
                handover_at, delivered_quantity,
                COALESCE(payment_method, 'COD'),
                COALESCE(payment_status, 'Unpaid'),
                COALESCE(delivery_charges, 0),
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
        cursor.execute("UPDATE enquiries SET order_code = 'ORD-2026-' || SUBSTR('0000' || id, -4) WHERE order_code IS NULL")
        cursor.execute("UPDATE enquiries SET handover_otp = PRINTF('%06d', ABS(RANDOM()) % 900000 + 100000) WHERE handover_otp IS NULL")
        cursor.execute("UPDATE enquiries SET handover_qr_token = HEX(RANDOMBLOB(16)) WHERE handover_qr_token IS NULL")
    except Exception as _e:
        pass

    # ============================================================================
    # DIRECT MEET & SELL AND SHARED RESCUE PRODUCTS MARKETPLACE TABLES
    # ============================================================================

    # 1. Shared Rescue Products Marketplace Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS rescue_products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        farmer_id INTEGER NOT NULL,
        listing_id INTEGER,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL CHECK(category IN ('Vegetables', 'Fruits', 'Grains', 'Leafy Vegetables', 'Other Agricultural Products')),
        photo TEXT,
        additional_photos TEXT,
        quantity REAL NOT NULL,
        initial_quantity REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'kg',
        original_price REAL NOT NULL,
        rescue_price REAL NOT NULL,
        discount_percent REAL DEFAULT 0,
        quality_grade TEXT NOT NULL DEFAULT 'Grade A',
        harvest_date DATE NOT NULL,
        expiry_date DATE,
        farm_location TEXT NOT NULL,
        district TEXT NOT NULL,
        pin_code TEXT,
        farmer_name TEXT NOT NULL,
        farmer_phone TEXT NOT NULL,
        whatsapp_number TEXT,
        description TEXT,
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Partially Reserved', 'Sold', 'Expired', 'Removed')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (listing_id) REFERENCES listings(id) ON DELETE SET NULL
    )
    ''')

    # 2. Direct Face-to-Face Meetings Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS direct_meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_code TEXT UNIQUE NOT NULL,
        listing_id INTEGER,
        rescue_product_id INTEGER,
        farmer_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_phone TEXT NOT NULL,
        farmer_name TEXT NOT NULL,
        farmer_phone TEXT NOT NULL,
        product_name TEXT NOT NULL,
        required_quantity REAL NOT NULL,
        proposed_date DATE NOT NULL,
        proposed_time TEXT NOT NULL,
        meeting_location TEXT NOT NULL,
        buyer_notes TEXT,
        farmer_notes TEXT,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Rescheduled', 'Completed', 'Cancelled', 'Rejected')),
        rescheduled_date DATE,
        rescheduled_time TEXT,
        rescheduled_location TEXT,
        rescheduled_by TEXT,
        cancellation_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (rescue_product_id) REFERENCES rescue_products(id) ON DELETE SET NULL
    )
    ''')

    # 3. Direct Product Inspections Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS direct_inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        inspector_id INTEGER NOT NULL,
        product_freshness TEXT,
        product_quality TEXT,
        actual_weight REAL,
        available_quantity REAL,
        packaging_condition TEXT,
        status TEXT NOT NULL DEFAULT 'Inspection Pending' CHECK(status IN ('Inspection Pending', 'Inspection in Progress', 'Approved', 'Not Approved')),
        buyer_notes TEXT,
        farmer_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES direct_meetings(id) ON DELETE CASCADE
    )
    ''')

    # 4. Direct Price Negotiations Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS direct_negotiations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        meeting_id INTEGER NOT NULL,
        farmer_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        farmer_initial_price REAL NOT NULL,
        buyer_proposed_price REAL NOT NULL,
        counter_price REAL,
        counter_by TEXT,
        final_agreed_price REAL,
        final_quantity REAL,
        total_amount REAL,
        buyer_agreed INTEGER DEFAULT 0,
        farmer_agreed INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'Negotiating' CHECK(status IN ('Negotiating', 'Agreed', 'Declined')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES direct_meetings(id) ON DELETE CASCADE
    )
    ''')

    # 5. Direct Sales, Payments & Receipts Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS direct_sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_code TEXT UNIQUE NOT NULL,
        meeting_id INTEGER,
        rescue_product_id INTEGER,
        listing_id INTEGER,
        farmer_id INTEGER NOT NULL,
        buyer_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        final_quantity REAL NOT NULL,
        agreed_price_per_kg REAL NOT NULL,
        total_amount REAL NOT NULL,
        meeting_date DATE NOT NULL,
        sale_location TEXT NOT NULL,
        payment_method TEXT NOT NULL CHECK(payment_method IN ('Cash', 'UPI', 'Bank Transfer')),
        payment_reference TEXT,
        payment_notes TEXT,
        payment_verified INTEGER DEFAULT 0,
        buyer_confirmed INTEGER DEFAULT 0,
        buyer_confirmed_at TIMESTAMP,
        farmer_confirmed INTEGER DEFAULT 0,
        farmer_confirmed_at TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'Pending Confirmation' CHECK(status IN ('Pending Confirmation', 'Confirmed', 'Completed', 'Cancelled')),
        receipt_number TEXT UNIQUE,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (meeting_id) REFERENCES direct_meetings(id) ON DELETE SET NULL,
        FOREIGN KEY (farmer_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (buyer_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # Migrations for chat_messages & listings
    cursor.execute("PRAGMA table_info(chat_messages)")
    cm_cols = [r[1] for r in cursor.fetchall()]
    if 'meeting_id' not in cm_cols:
        cursor.execute("ALTER TABLE chat_messages ADD COLUMN meeting_id INTEGER")

    cursor.execute("PRAGMA table_info(listings)")
    l_cols = [r[1] for r in cursor.fetchall()]
    if 'additional_photos' not in l_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN additional_photos TEXT")
    if 'expiry_date' not in l_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN expiry_date DATE")
    if 'rescue_price' not in l_cols:
        cursor.execute("ALTER TABLE listings ADD COLUMN rescue_price REAL")

    # Seed rescue_products from existing listings if empty
    try:
        cursor.execute("SELECT COUNT(*) FROM rescue_products")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO rescue_products (
                    farmer_id, listing_id, product_name, category, photo, quantity, initial_quantity,
                    unit, original_price, rescue_price, discount_percent, quality_grade, harvest_date,
                    expiry_date, farm_location, district, pin_code, farmer_name, farmer_phone, whatsapp_number,
                    description, status, created_at, updated_at
                )
                SELECT farmer_id, id, crop_name, 
                       CASE WHEN category IN ('Vegetables', 'Fruits', 'Grains', 'Leafy Vegetables', 'Other Agricultural Products') THEN category ELSE 'Vegetables' END,
                       photo, quantity, quantity, unit, 
                       CASE WHEN original_price IS NOT NULL AND original_price > price_per_unit THEN original_price ELSE ROUND(price_per_unit * 1.3, 2) END,
                       price_per_unit,
                       ROUND(MAX(0, ((CASE WHEN original_price IS NOT NULL AND original_price > price_per_unit THEN original_price ELSE ROUND(price_per_unit * 1.3, 2) END) - price_per_unit) / (CASE WHEN original_price IS NOT NULL AND original_price > price_per_unit THEN original_price ELSE ROUND(price_per_unit * 1.3, 2) END) * 100), 1),
                       COALESCE(quality_grade, 'Grade A'), harvest_date, estimated_freshness_date,
                       village_town, district, pin_code, farmer_name, farmer_phone, whatsapp_number,
                       description, 
                       CASE WHEN status = 'Available' THEN 'Available' ELSE 'Sold' END,
                       created_at, updated_at
                FROM listings
            """)
    except Exception as _seed_err:
        print(f"Rescue products seed notice: {_seed_err}")

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

# ============================================================================
# FARMER-TO-BUYER ORDER MANAGEMENT WORKFLOW FUNCTIONS (SECTIONS 1 TO 13)
# ============================================================================

def create_farmer_offer(farmer_id, buyer_id, crop_name, quantity, price_per_kg,
                        harvest_date, quality_description=None, photo=None,
                        delivery_preference='Farmer Pickup', notes=None,
                        requirement_id=None, listing_id=None):
    """
    Save farmer offer to buyer and return (True, offer_dict) or (False, error_msg).
    Generates unique Offer ID (OFF-2026-XXXX) and notifies the buyer.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Verify farmer exists
        cursor.execute("SELECT id, name, phone, location, district FROM users WHERE id = ?", (farmer_id,))
        farmer = cursor.fetchone()
        if not farmer:
            conn.close()
            return False, "Farmer account not found"

        # Verify buyer exists
        cursor.execute("SELECT id, name, email, phone FROM users WHERE id = ?", (buyer_id,))
        buyer = cursor.fetchone()
        if not buyer:
            conn.close()
            return False, "Buyer account not found"

        offer_code = f"OFF-2026-{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO farmer_offers (
                offer_code, requirement_id, farmer_id, buyer_id, listing_id,
                crop_name, quantity, unit, price_per_kg, harvest_date,
                quality_description, photo, delivery_preference, notes,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'kg', ?, ?, ?, ?, ?, ?, 'Pending Buyer Review', ?, ?)
        ''', (
            offer_code, requirement_id, farmer_id, buyer_id, listing_id,
            crop_name, float(quantity), float(price_per_kg), harvest_date,
            quality_description, photo, delivery_preference or 'Farmer Pickup', notes,
            now_str, now_str
        ))
        offer_id = cursor.lastrowid
        conn.commit()

        # Create in-app notification for buyer
        notif_msg = f"Farmer {farmer['name']} has sent a product offer for {quantity} kg of {crop_name} at ₹{price_per_kg}/kg (Offer #{offer_code})."
        create_notification(buyer_id, f"New Offer for {crop_name} 🌾", notif_msg, notif_type='order', link="/buyer/dashboard#offersSection")

        conn.close()
        return True, {
            'id': offer_id,
            'offer_code': offer_code,
            'farmer_id': farmer_id,
            'buyer_id': buyer_id,
            'crop_name': crop_name,
            'quantity': quantity,
            'price_per_kg': price_per_kg,
            'status': 'Pending Buyer Review'
        }
    except Exception as e:
        return False, str(e)

def get_farmer_offers(farmer_id):
    """Retrieve all offers submitted by this farmer."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fo.*, 
               u.name as buyer_name, u.phone as buyer_phone, u.email as buyer_email,
               br.business_type, br.target_price as req_target_price, br.required_quantity as req_quantity,
               e.id as order_id, e.order_code, e.status as order_status,
               e.delivery_status as order_delivery_status
        FROM farmer_offers fo
        JOIN users u ON fo.buyer_id = u.id
        LEFT JOIN buyer_requirements br ON fo.requirement_id = br.id
        LEFT JOIN enquiries e ON e.offer_id = fo.id
        WHERE fo.farmer_id = ?
        ORDER BY fo.created_at DESC, fo.id DESC
    ''', (farmer_id,))
    offers = cursor.fetchall()
    conn.close()
    return offers

def get_buyer_received_offers(buyer_id):
    """Retrieve all incoming offers received by this buyer."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fo.*,
               u.name as farmer_name, u.phone as farmer_phone, u.location as farmer_location, u.district as farmer_district,
               br.business_type, br.crop_name as req_crop_name, br.target_price as req_target_price, br.required_quantity as req_quantity,
               e.id as order_id, e.order_code, e.status as order_status
        FROM farmer_offers fo
        JOIN users u ON fo.farmer_id = u.id
        LEFT JOIN buyer_requirements br ON fo.requirement_id = br.id
        LEFT JOIN enquiries e ON e.offer_id = fo.id
        WHERE fo.buyer_id = ?
        ORDER BY fo.created_at DESC, fo.id DESC
    ''', (buyer_id,))
    offers = cursor.fetchall()
    conn.close()
    return offers

def get_offer_by_id(offer_id):
    """Retrieve a single offer with farmer and buyer details."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT fo.*,
               f.name as farmer_name, f.phone as farmer_phone, f.email as farmer_email, f.location as farmer_location, f.district as farmer_district,
               b.name as buyer_name, b.phone as buyer_phone, b.email as buyer_email, b.location as buyer_location,
               e.id as order_id, e.order_code
        FROM farmer_offers fo
        JOIN users f ON fo.farmer_id = f.id
        JOIN users b ON fo.buyer_id = b.id
        LEFT JOIN enquiries e ON e.offer_id = fo.id
        WHERE fo.id = ?
    ''', (offer_id,))
    offer = cursor.fetchone()
    conn.close()
    return offer

def accept_farmer_offer(offer_id, buyer_id):
    """
    Buyer accepts farmer offer:
    - Validates offer and prevents duplicate order creation
    - Creates unique order in enquiries with ORD-2026-XXXX code
    - Generates 6-digit Handover OTP and secure QR code token
    - Initializes the 11-stage status_timeline
    - Sets order status to Confirmed
    - Updates offer status to Accepted
    - Sends notifications to both parties
    """
    import random
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM farmer_offers WHERE id = ?", (offer_id,))
        offer = cursor.fetchone()
        if not offer:
            conn.close()
            return False, "Offer not found", None

        if offer['buyer_id'] != buyer_id:
            conn.close()
            return False, "Unauthorized: you can only accept offers sent to you", None

        # Prevent duplicate order creation if already accepted
        if offer['status'] == 'Accepted':
            cursor.execute("SELECT id, order_code FROM enquiries WHERE offer_id = ?", (offer_id,))
            existing = cursor.fetchone()
            conn.close()
            if existing:
                return True, f"Offer already accepted (Order #{existing['order_code'] or existing['id']})", existing['id']

        # Get buyer details
        cursor.execute("SELECT id, name, phone, email, location FROM users WHERE id = ?", (buyer_id,))
        buyer = cursor.fetchone()

        # Get farmer details
        cursor.execute("SELECT id, name, phone, location, district, pin_code FROM users WHERE id = ?", (offer['farmer_id'],))
        farmer = cursor.fetchone()

        # Ensure valid listing_id for relational integrity with existing modules
        listing_id = offer['listing_id']
        if not listing_id:
            cursor.execute("""
                SELECT id FROM listings 
                WHERE farmer_id = ? AND crop_name LIKE ? AND status = 'Available'
                LIMIT 1
            """, (offer['farmer_id'], f"%{offer['crop_name']}%"))
            matched = cursor.fetchone()
            if matched:
                listing_id = matched['id']
            else:
                farmer_pin = '641001'
                if farmer and 'pin_code' in farmer.keys() and farmer['pin_code']:
                    farmer_pin = str(farmer['pin_code'])
                cursor.execute("""
                    INSERT INTO listings (
                        farmer_id, crop_name, category, photo, quantity, unit,
                        price_per_unit, harvest_date, village_town, district, pin_code,
                        farmer_name, farmer_phone, description, status
                    ) VALUES (?, ?, 'Vegetables', ?, ?, 'kg', ?, ?, ?, ?, ?, ?, ?, ?, 'Available')
                """, (
                    offer['farmer_id'], offer['crop_name'], offer['photo'],
                    offer['quantity'], offer['price_per_kg'], offer['harvest_date'],
                    farmer['location'] or 'Farmgate', farmer['district'] or 'Tamil Nadu',
                    farmer_pin,
                    farmer['name'], farmer['phone'],
                    offer['notes'] or f"Harvest offer {offer['offer_code']}"
                ))
                listing_id = cursor.lastrowid

        final_qty = offer['counter_quantity'] if (offer['status'] == 'Counter Offered' and offer['counter_quantity']) else offer['quantity']
        final_price = offer['counter_price'] if (offer['status'] == 'Counter Offered' and offer['counter_price']) else offer['price_per_kg']
        total_price = round(float(final_qty) * float(final_price), 2)

        order_code = f"ORD-2026-{uuid.uuid4().hex[:6].upper()}"
        handover_otp = f"{random.randint(100000, 999999)}"
        handover_qr_token = str(uuid.uuid4())
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        initial_timeline = [
            {
                'status': 'Offer Submitted',
                'timestamp': str(offer['created_at']),
                'actor': 'Farmer',
                'note': f"Farmer submitted offer {offer['offer_code']} for {offer['quantity']} kg @ ₹{offer['price_per_kg']}/kg"
            },
            {
                'status': 'Buyer Accepted',
                'timestamp': now_str,
                'actor': 'Buyer',
                'note': f"Buyer accepted offer. Final terms: {final_qty} kg @ ₹{final_price}/kg"
            },
            {
                'status': 'Order Confirmed',
                'timestamp': now_str,
                'actor': 'System',
                'note': f"Order #{order_code} confirmed. Total value: ₹{total_price:,.2f}"
            }
        ]
        timeline_json = json.dumps(initial_timeline)

        cursor.execute('''
            INSERT INTO enquiries (
                listing_id, buyer_id, buyer_name, buyer_phone, buyer_email,
                offered_price, requested_quantity, delivery_preference, total_price,
                message, status, order_code, offer_id,
                harvest_status, delivery_mode, delivery_status,
                handover_otp, handover_qr_token, handover_verified,
                payment_method, payment_status, status_timeline,
                created_at, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, 'Confirmed', ?, ?,
                'Harvest Pending', ?, 'Pending',
                ?, ?, 0,
                'COD', 'Unpaid', ?,
                ?, ?
            )
        ''', (
            listing_id, buyer['id'], buyer['name'], buyer['phone'], buyer['email'],
            final_price, final_qty, offer['delivery_preference'] or 'Farmer Pickup', total_price,
            f"Order confirmed from offer {offer['offer_code']}", order_code, offer['id'],
            offer['delivery_preference'] or 'Farmer Pickup',
            handover_otp, handover_qr_token, timeline_json,
            now_str, now_str
        ))
        order_id = cursor.lastrowid

        # Update offer status to Accepted
        cursor.execute('''
            UPDATE farmer_offers
            SET status = 'Accepted', updated_at = ?
            WHERE id = ?
        ''', (now_str, offer_id))

        conn.commit()

        # Notify Farmer
        notif_msg = f"🎉 Great news! Buyer {buyer['name']} accepted your offer for {final_qty} kg of {offer['crop_name']}. Order #{order_code} is confirmed!"
        create_notification(offer['farmer_id'], "Offer Accepted! 🤝 Order Confirmed", notif_msg, notif_type='order', link=f"/order/track/{order_id}")

        # Notify Buyer
        buyer_notif = f"Order #{order_code} confirmed with farmer {farmer['name']}. Total: ₹{total_price:,.2f}."
        create_notification(buyer['id'], f"Order #{order_code} Confirmed ✅", buyer_notif, notif_type='order', link=f"/order/track/{order_id}")

        conn.close()
        return True, "Offer accepted and order confirmed!", order_id
    except Exception as e:
        return False, str(e), None

def reject_farmer_offer(offer_id, buyer_id, rejection_reason):
    """Buyer rejects a farmer offer with a reason."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farmer_offers WHERE id = ?", (offer_id,))
        offer = cursor.fetchone()
        if not offer or offer['buyer_id'] != buyer_id:
            conn.close()
            return False, "Offer not found or unauthorized"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE farmer_offers
            SET status = 'Rejected', rejection_reason = ?, updated_at = ?
            WHERE id = ?
        ''', (rejection_reason or 'Buyer declined this offer at this time', now_str, offer_id))
        conn.commit()

        # Notify farmer
        create_notification(
            offer['farmer_id'],
            f"Offer Update: {offer['crop_name']}",
            f"Buyer was unable to accept Offer #{offer['offer_code']}. Reason: {rejection_reason or 'Price / Terms mismatch'}.",
            notif_type='info',
            link="/farmer/dashboard#offersSection"
        )
        conn.close()
        return True, "Offer rejected"
    except Exception as e:
        return False, str(e)

def counter_farmer_offer(offer_id, buyer_id, counter_price, counter_quantity, counter_notes=None):
    """Buyer proposes a Counter Offer with adjusted price and/or quantity."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farmer_offers WHERE id = ?", (offer_id,))
        offer = cursor.fetchone()
        if not offer or offer['buyer_id'] != buyer_id:
            conn.close()
            return False, "Offer not found or unauthorized"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            UPDATE farmer_offers
            SET status = 'Counter Offered',
                counter_price = ?,
                counter_quantity = ?,
                counter_notes = ?,
                updated_at = ?
            WHERE id = ?
        ''', (float(counter_price), float(counter_quantity), counter_notes, now_str, offer_id))
        conn.commit()

        # Notify farmer
        notif_msg = f"Buyer sent a Counter Offer for #{offer['offer_code']}: ₹{counter_price}/kg for {counter_quantity} kg. Review and respond in your dashboard."
        create_notification(
            offer['farmer_id'],
            f"Counter Offer Received: {offer['crop_name']} 💬",
            notif_msg,
            notif_type='order',
            link="/farmer/dashboard#offersSection"
        )
        conn.close()
        return True, "Counter offer sent to farmer"
    except Exception as e:
        return False, str(e)

def farmer_respond_counter_offer(offer_id, farmer_id, action):
    """Farmer accepts or declines a buyer's counter offer."""
    if action == 'accept':
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM farmer_offers WHERE id = ?", (offer_id,))
        offer = cursor.fetchone()
        conn.close()
        if not offer or offer['farmer_id'] != farmer_id:
            return False, "Offer not found or unauthorized", None
        return accept_farmer_offer(offer_id, offer['buyer_id'])
    else:
        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("UPDATE farmer_offers SET status = 'Rejected', updated_at = ? WHERE id = ? AND farmer_id = ?", (now_str, offer_id, farmer_id))
        conn.commit()
        conn.close()
        return True, "Counter offer declined", None

def update_order_harvest_and_quality(order_id, harvest_status, harvested_qty=None, harvest_notes=None, fresh_image=None, actor='Farmer'):
    """
    Farmer updates harvest progress:
    - 'Harvest Pending'
    - 'Harvesting in Progress'
    - 'Ready for Quality Check'
    - 'Quality Approved'
    Appends entry to 11-stage status_timeline and notifies buyer.
    """
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timeline = []
        if order['status_timeline']:
            try:
                timeline = json.loads(order['status_timeline'])
            except Exception:
                timeline = []

        timeline_note = harvest_notes or f"Harvest status updated to {harvest_status}"
        if harvested_qty:
            timeline_note += f" (Harvested weight: {harvested_qty} kg)"

        milestone_status = harvest_status
        if harvest_status == 'Harvesting in Progress':
            milestone_status = 'Harvesting Started'

        timeline.append({
            'status': milestone_status,
            'timestamp': now_str,
            'actor': actor,
            'note': timeline_note
        })

        cursor.execute('''
            UPDATE enquiries
            SET harvest_status = ?,
                harvested_quantity = COALESCE(?, harvested_quantity),
                harvest_notes = COALESCE(?, harvest_notes),
                fresh_product_image = COALESCE(?, fresh_product_image),
                status_timeline = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            harvest_status,
            float(harvested_qty) if harvested_qty else None,
            harvest_notes,
            fresh_image,
            json.dumps(timeline),
            now_str,
            order_id
        ))
        conn.commit()

        # Notify buyer
        if harvest_status == 'Ready for Quality Check':
            notif_title = f"Quality Check Ready: Order #{order['order_code'] or order['id']} 🔍"
            notif_msg = f"Farmer has harvested fresh produce ({harvested_qty or order['requested_quantity']} kg). Please review and approve quality."
        else:
            notif_title = f"Harvest Update: Order #{order['order_code'] or order['id']} 🌾"
            notif_msg = f"Harvest progress: '{harvest_status}'."
        create_notification(order['buyer_id'], notif_title, notif_msg, notif_type='order', link=f"/order/track/{order_id}")

        conn.close()
        return True, "Harvest & Quality updated successfully"
    except Exception as e:
        return False, str(e)

def buyer_quality_decision(order_id, buyer_id, decision, notes=None):
    """Buyer approves produce quality or reports an issue."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order or order['buyer_id'] != buyer_id:
            conn.close()
            return False, "Order not found or unauthorized"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timeline = []
        if order['status_timeline']:
            try:
                timeline = json.loads(order['status_timeline'])
            except Exception:
                timeline = []

        if decision == 'approve':
            new_harvest_status = 'Quality Approved'
            timeline.append({
                'status': 'Quality Approved',
                'timestamp': now_str,
                'actor': 'Buyer',
                'note': notes or "Buyer reviewed and approved produce freshness and quality."
            })
            notif_title = f"Quality Approved! Order #{order['order_code'] or order['id']} ✅"
            notif_msg = "Buyer has approved produce quality. You can now schedule pickup / delivery."
        else:
            new_harvest_status = 'Quality Issue'
            timeline.append({
                'status': 'Quality Issue Raised',
                'timestamp': now_str,
                'actor': 'Buyer',
                'note': notes or "Buyer raised a quality concern on the harvest."
            })
            notif_title = f"Quality Concern on Order #{order['order_code'] or order['id']} ⚠️"
            notif_msg = f"Buyer reported: {notes or 'Please check fresh harvest details.'}"

        cursor.execute('''
            UPDATE enquiries
            SET harvest_status = ?,
                status_timeline = ?,
                updated_at = ?
            WHERE id = ?
        ''', (new_harvest_status, json.dumps(timeline), now_str, order_id))
        conn.commit()

        cursor.execute("SELECT farmer_id FROM listings WHERE id = ?", (order['listing_id'],))
        listing = cursor.fetchone()
        if listing:
            create_notification(listing['farmer_id'], notif_title, notif_msg, notif_type='urgent_risk' if decision != 'approve' else 'order', link=f"/order/track/{order_id}")

        conn.close()
        return True, "Quality decision recorded successfully"
    except Exception as e:
        return False, str(e)

def update_order_delivery_schedule(order_id, delivery_mode=None, pickup_datetime=None,
                                    delivery_partner=None, delivery_status=None,
                                    notes=None, actor='Buyer'):
    """Update pickup and delivery logistics schedule and status."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT e.*, l.farmer_id FROM enquiries e JOIN listings l ON e.listing_id = l.id WHERE e.id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timeline = []
        if order['status_timeline']:
            try:
                timeline = json.loads(order['status_timeline'])
            except Exception:
                timeline = []

        if delivery_status:
            timeline_note = notes or f"Delivery status updated to {delivery_status}"
            timeline.append({
                'status': delivery_status,
                'timestamp': now_str,
                'actor': actor,
                'note': timeline_note
            })

        cursor.execute('''
            UPDATE enquiries
            SET delivery_mode = COALESCE(?, delivery_mode),
                pickup_datetime = COALESCE(?, pickup_datetime),
                delivery_partner = COALESCE(?, delivery_partner),
                delivery_status = COALESCE(?, delivery_status),
                status = CASE 
                    WHEN ? IN ('In Transit', 'Out for Delivery') THEN 'In Transit'
                    WHEN ? = 'Delivered' THEN 'Delivered'
                    ELSE status END,
                status_timeline = ?,
                updated_at = ?
            WHERE id = ?
        ''', (
            delivery_mode, pickup_datetime, delivery_partner, delivery_status,
            delivery_status, delivery_status,
            json.dumps(timeline), now_str, order_id
        ))
        conn.commit()

        msg = f"Logistics update for Order #{order['order_code'] or order['id']}: {delivery_status or delivery_mode}."
        create_notification(order['buyer_id'], "Logistics Update 🚚", msg, notif_type='order', link=f"/order/track/{order_id}")
        create_notification(order['farmer_id'], "Logistics Update 🚚", msg, notif_type='order', link=f"/order/track/{order_id}")

        conn.close()
        return True, "Delivery logistics updated successfully"
    except Exception as e:
        return False, str(e)

def verify_order_handover(order_id, otp_or_token, delivered_quantity, user_id=None):
    """
    Secure product handover verification:
    - Validates 6-digit OTP or QR token
    - Prevents duplicate verification
    - Records delivered_quantity and timestamp
    - Updates order status to Delivered (or Completed if paid)
    - Appends Delivered milestone to 11-stage timeline
    """
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.*, l.farmer_id 
            FROM enquiries e
            JOIN listings l ON e.listing_id = l.id
            WHERE e.id = ?
        """, (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return False, "Order not found"

        if order['handover_verified'] == 1:
            conn.close()
            return False, f"Handover was already verified on {order['handover_at']}"

        entered = str(otp_or_token).strip()
        expected_otp = str(order['handover_otp']).strip() if order['handover_otp'] else None
        expected_token = str(order['handover_qr_token']).strip() if order['handover_qr_token'] else None

        if entered != expected_otp and entered != expected_token:
            conn.close()
            return False, "Invalid Handover OTP or QR Code. Please double-check with counterpart."

        try:
            deliv_qty = float(delivered_quantity)
            if deliv_qty <= 0:
                conn.close()
                return False, "Delivered quantity must be greater than 0 kg"
        except (ValueError, TypeError):
            conn.close()
            return False, "Please provide a valid delivered quantity in kg"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        timeline = []
        if order['status_timeline']:
            try:
                timeline = json.loads(order['status_timeline'])
            except Exception:
                timeline = []

        timeline.append({
            'status': 'Delivered',
            'timestamp': now_str,
            'actor': 'Counterparties',
            'note': f"Product Handover Verified via OTP. Delivered Quantity: {deliv_qty} kg"
        })

        is_paid = order['payment_status'] in ['Paid', 'Payment Verified']
        new_status = 'Completed' if is_paid else 'Delivered'
        if is_paid:
            timeline.append({
                'status': 'Order Completed',
                'timestamp': now_str,
                'actor': 'System',
                'note': "Both handover verification and payment are complete. Order successfully fulfilled."
            })

        cursor.execute('''
            UPDATE enquiries
            SET handover_verified = 1,
                handover_at = ?,
                delivered_quantity = ?,
                delivery_status = 'Delivered',
                status = ?,
                status_timeline = ?,
                updated_at = ?
            WHERE id = ?
        ''', (now_str, deliv_qty, new_status, json.dumps(timeline), now_str, order_id))

        conn.commit()

        # Notify both parties
        title = f"Handover Verified! Order #{order['order_code'] or order['id']} 🤝"
        msg = f"Delivery verified successfully ({deliv_qty} kg received)."
        create_notification(order['farmer_id'], title, msg, notif_type='order', link=f"/order/track/{order_id}")
        create_notification(order['buyer_id'], title, msg, notif_type='order', link=f"/order/track/{order_id}")

        conn.close()
        return True, "Product handover verified successfully!"
    except Exception as e:
        return False, str(e)

def build_11_stage_timeline(order, timeline_entries=None):
    """
    Constructs the 11-stage vertical progress timeline:
    1. Offer Submitted
    2. Buyer Accepted
    3. Order Confirmed
    4. Harvesting Started
    5. Quality Approved
    6. Pickup Scheduled
    7. Product Picked Up
    8. In Transit
    9. Delivered
    10. Payment Verified
    11. Order Completed
    """
    import json
    order = dict(order) if order is not None else {}
    if timeline_entries is None and order.get('status_timeline'):
        try:
            timeline_entries = json.loads(order['status_timeline'])
        except Exception:
            timeline_entries = []
    timeline_entries = timeline_entries or []

    entry_map = {}
    for entry in timeline_entries:
        status_name = (entry.get('status') or '').strip().lower()
        entry_map[status_name] = entry

    stages = [
        {'id': 1, 'name': 'Offer Submitted', 'icon': '📝', 'default_actor': 'Farmer'},
        {'id': 2, 'name': 'Buyer Accepted', 'icon': '🤝', 'default_actor': 'Buyer'},
        {'id': 3, 'name': 'Order Confirmed', 'icon': '✅', 'default_actor': 'System'},
        {'id': 4, 'name': 'Harvesting Started', 'icon': '🌾', 'default_actor': 'Farmer'},
        {'id': 5, 'name': 'Quality Approved', 'icon': '🔍', 'default_actor': 'Buyer'},
        {'id': 6, 'name': 'Pickup Scheduled', 'icon': '📅', 'default_actor': 'Buyer'},
        {'id': 7, 'name': 'Product Picked Up', 'icon': '📦', 'default_actor': 'Logistics'},
        {'id': 8, 'name': 'In Transit', 'icon': '🚚', 'default_actor': 'Logistics'},
        {'id': 9, 'name': 'Delivered', 'icon': '📍', 'default_actor': 'Farmer & Buyer'},
        {'id': 10, 'name': 'Payment Verified', 'icon': '💳', 'default_actor': 'Razorpay / Bank'},
        {'id': 11, 'name': 'Order Completed', 'icon': '🎉', 'default_actor': 'System'}
    ]

    status = (order.get('status') or '').strip()
    harvest_status = (order.get('harvest_status') or '').strip()
    delivery_status = (order.get('delivery_status') or '').strip()
    payment_status = (order.get('payment_status') or '').strip()
    handover_verified = bool(order.get('handover_verified'))

    completed_flags = [False] * 12

    # 1. Offer Submitted
    if 'offer submitted' in entry_map or order.get('offer_id'):
        completed_flags[1] = True
    else:
        completed_flags[1] = True

    # 2. Buyer Accepted
    if 'buyer accepted' in entry_map or status in ['Confirmed', 'Accepted', 'Packed', 'Shipped', 'Delivered', 'Completed', 'Ready for Pickup', 'In Transit']:
        completed_flags[2] = True

    # 3. Order Confirmed
    if 'order confirmed' in entry_map or status in ['Confirmed', 'Accepted', 'Packed', 'Shipped', 'Delivered', 'Completed', 'Ready for Pickup', 'In Transit']:
        completed_flags[3] = True

    # 4. Harvesting Started
    if 'harvesting started' in entry_map or 'harvesting in progress' in entry_map or harvest_status in ['Harvesting in Progress', 'Ready for Quality Check', 'Quality Approved']:
        completed_flags[4] = True

    # 5. Quality Approved
    if 'quality approved' in entry_map or harvest_status == 'Quality Approved':
        completed_flags[5] = True

    # 6. Pickup Scheduled
    if 'pickup scheduled' in entry_map or order.get('pickup_datetime') or delivery_status in ['Pickup Scheduled', 'Ready for Pickup', 'Picked Up', 'In Transit', 'Out for Delivery', 'Delivered']:
        completed_flags[6] = True

    # 7. Product Picked Up
    if 'product picked up' in entry_map or 'picked up' in entry_map or delivery_status in ['Picked Up', 'In Transit', 'Out for Delivery', 'Delivered'] or status in ['Packed', 'Shipped', 'Delivered', 'Completed']:
        completed_flags[7] = True

    # 8. In Transit
    if 'in transit' in entry_map or 'out for delivery' in entry_map or delivery_status in ['In Transit', 'Out for Delivery', 'Delivered'] or status in ['Shipped', 'Delivered', 'Completed']:
        completed_flags[8] = True

    # 9. Delivered
    if 'delivered' in entry_map or handover_verified or delivery_status == 'Delivered' or status in ['Delivered', 'Completed']:
        completed_flags[9] = True

    # 10. Payment Verified
    if 'payment verified' in entry_map or payment_status in ['Paid', 'Payment Verified', 'COD Pending', 'COD Verified']:
        completed_flags[10] = True

    # 11. Order Completed
    if 'order completed' in entry_map or (completed_flags[9] and completed_flags[10]) or status == 'Completed':
        completed_flags[11] = True

    active_stage_id = 11
    for st in stages:
        if not completed_flags[st['id']]:
            active_stage_id = st['id']
            break

    result = []
    for st in stages:
        sid = st['id']
        is_done = completed_flags[sid]
        is_active = (sid == active_stage_id and not completed_flags[11]) or (sid == 11 and completed_flags[11])

        matched_entry = entry_map.get(st['name'].lower())
        timestamp = matched_entry.get('timestamp') if matched_entry else None
        note = matched_entry.get('note') if matched_entry else None
        actor = matched_entry.get('actor') if matched_entry else st['default_actor']

        if not timestamp and is_done:
            timestamp = str(order.get('created_at') or '')

        if not note:
            if is_done:
                note = f"{st['name']} completed successfully."
            elif is_active:
                note = f"Action in progress: awaiting {st['default_actor'].lower()}."
            else:
                note = f"Pending previous stages."

        result.append({
            'step_num': sid,
            'name': st['name'],
            'icon': st['icon'],
            'actor': actor,
            'is_completed': is_done,
            'is_current': is_active and not is_done,
            'is_pending': not is_done and not is_active,
            'timestamp': timestamp,
            'note': note
        })

    return result


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

# ============================================================================
# SHARED RESCUE PRODUCTS MARKETPLACE & DIRECT MEET & SELL WORKFLOW MODULE
# ============================================================================

def create_rescue_product(farmer_id, product_name, category, quantity, original_price,
                          rescue_price, harvest_date, farm_location, district, pin_code,
                          description, quality_grade='Grade A', expiry_date=None,
                          photo=None, additional_photos=None, whatsapp_number=None):
    """
    Create a new shared rescue product in the database.
    Visible to BOTH Farmers and Buyers in real-time from the same table.
    Also synchronizes with listings table for platform-wide compatibility.
    """
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT id, name, phone, location, district, pin_code FROM users WHERE id = ?", (farmer_id,))
        farmer = cursor.fetchone()
        if not farmer:
            conn.close()
            return False, "Farmer account not found", None

        qty = float(quantity)
        orig_p = float(original_price)
        resc_p = float(rescue_price)
        if qty <= 0:
            conn.close()
            return False, "Quantity must be greater than 0 kg", None
        if resc_p <= 0:
            conn.close()
            return False, "Rescue price must be greater than 0", None

        discount_pct = round(((orig_p - resc_p) / orig_p) * 100, 1) if orig_p > 0 else 0
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        photos_json = json.dumps(additional_photos) if isinstance(additional_photos, list) else (additional_photos or '[]')
        loc = farm_location or farmer['location'] or 'Farmgate'
        dist = district or farmer['district'] or 'Tamil Nadu'
        pin = pin_code or farmer['pin_code'] or '641001'
        phone = farmer['phone'] or '9876543210'
        w_phone = whatsapp_number or phone

        # 1. Insert into listings table for platform interoperability
        cursor.execute("""
            INSERT INTO listings (
                farmer_id, crop_name, category, photo, quantity, unit,
                price_per_unit, original_price, harvest_date, estimated_freshness_date,
                village_town, district, pin_code, farmer_name, farmer_phone,
                whatsapp_number, description, quality_grade, urgency_level,
                status, rescued_from_waste, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'kg', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Normal', 'Available', 0, ?, ?)
        """, (
            farmer_id, product_name, category, photo, qty,
            resc_p, orig_p, harvest_date, expiry_date,
            loc, dist, pin, farmer['name'], phone,
            w_phone, description, quality_grade, now_str, now_str
        ))
        listing_id = cursor.lastrowid

        # 2. Insert into rescue_products shared marketplace table
        cursor.execute("""
            INSERT INTO rescue_products (
                farmer_id, listing_id, product_name, category, photo, additional_photos,
                quantity, initial_quantity, unit, original_price, rescue_price,
                discount_percent, quality_grade, harvest_date, expiry_date,
                farm_location, district, pin_code, farmer_name, farmer_phone,
                whatsapp_number, description, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'kg', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Available', ?, ?)
        """, (
            farmer_id, listing_id, product_name, category, photo, photos_json,
            qty, qty, orig_p, resc_p, discount_pct, quality_grade, harvest_date,
            expiry_date, loc, dist, pin, farmer['name'], phone,
            w_phone, description, now_str, now_str
        ))
        product_id = cursor.lastrowid
        conn.commit()

        # Create activity log
        cursor.execute("""
            INSERT INTO activity_logs (action, details, user_email)
            VALUES (?, ?, ?)
        """, ('RESCUE_PRODUCT_ADDED', f"Added rescue product {product_name} ({qty} kg @ ₹{resc_p}/kg)", farmer['name']))
        conn.commit()
        conn.close()

        return True, "Rescue product published successfully to shared marketplace!", product_id
    except Exception as e:
        return False, str(e), None

def get_shared_rescue_products(filters=None, sort_by='recent'):
    """
    Retrieve active rescue products visible to BOTH Farmers and Buyers in real-time.
    Automatically filters out expired products.
    """
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Auto-update status for expired products
        cursor.execute("""
            UPDATE rescue_products 
            SET status = 'Expired', updated_at = CURRENT_TIMESTAMP
            WHERE expiry_date IS NOT NULL AND date(expiry_date) < date('now') AND status = 'Available'
        """)
        conn.commit()

        query = """
            SELECT rp.*, u.email as farmer_email, u.location as farmer_default_location
            FROM rescue_products rp
            JOIN users u ON rp.farmer_id = u.id
            WHERE rp.status IN ('Available', 'Partially Reserved')
              AND rp.quantity > 0
              AND (rp.expiry_date IS NULL OR date(rp.expiry_date) >= date('now'))
        """
        params = []
        filters = filters or {}

        if filters.get('category') and filters['category'] != 'All':
            query += " AND rp.category = ?"
            params.append(filters['category'])

        if filters.get('district') and filters['district'] != 'All':
            query += " AND (rp.district LIKE ? OR rp.farm_location LIKE ?)"
            params.extend([f"%{filters['district']}%", f"%{filters['district']}%"])

        if filters.get('quality_grade') and filters['quality_grade'] != 'All':
            query += " AND rp.quality_grade = ?"
            params.append(filters['quality_grade'])

        if filters.get('min_price'):
            try:
                query += " AND rp.rescue_price >= ?"
                params.append(float(filters['min_price']))
            except (ValueError, TypeError):
                pass

        if filters.get('max_price'):
            try:
                query += " AND rp.rescue_price <= ?"
                params.append(float(filters['max_price']))
            except (ValueError, TypeError):
                pass

        if filters.get('min_qty'):
            try:
                query += " AND rp.quantity >= ?"
                params.append(float(filters['min_qty']))
            except (ValueError, TypeError):
                pass

        if filters.get('search_q'):
            q_pat = f"%{filters['search_q'].strip()}%"
            query += " AND (rp.product_name LIKE ? OR rp.description LIKE ? OR rp.farmer_name LIKE ? OR rp.farm_location LIKE ?)"
            params.extend([q_pat, q_pat, q_pat, q_pat])

        # Sorting
        if sort_by == 'lowest_price':
            query += " ORDER BY rp.rescue_price ASC, rp.created_at DESC"
        elif sort_by == 'highest_qty':
            query += " ORDER BY rp.quantity DESC, rp.created_at DESC"
        elif sort_by == 'discount':
            query += " ORDER BY rp.discount_percent DESC, rp.created_at DESC"
        else: # recent
            query += " ORDER BY rp.created_at DESC, rp.id DESC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()

        products = []
        for r in rows:
            p_dict = dict(r)
            # Parse additional photos
            try:
                p_dict['photos_list'] = json.loads(p_dict.get('additional_photos') or '[]')
            except Exception:
                p_dict['photos_list'] = []
            products.append(p_dict)
        return products
    except Exception as e:
        print(f"Error fetching shared rescue products: {e}")
        return []

def get_rescue_product_by_id(product_id):
    """Retrieve full details of a single rescue product with farmer info."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rp.*, u.email as farmer_email, u.phone as farmer_user_phone,
                   u.location as farmer_base_location, u.created_at as farmer_joined_at
            FROM rescue_products rp
            JOIN users u ON rp.farmer_id = u.id
            WHERE rp.id = ?
        """, (product_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        p_dict = dict(row)
        try:
            p_dict['photos_list'] = json.loads(p_dict.get('additional_photos') or '[]')
        except Exception:
            p_dict['photos_list'] = []
        return p_dict
    except Exception as e:
        print(f"Error fetching product {product_id}: {e}")
        return None

def get_farmer_rescue_products(farmer_id):
    """Retrieve all rescue products uploaded by a specific farmer."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM rescue_products 
            WHERE farmer_id = ? 
            ORDER BY created_at DESC, id DESC
        """, (farmer_id,))
        rows = cursor.fetchall()
        conn.close()

        result = []
        for r in rows:
            d = dict(r)
            try:
                d['photos_list'] = json.loads(d.get('additional_photos') or '[]')
            except Exception:
                d['photos_list'] = []
            result.append(d)
        return result
    except Exception:
        return []

def update_rescue_product(product_id, farmer_id, data):
    """Farmer updates their rescue product details."""
    import json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM rescue_products WHERE id = ? AND farmer_id = ?", (product_id, farmer_id))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return False, "Product not found or unauthorized"

        orig_p = float(data.get('original_price', existing['original_price']))
        resc_p = float(data.get('rescue_price', existing['rescue_price']))
        qty = float(data.get('quantity', existing['quantity']))
        discount_pct = round(((orig_p - resc_p) / orig_p) * 100, 1) if orig_p > 0 else 0
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        photos_json = existing['additional_photos']
        if 'additional_photos' in data:
            if isinstance(data['additional_photos'], list):
                photos_json = json.dumps(data['additional_photos'])
            else:
                photos_json = data['additional_photos']

        cursor.execute("""
            UPDATE rescue_products
            SET product_name = ?,
                category = ?,
                quantity = ?,
                original_price = ?,
                rescue_price = ?,
                discount_percent = ?,
                quality_grade = ?,
                harvest_date = ?,
                expiry_date = ?,
                farm_location = ?,
                district = ?,
                description = ?,
                status = ?,
                photo = COALESCE(?, photo),
                additional_photos = ?,
                updated_at = ?
            WHERE id = ? AND farmer_id = ?
        """, (
            data.get('product_name', existing['product_name']),
            data.get('category', existing['category']),
            qty, orig_p, resc_p, discount_pct,
            data.get('quality_grade', existing['quality_grade']),
            data.get('harvest_date', existing['harvest_date']),
            data.get('expiry_date', existing['expiry_date']),
            data.get('farm_location', existing['farm_location']),
            data.get('district', existing['district']),
            data.get('description', existing['description']),
            data.get('status', existing['status']),
            data.get('photo'),
            photos_json,
            now_str,
            product_id, farmer_id
        ))

        # Sync listings table
        if existing['listing_id']:
            cursor.execute("""
                UPDATE listings
                SET crop_name = ?, category = ?, quantity = ?,
                    price_per_unit = ?, original_price = ?,
                    harvest_date = ?, estimated_freshness_date = ?,
                    village_town = ?, district = ?, description = ?,
                    quality_grade = ?, photo = COALESCE(?, photo),
                    status = CASE WHEN ? = 'Sold' THEN 'Sold' ELSE 'Available' END,
                    updated_at = ?
                WHERE id = ?
            """, (
                data.get('product_name', existing['product_name']),
                data.get('category', existing['category']),
                qty, resc_p, orig_p,
                data.get('harvest_date', existing['harvest_date']),
                data.get('expiry_date', existing['expiry_date']),
                data.get('farm_location', existing['farm_location']),
                data.get('district', existing['district']),
                data.get('description', existing['description']),
                data.get('quality_grade', existing['quality_grade']),
                data.get('photo'),
                data.get('status', existing['status']),
                now_str,
                existing['listing_id']
            ))

        conn.commit()
        conn.close()
        return True, "Product updated successfully"
    except Exception as e:
        return False, str(e)

def delete_rescue_product(product_id, farmer_id):
    """Farmer deletes or marks product as Removed."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT listing_id FROM rescue_products WHERE id = ? AND farmer_id = ?", (product_id, farmer_id))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False, "Product not found or unauthorized"

        cursor.execute("UPDATE rescue_products SET status = 'Removed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (product_id,))
        if row['listing_id']:
            cursor.execute("UPDATE listings SET status = 'Inactive', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (row['listing_id'],))
        conn.commit()
        conn.close()
        return True, "Product removed from marketplace"
    except Exception as e:
        return False, str(e)

# ----------------------------------------------------------------------------
# DIRECT MEET & SELL: MEETINGS, INSPECTION, NEGOTIATION, SALE, RECEIPT
# ----------------------------------------------------------------------------

def create_direct_meeting(buyer_id, product_id, required_quantity, proposed_date, proposed_time,
                          meeting_location, buyer_notes=None):
    """
    Buyer schedules a direct face-to-face farmgate meeting with the farmer.
    Generates unique meeting code MTG-2026-XXXX and notifies the farmer.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()

        # Buyer info
        cursor.execute("SELECT id, name, phone, email, location FROM users WHERE id = ?", (buyer_id,))
        buyer = cursor.fetchone()
        if not buyer:
            conn.close()
            return False, "Buyer account not found", None

        # Product info
        cursor.execute("""
            SELECT rp.*, u.name as farmer_name, u.phone as farmer_phone
            FROM rescue_products rp
            JOIN users u ON rp.farmer_id = u.id
            WHERE rp.id = ?
        """, (product_id,))
        prod = cursor.fetchone()
        if not prod:
            conn.close()
            return False, "Produce item not found", None

        req_qty = float(required_quantity)
        if req_qty <= 0:
            conn.close()
            return False, "Requested quantity must be greater than 0 kg", None

        if req_qty > float(prod['quantity']):
            conn.close()
            return False, f"Requested quantity ({req_qty} kg) exceeds available stock ({prod['quantity']} kg)", None

        meeting_code = f"MTG-2026-{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        loc = meeting_location or prod['farm_location'] or 'Farmer Farmgate'

        cursor.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, rescue_product_id, farmer_id, buyer_id,
                buyer_name, buyer_phone, farmer_name, farmer_phone, product_name,
                required_quantity, proposed_date, proposed_time, meeting_location,
                buyer_notes, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?)
        """, (
            meeting_code, prod['listing_id'], prod['id'], prod['farmer_id'], buyer_id,
            buyer['name'], buyer['phone'], prod['farmer_name'], prod['farmer_phone'],
            prod['product_name'], req_qty, proposed_date, proposed_time, loc,
            buyer_notes, now_str, now_str
        ))
        meeting_id = cursor.lastrowid
        conn.commit()

        # Send in-app notification to the farmer
        notif_msg = f"Buyer {buyer['name']} requested a direct meeting on {proposed_date} at {proposed_time} to inspect {req_qty} kg of {prod['product_name']}."
        create_notification(
            prod['farmer_id'],
            f"Direct Meeting Request: {prod['product_name']} 🤝",
            notif_msg,
            notif_type='order',
            link=f"/meeting/{meeting_id}"
        )
        conn.close()

        return True, "Direct meeting request sent to farmer!", {
            'id': meeting_id,
            'meeting_code': meeting_code,
            'farmer_name': prod['farmer_name'],
            'product_name': prod['product_name'],
            'status': 'Pending'
        }
    except Exception as e:
        return False, str(e), None

def get_meeting_by_id(meeting_id):
    """Fetch complete meeting record with inspection, negotiation, and sale status."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dm.*, 
                   rp.photo as product_photo, rp.rescue_price as original_rescue_price,
                   rp.original_price as market_original_price, rp.quantity as current_stock_qty,
                   f.email as farmer_email, f.location as farmer_address,
                   b.email as buyer_email, b.location as buyer_address
            FROM direct_meetings dm
            LEFT JOIN rescue_products rp ON dm.rescue_product_id = rp.id
            JOIN users f ON dm.farmer_id = f.id
            JOIN users b ON dm.buyer_id = b.id
            WHERE dm.id = ?
        """, (meeting_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None
        meeting = dict(row)

        # Inspection details
        cursor.execute("SELECT * FROM direct_inspections WHERE meeting_id = ? ORDER BY id DESC LIMIT 1", (meeting_id,))
        insp = cursor.fetchone()
        meeting['inspection'] = dict(insp) if insp else None

        # Negotiation details
        cursor.execute("SELECT * FROM direct_negotiations WHERE meeting_id = ? ORDER BY id DESC LIMIT 1", (meeting_id,))
        nego = cursor.fetchone()
        meeting['negotiation'] = dict(nego) if nego else None

        # Direct sale details
        cursor.execute("SELECT * FROM direct_sales WHERE meeting_id = ? ORDER BY id DESC LIMIT 1", (meeting_id,))
        sale = cursor.fetchone()
        meeting['sale'] = dict(sale) if sale else None

        conn.close()
        return meeting
    except Exception as e:
        print(f"Error fetching meeting {meeting_id}: {e}")
        return None

def get_buyer_meetings(buyer_id, status_filter=None):
    """Retrieve all meetings for a buyer, optionally filtered by status."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        query = """
            SELECT dm.*, rp.photo as product_photo, rp.rescue_price
            FROM direct_meetings dm
            LEFT JOIN rescue_products rp ON dm.rescue_product_id = rp.id
            WHERE dm.buyer_id = ?
        """
        params = [buyer_id]
        if status_filter and status_filter != 'all':
            query += " AND dm.status = ?"
            params.append(status_filter.capitalize())

        query += " ORDER BY dm.created_at DESC, dm.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_farmer_meetings(farmer_id, status_filter=None):
    """Retrieve all meetings for a farmer, optionally filtered by status."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        query = """
            SELECT dm.*, rp.photo as product_photo, rp.rescue_price
            FROM direct_meetings dm
            LEFT JOIN rescue_products rp ON dm.rescue_product_id = rp.id
            WHERE dm.farmer_id = ?
        """
        params = [farmer_id]
        if status_filter and status_filter != 'all':
            query += " AND dm.status = ?"
            params.append(status_filter.capitalize())

        query += " ORDER BY dm.created_at DESC, dm.id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def respond_direct_meeting(meeting_id, user_id, action, reschedule_data=None, notes=None):
    """
    Handle meeting response:
    - accept: confirms meeting
    - reject: farmer rejects
    - reschedule: farmer or buyer proposes alternative date/time/location
    - cancel: cancel meeting
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM direct_meetings WHERE id = ?", (meeting_id,))
        m = cursor.fetchone()
        if not m:
            conn.close()
            return False, "Meeting not found"

        is_farmer = (m['farmer_id'] == user_id)
        is_buyer = (m['buyer_id'] == user_id)
        if not (is_farmer or is_buyer):
            conn.close()
            return False, "Unauthorized: you are not a party in this meeting"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if action == 'accept':
            cursor.execute("""
                UPDATE direct_meetings
                SET status = 'Confirmed',
                    farmer_notes = COALESCE(?, farmer_notes),
                    updated_at = ?
                WHERE id = ?
            """, (notes, now_str, meeting_id))
            conn.commit()
            conn.close()

            notify_user = m['buyer_id'] if is_farmer else m['farmer_id']
            actor_name = m['farmer_name'] if is_farmer else m['buyer_name']
            create_notification(
                notify_user,
                f"Meeting Confirmed! #{m['meeting_code']} ✅",
                f"{actor_name} confirmed the meeting on {m['proposed_date']} at {m['proposed_time']}. Location: {m['meeting_location']}.",
                notif_type='order',
                link=f"/meeting/{meeting_id}"
            )
            return True, "Meeting confirmed successfully!"

        elif action == 'reject':
            cursor.execute("""
                UPDATE direct_meetings
                SET status = 'Rejected',
                    cancellation_reason = ?,
                    updated_at = ?
                WHERE id = ?
            """, (notes or 'Declined by counterpart', now_str, meeting_id))
            conn.commit()
            conn.close()

            notify_user = m['buyer_id'] if is_farmer else m['farmer_id']
            create_notification(
                notify_user,
                f"Meeting Request Declined #{m['meeting_code']}",
                f"Meeting request for {m['product_name']} was declined. Note: {notes or 'No reason provided'}.",
                notif_type='info',
                link=f"/meeting/{meeting_id}"
            )
            return True, "Meeting request rejected"

        elif action == 'reschedule':
            r_data = reschedule_data or {}
            new_date = r_data.get('date', m['proposed_date'])
            new_time = r_data.get('time', m['proposed_time'])
            new_loc = r_data.get('location', m['meeting_location'])
            actor_label = 'Farmer' if is_farmer else 'Buyer'

            cursor.execute("""
                UPDATE direct_meetings
                SET status = 'Rescheduled',
                    proposed_date = ?,
                    proposed_time = ?,
                    meeting_location = ?,
                    rescheduled_date = ?,
                    rescheduled_time = ?,
                    rescheduled_location = ?,
                    rescheduled_by = ?,
                    farmer_notes = CASE WHEN ? = 'Farmer' THEN ? ELSE farmer_notes END,
                    buyer_notes = CASE WHEN ? = 'Buyer' THEN ? ELSE buyer_notes END,
                    updated_at = ?
                WHERE id = ?
            """, (
                new_date, new_time, new_loc,
                new_date, new_time, new_loc,
                actor_label, actor_label, notes, actor_label, notes,
                now_str, meeting_id
            ))
            conn.commit()
            conn.close()

            notify_user = m['buyer_id'] if is_farmer else m['farmer_id']
            create_notification(
                notify_user,
                f"Meeting Rescheduled #{m['meeting_code']} 📅",
                f"{actor_label} proposed new time: {new_date} at {new_time}. Location: {new_loc}.",
                notif_type='order',
                link=f"/meeting/{meeting_id}"
            )
            return True, "Alternative meeting details sent to counterpart"

        elif action == 'cancel':
            cursor.execute("""
                UPDATE direct_meetings
                SET status = 'Cancelled',
                    cancellation_reason = ?,
                    updated_at = ?
                WHERE id = ?
            """, (notes or 'Cancelled by user', now_str, meeting_id))
            conn.commit()
            conn.close()

            notify_user = m['buyer_id'] if is_farmer else m['farmer_id']
            create_notification(
                notify_user,
                f"Meeting Cancelled #{m['meeting_code']}",
                f"The meeting scheduled for {m['proposed_date']} has been cancelled.",
                notif_type='info',
                link=f"/meetings"
            )
            return True, "Meeting cancelled"

        conn.close()
        return False, "Unknown action"
    except Exception as e:
        return False, str(e)

def record_direct_inspection(meeting_id, inspector_id, freshness, quality, actual_weight,
                             available_qty, packaging, status, buyer_notes, farmer_notes=None):
    """
    Record in-person product inspection during the meeting.
    Inspection statuses: Inspection Pending, Inspection in Progress, Approved, Not Approved.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM direct_meetings WHERE id = ?", (meeting_id,))
        m = cursor.fetchone()
        if not m:
            conn.close()
            return False, "Meeting not found"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check existing inspection
        cursor.execute("SELECT id FROM direct_inspections WHERE meeting_id = ?", (meeting_id,))
        exist = cursor.fetchone()

        if exist:
            cursor.execute("""
                UPDATE direct_inspections
                SET product_freshness = ?,
                    product_quality = ?,
                    actual_weight = ?,
                    available_quantity = ?,
                    packaging_condition = ?,
                    status = ?,
                    buyer_notes = COALESCE(?, buyer_notes),
                    farmer_notes = COALESCE(?, farmer_notes),
                    updated_at = ?
                WHERE id = ?
            """, (
                freshness, quality, float(actual_weight or 0), float(available_qty or 0),
                packaging, status, buyer_notes, farmer_notes, now_str, exist['id']
            ))
        else:
            cursor.execute("""
                INSERT INTO direct_inspections (
                    meeting_id, inspector_id, product_freshness, product_quality,
                    actual_weight, available_quantity, packaging_condition, status,
                    buyer_notes, farmer_notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meeting_id, inspector_id, freshness, quality, float(actual_weight or 0),
                float(available_qty or 0), packaging, status, buyer_notes, farmer_notes,
                now_str, now_str
            ))

        conn.commit()
        conn.close()

        # Send notification to the farmer
        notif_msg = f"Buyer completed product inspection: Status is '{status}' ({quality}, Freshness: {freshness})."
        create_notification(
            m['farmer_id'],
            f"Product Inspection Recorded: {m['product_name']} 🔍",
            notif_msg,
            notif_type='order',
            link=f"/meeting/{meeting_id}"
        )
        return True, "Product inspection saved successfully"
    except Exception as e:
        return False, str(e)

def record_direct_negotiation(meeting_id, user_id, role, farmer_initial_price, buyer_proposed_price,
                              counter_price=None, counter_by=None, final_agreed_price=None,
                              final_quantity=None, notes=None):
    """
    Record or update face-to-face direct price and quantity negotiation.
    Both parties can propose terms and confirm agreement.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM direct_meetings WHERE id = ?", (meeting_id,))
        m = cursor.fetchone()
        if not m:
            conn.close()
            return False, "Meeting not found"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f_init = float(farmer_initial_price)
        b_prop = float(buyer_proposed_price)
        c_price = float(counter_price) if counter_price else None
        f_agreed = float(final_agreed_price) if final_agreed_price else None
        f_qty = float(final_quantity) if final_quantity else float(m['required_quantity'])
        tot_amt = round(f_agreed * f_qty, 2) if f_agreed else round(b_prop * f_qty, 2)

        # Check existing negotiation
        cursor.execute("SELECT id, buyer_agreed, farmer_agreed FROM direct_negotiations WHERE meeting_id = ?", (meeting_id,))
        exist = cursor.fetchone()

        buyer_agreed = 1 if role == 'buyer' and final_agreed_price else (exist['buyer_agreed'] if exist else 0)
        farmer_agreed = 1 if role == 'farmer' and final_agreed_price else (exist['farmer_agreed'] if exist else 0)
        nego_status = 'Agreed' if (buyer_agreed == 1 and farmer_agreed == 1) else 'Negotiating'

        if exist:
            cursor.execute("""
                UPDATE direct_negotiations
                SET farmer_initial_price = ?,
                    buyer_proposed_price = ?,
                    counter_price = COALESCE(?, counter_price),
                    counter_by = COALESCE(?, counter_by),
                    final_agreed_price = COALESCE(?, final_agreed_price),
                    final_quantity = ?,
                    total_amount = ?,
                    buyer_agreed = ?,
                    farmer_agreed = ?,
                    status = ?,
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE id = ?
            """, (
                f_init, b_prop, c_price, counter_by, f_agreed, f_qty, tot_amt,
                buyer_agreed, farmer_agreed, nego_status, notes, now_str, exist['id']
            ))
        else:
            cursor.execute("""
                INSERT INTO direct_negotiations (
                    meeting_id, farmer_id, buyer_id, farmer_initial_price,
                    buyer_proposed_price, counter_price, counter_by, final_agreed_price,
                    final_quantity, total_amount, buyer_agreed, farmer_agreed,
                    status, notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                meeting_id, m['farmer_id'], m['buyer_id'], f_init,
                b_prop, c_price, counter_by, f_agreed, f_qty, tot_amt,
                buyer_agreed, farmer_agreed, nego_status, notes, now_str, now_str
            ))

        conn.commit()
        conn.close()

        # Notify counterpart
        other_user = m['farmer_id'] if role == 'buyer' else m['buyer_id']
        msg_body = f"Negotiation update: Proposed ₹{final_agreed_price or counter_price or buyer_proposed_price}/kg for {f_qty} kg."
        if nego_status == 'Agreed':
            msg_body = f"Both parties agreed to final price: ₹{f_agreed}/kg for {f_qty} kg (Total: ₹{tot_amt}). You can now proceed to direct sale confirmation!"
        create_notification(
            other_user,
            f"Price Negotiation Update: {m['product_name']} 💬",
            msg_body,
            notif_type='order',
            link=f"/meeting/{meeting_id}"
        )
        return True, "Negotiation terms saved successfully"
    except Exception as e:
        return False, str(e)

def confirm_direct_negotiation_agreement(meeting_id, user_id, role):
    """Confirm agreement to negotiated price and quantity."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM direct_negotiations WHERE meeting_id = ?", (meeting_id,))
        nego = cursor.fetchone()
        if not nego:
            conn.close()
            return False, "No active negotiation terms found"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        b_agree = 1 if role == 'buyer' else nego['buyer_agreed']
        f_agree = 1 if role == 'farmer' else nego['farmer_agreed']
        new_status = 'Agreed' if (b_agree == 1 and f_agree == 1) else 'Negotiating'

        cursor.execute("""
            UPDATE direct_negotiations
            SET buyer_agreed = ?,
                farmer_agreed = ?,
                status = ?,
                updated_at = ?
            WHERE id = ?
        """, (b_agree, f_agree, new_status, now_str, nego['id']))
        cursor.execute("SELECT farmer_id, buyer_id, product_name FROM direct_meetings WHERE id = ?", (meeting_id,))
        m = cursor.fetchone()
        other_user = m['farmer_id'] if role == 'buyer' else m['buyer_id']
        conn.commit()
        conn.close()

        create_notification(
            other_user,
            f"Negotiation Confirmed! {m['product_name']} 🤝",
            f"Counterpart confirmed agreement to final terms. Status: {new_status}.",
            notif_type='order',
            link=f"/meeting/{meeting_id}"
        )
        return True, "Agreement recorded"
    except Exception as e:
        return False, str(e)

def initiate_or_update_direct_sale(meeting_id, user_id, role, payment_method,
                                    payment_reference=None, payment_notes=None):
    """
    Create or update direct sale record:
    - Generates unique DIR-2026-XXXX Sale ID and REC-2026-XXXX Receipt Number.
    - Sets initial confirmation flag for initiating user.
    - Supports Cash, UPI, Bank Transfer with payment references.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT dm.*, rp.rescue_price, rp.quantity as stock_qty
            FROM direct_meetings dm
            LEFT JOIN rescue_products rp ON dm.rescue_product_id = rp.id
            WHERE dm.id = ?
        """, (meeting_id,))
        m = cursor.fetchone()
        if not m:
            conn.close()
            return False, "Meeting not found", None

        # Fetch negotiation details for final price and quantity
        cursor.execute("SELECT * FROM direct_negotiations WHERE meeting_id = ?", (meeting_id,))
        nego = cursor.fetchone()

        final_price = float(nego['final_agreed_price']) if (nego and nego['final_agreed_price']) else float(m['rescue_price'] or 20.0)
        final_qty = float(nego['final_quantity']) if (nego and nego['final_quantity']) else float(m['required_quantity'])
        total_amt = round(final_price * final_qty, 2)

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        b_conf = 1 if role == 'buyer' else 0
        b_time = now_str if role == 'buyer' else None
        f_conf = 1 if role == 'farmer' else 0
        f_time = now_str if role == 'farmer' else None

        cursor.execute("SELECT * FROM direct_sales WHERE meeting_id = ?", (meeting_id,))
        exist = cursor.fetchone()

        if exist:
            sale_id = exist['id']
            cursor.execute("""
                UPDATE direct_sales
                SET payment_method = ?,
                    payment_reference = COALESCE(?, payment_reference),
                    payment_notes = COALESCE(?, payment_notes),
                    buyer_confirmed = CASE WHEN ? = 'buyer' THEN 1 ELSE buyer_confirmed END,
                    buyer_confirmed_at = CASE WHEN ? = 'buyer' THEN ? ELSE buyer_confirmed_at END,
                    farmer_confirmed = CASE WHEN ? = 'farmer' THEN 1 ELSE farmer_confirmed END,
                    farmer_confirmed_at = CASE WHEN ? = 'farmer' THEN ? ELSE farmer_confirmed_at END,
                    updated_at = ?
                WHERE id = ?
            """, (
                payment_method, payment_reference, payment_notes,
                role, role, now_str, role, role, now_str, now_str, sale_id
            ))
        else:
            sale_code = f"DIR-2026-{uuid.uuid4().hex[:6].upper()}"
            receipt_no = f"REC-2026-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT INTO direct_sales (
                    sale_code, meeting_id, rescue_product_id, listing_id,
                    farmer_id, buyer_id, product_name, final_quantity,
                    agreed_price_per_kg, total_amount, meeting_date, sale_location,
                    payment_method, payment_reference, payment_notes,
                    buyer_confirmed, buyer_confirmed_at, farmer_confirmed, farmer_confirmed_at,
                    status, receipt_number, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending Confirmation', ?, ?, ?)
            """, (
                sale_code, meeting_id, m['rescue_product_id'], m['listing_id'],
                m['farmer_id'], m['buyer_id'], m['product_name'], final_qty,
                final_price, total_amt, m['proposed_date'], m['meeting_location'],
                payment_method, payment_reference, payment_notes,
                b_conf, b_time, f_conf, f_time, receipt_no, now_str, now_str
            ))
            sale_id = cursor.lastrowid

        conn.commit()

        # Notify counterpart
        other_user = m['farmer_id'] if role == 'buyer' else m['buyer_id']
        create_notification(
            other_user,
            f"Direct Sale Confirmation Initiated: {m['product_name']} 🧾",
            f"Direct sale details recorded via {payment_method}. Total: ₹{total_amt}. Please review and confirm to complete.",
            notif_type='order',
            link=f"/meeting/{meeting_id}"
        )
        conn.close()

        # Check if both already confirmed
        return True, "Direct sale terms recorded", sale_id
    except Exception as e:
        return False, str(e), None

def confirm_direct_sale_step(sale_id, user_id, role, payment_verified=None, notes=None):
    """
    Finalize direct sale:
    - Both Buyer and Farmer must confirm.
    - Farmer acknowledges payment receipt (Cash / UPI / Bank Transfer).
    - Reduces available inventory in rescue_products and listings.
    - Prevents overselling using atomic transactions.
    - Updates rescued produce quantity in analytics.
    - Finalizes sale status to 'Completed'.
    - Generates sale receipt.
    """
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM direct_sales WHERE id = ?", (sale_id,))
        sale = cursor.fetchone()
        if not sale:
            conn.close()
            return False, "Sale record not found"

        if sale['status'] == 'Completed':
            conn.close()
            return True, "Sale is already completed and finalized"

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Update confirmations
        b_conf = 1 if (role == 'buyer' or sale['buyer_confirmed'] == 1) else (sale['buyer_confirmed'] or 0)
        b_time = now_str if (role == 'buyer' and not sale['buyer_confirmed']) else sale['buyer_confirmed_at']
        f_conf = 1 if (role == 'farmer' or sale['farmer_confirmed'] == 1) else (sale['farmer_confirmed'] or 0)
        f_time = now_str if (role == 'farmer' and not sale['farmer_confirmed']) else sale['farmer_confirmed_at']
        p_ver = 1 if (payment_verified or sale['payment_verified'] == 1) else (sale['payment_verified'] or 0)

        # Both must confirm and payment verified
        is_completed = (b_conf == 1 and f_conf == 1 and p_ver == 1)
        new_status = 'Completed' if is_completed else 'Confirmed'

        cursor.execute("""
            UPDATE direct_sales
            SET buyer_confirmed = ?,
                buyer_confirmed_at = ?,
                farmer_confirmed = ?,
                farmer_confirmed_at = ?,
                payment_verified = ?,
                status = ?,
                notes = COALESCE(?, notes),
                updated_at = ?
            WHERE id = ?
        """, (b_conf, b_time, f_conf, f_time, p_ver, new_status, notes, now_str, sale_id))

        if is_completed:
            sold_qty = float(sale['final_quantity'])

            # 1. Decrement rescue_products inventory
            if sale['rescue_product_id']:
                cursor.execute("""
                    UPDATE rescue_products
                    SET quantity = MAX(0, quantity - ?),
                        status = CASE WHEN quantity - ? <= 0 THEN 'Sold' ELSE 'Partially Reserved' END,
                        updated_at = ?
                    WHERE id = ?
                """, (sold_qty, sold_qty, now_str, sale['rescue_product_id']))

            # 2. Decrement listings inventory and increment rescued_from_waste
            if sale['listing_id']:
                cursor.execute("""
                    UPDATE listings
                    SET quantity = MAX(0, quantity - ?),
                        status = CASE WHEN quantity - ? <= 0 THEN 'Sold' ELSE 'Available' END,
                        rescued_from_waste = rescued_from_waste + ?,
                        updated_at = ?
                    WHERE id = ?
                """, (sold_qty, sold_qty, int(sold_qty), now_str, sale['listing_id']))

            # 3. Update meeting status to Completed
            if sale['meeting_id']:
                cursor.execute("""
                    UPDATE direct_meetings
                    SET status = 'Completed', updated_at = ?
                    WHERE id = ?
                """, (now_str, sale['meeting_id']))

            # 4. Record in activity log
            cursor.execute("""
                INSERT INTO activity_logs (action, details, user_email)
                VALUES (?, ?, ?)
            """, (
                'DIRECT_SALE_COMPLETED',
                f"Direct Meet & Sell #{sale['sale_code']} completed: {sold_qty} kg of {sale['product_name']} for ₹{sale['total_amount']}",
                f"Farmer ID {sale['farmer_id']} & Buyer ID {sale['buyer_id']}"
            ))

        conn.commit()
        conn.close()

        if is_completed:
            # 5. Notify both parties
            buyer_msg = f"Direct Sale #{sale['sale_code']} complete! Receipt #{sale['receipt_number']} generated. Thank you for rescuing fresh farm produce!"
            farmer_msg = f"Direct Sale #{sale['sale_code']} complete! Sold {sold_qty} kg for ₹{sale['total_amount']} via {sale['payment_method']}."
            create_notification(sale['buyer_id'], "Direct Sale Completed 🎉", buyer_msg, notif_type='order', link=f"/direct-sale/{sale_id}/receipt")
            create_notification(sale['farmer_id'], "Direct Sale Completed 🎉", farmer_msg, notif_type='order', link=f"/direct-sale/{sale_id}/receipt")

        msg = "Direct sale completed and finalized! Receipt generated." if is_completed else "Your sale confirmation recorded. Waiting for counterpart."
        return True, msg
    except Exception as e:
        return False, str(e)

def get_direct_sale_by_id(sale_id):
    """Retrieve full direct sale record for details and receipt view."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ds.*, 
                   f.name as farmer_name, f.phone as farmer_phone, f.email as farmer_email, f.location as farmer_address,
                   b.name as buyer_name, b.phone as buyer_phone, b.email as buyer_email, b.location as buyer_address,
                   dm.meeting_code, dm.proposed_time as meeting_time, dm.meeting_location as confirmed_location,
                   rp.photo as product_photo, rp.quality_grade
            FROM direct_sales ds
            JOIN users f ON ds.farmer_id = f.id
            JOIN users b ON ds.buyer_id = b.id
            LEFT JOIN direct_meetings dm ON ds.meeting_id = dm.id
            LEFT JOIN rescue_products rp ON ds.rescue_product_id = rp.id
            WHERE ds.id = ?
        """, (sale_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None

def get_direct_sales_for_user(user_id, role):
    """Retrieve direct sales history for a buyer or farmer."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        col = "farmer_id" if role == 'farmer' else "buyer_id"
        cursor.execute(f"""
            SELECT ds.*, 
                   f.name as farmer_name, f.phone as farmer_phone,
                   b.name as buyer_name, b.phone as buyer_phone,
                   rp.photo as product_photo
            FROM direct_sales ds
            JOIN users f ON ds.farmer_id = f.id
            JOIN users b ON ds.buyer_id = b.id
            LEFT JOIN rescue_products rp ON ds.rescue_product_id = rp.id
            WHERE ds.{col} = ?
            ORDER BY ds.created_at DESC, ds.id DESC
        """, (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def get_direct_chat_messages(user1_id, user2_id, meeting_id=None):
    """Retrieve in-app chat messages between buyer and farmer."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        if meeting_id:
            cursor.execute("""
                SELECT cm.*, u.name as sender_name, u.role as sender_role
                FROM chat_messages cm
                JOIN users u ON cm.sender_id = u.id
                WHERE ((cm.sender_id = ? AND cm.receiver_id = ?) OR (cm.sender_id = ? AND cm.receiver_id = ?))
                  AND (cm.meeting_id = ? OR cm.meeting_id IS NULL)
                ORDER BY cm.created_at ASC
            """, (user1_id, user2_id, user2_id, user1_id, meeting_id))
        else:
            cursor.execute("""
                SELECT cm.*, u.name as sender_name, u.role as sender_role
                FROM chat_messages cm
                JOIN users u ON cm.sender_id = u.id
                WHERE ((cm.sender_id = ? AND cm.receiver_id = ?) OR (cm.sender_id = ? AND cm.receiver_id = ?))
                ORDER BY cm.created_at ASC
            """, (user1_id, user2_id, user2_id, user1_id))

        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []

def send_direct_chat_message(sender_id, receiver_id, message, meeting_id=None, listing_id=None):
    """Send an in-app message between counterparties."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO chat_messages (
                sender_id, receiver_id, message, meeting_id, listing_id, is_read, created_at
            ) VALUES (?, ?, ?, ?, ?, 0, ?)
        """, (sender_id, receiver_id, message, meeting_id, listing_id, now_str))
        msg_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT name FROM users WHERE id = ?", (sender_id,))
        sender = cursor.fetchone()
        sender_name = sender['name'] if sender else 'User'
        conn.close()

        create_notification(
            receiver_id,
            f"New Message from {sender_name} 💬",
            message[:100],
            notif_type='info',
            link=f"/meeting/{meeting_id}" if meeting_id else f"/direct-messages/{sender_id}"
        )
        return True, "Message sent", msg_id
    except Exception as e:
        return False, str(e), None


    init_db()
    seed_db()
    print("Database initialized and updated successfully.")
