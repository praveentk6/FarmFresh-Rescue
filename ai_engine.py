import os
import json
import urllib.request
import urllib.error
from datetime import datetime, date

def get_ai_rescue_advice(crop_name, quantity, unit, harvest_date, freshness_obs, storage_condition, location, urgency='Normal', lang='en'):
    """
    Generates actionable selling strategies and spoilage prevention advice for farmers.
    Attempts external AI API call (Google Gemini / OpenAI) if API key configured,
    otherwise uses intelligent, rule-based agronomic knowledge engine.
    """
    crop_name = (crop_name or "").strip()
    location = (location or "Tamil Nadu").strip()
    freshness_obs = (freshness_obs or "").strip()
    storage_condition = (storage_condition or "Ambient / Room Temperature").strip()
    urgency = (urgency or "Normal").strip()

    gemini_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('AI_API_KEY')
    openai_key = os.environ.get('OPENAI_API_KEY')

    # Try external Gemini API if key is present
    if gemini_key:
        try:
            advice = call_gemini_api(gemini_key, crop_name, quantity, unit, harvest_date, freshness_obs, storage_condition, location, urgency)
            if advice:
                advice['source'] = 'Google Gemini AI'
                return advice
        except Exception as e:
            print(f"Notice: Gemini API call fallback: {e}")

    # Fallback to rich expert agronomic engine
    return generate_expert_agronomic_advice(crop_name, quantity, unit, harvest_date, freshness_obs, storage_condition, location, urgency)

def call_gemini_api(api_key, crop_name, quantity, unit, harvest_date, freshness_obs, storage_condition, location, urgency):
    """Call Google Gemini 1.5 Flash endpoint using standard library urllib."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
You are an agricultural marketplace and post-harvest produce advisor for Tamil Nadu farmers in India.
Analyze the following farm produce and provide a practical rescue strategy to prevent post-harvest waste:
Produce: {crop_name}
Quantity: {quantity} {unit}
Harvest Date: {harvest_date}
Current Observations: {freshness_obs or 'Freshly harvested, standard market state'}
Storage Conditions: {storage_condition}
Location: {location}, Tamil Nadu
Stated Urgency: {urgency}

Rules:
1. Do not state an exact laboratory spoilage time; provide safe practical estimation based on storage and crop type.
2. Do not invent fake market prices.
3. Suggest the most suitable buyer categories in Tamil Nadu (e.g. food processors, hotels, juice shops, wholesale mandis).
4. Provide practical lot-splitting and preservation tips.
5. Provide a short marketing pitch in English and in Tamil for WhatsApp.

Respond ONLY with valid JSON in this format:
{{
  "urgency_assessment": "...",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "target_buyers": ["category 1", "category 2"],
  "storage_tips": "...",
  "english_pitch": "...",
  "tamil_pitch": "..."
}}
"""
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.3,
            "responseMimeType": "application/json"
        }
    }

    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode('utf-8'))
        text_content = result['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text_content)
        data['disclaimer'] = "AI-generated practical guidance based on provided observations. Not an exact laboratory certificate."
        return data

def generate_expert_agronomic_advice(crop_name, quantity, unit, harvest_date, freshness_obs, storage_condition, location, urgency):
    """
    Robust agronomic engine tailored to Tamil Nadu agriculture crops:
    tomatoes, shallots, carrots, bananas, greens, coconuts, flowers, etc.
    """
    crop_lower = crop_name.lower()
    days_since_harvest = 1
    if harvest_date:
        try:
            h_dt = datetime.strptime(harvest_date, '%Y-%m-%d').date()
            days_since_harvest = max(0, (date.today() - h_dt).days)
        except Exception:
            days_since_harvest = 1

    # Perishable profiles
    is_highly_perishable = any(c in crop_lower for c in ['tomato', 'keerai', 'spinach', 'flower', 'malli', 'jasmine', 'mushroom', 'curry leaf', 'coriander'])
    is_moderately_perishable = any(c in crop_lower for c in ['carrot', 'beans', 'brinjal', 'eggplant', 'okra', 'lady', 'cabbage', 'cauliflower', 'banana', 'guava'])
    is_durable = any(c in crop_lower for c in ['onion', 'shallot', 'vengayam', 'potato', 'coconut', 'garlic', 'ginger', 'rice', 'grain', 'pulse', 'turmeric'])

    # Determine assessment
    if is_highly_perishable:
        shelf_life_desc = "Highly perishable crop. Ambient shelf life is typically 3 to 5 days from harvest."
        if days_since_harvest >= 3 or urgency in ['Critical', 'High']:
            urgency_level = "High Urgency - Immediate Clearance Recommended"
            strategy = "Offer in smaller lots (e.g. 20-25 kg crates) to local mess, restaurants, or sauce/puree processors in your district."
        else:
            urgency_level = "Moderate Urgency - Plan Buyer Contact Within 48 Hours"
            strategy = "Connect with local vegetable retailers, supermarkets, or weekly shandies (Uzhavar Sandhai)."
        target_buyers = [
            "Hotels and Restaurants (Daily kitchen consumption)",
            "Vegetable Shops & Retailers",
            "Food Processing Companies (Sauces, Purees, Chutneys)"
        ]
        storage_tips = "Keep well-ventilated in single-layer wooden crates out of direct sunlight. Do not seal in airtight plastic bags."
        
    elif is_moderately_perishable:
        shelf_life_desc = "Moderately perishable. Typically maintains good commercial quality for 5 to 8 days with good airflow."
        if days_since_harvest >= 5 or urgency in ['Critical', 'High']:
            urgency_level = "High Urgency - Swift Clearance Needed"
            strategy = "Bundle into wholesale crates. Offer 10-15% discount for bulk clearance by hotels or caterers."
        else:
            urgency_level = "Normal - Fresh Harvest Window"
            strategy = "List on FarmFresh Rescue and reach out to local supermarket procurement desks."
        target_buyers = [
            "Supermarkets & Retail Chains",
            "Hotels, Caterers & Canteens",
            "Wholesale Mandis"
        ]
        storage_tips = "Store in shaded, cool, well-aerated area. Avoid stacking crates more than 3 high to prevent crushing."

    else:
        shelf_life_desc = "Storable produce. Retains good quality for 2 to 4 weeks if maintained under dry, moisture-free conditions."
        urgency_level = "Low to Moderate - Manage Moisture to Prevent Weight Loss"
        strategy = "Grade into size categories. Reach out to wholesale traders and regional grocery supermarkets."
        target_buyers = [
            "Wholesalers & Stockists",
            "Supermarkets",
            "Food Processing Companies"
        ]
        storage_tips = "Ensure zero floor moisture. Use dry jute gunny bags with wooden pallets underneath."

    # Practical recommendations
    recommended_actions = [
        f"Contact verified buyers in {location} or neighboring districts directly via Call or WhatsApp.",
        f"Consider dividing the total {quantity} {unit} into smaller lots (e.g., 20-50 kg) to attract multiple smaller retail shops or restaurants.",
        "Highlight your harvest date and pesticide-free / natural freshness in your listing description.",
        "If buyer pickup is available at farm-gate, specify it to reduce your transportation overhead."
    ]

    # English pitch
    english_pitch = (
        f"🌾 Farm-Direct Fresh {crop_name} available in {location}! "
        f"Harvested on {harvest_date or 'recent harvest'}, total {quantity} {unit}. "
        f"Direct from farmer with zero middlemen. Suitable for hotels, retailers, and bulk buyers. "
        f"Contact directly for prompt pickup or delivery."
    )

    # Tamil pitch
    tamil_pitch = (
        f"🌾 பண்ணை நேரடி புதிய {crop_name}! "
        f"அறுவடை தேதி: {harvest_date or 'புதிய அறுவடை'}, மொத்த கையிருப்பு: {quantity} {unit}. "
        f"இடம்: {location}. இடைத்தரகர் இன்றி விவசாயியிடம் நேரடியாகப் பெற்றுக்கொள்ளலாம். "
        f"உணவகங்கள், காய்கறிக் கடைகள் மற்றும் மொத்த வியாபாரிகள் உடனடியாக தொடர்பு கொள்ளவும்."
    )

    return {
        'source': 'FarmFresh Agronomic Intelligence Engine',
        'urgency_assessment': urgency_level,
        'shelf_life_overview': shelf_life_desc,
        'recommended_actions': recommended_actions,
        'target_buyers': target_buyers,
        'storage_tips': storage_tips,
        'english_pitch': english_pitch,
        'tamil_pitch': tamil_pitch,
        'disclaimer': 'Practical agricultural suggestions based on crop physiology and typical Tamil Nadu market practices. Always verify actual physical produce firmness.'
    }
