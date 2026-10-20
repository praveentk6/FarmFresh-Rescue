# FarmFresh Rescue 🌾
**A Real-Time Platform to Reduce Agricultural Produce Waste by Connecting Farmers with Nearby Buyers**

![Python](https://img.shields.io/badge/Python-3.14-green)
![Flask](https://img.shields.io/badge/Flask-3.1-emerald)
![Database](https://img.shields.io/badge/SQLite-database.db-blue)
![Frontend](https://img.shields.io/badge/Frontend-HTML5%20%7C%20CSS3%20%7C%20Vanilla%20JS-orange)
![Region](https://img.shields.io/badge/Region-Tamil%20Nadu-gold)

---

## 1. Project Overview & Objective
**FarmFresh Rescue** solves a critical post-harvest challenge in Indian agriculture: **food waste resulting from temporary market gluts and distribution bottlenecks**. During peak harvests, smallholder farmers often struggle with unsold perishable fruits and vegetables, risking total financial loss and crop spoilage.

FarmFresh Rescue provides a real-time digital bridge between **Farmers** and nearby **Commercial Buyers** (hotels, restaurants, supermarkets, caterers, and food processing units). The system dynamically detects listings that remain unsold for **3 or more days** and highlights them with a prominent **Needs Attention** badge to incentivize rapid buyer clearance at attractive wholesale rates.

---

## 2. Key Features
- **Role-Based Portals**:
  - **Farmer**: Register, login, create produce listings, upload crop photos, set quantities and prices in ₹ (INR), specify harvest dates & Tamil Nadu PIN codes, update/edit listings, mark produce as **Sold / Rescued**, and respond to buyer enquiries.
  - **Buyer**: Register, login, browse the marketplace, search by crop name/PIN/village, filter by Tamil Nadu district, price range, and quantity, filter specifically for **Needs Attention** items, call farmers directly, initiate WhatsApp chats, or submit counter-offers/enquiries.
  - **Admin**: Monitor platform-wide statistics (available batches, urgent unsold batches, rescued batches, total users), moderate/delete duplicate or spam listings, manage registered user accounts, and inspect the real-time activity audit log.
- **Urgent Rescue Indicator ("Needs Attention" Badge)**:
  - Automatically flags available listings that are 3+ days old with a pulsing indicator.
  - Includes a transparent disclaimer clarifying that the indicator reflects listing duration on the platform to prevent waste and does not claim to replace physical inspection or certify laboratory freshness.
- **Tamil Nadu Agricultural Focus**:
  - Built-in data covering key agricultural hubs: **Krishnagiri** (Tomatoes), **Dindigul / Ottanchathiram** (Shallots), **The Nilgiris / Ooty** (Carrots), **Pollachi** (Tender Coconuts), **Madurai** (Jasmine Buds), and **Thanjavur** (Ponni Rice).
- **Responsive & Modern Design**:
  - Fresh green, white, and earthy warm tones.
  - Smooth card layouts, micro-animations, mobile responsive navigation, and modal enquiries.
- **Security & Data Integrity**:
  - Server-side input validation and error feedback.
  - Password hashing with PBKDF2/SHA256 (`werkzeug.security`).
  - Secure parameterized SQLite queries.
  - Ownership verification on edit and delete operations.
  - Image type and file size validation (max 3MB, PNG/JPG/WEBP) with PIL image verification.

---

## 3. Technology Stack & Directory Structure
- **Backend**: Python Flask 3.1
- **Database**: SQLite 3 (`database.db`)
- **Frontend**: Responsive HTML5, Vanilla CSS3 (custom design system), JavaScript (ES6)
- **Image Processing**: Pillow (PIL)

```
c:\Users\win\OneDrive\Documents\mca project/
├── app.py                     # Flask web server, routes, auth & business logic
├── database.py                # SQLite schema definition, connection helpers, and seed data
├── requirements.txt           # Dependencies (Flask, Werkzeug, Pillow)
├── README.md                  # Comprehensive setup and documentation
├── database.db                # SQLite database file
├── static/
│   ├── css/
│   │   └── style.css          # Responsive styling, color tokens, badges & tables
│   ├── js/
│   │   └── main.js            # Image preview, modals, fast-fill, confirmations
│   └── uploads/               # Uploaded crop images & seed demo photos
└── templates/
    ├── base.html              # Base layout with navbar, flash alerts, and footer
    ├── index.html             # Homepage with hero, live counters, urgent spotlight
    ├── listings.html          # Produce marketplace with search and multi-filtering
    ├── listing_detail.html    # Full produce details, farmer card, WhatsApp/Call CTA, modal
    ├── add_listing.html       # Farmer add produce form with image live preview
    ├── edit_listing.html      # Farmer edit listing form
    ├── farmer_dashboard.html  # Farmer management center (listings table, mark as sold, enquiries)
    ├── buyer_dashboard.html   # Buyer tracking center (sent enquiries & recommendations)
    ├── admin_dashboard.html   # Admin control center (KPIs, user management, moderation, audit log)
    ├── login.html             # Login with 1-click test fill buttons
    ├── register.html          # Registration with role selection (Farmer / Buyer)
    ├── about.html             # Waste reduction mission, urgency explanation & TN hubs
    └── 404.html               # Custom 404 error page
```

---

## 4. Setup & Installation Instructions

### Step 1: Open Terminal in Project Directory
Open PowerShell or Command Prompt in the project folder:
```powershell
cd "c:\Users\win\OneDrive\Documents\mca project"
```

### Step 2: Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### Step 3: Initialize and Seed Database
Run the database initialization script (pre-populates realistic Tamil Nadu farmer listings, urgent batches, and sample enquiries):
```powershell
python database.py
```

### Step 4: Start the Flask Application
```powershell
python app.py
```

Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## 5. Demo Accounts for Immediate Testing
On the Login page (`/login`), you can use the **1-Click Quick Test Login buttons** or enter the credentials below:

| Role | Name & Region | Email | Password |
|---|---|---|---|
| **Farmer** | Selvi Shanmugam (Krishnagiri) | `selvi.farms@gmail.com` | `farmer123` |
| **Farmer** | Muthuvel Karuppan (Dindigul) | `muthu.farmer@gmail.com` | `farmer123` |
| **Buyer** | Saravana Bhavan Procurement (Madurai) | `saravana.hotel@gmail.com` | `buyer123` |
| **Buyer** | Kumar Daily Fresh Mart (Coimbatore) | `kumar.mart@gmail.com` | `buyer123` |
| **Admin** | Platform Administrator (Chennai) | `admin@farmfresh.org` | `admin123` |

---

## 6. Testing User Workflows

### 1. Urgent Produce Rescue Workflow
1. Visit the Home Page (`/`) or Marketplace (`/listings`).
2. Notice the **Needs Attention** badge on batches like **Krishnagiri Tomatoes** and **Dindigul Small Onions** that have been listed for 4 days.
3. Click on the listing to view details, harvest date, and age.
4. Click **Call Farmer** or **WhatsApp Chat** to test immediate contact.
5. Click **Send Purchase Enquiry** to send a formal purchase request with quantity and offer price.

### 2. Farmer Workflow
1. Log in as `selvi.farms@gmail.com` (password: `farmer123`).
2. You will be directed to the **Farmer Dashboard**.
3. View listing statistics, older listings needing attention, and received enquiries.
4. Click **+ Post New Produce Listing** to add a new crop with photos, unit, and harvest date.
5. Click **Mark Sold** on an active listing to record that the produce was successfully rescued.
6. Respond to incoming buyer enquiries by updating status to **Accepted** or **Completed**.

### 3. Buyer Workflow
1. Log in as `saravana.hotel@gmail.com` (password: `buyer123`).
2. Go to **Browse Produce** and filter by district (e.g. `Krishnagiri`, `Dindigul`).
3. Click the **3+ Days Unsold (Needs Attention)** quick filter to discover high-urgency batches.
4. Check **My Enquiries** on the Buyer Dashboard to monitor responses from farmers.

### 4. Admin Workflow
1. Log in as `admin@farmfresh.org` (password: `admin123`).
2. Access the **Admin Control Center** (`/admin/dashboard`).
3. Review total platform statistics, manage/delete inappropriate listings, review user accounts, and inspect the real-time activity audit log.
