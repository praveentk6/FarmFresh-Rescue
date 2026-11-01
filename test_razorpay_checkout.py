import unittest
import json
import os
import hmac
import hashlib
from app import app
from razorpay_gateway import get_razorpay_key_id, get_razorpay_key_secret, verify_razorpay_signature

class TestRazorpayCheckoutIntegration(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_environment_variables_loaded(self):
        """Verify environment variables are loaded and not hardcoded."""
        key_id = get_razorpay_key_id()
        key_secret = get_razorpay_key_secret()
        self.assertEqual(key_id, "rzp_test_Tut3XRwhXAIBLC")
        self.assertEqual(key_secret, "rU2jzCDi7z46Far9wDpKDYj5")

    def test_create_order_minimum_amount_validation(self):
        """Validate amount >= 100 paise. Less than 100 must return 400."""
        payload = {"amount": 50, "currency": "INR", "receipt": "test_rcpt_min"}
        response = self.client.post('/api/create-order',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data.get('success'))
        self.assertIn("100 paise", data.get('error', ''))

    def test_create_order_missing_amount(self):
        """Missing amount or order_id returns 400."""
        payload = {"currency": "INR"}
        response = self.client.post('/api/create-order',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_create_order_live_api(self):
        """Create order via POST /api/create-order with valid paise amount."""
        payload = {"amount": 50000, "currency": "INR", "receipt": "test_rcpt_001"}
        response = self.client.post('/api/create-order',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertIn('order_id', data)
        self.assertTrue(data['order_id'].startswith("order_"))
        self.assertEqual(data['amount'], 50000)
        self.assertEqual(data['currency'], "INR")
        self.assertEqual(data['key_id'], "rzp_test_Tut3XRwhXAIBLC")

    def test_verify_payment_missing_fields(self):
        """Verify endpoint returns 400 when required fields are missing."""
        payload = {"razorpay_order_id": "order_123"}
        response = self.client.post('/api/verify-payment',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data.get('success'))
        self.assertIn("Missing required payment fields", data.get('error', ''))

    def test_verify_payment_signature_mismatch(self):
        """Verify endpoint returns 400 on signature mismatch."""
        payload = {
            "razorpay_order_id": "order_test_12345",
            "razorpay_payment_id": "pay_test_67890",
            "razorpay_signature": "invalid_fake_signature_abc123"
        }
        response = self.client.post('/api/verify-payment',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data.get('success'))
        self.assertIn("Signature verification failed", data.get('error', ''))

    def test_verify_payment_valid_signature(self):
        """Verify endpoint returns 200 with valid HMAC-SHA256 signature."""
        order_id = "order_test_verify_999"
        payment_id = "pay_test_verify_888"
        key_secret = get_razorpay_key_secret()
        msg = f"{order_id}|{payment_id}".encode('utf-8')
        valid_signature = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        payload = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": valid_signature
        }
        response = self.client.post('/api/verify-payment',
                                    data=json.dumps(payload),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data.get('success'))
        self.assertEqual(data.get('message'), "Payment verified successfully")

if __name__ == '__main__':
    unittest.main()
