import unittest
import json
from app import app
from database import get_db

class TestFarmFreshRescue(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

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
            res = self.client.get(r)
            self.assertEqual(res.status_code, 200, f"Route {r} failed with status {res.status_code}")

    def test_02_language_switching(self):
        # Switch to Tamil
        res = self.client.get('/set-language/ta', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Check cookie or session
        res_home = self.client.get('/')
        self.assertIn(b'lang-ta', res_home.data)

        # Switch back to English
        res = self.client.get('/set-language/en', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        res_home = self.client.get('/')
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
            sess['user_id'] = 1 # Admin
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
            sess['user_id'] = 1  # Admin
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


if __name__ == '__main__':
    unittest.main()
