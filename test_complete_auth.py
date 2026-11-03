import unittest
import os
import json
import auth_service
from app import app
from database import get_db

class TestCompleteAuthSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # Ensure single admin is seeded
        auth_service.seed_single_admin_account()

    def setUp(self):
        self.client = app.test_client()

    def test_01_root_unauthenticated_redirects_to_login(self):
        """Visiting root / when not authenticated must redirect to /login (Requirement 1)."""
        response = self.client.get('/', follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers.get('Location', ''))

    def test_02_login_page_renders_with_three_roles(self):
        """Login page must display options for Farmer, Buyer, and Admin."""
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        html = response.data.decode('utf-8')
        self.assertIn("Farmer Login", html)
        self.assertIn("Buyer Login", html)
        self.assertIn("Admin Login", html)
        self.assertIn("FarmFresh", html)

    def test_03_farmer_registration_web(self):
        """Farmer registration form validation and dashboard redirect."""
        test_email = "test.farmer.new@gmail.com"
        # Cleanup if previously existed
        conn = get_db()
        conn.cursor().execute("DELETE FROM users WHERE LOWER(email) = ?", (test_email,))
        conn.commit()
        conn.close()

        data = {
            'role': 'farmer',
            'name': 'Ramasamy Farmer',
            'email': test_email,
            'phone': '9876543210',
            'location': 'Ottanchathiram, Dindigul',
            'pin_code': '624619',
            'user_type': 'Vegetable Cultivator',
            'password': 'farmerSecret123',
            'confirm_password': 'farmerSecret123',
            'terms': '1'
        }
        res = self.client.post('/register_post', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        loc = res.headers.get('Location', '')
        self.assertTrue('/dashboard/farmer' in loc or '/farmer/dashboard' in loc)

        # Verify password is saved as bcrypt hash
        user = auth_service.get_user_by_email(test_email)
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'farmer')
        self.assertTrue(user['password_hash'].startswith('$2b$') or user['password_hash'].startswith('$2a$'))
        self.assertTrue(auth_service.verify_password('farmerSecret123', user['password_hash']))

    def test_04_buyer_registration_web(self):
        """Buyer registration form validation and dashboard redirect."""
        test_email = "test.buyer.hotel@gmail.com"
        conn = get_db()
        conn.cursor().execute("DELETE FROM users WHERE LOWER(email) = ?", (test_email,))
        conn.commit()
        conn.close()

        data = {
            'role': 'buyer',
            'name': 'Anand Bhavan Hotel',
            'email': test_email,
            'phone': '9840123456',
            'location': 'T. Nagar, Chennai',
            'pin_code': '600017',
            'user_type': 'Restaurant',
            'password': 'buyerSecret123',
            'confirm_password': 'buyerSecret123',
            'terms': '1'
        }
        res = self.client.post('/register_post', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        loc_b = res.headers.get('Location', '')
        self.assertTrue('/dashboard/buyer' in loc_b or '/buyer/dashboard' in loc_b)

        user = auth_service.get_user_by_email(test_email)
        self.assertIsNotNone(user)
        self.assertEqual(user['role'], 'buyer')
        self.assertTrue(auth_service.verify_password('buyerSecret123', user['password_hash']))

    def test_05_public_admin_registration_blocked(self):
        """Public admin registration must be strictly forbidden."""
        data = {
            'role': 'admin',
            'name': 'Malicious Hacker',
            'email': 'hacker@admin.com',
            'phone': '9876500000',
            'password': 'hackPassword123',
            'confirm_password': 'hackPassword123',
            'terms': '1'
        }
        # Web POST attempt
        res_web = self.client.post('/register_post', data=data, follow_redirects=True)
        self.assertIn("Admin accounts cannot be registered publicly", res_web.data.decode('utf-8'))

        # API attempt
        res_api = self.client.post('/api/auth/register/farmer', json={**data, 'role': 'admin'})
        # Auto-assigned role is farmer in farmer endpoint, but if tried directly, no admin register endpoint exists
        self.assertNotEqual(res_api.status_code, 201)

    def test_06_single_authorized_admin_login(self):
        """Admin login using configured credentials Pp274142@gmail.com / praveen16."""
        admin_email = os.environ.get('ADMIN_EMAIL', 'Pp274142@gmail.com').strip().lower()
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'praveen16')

        data = {
            'role': 'admin',
            'email': admin_email,
            'password': admin_pass
        }
        res = self.client.post('/login_post', data=data, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        loc = res.headers.get('Location', '')
        self.assertTrue('/dashboard/admin' in loc or '/admin/dashboard' in loc)

        # Test API endpoint
        res_api = self.client.post('/api/auth/login/admin', json=data)
        self.assertEqual(res_api.status_code, 200)
        api_data = json.loads(res_api.data.decode('utf-8'))
        self.assertTrue(api_data.get('success'))
        self.assertIn('token', api_data)
        self.assertEqual(api_data['user']['role'], 'admin')

    def test_07_role_isolation_farmer_cannot_access_buyer_or_admin_dashboard(self):
        """A logged-in Farmer must be blocked from accessing Buyer and Admin dashboards."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3 # Selvi (Farmer)
            sess['user_role'] = 'farmer'
            sess['user_name'] = 'Selvi Shanmugam'

        # Attempt to access buyer dashboard
        res_buyer = self.client.get('/buyer/dashboard', follow_redirects=False)
        self.assertEqual(res_buyer.status_code, 302)
        loc_b = res_buyer.headers.get('Location', '')
        self.assertTrue('/dashboard/farmer' in loc_b or '/farmer/dashboard' in loc_b)

        # Attempt to access admin dashboard
        res_admin = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        loc_a = res_admin.headers.get('Location', '')
        self.assertTrue('/dashboard/farmer' in loc_a or '/farmer/dashboard' in loc_a)

    def test_08_role_isolation_buyer_cannot_access_farmer_or_admin_dashboard(self):
        """A logged-in Buyer must be blocked from accessing Farmer and Admin dashboards."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 6 # Saravana Bhavan Procurement (Buyer)
            sess['user_role'] = 'buyer'
            sess['user_name'] = 'Saravana Bhavan Procurement'

        # Attempt to access farmer dashboard
        res_farmer = self.client.get('/farmer/dashboard', follow_redirects=False)
        self.assertEqual(res_farmer.status_code, 302)
        loc_f = res_farmer.headers.get('Location', '')
        self.assertTrue('/dashboard/buyer' in loc_f or '/buyer/dashboard' in loc_f)

        # Attempt to access admin dashboard
        res_admin = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(res_admin.status_code, 302)
        loc_a = res_admin.headers.get('Location', '')
        self.assertTrue('/dashboard/buyer' in loc_a or '/buyer/dashboard' in loc_a)

    def test_09_forgot_and_reset_password_flow(self):
        """Forgot password token issuance and password reset verification."""
        test_email = "selvi.farms@gmail.com"
        ok, token = auth_service.generate_password_reset_token(test_email)
        self.assertTrue(ok)
        self.assertIsNotNone(token)

        # Reset password with token
        new_pw = "newFarmerPass2026"
        res = self.client.post(f'/reset-password/{token}', data={
            'password': new_pw,
            'confirm_password': new_pw
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

        # Verify login works with new password
        login_res = self.client.post('/login_post', data={
            'role': 'farmer',
            'email': test_email,
            'password': new_pw
        }, follow_redirects=False)
        self.assertEqual(login_res.status_code, 302)
        loc = login_res.headers.get('Location', '')
        self.assertTrue('/dashboard/farmer' in loc or '/farmer/dashboard' in loc)

    def test_10_logout_clears_session_and_redirects_to_login(self):
        """Logging out must clear session/cookies and redirect to /login (Requirement 11)."""
        with self.client.session_transaction() as sess:
            sess['user_id'] = 101
            sess['user_role'] = 'farmer'

        res = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

        # Client session should now be empty
        with self.client.session_transaction() as sess:
            self.assertNotIn('user_id', sess)

if __name__ == '__main__':
    unittest.main()
