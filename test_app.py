import unittest
import json
import auth_service
from app import app
from database import get_db

class TestFarmFreshRescue(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        admin = auth_service.get_user_by_email('pp274142@gmail.com')
        self.admin_id = admin['id'] if admin else 103

    def test_01_public_routes(self):
        routes = [
            '/',
            '/about',
            '/listings',
            '/listings?urgency=urgent_only',
            '/listing/1',
            '/nearby-buyers',
            '/ai-assistant',
            '/login',
            '/register'
        ]
        for r in routes:
            res = self.client.get(r, follow_redirects=False)
            expected_status = 302 if r == '/' else 200
            self.assertEqual(res.status_code, expected_status, f"Route {r} failed with status {res.status_code}")

    def test_02_language_switching(self):
        # Switch to Tamil
        res = self.client.get('/set-language/ta', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Check cookie or session
        res_home = self.client.get('/', follow_redirects=True)
        self.assertIn(b'lang-ta', res_home.data)

        # Switch back to English
        res = self.client.get('/set-language/en', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        res_home = self.client.get('/', follow_redirects=True)
        self.assertIn(b'lang-en', res_home.data)

    def test_03_farmer_dashboard_and_kpis(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2 # Selvi
            sess['user_role'] = 'farmer'
        
        res = self.client.get('/farmer/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'kpiTotalProducts', res.data)
        self.assertIn(b'kpiAvailableQty', res.data)
        self.assertIn(b'kpiPendingOrders', res.data)
        self.assertIn(b'kpiCompletedSales', res.data)
        self.assertIn(b'kpiProduceAtRisk', res.data)
        self.assertIn(b'kpiTotalRevenue', res.data)

    def test_04_buyer_dashboard(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 6 # Saravana Bhavan Procurement
            sess['user_role'] = 'buyer'

        res = self.client.get('/buyer/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'postRequirementSection', res.data)

    def test_05_admin_dashboard(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['user_role'] = 'admin'

        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)

    def test_06_analytics_view(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_role'] = 'farmer'

        res = self.client.get('/analytics')
        self.assertEqual(res.status_code, 200)

    def test_07_notifications_view(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['user_role'] = 'farmer'

        res = self.client.get('/notifications')
        self.assertEqual(res.status_code, 200)

    def test_08_order_workflow_and_inventory(self):
        # Reset listing 1 stock & status to Available for test repeatability
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE listings SET status = 'Available', quantity = 500 WHERE id = 1")
        conn.commit()
        conn.close()

        # 1. Buyer submits purchase order
        order_data = {
            'listing_id': '1',
            'buyer_name': 'Test Hotel Procurement',
            'buyer_phone': '9840199999',
            'buyer_email': 'test.hotel@gmail.com',
            'requested_quantity': '50',
            'offered_price': '18',
            'delivery_preference': 'Direct Pickup / Collection at Farm',
            'message': 'We can collect tomorrow morning at farmgate.'
        }
        res = self.client.post('/order/submit', data=order_data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        # Get latest order id
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id, listing_id, requested_quantity, status FROM enquiries ORDER BY id DESC LIMIT 1")
        order = c.fetchone()
        c.execute("SELECT farmer_id FROM listings WHERE id = 1")
        farmer_id = c.fetchone()['farmer_id']
        conn.close()

        self.assertIsNotNone(order)
        order_id = order['id']
        self.assertEqual(order['status'], 'Pending')

        # 2. Farmer accepts order
        with self.client.session_transaction() as sess:
            sess['user_id'] = farmer_id
            sess['user_role'] = 'farmer'

        res_accept = self.client.post(f'/order/update-status/{order_id}', data={'status': 'Accepted'}, follow_redirects=False)
        self.assertEqual(res_accept.status_code, 302)

        # 3. Farmer marks ready for pickup
        res_ready = self.client.post(f'/order/update-status/{order_id}', data={'status': 'Ready for Collection'}, follow_redirects=False)
        self.assertEqual(res_ready.status_code, 302)

        # Check stock before complete
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT quantity FROM listings WHERE id = 1")
        stock_before = c.fetchone()['quantity']

        # 4. Farmer completes sale
        res_complete = self.client.post(f'/order/update-status/{order_id}', data={'status': 'Completed'}, follow_redirects=False)
        self.assertEqual(res_complete.status_code, 302)

        # Verify stock deducted
        c.execute("SELECT quantity FROM listings WHERE id = 1")
        stock_after = c.fetchone()['quantity']
        conn.close()

        self.assertAlmostEqual(stock_after, stock_before - 50.0)

    def test_09_ai_rescue_api(self):
        res = self.client.post('/api/ai-rescue-advice', json={
            'crop_name': 'Country Tomatoes',
            'quantity': '200',
            'unit': 'kg',
            'harvest_date': '2026-10-18',
            'freshness_obs': 'Ripe red, slight softness on stems',
            'storage_condition': 'Ambient / Room Temperature',
            'location': 'Erode',
            'urgency': 'Critical'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('recommended_actions', data)
        self.assertIn('target_buyers', data)
        self.assertIn('english_pitch', data)
        self.assertIn('tamil_pitch', data)

    def test_11_admin_sample_data_workflow(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['user_role'] = 'admin'

        # 1. Admin dashboard shows sample data section
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'sample-data', res.data)

        # 2. Admin can remove sample data
        res_remove = self.client.post('/admin/sample-data/remove', follow_redirects=True)
        self.assertEqual(res_remove.status_code, 200)
        self.assertIn(b'No Sample Data', res_remove.data)

        # 3. Admin can reset/re-seed sample data
        res_reset = self.client.post('/admin/sample-data/reset', follow_redirects=True)
        self.assertEqual(res_reset.status_code, 200)
        self.assertIn(b'10 Demo Vegetables Active', res_reset.data)

    def test_12_ai_freshness_api(self):
        res = self.client.post('/api/ai/freshness-predict', json={
            'crop_name': 'Tomatoes',
            'harvest_date': '2026-10-29',
            'storage_condition': 'cold_storage',
            'quantity': 150
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('freshness_score', data)
        self.assertIn('status', data)

    def test_13_ai_price_recommendation_api(self):
        res = self.client.post('/api/ai/price-recommend', json={
            'crop_name': 'Carrots',
            'quantity': 200,
            'harvest_date': '2026-10-30',
            'storage_condition': 'ambient',
            'asking_price': 35
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('suggested_price', data)
        self.assertIn('expected_revenue', data)

    def test_14_ai_buyer_matching_api(self):
        res = self.client.get('/api/ai/match-buyers/1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('matches', data)

    def test_15_voice_assistant_page_and_api(self):
        # 1. Voice page GET
        res_page = self.client.get('/voice-assistant')
        self.assertEqual(res_page.status_code, 200)
        self.assertIn(b'voice', res_page.data.lower())

        # 2. Voice command parsing in Tamil
        res_ta = self.client.post('/api/ai/voice-command', json={
            'speech_text': 'தக்காளி 100 கிலோ விற்பனைக்கு சேர்க்கவும்',
            'lang': 'ta'
        })
        self.assertEqual(res_ta.status_code, 200)
        data_ta = res_ta.get_json()
        self.assertEqual(data_ta['intent'], 'add_produce')

        # 3. Voice command parsing in English
        res_en = self.client.post('/api/ai/voice-command', json={
            'speech_text': 'Where are my orders?',
            'lang': 'en'
        })
        self.assertEqual(res_en.status_code, 200)
        data_en = res_en.get_json()
        self.assertEqual(data_en['intent'], 'check_orders')

    def test_16_quality_grading_page_and_api(self):
        import io
        from PIL import Image

        # 1. Quality grading page GET
        res_page = self.client.get('/quality-grading')
        self.assertEqual(res_page.status_code, 200)

        # 2. Grade produce API with synthetic test image
        img_byte_arr = io.BytesIO()
        test_img = Image.new('RGB', (100, 100), color=(200, 40, 40))
        test_img.save(img_byte_arr, format='JPEG')
        img_byte_arr.seek(0)

        res_grade = self.client.post('/api/ai/grade-produce', data={
            'crop_name': 'Tomatoes',
            'photo': (img_byte_arr, 'test_crop.jpg')
        }, content_type='multipart/form-data')

        self.assertEqual(res_grade.status_code, 200)
        data_grade = res_grade.get_json()
        self.assertIn('quality_grade', data_grade)
        self.assertIn(data_grade['quality_grade'], ['Grade A', 'Grade B', 'Grade C'])

    def test_17_demand_prediction_page_and_api(self):
        # 1. Demand prediction page GET
        res_page = self.client.get('/demand-prediction')
        self.assertEqual(res_page.status_code, 200)

        # 2. Demand prediction API GET
        res_api = self.client.get('/api/ai/demand-prediction')
        self.assertEqual(res_api.status_code, 200)
        data_api = res_api.get_json()
        self.assertIn('predictions', data_api)

    def test_18_order_tracking_and_timeline(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['user_role'] = 'admin'

        # Order 1 tracking page
        res = self.client.get('/order/track/1')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'deliveryMap', res.data)

        # Order 1 timeline API
        res_api = self.client.get('/api/order/timeline/1')
        self.assertEqual(res_api.status_code, 200)
        data = res_api.get_json()
        self.assertTrue(data['success'])
        self.assertIn('timeline', data)

    def test_19_ai_chatbot_api(self):
        res = self.client.post('/api/ai/chatbot', json={
            'message': 'What is the current market price for tomatoes?'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn('reply', data)

    def test_20_buyer_favorite_and_export_csv(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 6  # Buyer
            sess['user_role'] = 'buyer'

        # Toggle favorite farmer
        res_fav = self.client.post('/api/buyer/favorite-farmer/2')
        self.assertEqual(res_fav.status_code, 200)
        data_fav = res_fav.get_json()
        self.assertTrue(data_fav['success'])
        self.assertIn('favorited', data_fav)

        # CSV Export
        res_csv = self.client.get('/analytics/export-csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.content_type, 'text/csv; charset=utf-8')
        self.assertIn(b'Order ID', res_csv.data)


if __name__ == '__main__':
    unittest.main()
