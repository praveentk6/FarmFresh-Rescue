"""
seed_vegetables.py – One-time script to add 10 demonstration vegetable listings
to the FarmFresh Rescue database.

Run once:  python seed_vegetables.py

All listings are clearly marked as DEMO / SAMPLE data (is_demo flag via
description prefix and a farmer account named "[DEMO Farmer]"). They use the
same database schema as real farmer listings so filters, search, and order
workflow all work correctly. Prices and quantities use realistic Tamil Nadu
wholesale market values.
"""

import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')

DEMO_FARMER_EMAIL = 'demo.farmer@farmfresh-sample.org'
DEMO_FARMER_EMAIL2 = 'demo.farmer2@farmfresh-sample.org'
DEMO_FARMER_EMAIL3 = 'demo.farmer3@farmfresh-sample.org'

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def seed_vegetables():
    conn = get_db()
    cursor = conn.cursor()

    # ── 1. Check if demo vegetables already exist ──────────────────────────
    cursor.execute(
        "SELECT COUNT(*) FROM listings WHERE farmer_name LIKE '[DEMO]%'"
    )
    already = cursor.fetchone()[0]
    if already >= 10:
        print(f"Demo vegetables already seeded ({already} records). Nothing to do.")
        conn.close()
        return

    # ── 2. Get or create demo farmer accounts ─────────────────────────────
    def get_or_create_farmer(email, name, phone, location, pin_code, user_type):
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if row:
            return row['id']
        pw = generate_password_hash("demo_farmer_pw_2024")
        cursor.execute(
            """INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type, is_active)
               VALUES (?, ?, ?, 'farmer', ?, ?, ?, ?, 1)""",
            (name, email, pw, phone, location, pin_code, user_type)
        )
        conn.commit()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        return cursor.fetchone()['id']

    f1 = get_or_create_farmer(
        DEMO_FARMER_EMAIL,
        "[DEMO] Arumugam Velusamy",
        "9443000101",
        "Palladam",
        "641664",
        "Vegetable Farmer"
    )
    f2 = get_or_create_farmer(
        DEMO_FARMER_EMAIL2,
        "[DEMO] Geetha Palanisamy",
        "9443000202",
        "Hosur",
        "635109",
        "Organic Vegetable Grower"
    )
    f3 = get_or_create_farmer(
        DEMO_FARMER_EMAIL3,
        "[DEMO] Subramaniam Pillai",
        "9443000303",
        "Coimbatore North",
        "641001",
        "Mixed Vegetable Farmer"
    )

    now = datetime.now()

    def days_ago(n):
        return (now - timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S')

    def days_from_now(n):
        return (now + timedelta(days=n)).strftime('%Y-%m-%d')

    harvest_today  = now.strftime('%Y-%m-%d')
    harvest_1d     = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    harvest_2d     = (now - timedelta(days=2)).strftime('%Y-%m-%d')
    harvest_3d     = (now - timedelta(days=3)).strftime('%Y-%m-%d')
    harvest_4d     = (now - timedelta(days=4)).strftime('%Y-%m-%d')

    # ── 3. 10 Vegetable listings ─────────────────────────────────────────
    # Fields: farmer_id, crop_name, category, photo, quantity, unit,
    #         price_per_unit, original_price, harvest_date,
    #         estimated_freshness_date, village_town, district, state, pin_code,
    #         farmer_name, farmer_phone, whatsapp_number, description,
    #         urgency_level, status, rescued_from_waste, created_at, updated_at

    listings = [
        # 1 – Tomato
        (
            f1,
            "Salem Nattu Thakkali (Country Tomatoes)",       # crop_name
            "Vegetables",                                     # category
            "tomatoes.jpg",                                   # photo
            400.0, "kg", 20.0, 28.0,                         # qty, unit, price, orig
            harvest_2d,                                       # harvest_date
            days_from_now(4),                                 # estimated_freshness_date
            "Attur", "Salem", "Tamil Nadu", "636102",        # village, district, state, pin
            "[DEMO] Arumugam Velusamy", "9443000101", "9443000101",
            "[SAMPLE LISTING – Demonstration Data]\nFirm, naturally red farm-gate tomatoes from Salem. "
            "Ideal for hotels, restaurants, and vegetable retailers. Ready for same-day bulk pickup.",
            "Normal", "Available", 0,
            days_ago(2), days_ago(2)
        ),

        # 2 – Onion
        (
            f1,
            "Erode Red Onions (Vengayam)",
            "Vegetables",
            "onions.jpg",
            800.0, "kg", 25.0, 35.0,
            harvest_3d,
            days_from_now(20),
            "Bhavani", "Erode", "Tamil Nadu", "638301",
            "[DEMO] Arumugam Velusamy", "9443000101", "9443000101",
            "[SAMPLE LISTING – Demonstration Data]\nPungent, farm-dried red onions sorted in 50 kg gunny bags. "
            "High shelf life in dry storage. Preferred by supermarkets, hotels, and wholesale mandis.",
            "Normal", "Available", 0,
            days_ago(3), days_ago(3)
        ),

        # 3 – Potato
        (
            f2,
            "Ooty Hill Potatoes (Urulaikizhangu)",
            "Vegetables",
            "potatoes.jpg",
            600.0, "kg", 22.0, 30.0,
            harvest_1d,
            days_from_now(30),
            "Udhagamandalam", "Nilgiris", "Tamil Nadu", "643001",
            "[DEMO] Geetha Palanisamy", "9443000202", "9443000202",
            "[SAMPLE LISTING – Demonstration Data]\nFresh high-altitude Ooty potatoes, firm and clean. "
            "Excellent for chips factories, hotels, and supermarket chains. Crates available.",
            "Normal", "Available", 0,
            days_ago(1), days_ago(1)
        ),

        # 4 – Carrot (Ooty already has one, adding a different district)
        (
            f2,
            "Kodaikanal Fresh Carrots (Carrot)",
            "Vegetables",
            "carrots.jpg",
            300.0, "kg", 40.0, 55.0,
            harvest_today,
            days_from_now(6),
            "Kodaikanal", "Dindigul", "Tamil Nadu", "624101",
            "[DEMO] Geetha Palanisamy", "9443000202", "9443000202",
            "[SAMPLE LISTING – Demonstration Data]\nSweet, washed Kodaikanal carrots direct from hill farms. "
            "Suitable for juice shops, cold-press units, hotels, and retail stores.",
            "Normal", "Available", 0,
            days_ago(0), days_ago(0)
        ),

        # 5 – Cabbage
        (
            f2,
            "Ooty Tender Cabbage (Muttaikose)",
            "Vegetables",
            "cabbage.jpg",
            500.0, "kg", 15.0, 20.0,
            harvest_2d,
            days_from_now(5),
            "Kothagiri", "Nilgiris", "Tamil Nadu", "643217",
            "[DEMO] Geetha Palanisamy", "9443000202", "9443000202",
            "[SAMPLE LISTING – Demonstration Data]\nCompact, tender green cabbages from hill station farms. "
            "Crisp outer leaves, minimal trim waste. Bulk crates available for hotels and vegetable retailers.",
            "Needs Attention", "Available", 0,
            days_ago(4), days_ago(4)
        ),

        # 6 – Brinjal
        (
            f3,
            "Coimbatore Purple Brinjal (Kathirikai)",
            "Vegetables",
            "brinjal.jpg",
            250.0, "kg", 18.0, 25.0,
            harvest_1d,
            days_from_now(4),
            "Mettupalayam", "Coimbatore", "Tamil Nadu", "641301",
            "[DEMO] Subramaniam Pillai", "9443000303", "9443000303",
            "[SAMPLE LISTING – Demonstration Data]\nShiny, firm purple brinjals with green calyx freshly harvested. "
            "Suitable for sambar, curries, and restaurant kitchens. Available in 10 kg bundles.",
            "Normal", "Available", 0,
            days_ago(1), days_ago(1)
        ),

        # 7 – Green Chilli
        (
            f1,
            "Guntur-Style Green Chillies (Pachai Milagai)",
            "Vegetables",
            "chillies.jpg",
            200.0, "kg", 30.0, 42.0,
            harvest_today,
            days_from_now(3),
            "Palladam", "Tiruppur", "Tamil Nadu", "641664",
            "[DEMO] Arumugam Velusamy", "9443000101", "9443000101",
            "[SAMPLE LISTING – Demonstration Data]\nMedium-hot bright green chillies. Best for curries, chutneys, "
            "pickles, and hotel kitchens. Packed in breathable mesh bags. Needs quick clearance to stay fresh.",
            "Needs Attention", "Available", 0,
            days_ago(4), days_ago(4)
        ),

        # 8 – Drumstick (Murungakkai)
        (
            f3,
            "Tirunelveli Drumstick (Murungakkai)",
            "Vegetables",
            "drumstick.jpg",
            150.0, "kg", 45.0, 60.0,
            harvest_1d,
            days_from_now(5),
            "Palayamkottai", "Tirunelveli", "Tamil Nadu", "627002",
            "[DEMO] Subramaniam Pillai", "9443000303", "9443000303",
            "[SAMPLE LISTING – Demonstration Data]\nLong, fibrous drumsticks freshly plucked from moringa trees. "
            "Ideal for sambar and health-conscious consumers. Bundled in 5 kg lots for restaurants and homes.",
            "Normal", "Available", 0,
            days_ago(1), days_ago(1)
        ),

        # 9 – Lady's Finger
        (
            f3,
            "Madurai Lady's Finger / Okra (Vendaikkai)",
            "Vegetables",
            "ladysfinger.jpg",
            180.0, "kg", 35.0, 48.0,
            harvest_today,
            days_from_now(3),
            "Melur", "Madurai", "Tamil Nadu", "625106",
            "[DEMO] Subramaniam Pillai", "9443000303", "9443000303",
            "[SAMPLE LISTING – Demonstration Data]\nTender green okra pods handpicked at peak softness. "
            "Perfect for sabzi, sambar, and southern curries. Packed in ventilated crates to prevent sliminess.",
            "Normal", "Available", 0,
            days_ago(0), days_ago(0)
        ),

        # 10 – Cauliflower
        (
            f2,
            "Ooty White Cauliflower (Cauliflower / Kobipoo)",
            "Vegetables",
            "cauliflower.jpg",
            280.0, "kg", 38.0, 52.0,
            harvest_2d,
            days_from_now(4),
            "Coonoor", "Nilgiris", "Tamil Nadu", "643101",
            "[DEMO] Geetha Palanisamy", "9443000202", "9443000202",
            "[SAMPLE LISTING – Demonstration Data]\nFirm white cauliflower heads from Ooty foothills, tightly packed curds. "
            "Great for restaurants, hotels, and supermarkets. Delivered in ventilated wooden crates.",
            "Normal", "Available", 0,
            days_ago(2), days_ago(2)
        ),
    ]

    cursor.executemany('''
        INSERT INTO listings (
            farmer_id, crop_name, category, photo, quantity, unit,
            price_per_unit, original_price, harvest_date, estimated_freshness_date,
            village_town, district, state, pin_code,
            farmer_name, farmer_phone, whatsapp_number, description,
            urgency_level, status, rescued_from_waste, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', listings)

    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM listings WHERE farmer_name LIKE '[DEMO]%'")
    inserted = cursor.fetchone()[0]
    print(f"[OK] Successfully inserted {inserted} demonstration vegetable listings.")
    print("     Open http://127.0.0.1:5000/listings to see them in Browse Produce.")
    conn.close()


if __name__ == '__main__':
    seed_vegetables()
