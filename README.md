# FarmFresh Rescue AI 2.0 🌾
**An Intelligent AI-Powered Agricultural Marketplace to Eliminate Harvest Spoilage & Connect Farmers with Nearby Buyers**

Live Deployment: [https://farmfresh-rescue.onrender.com](https://farmfresh-rescue.onrender.com)

![Python](https://img.shields.io/badge/Python-3.14-green)
![Flask](https://img.shields.io/badge/Flask-3.1-emerald)
![AI Engine](https://img.shields.io/badge/AI%20Engine-Gemini%20API%20%2B%20Vision%20%2B%20Speech-blue)
![Database](https://img.shields.io/badge/SQLite-database.db-blue)
![Logistics](https://img.shields.io/badge/Maps-Leaflet.js%20%7C%20OSM-forestgreen)
![Region](https://img.shields.io/badge/Region-Tamil%20Nadu-gold)

---

## 1. Project Overview & Objective
**FarmFresh Rescue AI 2.0** upgrades the original platform into an intelligent, AI-powered agricultural marketplace dedicated to preventing food waste and post-harvest economic loss across Tamil Nadu.

Smallholder farmers frequently suffer financial loss during bumper harvests due to rapid spoilage, lack of cold chain infrastructure, and opaque local market pricing. FarmFresh Rescue AI 2.0 integrates **Google Gemini API**, **multilingual voice recognition (Tamil & English)**, **computer vision quality grading**, **algorithmic price recommendations**, **intelligent multi-factor buyer matching**, **open-source logistics routing**, and **real-time order lifecycle tracking** to clear fresh farmgate harvests before spoilage occurs.

---

## 2. 12 Core AI 2.0 Features

### 1. AI Freshness Prediction System
- Evaluates produce information: crop type, harvest date, elapsed days, and storage conditions (Ambient, Shaded Shed, Ventilated Crates, Cold Storage).
- Estimates remaining shelf life in hours/days and classifies produce into: **Fresh (70-100%)**, **Moderate (40-69%)**, and **Urgent Spoilage Risk (<40%)**.
- Prioritizes produce in the Farmer Dashboard **AI Priority Clearance Queue**.
- Transparent scientific estimate disclaimer displayed across all cards.

### 2. AI Smart Price Recommendation
- Analyzes crop name, lot size, current freshness score, and live marketplace listings.
- Compares against Tamil Nadu Uzhavar Sandhai & Mandi wholesale benchmarks.
- Displays: **Suggested Selling Price**, **Market Benchmark Price**, **Price Difference**, and **Expected Total Revenue**.
- 1-click **Accept AI Price** button auto-populates listing forms.

### 3. AI Smart Buyer Matching
- Multi-factor scoring algorithm matching farmers with commercial buyers based on:
  - Crop category compatibility (40 pts)
  - Requested procurement volume (20 pts)
  - Haversine geographic distance in kilometers (25 pts)
  - Target price match (15 pts)
- Displays match percentage, distance in km, and direct notification dispatch.

### 4. Bilingual Tamil & English AI Voice Assistant (`/voice-assistant`)
- Speech-to-text via browser Web Speech API with audio feedback via SpeechSynthesis.
- Full Tamil voice commands:
  - *"தக்காளி 100 கிலோ விற்பனைக்கு சேர்க்கவும்"* &rarr; Auto-fills listing form
  - *"எனது ஆர்டர்கள் எங்கே?"* &rarr; Reads pending order counts
  - *"அருகில் வாங்குபவர்கள் யார்?"* &rarr; Suggests nearby verified buyers
  - *"எனது பொருளின் விலையை பரிந்துரை செய்யவும்"* &rarr; Mandi benchmark price quote

### 5. AI Produce Quality Grading (`/quality-grading`)
- Multi-modal image analysis powered by Gemini 1.5 Flash Vision API with local Pillow computer vision fallback.
- Classifies fruit and vegetable harvests into:
  - **Grade A (Premium Retail & Export)**: Superior shape, color uniformity, zero skin blemishes.
  - **Grade B (Commercial & Supermarkets)**: Good market quality, minor cosmetic asymmetry.
  - **Grade C (Processing & Value Addition)**: Fully ripe, suited for sauces, purees, and pulping.
- Recommends tailored buyer channels based on physical grade.

### 6. AI Demand Prediction (`/demand-prediction`)
- Analyzes live marketplace listings, buyer procurement requirements, and completed order volume.
- Computes a dynamic **Market Demand Index (0-100)** for every major Tamil Nadu crop.
- Identifies **High Demand Crops** vs **Oversupplied Crops**.
- Transparently alerts farmers when transaction volume is insufficient rather than fabricating trends.

### 7. Real-Time 6-Stage Order Management
- Complete order lifecycle: `Pending` &rarr; `Accepted` &rarr; `Packed` &rarr; `Shipped` &rarr; `Delivered` / `Completed` (or `Cancelled`).
- Auto-deducts listing stock upon fulfillment.
- Comprehensive JSON status audit timeline for every transaction.

### 8. Smart Delivery Tracking & Interactive Route Map (`/order/track/<id>`)
- Interactive **Leaflet.js + OpenStreetMap** logistics visualizer (zero proprietary API keys required).
- Displays farmer farmgate coordinates, buyer destination coordinates, and road transit route.
- Calculates Haversine highway distance in km, estimated transit duration, and milestone progress stepper.
- Strict buyer/farmer privacy protection.

### 9. Farmer Profit & Revenue Analytics
- Comprehensive revenue tracking: **Total Sales**, **Completed Earnings**, **Pending Payments**, and **Estimated Profit Margin**.
- Visual breakdowns rendered with Chart.js and Recharts design tokens.
- 1-Click CSV export of sales and waste audit records (`/analytics/export-csv`).

### 10. Food Waste Reduction Tracker
- Tracks verified kilograms of produce rescued from landfill decomposition (only confirmed fulfilled orders counted).
- Calculates environmental impact based on FAO agricultural benchmarks:
  - **CO2e Emissions Prevented**: ~1.9 kg CO2e / kg produce
  - **Embedded Agricultural Water Conserved**: ~230 Liters / kg produce
- Transparent methodology statement ensuring authentic metric tracking.

### 11. Universal Floating AI FarmFresh Chatbot
- Omnipresent floating widget accessible from every page.
- Context-aware: greets users with their authenticated account role, active listings, and pending orders.
- Supports conversational Tamil and English.
- Voice input microphone and spoken audio toggle.

### 12. Improved Role-Specific Dashboards
- **Farmer Dashboard**: 6 KPI cards, AI Freshness Priority Clearance Queue, top recommended buyers, and order status controls.
- **Buyer Dashboard**: Active procurement tracking, route map buttons, AI recommended produce, and favorited farmers.
- **Admin Dashboard**: Platform-wide rescued kg, total revenue, user verification directory, and moderation tools.

---

## 3. Technology Stack

- **Backend**: Python 3.14 / Flask 3.1
- **Database**: SQLite 3 (`database.db`) with relational integrity and automatic schema migrations
- **AI & ML**: Google Gemini 1.5 Flash API + rule-based agronomic algorithms
- **Computer Vision**: Gemini Multimodal Vision API + Pillow (PIL)
- **Logistics & Maps**: Leaflet.js + OpenStreetMap Tile Layer
- **Charts**: Chart.js / Recharts-style CSS
- **Voice & Speech**: Web Speech API (`SpeechRecognition` & `SpeechSynthesis`)
- **Server / WSGI**: Gunicorn 23.0

---

## 4. Setup & Local Execution

### Step 1: Clone Repository
```powershell
git clone https://github.com/praveentk6/FarmFresh-Rescue.git
cd FarmFresh-Rescue
```

### Step 2: Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run Database Migrations
```powershell
python database.py
```

### Step 4: (Optional) Set Gemini API Key
To enable cloud Gemini AI multimodal capabilities, set the environment variable:
```powershell
$env:GEMINI_API_KEY="your-gemini-api-key-here"
```
*(If unset, the platform seamlessly uses its built-in local agronomic AI expert fallback).*

### Step 5: Start the Application
```powershell
python app.py
```
Open your browser at: **http://127.0.0.1:5000**

---

## 5. Deployment on Render

This repository is pre-configured for automated zero-downtime deployment on Render:

1. **Link Repository**: Create a new Web Service on [Render Dashboard](https://dashboard.render.com) and connect `https://github.com/praveentk6/FarmFresh-Rescue.git`.
2. **Runtime**: Select **Python 3**.
3. **Build Command**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Start Command**:
   ```bash
   gunicorn app:app
   ```
   *(Or Render reads `Procfile` automatically)*.
5. **Environment Variables**:
   - `SECRET_KEY`: Set to a strong random secret key.
   - `GEMINI_API_KEY`: (Optional) Your Google Gemini API key.
   - `PYTHON_VERSION`: `3.11.0` or higher.
6. **Deploy**: Click **Create Web Service**. Render builds the service and exposes it at your `.onrender.com` domain.

---

## 6. Pre-Configured Demo Accounts

| Role | Name & Region | Email | Password |
|---|---|---|---|
| **Farmer** | Selvi Shanmugam (Krishnagiri) | `selvi.farms@gmail.com` | `farmer123` |
| **Farmer** | Muthuvel Karuppan (Dindigul) | `muthu.farmer@gmail.com` | `farmer123` |
| **Buyer** | Saravana Bhavan Procurement (Madurai) | `saravana.hotel@gmail.com` | `buyer123` |
| **Buyer** | Kumar Daily Fresh Mart (Coimbatore) | `kumar.mart@gmail.com` | `buyer123` |
| **Admin** | Platform Administrator (Chennai) | `admin@farmfresh.org` | `admin123` |

---

## 7. Automated Test Suite
Run the 19 comprehensive unit tests covering all routes, authentication, AI endpoints, and order lifecycles:
```powershell
python test_app.py
```
Expected output:
```
Ran 19 tests in 2.3s
OK
```
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
