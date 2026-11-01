"""
Comprehensive Test Suite for FarmFresh Rescue
Real-Time Agricultural Marketplace & Full Razorpay Payment Gateway Integration
"""
import unittest
import json
import os
import hmac
import hashlib
import uuid
from app import app
from database import (
    get_db, get_crop_benchmark_price, get_available_stock,
    get_weather_alerts, get_market_prices
)
from razorpay_gateway import get_razorpay_key_id, get_razorpay_key_secret

class TestRealTimeAndPayment(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def set_buyer_session(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 6
            sess['user_role'] = 'buyer'

    def set_farmer_session(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 3
            sess['user_role'] = 'farmer'

    def set_admin_session(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['user_role'] = 'admin'

    def clear_session(self):
        with self.client.session_transaction() as sess:
            sess.clear()

    def test_01_market_prices_and_benchmarks(self):
        """Test Mandi Wholesale rates API and benchmarks."""
        res = self.client.get('/market-prices')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Live Agricultural Market Prices', res.data)
        self.assertIn(b'Country Tomatoes', res.data)

        # Test database benchmark helper
        bench = get_crop_benchmark_price('Country Tomato')
        self.assertIsNotNone(bench)
        self.assertGreater(bench['modal_price'], 0)

    def test_02_live_map_and_weather_alerts(self):
        """Test interactive Leaflet map and agro-weather advisories."""
        res_map = self.client.get('/live-map')
        self.assertEqual(res_map.status_code, 200)
        self.assertIn(b'leaflet', res_map.data.lower())

        res_weather = self.client.get('/weather-alerts')
        self.assertEqual(res_weather.status_code, 200)
        self.assertIn(b'Weather-Based Crop Advisories', res_weather.data)

    def test_03_qr_code_and_provenance_passport(self):
        """Test dynamic QR image generation and public provenance passport."""
        db = get_db()
        listing = db.execute("SELECT id FROM listings LIMIT 1").fetchone()
        db.close()
        self.assertIsNotNone(listing)
        lid = listing['id']

        # QR PNG generation
        res_qr = self.client.get(f'/qr/{lid}')
        self.assertEqual(res_qr.status_code, 200)
        self.assertEqual(res_qr.content_type, 'image/png')

        # Provenance passport HTML
        res_passport = self.client.get(f'/trace/{lid}')
        self.assertEqual(res_passport.status_code, 200)
        self.assertIn(b'Produce Traceability Passport', res_passport.data)

    def test_04_direct_checkout_page(self):
        """Test direct checkout page loading."""
        self.set_buyer_session()
        db = get_db()
        listing = db.execute("SELECT id FROM listings WHERE status = 'Available' LIMIT 1").fetchone()
        db.close()
        self.assertIsNotNone(listing)
        lid = listing['id']

        res = self.client.get(f'/checkout/direct/{lid}', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Secure Produce Checkout', res.data)
        self.assertIn(b'Payment Breakdown', res.data)
        self.clear_session()

    def test_05_online_payment_order_and_signature_verification(self):
        """Test Razorpay order creation and HMAC-SHA256 signature verification."""
        self.set_buyer_session()
        db = get_db()
        listing = db.execute("SELECT id, price_per_unit FROM listings WHERE status = 'Available' LIMIT 1").fetchone()
        lid = listing['id']

        # 1. Initiate direct checkout to create order
        res_direct = self.client.get(f'/checkout/direct/{lid}')
        self.assertEqual(res_direct.status_code, 302)
        location = res_direct.headers.get('Location')
        internal_order_id = int(location.split('/')[-1])

        # 2. Call /api/payment/create-order
        order_payload = {
            'order_id': internal_order_id,
            'delivery_charges': 60.0
        }
        res_order = self.client.post('/api/payment/create-order',
                                     data=json.dumps(order_payload),
                                     content_type='application/json')
        self.assertEqual(res_order.status_code, 200)
        order_data = json.loads(res_order.data)
        self.assertTrue(order_data.get('success'))
        rzp_order_id = order_data['razorpay_order_id']
        txn_id = order_data['transaction_id']

        # 3. Simulate valid Razorpay payment signature
        rzp_payment_id = f"pay_test_{internal_order_id}_{uuid.uuid4().hex[:6]}"
        key_secret = get_razorpay_key_secret()
        msg = f"{rzp_order_id}|{rzp_payment_id}".encode('utf-8')
        signature = hmac.new(key_secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()

        # 4. Verify payment API
        verify_payload = {
            'order_id': internal_order_id,
            'transaction_id': txn_id,
            'razorpay_order_id': rzp_order_id,
            'razorpay_payment_id': rzp_payment_id,
            'razorpay_signature': signature
        }
        res_verify = self.client.post('/api/payment/verify',
                                      data=json.dumps(verify_payload),
                                      content_type='application/json')
        self.assertEqual(res_verify.status_code, 200)
        verify_data = json.loads(res_verify.data)
        self.assertTrue(verify_data.get('success'))

        # Check DB payment status
        cur = db.cursor()
        cur.execute("SELECT payment_status FROM payments WHERE order_id = ?", (internal_order_id,))
        p_row = cur.fetchone()
        self.assertIsNotNone(p_row)
        self.assertEqual(p_row['payment_status'], 'Paid')

        # 5. Digital Invoice View
        res_invoice = self.client.get(f'/order/{internal_order_id}/invoice')
        self.assertEqual(res_invoice.status_code, 200)
        self.assertIn(b'PAID & CONFIRMED', res_invoice.data)

        db.close()
        self.clear_session()

    def test_06_cash_on_delivery_order(self):
        """Test Cash on Delivery (COD) flow."""
        self.set_buyer_session()
        db = get_db()
        listing = db.execute("SELECT id FROM listings WHERE status = 'Available' LIMIT 1").fetchone()
        lid = listing['id']

        # 1. Direct checkout to create order
        res_direct = self.client.get(f'/checkout/direct/{lid}')
        self.assertEqual(res_direct.status_code, 302)
        location = res_direct.headers.get('Location')
        internal_order_id = int(location.split('/')[-1])

        # 2. Confirm COD
        cod_payload = {
            'order_id': internal_order_id,
            'delivery_charges': 0.0,
            'delivery_address': 'Shop 14, Koyambedu Wholesale Market, Chennai, TN'
        }
        res_cod = self.client.post('/api/payment/cod',
                                   data=json.dumps(cod_payload),
                                   content_type='application/json')
        self.assertEqual(res_cod.status_code, 200)
        cod_data = json.loads(res_cod.data)
        self.assertTrue(cod_data.get('success'))

        cur = db.cursor()
        cur.execute("SELECT payment_status, payment_method FROM payments WHERE order_id = ?", (internal_order_id,))
        p_row = cur.fetchone()
        self.assertIsNotNone(p_row)
        self.assertIn(p_row['payment_status'], ['COD Pending', 'Pending COD'])
        self.assertTrue('COD' in p_row['payment_method'] or 'Cash' in p_row['payment_method'])

        db.close()
        self.clear_session()

    def test_07_live_chat_and_negotiation(self):
        """Test real-time chat message exchange and price negotiation."""
        self.set_buyer_session()
        db = get_db()
        farmer = db.execute("SELECT id FROM users WHERE role = 'farmer' LIMIT 1").fetchone()
        farmer_id = farmer['id']

        # Send chat message
        send_payload = {
            'receiver_id': farmer_id,
            'message': 'Vanakkam! Is 150 kg fresh country tomatoes ready for collection tomorrow morning?',
            'offer_price': 22.0,
            'offer_quantity': 150.0
        }
        res_send = self.client.post('/api/chat/send',
                                    data=json.dumps(send_payload),
                                    content_type='application/json')
        self.assertEqual(res_send.status_code, 200)
        res_data = json.loads(res_send.data)
        self.assertTrue(res_data.get('success'))

        # Poll conversation
        res_poll = self.client.get(f'/api/chat/messages/{farmer_id}')
        self.assertEqual(res_poll.status_code, 200)
        poll_data = json.loads(res_poll.data)
        self.assertTrue(poll_data.get('success'))
        self.assertGreaterEqual(len(poll_data['messages']), 1)

        db.close()
        self.clear_session()

    def test_08_refund_request_and_admin_approval(self):
        """Test buyer refund submission and admin approval process."""
        self.set_buyer_session()
        db = get_db()
        cur = db.cursor()
        cur.execute("""
            INSERT INTO enquiries (listing_id, buyer_id, buyer_name, buyer_phone, buyer_email, requested_quantity, status, payment_status, payment_method, total_price, message)
            VALUES (1, 6, 'Saravana Bhavan Procurement', '9840123456', 'saravana.hotel@gmail.com', 10, 'Accepted', 'Paid', 'Razorpay UPI', 300, 'Paid in advance')
        """)
        new_order_id = cur.lastrowid
        txn_ref = f"TXN_TEST_{uuid.uuid4().hex[:8]}"
        cur.execute("""
            INSERT INTO payments (order_id, transaction_id, buyer_id, farmer_id, listing_id, amount, subtotal, delivery_charges, payment_method, payment_status)
            VALUES (?, ?, 6, 3, 1, 300.0, 300.0, 0.0, 'Razorpay UPI', 'Paid')
        """, (new_order_id, txn_ref))
        payment_id = cur.lastrowid
        db.commit()

        # Buyer requests refund
        refund_req = self.client.post('/api/payment/refund-request',
                                      data=json.dumps({'order_id': new_order_id, 'reason': 'Damaged in transit'}),
                                      content_type='application/json')
        self.assertEqual(refund_req.status_code, 200)
        self.assertTrue(json.loads(refund_req.data).get('success'))

        # Verify DB refund status
        cur.execute("SELECT refund_status FROM payments WHERE id = ?", (payment_id,))
        row = cur.fetchone()
        self.assertIn(row['refund_status'], ['Requested', 'Refund Requested'])
        self.clear_session()

        # Admin approves refund
        self.set_admin_session()
        res_admin = self.client.post(f'/api/admin/refund/{payment_id}',
                                     data={'action': 'approve'},
                                     follow_redirects=True)
        self.assertEqual(res_admin.status_code, 200)

        cur.execute("SELECT payment_status, refund_status FROM payments WHERE id = ?", (payment_id,))
        row_after = cur.fetchone()
        self.assertEqual(row_after['payment_status'], 'Refunded')
        self.assertIn(row_after['refund_status'], ['Processed', 'Refunded'])

        db.close()
        self.clear_session()


if __name__ == '__main__':
    unittest.main()
