"""
Unit Tests for Email OTP Verification & Welcome Email Dispatch
Validates registration OTP generation, verification endpoints, role-tailored
welcome email dispatch (Farmer vs Buyer), template rendering, and registration flows.
"""

import unittest
from unittest.mock import patch
import sqlite3
import datetime
from app import app
import email_service
import auth_service

class TestRegistrationOtpAndWelcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

    def setUp(self):
        self.client = app.test_client()
        email_service.init_registration_otps()
        email_service.init_sent_emails()

    def test_01_otp_template_generation(self):
        """Test OTP HTML template renders the 6-digit code correctly."""
        html = email_service.build_registration_otp_html("789123", "Ravi Kumar")
        self.assertIn("789123", html)
        self.assertIn("Ravi Kumar", html)
        self.assertIn("FarmFresh Rescue Email Verification", html)
        self.assertIn("Valid for 10 minutes", html)

    def test_02_farmer_welcome_template_generation(self):
        """Test Farmer Welcome Email HTML includes role-specific features and dashboard link."""
        html = email_service.build_farmer_welcome_html("Selvi Shanmugam", "https://farmfresh-rescue.onrender.com")
        self.assertIn("Selvi Shanmugam", html)
        self.assertIn("Farmer Producer Account", html)
        self.assertIn("Urgent Produce Rescue", html)
        self.assertIn("Direct Meet & Sell", html)
        self.assertIn("https://farmfresh-rescue.onrender.com/farmer/dashboard", html)

    def test_03_buyer_welcome_template_generation(self):
        """Test Buyer Welcome Email HTML includes procurement features and dashboard link."""
        html = email_service.build_buyer_welcome_html("Saravana Hotels", "https://farmfresh-rescue.onrender.com")
        self.assertIn("Saravana Hotels", html)
        self.assertIn("Wholesale Desk", html)
        self.assertIn("Direct Farm Produce Browse", html)
        self.assertIn("Secure Escrow", html)
        self.assertIn("https://farmfresh-rescue.onrender.com/buyer/dashboard", html)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_04_generate_and_verify_otp(self, mock_send):
        test_email = "otp.tester@farmfresh-sample.org"
        ok, msg, otp = email_service.generate_and_send_registration_otp(test_email, "OTP Tester")
        self.assertTrue(ok, f"Failed to generate OTP: {msg}")
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp), 6)
        self.assertTrue(mock_send.called)

        # Check DB entry
        conn = email_service.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT otp_code, is_verified FROM registration_otps WHERE LOWER(email) = LOWER(?)", (test_email,))
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row['otp_code'], otp)
        self.assertEqual(row['is_verified'], 0)

        # Verify with wrong OTP
        wrong_ok, wrong_msg = email_service.verify_registration_otp(test_email, "000000")
        self.assertFalse(wrong_ok)

        # Verify with correct OTP
        corr_ok, corr_msg = email_service.verify_registration_otp(test_email, otp)
        self.assertTrue(corr_ok, f"Verification failed: {corr_msg}")
        self.assertTrue(email_service.is_email_otp_verified(test_email))

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_05_api_otp_endpoints(self, mock_send):
        test_email = f"api.tester_{int(datetime.datetime.now().timestamp())}@farmfresh-sample.org"
        # 1. Send OTP via REST API
        resp = self.client.post('/api/auth/send-registration-otp', json={
            'email': test_email,
            'name': 'API Tester'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))

        # Fetch generated OTP from DB
        conn = email_service.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT otp_code FROM registration_otps WHERE LOWER(email) = LOWER(?)", (test_email,))
        row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        otp = row['otp_code']

        # 2. Verify OTP via REST API
        verify_resp = self.client.post('/api/auth/verify-registration-otp', json={
            'email': test_email,
            'otp_code': otp
        })
        self.assertEqual(verify_resp.status_code, 200)
        verify_data = verify_resp.get_json()
        self.assertTrue(verify_data.get('success'))

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_06_farmer_registration_welcome_email(self, mock_send):
        ts = int(datetime.datetime.now().timestamp())
        farmer_email = f"farmer_welcome_{ts}@farmfresh-sample.org"

        ok, msg = email_service.send_welcome_email(farmer_email, "Muthuvel Farmer", "farmer", "http://127.0.0.1:5000")
        self.assertTrue(ok)
        self.assertTrue(mock_send.called)

        # Check call arguments
        args, kwargs = mock_send.call_args
        to_email, subject, html_body = args[0], args[1], args[2]
        self.assertEqual(to_email, farmer_email)
        self.assertIn("Vanakkam & Welcome to FarmFresh Rescue", subject)
        self.assertIn("Muthuvel Farmer", html_body)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_07_buyer_registration_welcome_email(self, mock_send):
        ts = int(datetime.datetime.now().timestamp())
        buyer_email = f"buyer_welcome_{ts}@farmfresh-sample.org"

        ok, msg = email_service.send_welcome_email(buyer_email, "Kovai Traders", "buyer", "http://127.0.0.1:5000")
        self.assertTrue(ok)
        self.assertTrue(mock_send.called)

        # Check call arguments
        args, kwargs = mock_send.call_args
        to_email, subject, html_body = args[0], args[1], args[2]
        self.assertEqual(to_email, buyer_email)
        self.assertIn("Welcome to FarmFresh Rescue Wholesale Hub", subject)
        self.assertIn("Kovai Traders", html_body)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_08_end_to_end_registration_with_welcome_mail(self, mock_send):
        """End-to-end registration triggers welcome email and sets email_verified=1."""
        ts = int(datetime.datetime.now().timestamp())
        new_farmer_email = f"live_reg_farmer_{ts}@farmfresh-sample.org"

        # Pre-verify OTP in DB
        email_service.generate_and_send_registration_otp(new_farmer_email, "Live Farmer")
        conn = email_service.get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE registration_otps SET is_verified = 1 WHERE LOWER(email) = LOWER(?)", (new_farmer_email,))
        conn.commit()
        conn.close()

        # Submit registration form
        resp = self.client.post('/register_post', data={
            'role': 'farmer',
            'name': 'Live Farmer Testing',
            'email': new_farmer_email,
            'phone': '9876501234',
            'location': 'Thanjavur, TN',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'terms': '1',
            'email_otp_verified': '1'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        # Verify user in database has email_verified == 1
        user = auth_service.get_user_by_email(new_farmer_email)
        self.assertIsNotNone(user, "User was not created in database")
        self.assertEqual(user['email_verified'], 1)

        # Check that welcome email was triggered
        welcome_calls = [c for c in mock_send.call_args_list if "Vanakkam & Welcome" in c[0][1]]
        self.assertTrue(len(welcome_calls) > 0, "Welcome email was not dispatched during registration")

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_09_buyer_end_to_end_registration_with_otp(self, mock_send):
        """End-to-end buyer registration triggers buyer welcome email and sets email_verified=1."""
        ts = int(datetime.datetime.now().timestamp())
        new_buyer_email = f"live_reg_buyer_{ts}@farmfresh-sample.org"

        # 1. Send OTP
        res = email_service.generate_and_send_registration_otp(new_buyer_email, "Saravana Hotel")
        self.assertTrue(res[0])
        otp_code = res[2]

        # 2. Verify OTP via API
        verify_resp = self.client.post('/api/auth/verify-registration-otp', json={
            'email': new_buyer_email,
            'otp_code': otp_code
        })
        self.assertEqual(verify_resp.status_code, 200)

        # 3. Submit buyer registration form
        resp = self.client.post('/register_post', data={
            'role': 'buyer',
            'name': 'Saravana Hotel Procurement',
            'email': new_buyer_email,
            'phone': '9840123456',
            'location': 'T. Nagar, Chennai',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'terms': '1',
            'email_otp_verified': '1'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)

        # Verify buyer in database has email_verified == 1 and role == 'buyer'
        user = auth_service.get_user_by_email(new_buyer_email)
        self.assertIsNotNone(user, "Buyer was not created in database")
        self.assertEqual(user['role'], 'buyer')
        self.assertEqual(user['email_verified'], 1)

        # Check buyer welcome email was dispatched
        welcome_calls = [c for c in mock_send.call_args_list if "Welcome to FarmFresh Rescue Wholesale Hub" in c[0][1]]
        self.assertTrue(len(welcome_calls) > 0, "Buyer welcome email was not dispatched during registration")

if __name__ == '__main__':
    unittest.main()
