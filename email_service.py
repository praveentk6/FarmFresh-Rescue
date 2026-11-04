"""
Email and SMTP Verification Service for FarmFresh Rescue Platform.
Provides SMTP email delivery, offline/local simulation fallback, dynamic database configuration,
and responsive HTML email templates for Farmers, Buyers, and Platform Broadcasts.
"""

import os
import smtplib
import sqlite3
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_system_settings():
    """Ensure system_settings table exists for dynamic runtime configuration."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[init_system_settings Error] {e}")

init_system_settings()

def get_system_setting(key, default=None):
    """Retrieve runtime system setting value from database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        if row and row['value'] is not None and row['value'] != '':
            return row['value']
    except Exception:
        pass
    return default

def set_system_setting(key, value):
    """Upsert runtime system setting in database."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO system_settings (key, value, updated_at) 
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, str(value) if value is not None else '', now_str))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[set_system_setting Error] {e}")
        return False

def log_activity(action, details, user_email='system'):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO activity_logs (action, details, user_email) VALUES (?, ?, ?)",
            (action, details, user_email)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[ActivityLog Error] {e}")

def get_smtp_config():
    """Retrieve active SMTP configuration from database settings, environment, or defaults."""
    server = get_system_setting('smtp_server') or os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    try:
        port_val = get_system_setting('smtp_port') or os.environ.get('SMTP_PORT', 587)
        port = int(port_val)
    except ValueError:
        port = 587

    username = (get_system_setting('smtp_username') or os.environ.get('SMTP_USERNAME') or os.environ.get('ADMIN_EMAIL', 'Pp274142@gmail.com')).strip()
    password = (get_system_setting('smtp_password') or os.environ.get('SMTP_PASSWORD', '')).strip()

    tls_val = get_system_setting('smtp_use_tls')
    if tls_val is not None:
        use_tls = str(tls_val).lower() in ('true', '1', 'yes')
    else:
        use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() in ('true', '1', 'yes')

    sender_name = get_system_setting('smtp_sender_name') or os.environ.get('SMTP_SENDER_NAME', 'FarmFresh Rescue Admin')
    default_sender = f"{sender_name} <{username or 'noreply@farmfresh.org'}>"

    is_configured = bool(username and password)

    return {
        'server': server,
        'port': port,
        'username': username,
        'password': password,
        'use_tls': use_tls,
        'sender_name': sender_name,
        'default_sender': default_sender,
        'is_configured': is_configured,
        'mode': 'Live SMTP Delivery' if is_configured else 'Local Development / Simulator Mode'
    }

def save_smtp_config(server: str, port: int, username: str, password: str, use_tls: bool, sender_name: str = 'FarmFresh Rescue Admin'):
    """Save SMTP configuration into system_settings database and sync environment variables & .env file."""
    server = (server or 'smtp.gmail.com').strip()
    port = int(port or 587)
    username = (username or '').strip()
    sender_name = (sender_name or 'FarmFresh Rescue Admin').strip()
    
    set_system_setting('smtp_server', server)
    set_system_setting('smtp_port', str(port))
    set_system_setting('smtp_username', username)
    if password is not None:
        pw_clean = password.strip()
        if ' ' in pw_clean and len(pw_clean.replace(' ', '')) == 16:
            pw_clean = pw_clean.replace(' ', '')
        set_system_setting('smtp_password', pw_clean)
    set_system_setting('smtp_use_tls', '1' if use_tls else '0')
    set_system_setting('smtp_sender_name', sender_name)

    # Sync process environment variables
    os.environ['SMTP_SERVER'] = server
    os.environ['SMTP_PORT'] = str(port)
    os.environ['SMTP_USERNAME'] = username
    if password is not None:
        os.environ['SMTP_PASSWORD'] = password.strip()
    os.environ['SMTP_USE_TLS'] = 'true' if use_tls else 'false'
    os.environ['SMTP_SENDER_NAME'] = sender_name

    # Persist to .env file
    try:
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        env_dict = {}
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line_str = line.strip()
                    if line_str and not line_str.startswith('#') and '=' in line_str:
                        k, v = line_str.split('=', 1)
                        env_dict[k.strip()] = v.strip()

        env_dict['SMTP_SERVER'] = server
        env_dict['SMTP_PORT'] = str(port)
        env_dict['SMTP_USERNAME'] = username
        if password is not None:
            env_dict['SMTP_PASSWORD'] = password.strip()
        env_dict['SMTP_USE_TLS'] = 'true' if use_tls else 'false'
        env_dict['SMTP_SENDER_NAME'] = sender_name

        with open(env_path, 'w', encoding='utf-8') as f:
            for k, v in env_dict.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        print(f"[save_smtp_config .env notice] {e}")

    log_activity('SMTP_CONFIG_UPDATED', f"Updated SMTP settings: {username} via {server}:{port} (TLS={use_tls})")
    return True, "SMTP configuration settings saved and activated successfully!"

def send_email(to_email: str, subject: str, html_body: str, text_body: str = None):
    """
    Deliver an email via SMTP with support for TLS (587), SSL (465),
    automatic Google App Password whitespace stripping, and clear error diagnostics.
    """
    import ssl
    config = get_smtp_config()
    to_email_clean = to_email.strip().lower()

    if not config['is_configured']:
        msg = f"[SMTP Simulator] Email to <{to_email_clean}>: '{subject}'. No SMTP credentials in .env. Simulated successfully."
        try:
            print(msg)
        except Exception:
            print(msg.encode('ascii', 'replace').decode('ascii'))
        log_activity('EMAIL_SIMULATED', f"To: {to_email_clean} | Subject: {subject}", to_email_clean)
        return True, "Email simulated successfully (SMTP credentials not yet configured in .env)."

    clean_username = config['username'].strip().lower()
    raw_password = config['password'] or ''
    # Automatically strip spaces from App Passwords (e.g. 'uvga zhhj hjng spgo' -> 'uvgazhhjhjngspgo')
    clean_password = raw_password.replace(' ', '').strip()

    is_ssl = (config['port'] == 465) or (not config['use_tls'] and config['port'] != 587)

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = config['default_sender']
        msg['To'] = to_email_clean
        msg['Date'] = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0530")

        if text_body:
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        server = None
        try:
            if is_ssl:
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(config['server'], config['port'], context=context, timeout=10)
                server.ehlo()
            else:
                server = smtplib.SMTP(config['server'], config['port'], timeout=10)
                server.ehlo()
                if config['use_tls']:
                    server.starttls()
                    server.ehlo()

            # Attempt authentication
            try:
                server.login(clean_username, clean_password)
            except smtplib.SMTPAuthenticationError as auth_err:
                raise ValueError(f"Google rejected credentials ({auth_err.smtp_code}): Username or App Password for {config['username']} was rejected. Please ensure 2-Step Verification is active and generate a fresh 16-character App Password at myaccount.google.com/apppasswords.")
            except smtplib.SMTPServerDisconnected:
                raise ValueError(f"Google rejected credentials (535 Bad Credentials): The 16-character App Password for {config['username']} was rejected by Google. Please generate a new App Password for this exact Gmail account at myaccount.google.com/apppasswords.")

            server.send_message(msg)
            try: server.quit()
            except: pass
        finally:
            if server:
                try: server.close()
                except: pass

        log_activity('EMAIL_SENT', f"Delivered email to {to_email_clean} | Subject: {subject}", to_email_clean)
        return True, f"Email delivered to {to_email_clean} via {config['server']}."
    except Exception as e:
        err_msg = f"SMTP Delivery Failed to {to_email_clean}: {str(e)}"
        print(f"[SMTP Error] {err_msg}")
        log_activity('EMAIL_FAILED', err_msg, to_email_clean)
        return False, err_msg

def build_verification_html(user_name: str, verify_url: str, token: str):
    """Generate professional HTML verification email template."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Verify Your FarmFresh Rescue Account</title>
  <style>
    body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; margin: 0; padding: 0; color: #1e293b; }}
    .email-container {{ max-width: 580px; margin: 30px auto; background: #ffffff; border-radius: 14px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 15px rgba(0,0,0,0.04); }}
    .email-header {{ background: linear-gradient(135deg, #16a34a, #15803d); padding: 28px 24px; text-align: center; color: #ffffff; }}
    .email-logo {{ font-size: 28px; margin-bottom: 6px; }}
    .email-title {{ font-size: 22px; font-weight: 800; margin: 0; letter-spacing: -0.5px; }}
    .email-subtitle {{ font-size: 13px; opacity: 0.9; margin-top: 4px; }}
    .email-body {{ padding: 32px 28px; }}
    .greeting {{ font-size: 18px; font-weight: 700; color: #0f172a; margin-bottom: 12px; }}
    .message-text {{ font-size: 15px; line-height: 1.6; color: #475569; margin-bottom: 24px; }}
    .btn-wrap {{ text-align: center; margin: 30px 0; }}
    .btn-verify {{ display: inline-block; background: #16a34a; color: #ffffff !important; padding: 14px 32px; font-size: 16px; font-weight: 700; text-decoration: none; border-radius: 10px; box-shadow: 0 4px 10px rgba(22,163,74,0.3); }}
    .token-box {{ background: #f1f5f9; border-radius: 8px; padding: 14px; text-align: center; font-family: monospace; font-size: 14px; color: #334155; word-break: break-all; margin: 20px 0; }}
    .footer-note {{ font-size: 12px; color: #94a3b8; line-height: 1.5; border-top: 1px solid #f1f5f9; padding-top: 20px; margin-top: 30px; text-align: center; }}
  </style>
</head>
<body>
  <div class="email-container">
    <div class="email-header">
      <div class="email-logo">🌾</div>
      <h1 class="email-title">FarmFresh Rescue</h1>
      <div class="email-subtitle">Tamil Nadu Direct Agricultural Marketplace</div>
    </div>
    <div class="email-body">
      <div class="greeting">Vanakkam, {user_name}!</div>
      <p class="message-text">
        Thank you for joining <strong>FarmFresh Rescue</strong>. Please verify your email address to activate all platform benefits, including direct harvest listing, WhatsApp notifications, and verified buyer matching.
      </p>
      
      <div class="btn-wrap">
        <a href="{verify_url}" class="btn-verify" target="_blank">✓ Verify Email Address</a>
      </div>

      <p class="message-text" style="font-size: 13px;">
        Or copy and paste this verification link into your web browser:
      </p>
      <div class="token-box">
        <a href="{verify_url}" style="color: #16a34a; text-decoration: underline;">{verify_url}</a>
      </div>

      <div class="footer-note">
        This link is valid for 24 hours. If you did not create an account on FarmFresh Rescue, you can safely ignore this email.<br>
        &copy; 2026 FarmFresh Rescue &bull; Tamil Nadu Zero-Waste Agricultural Initiative
      </div>
    </div>
  </div>
</body>
</html>"""

def send_verification_email(user_email: str, user_name: str, token: str, base_url: str = 'http://127.0.0.1:5000'):
    """Generate verification URL and send responsive HTML verification message."""
    verify_url = f"{base_url.rstrip('/')}/verify-email/{token}"
    subject = "🌾 Verify your FarmFresh Rescue account"
    html_content = build_verification_html(user_name, verify_url, token)
    text_content = f"Vanakkam {user_name},\n\nPlease verify your FarmFresh Rescue account by visiting this link:\n{verify_url}\n\nToken: {token}\n\nThank you,\nFarmFresh Rescue Team"
    return send_email(user_email, subject, html_content, text_content)

def test_smtp_connection(test_recipient: str, base_url: str = 'http://127.0.0.1:5000'):
    """Diagnostic utility to test live SMTP connectivity from Admin Control Center."""
    subject = "🧪 FarmFresh Rescue SMTP Diagnostic Test"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content = f"""<div style="font-family: sans-serif; padding: 20px; border-left: 5px solid #16a34a; background: #f8fafc;">
        <h2>FarmFresh Rescue SMTP Configuration Test</h2>
        <p>This is a live diagnostic message dispatched from the <strong>Admin Control Center</strong>.</p>
        <p><strong>Timestamp:</strong> {now_str}</p>
        <p><strong>Status:</strong> SMTP connection active and functioning correctly.</p>
    </div>"""
    return send_email(test_recipient, subject, html_content, f"SMTP Diagnostic Test successful at {now_str}")

# ============================================================================
# DEFAULT EMAIL COMMUNICATION TEMPLATES (FARMERS, BUYERS, BOTH)
# ============================================================================

DEFAULT_COMMUNICATION_TEMPLATES = {
    'weather_farmer': {
        'id': 'weather_farmer',
        'name': '⛈️ Weather Warning & Harvest Protection (For Farmers)',
        'target_audience': 'farmer',
        'subject': '⛈️ Urgent Agro-Weather Advisory & Crop Rescue - FarmFresh Rescue',
        'html': """<div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #fed7aa; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
  <div style="background: linear-gradient(135deg, #c2410c, #ea580c); padding: 24px; color: #ffffff; text-align: center;">
    <div style="font-size: 34px; margin-bottom: 6px;">⛈️</div>
    <h2 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">Urgent Weather & Crop Protection Advisory</h2>
    <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">Tamil Nadu State Agro-Advisory Bulletin</div>
  </div>
  <div style="padding: 26px 24px; color: #1e293b; font-size: 15px; line-height: 1.6;">
    <p style="margin-top: 0;"><strong>Vanakkam Farmer Partner,</strong></p>
    <p>Regional Meteorological Advisories forecast unseasonal heavy rainfall and gusty winds across agricultural districts in Tamil Nadu over the next 48 to 72 hours.</p>
    
    <div style="background: #fff7ed; border-left: 4px solid #ea580c; padding: 14px 18px; border-radius: 6px; margin: 20px 0;">
      <strong style="color: #9a3412;">Recommended Immediate Farm Actions:</strong>
      <ul style="margin: 8px 0 0; padding-left: 20px; color: #7c2d12;">
        <li>Harvest mature vegetable, tomato, shallot, and fruit crops immediately to prevent waterlogging.</li>
        <li>Clear all farm drainage channels to prevent stagnant water in root zones.</li>
        <li>Move harvested produce bags to elevated, tarpaulin-covered dry shelters.</li>
        <li>Post urgent rescue lots on FarmFresh Rescue to connect with ready bulk buyers at fair rates.</li>
      </ul>
    </div>

    <div style="text-align: center; margin: 28px 0;">
      <a href="http://127.0.0.1:5000/add-listing" style="background: #ea580c; color: #ffffff !important; text-decoration: none; padding: 13px 30px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 4px 12px rgba(234, 88, 12, 0.3);">
        ➕ List Harvest for Urgent Rescue &rarr;
      </a>
    </div>

    <p style="font-size: 13px; color: #64748b; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
      FarmFresh Rescue Control Center &bull; Zero-Waste Agricultural Protection &bull; Tamil Nadu
    </p>
  </div>
</div>"""
    },
    'harvest_buyer': {
        'id': 'harvest_buyer',
        'name': '🛒 Fresh Direct Harvest Availability (For Buyers)',
        'target_audience': 'buyer',
        'subject': '🛒 New Verified Direct Farm Produce Batches Available - FarmFresh Rescue',
        'html': """<div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #bbf7d0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
  <div style="background: linear-gradient(135deg, #15803d, #16a34a); padding: 24px; color: #ffffff; text-align: center;">
    <div style="font-size: 34px; margin-bottom: 6px;">🥕</div>
    <h2 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">Fresh Direct Harvest Batches Available</h2>
    <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">Zero-Intermediary Wholesale Agricultural Procurement</div>
  </div>
  <div style="padding: 26px 24px; color: #1e293b; font-size: 15px; line-height: 1.6;">
    <p style="margin-top: 0;"><strong>Dear Wholesale Buyer / Hotelier / Retail Partner,</strong></p>
    <p>Tamil Nadu farmers have listed premium, freshly harvested crop lots on <strong>FarmFresh Rescue</strong>. Procure directly at source rates with guaranteed freshness.</p>
    
    <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 14px 18px; border-radius: 6px; margin: 20px 0;">
      <strong style="color: #166534;">Today's Priority Harvest Categories:</strong>
      <ul style="margin: 8px 0 0; padding-left: 20px; color: #14532d;">
        <li><strong>Country & Hybrid Tomatoes:</strong> Direct farm lots in Dindigul, Salem, and Krishnagiri.</li>
        <li><strong>Small Onions (Chinna Vengayam):</strong> High-grade dry shallots from Tiruppur and Perambalur.</li>
        <li><strong>Green Chillies & Capsicum:</strong> Freshly plucked morning harvest at mandi-matching rates.</li>
        <li><strong>Orchard Fresh Fruits:</strong> Bananas, guavas, and papayas ready for immediate dispatch.</li>
      </ul>
    </div>

    <div style="text-align: center; margin: 28px 0;">
      <a href="http://127.0.0.1:5000/browse" style="background: #16a34a; color: #ffffff !important; text-decoration: none; padding: 13px 30px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 4px 12px rgba(22, 163, 74, 0.3);">
        🔍 Browse & Order Fresh Lots &rarr;
      </a>
    </div>

    <p style="font-size: 13px; color: #64748b; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
      FarmFresh Rescue Buyer Desk &bull; 100% Direct Farmer Trade &bull; Tamil Nadu
    </p>
  </div>
</div>"""
    },
    'market_both': {
        'id': 'market_both',
        'name': '🌾 Statewide Market Trends & Zero-Waste Trading (For Both)',
        'target_audience': 'both',
        'subject': '🌾 FarmFresh Statewide Market Advisory & Zero-Waste Trading Update',
        'html': """<div style="font-family: 'Inter', -apple-system, sans-serif; max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #bfdbfe; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
  <div style="background: linear-gradient(135deg, #1e40af, #2563eb); padding: 24px; color: #ffffff; text-align: center;">
    <div style="font-size: 34px; margin-bottom: 6px;">🌾</div>
    <h2 style="margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">Statewide Agricultural Market Advisory</h2>
    <div style="font-size: 13px; opacity: 0.9; margin-top: 4px;">Tamil Nadu Direct Farm Trade & Policy Briefing</div>
  </div>
  <div style="padding: 26px 24px; color: #1e293b; font-size: 15px; line-height: 1.6;">
    <p style="margin-top: 0;"><strong>Dear FarmFresh Platform Member,</strong></p>
    <p>Here is your regular briefing on agricultural market trends, direct trade protections, and zero-waste logistics across Tamil Nadu.</p>
    
    <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 14px 18px; border-radius: 6px; margin: 20px 0;">
      <strong style="color: #1e40af;">Key Platform Updates & Trading Highlights:</strong>
      <ul style="margin: 8px 0 0; padding-left: 20px; color: #1e3a8a;">
        <li><strong>In-Person Farm Meetings:</strong> Buyers can schedule direct on-farm quality inspections before purchase.</li>
        <li><strong>Escrow Settlement Security:</strong> All digital payments are held in escrow and settled swiftly upon delivery sign-off.</li>
        <li><strong>Zero Waste Impact:</strong> Thousands of kg of fresh produce successfully rescued this season across 38 districts.</li>
        <li><strong>Fair Mandi Price Benchmarks:</strong> AI Price Engine updated with live Koyambedu & regional regulated market indices.</li>
      </ul>
    </div>

    <div style="text-align: center; margin: 28px 0;">
      <a href="http://127.0.0.1:5000/" style="background: #2563eb; color: #ffffff !important; text-decoration: none; padding: 13px 30px; border-radius: 8px; font-weight: 700; font-size: 15px; display: inline-block; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);">
        🚀 Visit FarmFresh Rescue Platform &rarr;
      </a>
    </div>

    <p style="font-size: 13px; color: #64748b; margin-top: 24px; border-top: 1px solid #f1f5f9; padding-top: 16px;">
      FarmFresh Rescue &bull; Tamil Nadu Direct Agricultural Initiative &bull; Vanakkam
    </p>
  </div>
</div>"""
    }
}

def send_broadcast_communication(target_audience: str, subject: str, html_content: str, text_content: str = None, single_email: str = None, base_url: str = 'http://127.0.0.1:5000'):
    """
    Deliver targeted broadcast emails to:
    - 'farmer': All active registered farmers
    - 'buyer': All active registered buyers
    - 'both': All active registered users
    - 'single': Specific single recipient email
    """
    conn = get_db()
    cursor = conn.cursor()
    
    recipients = []
    if target_audience == 'single' and single_email:
        recipients = [{'name': 'Subscriber', 'email': single_email.strip().lower()}]
    elif target_audience == 'farmer':
        cursor.execute("SELECT name, email FROM users WHERE role = 'farmer' AND is_active = 1")
        recipients = [dict(r) for r in cursor.fetchall()]
    elif target_audience == 'buyer':
        cursor.execute("SELECT name, email FROM users WHERE role = 'buyer' AND is_active = 1")
        recipients = [dict(r) for r in cursor.fetchall()]
    else: # 'both'
        cursor.execute("SELECT name, email FROM users WHERE is_active = 1")
        recipients = [dict(r) for r in cursor.fetchall()]

    conn.close()

    if not recipients:
        return False, "No active recipient users found for selected audience.", 0, 0

    success_count = 0
    fail_count = 0
    
    for r in recipients:
        r_email = r.get('email', '').strip()
        r_name = r.get('name', 'Partner')
        if not r_email or '@' not in r_email:
            continue
        
        personalized_html = html_content.replace('{user_name}', r_name)
        ok, msg = send_email(r_email, subject, personalized_html, text_content)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    log_activity(
        'EMAIL_BROADCAST_COMPLETED',
        f"Audience: {target_audience} | Delivered: {success_count}/{len(recipients)} | Subject: {subject}",
        'admin'
    )
    return True, f"Broadcast complete: {success_count} emails dispatched ({fail_count} failed) to {target_audience}.", success_count, fail_count
