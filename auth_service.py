import os
import hmac
import hashlib
import time
import uuid
import datetime
import secrets
import bcrypt
import jwt
from werkzeug.security import check_password_hash
from database import get_db

# Load environment variables if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

JWT_SECRET = os.environ.get('JWT_SECRET', 'farmfresh_rescue_super_secure_jwt_token_secret_key_2026')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'Pp274142@gmail.com').strip().lower()
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'praveen16')
MONGODB_URI = os.environ.get('MONGODB_URI', '').strip()

# ==========================================
# 1. MongoDB Atlas Client & Connection
# ==========================================

_mongo_client = None
_mongo_db = None
_mongo_connected = False

def get_mongo_db():
    """Return MongoDB Atlas database instance if configured and reachable."""
    global _mongo_client, _mongo_db, _mongo_connected
    if not MONGODB_URI:
        return None

    if _mongo_db is not None:
        return _mongo_db

    try:
        from pymongo import MongoClient
        _mongo_client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        # Verify server connection
        _mongo_client.admin.command('ping')
        _mongo_db = _mongo_client.get_database('farmfresh_rescue')
        _mongo_connected = True
        # Ensure unique index on email
        _mongo_db.users.create_index("email", unique=True)
        return _mongo_db
    except Exception as e:
        _mongo_connected = False
        print(f"[MongoDB] Atlas connection notice: {e}. Falling back to SQLite primary store.")
        return None

def is_mongo_active():
    return _mongo_connected or bool(get_mongo_db() is not None)

# ==========================================
# 2. Password Hashing (bcrypt)
# ==========================================

def hash_password(plain_password: str) -> str:
    """Hash password securely using bcrypt."""
    if not isinstance(plain_password, str):
        plain_password = str(plain_password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash or fallback legacy hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        # Check bcrypt prefix
        if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$') or hashed_password.startswith('$2y$'):
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        # Fallback for existing Werkzeug scrypt/pbkdf2 hashes in seed data
        return check_password_hash(hashed_password, plain_password)
    except Exception:
        return False

# ==========================================
# 3. JWT Token Handling
# ==========================================

def generate_jwt_token(user_id: int, email: str, role: str, days: int = 7) -> str:
    """Generate signed JWT authentication token."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    exp_utc = now_utc + datetime.timedelta(days=days)
    payload = {
        'user_id': user_id,
        'email': email.lower().strip(),
        'role': role.lower().strip(),
        'iat': int(now_utc.timestamp()),
        'exp': int(exp_utc.timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')

def decode_jwt_token(token: str):
    """Decode and validate a JWT authentication token."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# ==========================================
# 4. User Lookup & Persistence
# ==========================================

def get_user_by_email(email: str):
    """Retrieve user dictionary by email from SQLite and MongoDB."""
    if not email:
        return None
    email_clean = email.strip().lower()

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, password_hash, role, phone, location, pin_code, user_type, is_active, created_at, email_verified, verification_token, verified_at, district
        FROM users WHERE LOWER(email) = ?
    """, (email_clean,))
    row = cursor.fetchone()
    conn.close()

    if row:
        user_dict = dict(row)
        return user_dict

    # Check MongoDB if available
    db = get_mongo_db()
    if db is not None:
        try:
            m_user = db.users.find_one({"email": email_clean})
            if m_user:
                return {
                    'id': m_user.get('sqlite_id', 0),
                    'name': m_user.get('name'),
                    'email': m_user.get('email'),
                    'password_hash': m_user.get('password'),
                    'role': m_user.get('role', '').lower(),
                    'phone': m_user.get('phone', ''),
                    'location': m_user.get('address', ''),
                    'pin_code': m_user.get('pin_code', ''),
                    'user_type': m_user.get('user_type', ''),
                    'is_active': 1 if m_user.get('status') == 'active' else 0,
                    'email_verified': m_user.get('email_verified', 0),
                    'created_at': str(m_user.get('createdAt', ''))
                }
        except Exception as e:
            print(f"[MongoDB] Error querying user: {e}")

    return None

def get_user_by_id(user_id: int):
    """Retrieve user dictionary by ID."""
    if not user_id:
        return None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, email, password_hash, role, phone, location, pin_code, user_type, is_active, created_at, email_verified, verification_token, verified_at, district
        FROM users WHERE id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user_account(name: str, email: str, plain_password: str, role: str, phone: str = "", address: str = "", location: str = "", pin_code: str = "", user_type: str = ""):
    """
    Create a new user account with bcrypt password hashing.
    Saves to both SQLite and MongoDB Atlas (if configured).
    Returns (success: bool, user_or_error: dict/str)
    """
    email_clean = email.strip().lower()
    role_clean = role.strip().lower()
    final_address = (address or location or "").strip()

    if role_clean not in ['farmer', 'buyer', 'admin']:
        return False, "Invalid role specified."

    # Prevent public registration of admin
    if role_clean == 'admin':
        return False, "Public Administrator registration is not permitted."

    # Check duplicate email
    existing = get_user_by_email(email_clean)
    if existing:
        return False, "An account with this email address already exists. Please log in."

    hashed_pw = hash_password(plain_password)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Save to SQLite
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (name.strip(), email_clean, hashed_pw, role_clean, phone.strip(), final_address, pin_code.strip(), user_type.strip(), now_str))
        conn.commit()
        user_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        return False, f"Database error creating user: {e}"
    conn.close()

    # Save to MongoDB Atlas collection
    db = get_mongo_db()
    if db is not None:
        try:
            mongo_doc = {
                "sqlite_id": user_id,
                "name": name.strip(),
                "email": email_clean,
                "phone": phone.strip(),
                "password": hashed_pw,
                "role": role_clean.upper(),
                "address": address.strip(),
                "pin_code": pin_code.strip(),
                "status": "active",
                "createdAt": datetime.datetime.utcnow(),
                "updatedAt": datetime.datetime.utcnow()
            }
            db.users.replace_one({"email": email_clean}, mongo_doc, upsert=True)
        except Exception as e:
            print(f"[MongoDB] Could not sync user to Atlas: {e}")

    user_obj = {
        'id': user_id,
        'name': name.strip(),
        'email': email_clean,
        'role': role_clean,
        'phone': phone.strip(),
        'location': address.strip(),
        'pin_code': pin_code.strip(),
        'user_type': user_type.strip(),
        'is_active': 1,
        'created_at': now_str
    }
    return True, user_obj

# ==========================================
# 5. Exactly One Authorized Admin Account Seeder
# ==========================================

def seed_single_admin_account():
    """
    Ensure EXACTLY ONE authorized Admin account exists:
    Email: ADMIN_EMAIL (Pp274142@gmail.com by default)
    Password: ADMIN_PASSWORD (praveen16 by default) hashed with bcrypt.
    Removes any conflicting duplicate admin accounts.
    """
    admin_email_clean = ADMIN_EMAIL.strip().lower()
    hashed_pw = hash_password(ADMIN_PASSWORD)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()

    # Check if this exact admin already exists
    cursor.execute("SELECT id, email, password_hash, role FROM users WHERE LOWER(email) = ?", (admin_email_clean,))
    existing_admin = cursor.fetchone()

    if existing_admin:
        admin_id = existing_admin['id']
        # Update password hash with fresh bcrypt hash and ensure role is 'admin' and active
        cursor.execute("""
            UPDATE users 
            SET name = 'Platform Administrator', password_hash = ?, role = 'admin', is_active = 1, phone = '9842100001', location = 'Chennai HQ'
            WHERE id = ?
        """, (hashed_pw, admin_id))
    else:
        # Check if an old admin existed with another email (e.g. admin@farmfresh.org)
        cursor.execute("SELECT id FROM users WHERE role = 'admin' AND LOWER(email) != ?", (admin_email_clean,))
        old_admins = cursor.fetchall()
        for old in old_admins:
            cursor.execute("DELETE FROM users WHERE id = ?", (old['id'],))

        # Insert the single authorized admin
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role, phone, location, pin_code, user_type, is_active, created_at)
            VALUES (?, ?, ?, 'admin', '9842100001', 'Chennai HQ', '600001', 'Platform Admin', 1, ?)
        """, ('Platform Administrator', admin_email_clean, hashed_pw, now_str))
        admin_id = cursor.lastrowid

    # Ensure no other admin accounts exist in SQLite
    cursor.execute("DELETE FROM users WHERE role = 'admin' AND LOWER(email) != ?", (admin_email_clean,))
    conn.commit()
    conn.close()

    # Sync to MongoDB Atlas
    db = get_mongo_db()
    if db is not None:
        try:
            # Delete any other admin accounts
            db.users.delete_many({"role": "ADMIN", "email": {"$ne": admin_email_clean}})
            admin_doc = {
                "sqlite_id": admin_id,
                "name": "Platform Administrator",
                "email": admin_email_clean,
                "phone": "9842100001",
                "password": hashed_pw,
                "role": "ADMIN",
                "address": "Chennai HQ",
                "pin_code": "600001",
                "status": "active",
                "createdAt": datetime.datetime.utcnow(),
                "updatedAt": datetime.datetime.utcnow()
            }
            db.users.replace_one({"email": admin_email_clean}, admin_doc, upsert=True)
        except Exception as e:
            print(f"[MongoDB] Error seeding admin account to Atlas: {e}")

    return admin_id

# ==========================================
# 6. Password Reset Token Management
# ==========================================

def init_password_resets_table():
    """Create password reset tokens table if it does not exist."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def generate_password_reset_token(email: str):
    """Generate secure password reset token valid for 1 hour."""
    user = get_user_by_email(email)
    if not user:
        return False, None

    init_password_resets_table()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    exp_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO password_resets (email, token, expires_at, used)
        VALUES (?, ?, ?, 0)
    """, (email.strip().lower(), token, exp_str))
    conn.commit()
    conn.close()
    return True, token

def verify_reset_token(token: str):
    """Verify reset token validity. Returns email if valid, else None."""
    if not token:
        return None
    init_password_resets_table()
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT email FROM password_resets
        WHERE token = ? AND used = 0 AND expires_at > ?
    """, (token, now_str))
    row = cursor.fetchone()
    conn.close()
    return row['email'] if row else None

def reset_password_with_token(token: str, new_password: str):
    """Reset password using verified token. Returns (success: bool, message: str)"""
    email = verify_reset_token(token)
    if not email:
        return False, "Invalid or expired password reset token."

    hashed_pw = hash_password(new_password)
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = ?", (hashed_pw, email.lower()))
    cursor.execute("UPDATE password_resets SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()

    # Sync to MongoDB Atlas
    db = get_mongo_db()
    if db is not None:
        try:
            db.users.update_one(
                {"email": email.lower()},
                {"$set": {"password": hashed_pw, "updatedAt": datetime.datetime.utcnow()}}
            )
        except Exception:
            pass

    return True, "Password updated successfully"

    return True
