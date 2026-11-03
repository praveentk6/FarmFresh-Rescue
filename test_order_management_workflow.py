import unittest
import json
import os
import io
from app import app
from database import (
    get_db, init_db, create_farmer_offer, get_farmer_offers,
    get_buyer_received_offers, accept_farmer_offer, reject_farmer_offer,
    counter_farmer_offer, farmer_respond_counter_offer,
    update_order_harvest_and_quality, buyer_quality_decision,
    update_order_delivery_schedule, verify_order_handover,
    build_11_stage_timeline, create_notification, get_user_notifications
)
import auth_service

class OrderManagementWorkflowTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        conn = get_db()
        cursor = conn.cursor()

        # Create or find a test farmer
        cursor.execute("SELECT id, email FROM users WHERE role = 'farmer' AND is_active = 1 LIMIT 1")
        farmer_row = cursor.fetchone()
        if not farmer_row:
            ok, res = auth_service.create_user_account(
                name="Workflow Test Farmer",
                email="workflow.farmer@test.org",
                phone="9876543210",
                password="password123",
                role="farmer",
                location="Coimbatore"
            )
            cls.farmer_id = res['id']
            cls.farmer_email = "workflow.farmer@test.org"
        else:
            cls.farmer_id = farmer_row['id']
            cls.farmer_email = farmer_row['email']

        # Create or find a test buyer
        cursor.execute("SELECT id, email FROM users WHERE role = 'buyer' AND is_active = 1 LIMIT 1")
        buyer_row = cursor.fetchone()
        if not buyer_row:
            ok, res = auth_service.create_user_account(
                name="Workflow Test Buyer",
                email="workflow.buyer@test.org",
                phone="9876500001",
                password="password123",
                role="buyer",
                location="Chennai"
            )
            cls.buyer_id = res['id']
            cls.buyer_email = "workflow.buyer@test.org"
        else:
            cls.buyer_id = buyer_row['id']
            cls.buyer_email = buyer_row['email']

        # Ensure a buyer requirement exists
        cursor.execute("SELECT id FROM buyer_requirements WHERE buyer_id = ? LIMIT 1", (cls.buyer_id,))
        req_row = cursor.fetchone()
        if not req_row:
            cursor.execute("""
                INSERT INTO buyer_requirements (
                    buyer_id, buyer_name, business_type, crop_name, category,
                    required_quantity, unit, target_price, village_town, district,
                    state, contact_phone, notes, status, is_verified, required_date, payment_terms
                ) VALUES (?, 'Supermarket Procurement', 'Supermarkets', 'Organic Tomato', 'Vegetables',
                          500.0, 'kg', 22.0, 'RS Puram', 'Coimbatore', 'Tamil Nadu',
                          '9876500001', 'Need Grade A firm ripe tomatoes', 'Active', 1, DATE('now', '+3 days'), 'Immediate Payment on Delivery')
            """, (cls.buyer_id,))
            cls.requirement_id = cursor.lastrowid
        else:
            cls.requirement_id = req_row['id']

        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        self.farmer_id = self.__class__.farmer_id
        self.farmer_email = self.__class__.farmer_email
        self.buyer_id = self.__class__.buyer_id
        self.buyer_email = self.__class__.buyer_email
        self.requirement_id = self.__class__.requirement_id

    def set_session(self, user_id, role, email):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['user_role'] = role
            sess['user_email'] = email

    # 1. Test Nearby Buyers Filter & View Details (Section 1)
    def test_nearby_buyers_page_and_filtering(self):
        resp = self.client.get('/nearby-buyers')
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn("Active Procurement Requests", body)
        self.assertIn("Verified Buyer", body)
        self.assertIn("View Details", body)
        self.assertIn("Send Offer", body)

        # Filter by crop query
        resp_filter = self.client.get('/nearby-buyers?q=Tomato&min_qty=100&max_price=50')
        self.assertEqual(resp_filter.status_code, 200)
        self.assertIn("Tomato", resp_filter.data.decode('utf-8'))

    # 2. Test Farmer Send Product Offer (Section 2)
    def test_farmer_submit_offer(self):
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)

        offer_payload = {
            'buyer_id': self.buyer_id,
            'requirement_id': self.requirement_id,
            'crop_name': 'Organic Tomato',
            'quantity': '400',
            'price_per_kg': '21',
            'harvest_date': '2026-11-05',
            'quality_description': 'Grade A fresh harvest from drip irrigated farm',
            'delivery_preference': 'Farmer Pickup',
            'notes': 'Can pack in 20kg crates.'
        }

        resp = self.client.post('/farmer/offer/submit', data=offer_payload, follow_redirects=False)
        self.assertEqual(resp.status_code, 302)

        # Verify offer saved in database
        offers = get_farmer_offers(self.farmer_id)
        self.assertTrue(len(offers) > 0)
        matching_offers = [o for o in offers if o['crop_name'] == 'Organic Tomato' and float(o['quantity']) == 400.0]
        self.assertTrue(len(matching_offers) > 0)
        latest_offer = matching_offers[0]
        self.assertTrue(latest_offer['offer_code'].startswith("OFF-2026-"))
        self.assertEqual(latest_offer['status'], "Pending Buyer Review")
        self.assertEqual(float(latest_offer['quantity']), 400.0)
        self.assertEqual(float(latest_offer['price_per_kg']), 21.0)

        # Verify buyer received in-app notification
        notifs = get_user_notifications(self.buyer_id)
        self.assertTrue(any("New Offer for Organic Tomato" in n['title'] for n in notifs))

    # 3. Test Buyer Review Offers, Counter Offer, and Acceptance (Sections 3 & 4)
    def test_buyer_counter_and_accept_workflow(self):
        # 1. Farmer creates offer
        ok, res = create_farmer_offer(
            farmer_id=self.farmer_id,
            buyer_id=self.buyer_id,
            crop_name="Shallots",
            quantity=250.0,
            price_per_kg=48.0,
            harvest_date="2026-11-06",
            quality_description="Fresh cleaned shallots",
            delivery_preference="Farmer Pickup",
            requirement_id=self.requirement_id
        )
        self.assertTrue(ok)
        offer_id = res['id']

        # 2. Buyer sends Counter Offer
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        counter_resp = self.client.post('/api/offers/respond', json={
            'offer_id': offer_id,
            'action': 'counter',
            'counter_price': 44.0,
            'counter_quantity': 250.0,
            'counter_notes': 'Target rate is 44/kg'
        })
        self.assertEqual(counter_resp.status_code, 200)

        # Verify counter status
        offers = get_buyer_received_offers(self.buyer_id)
        matched = [o for o in offers if o['id'] == offer_id][0]
        self.assertEqual(matched['status'], "Counter Offered")
        self.assertEqual(float(matched['counter_price']), 44.0)

        # 3. Farmer accepts Counter Offer -> Generates Order
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        accept_counter = self.client.post(f'/farmer/offer/counter-respond/{offer_id}', json={
            'action': 'accept'
        })
        self.assertEqual(accept_counter.status_code, 200)
        res_data = accept_counter.get_json()
        self.assertTrue(res_data['success'])
        order_id = res_data['order_id']

        # Verify Order Confirmed in database
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(order)
        self.assertEqual(order['status'], "Confirmed")
        self.assertTrue(order['order_code'].startswith("ORD-2026-"))
        self.assertIsNotNone(order['handover_otp'])
        self.assertEqual(len(str(order['handover_otp'])), 6)
        self.assertIsNotNone(order['handover_qr_token'])
        self.assertEqual(float(order['requested_quantity']), 250.0)
        self.assertEqual(float(order['offered_price']), 44.0)

        # 4. Prevent duplicate order creation if offer accepted again
        ok_dup, msg_dup, dup_order_id = accept_farmer_offer(offer_id, self.buyer_id)
        self.assertEqual(dup_order_id, order_id)

    # 4. Test 11-Stage Progress Timeline (Section 9)
    def test_11_stage_timeline_and_tracking_page(self):
        # Create an offer and accept it to create confirmed order
        ok, res = create_farmer_offer(
            farmer_id=self.farmer_id,
            buyer_id=self.buyer_id,
            crop_name="Country Cabbage",
            quantity=300.0,
            price_per_kg=15.0,
            harvest_date="2026-11-05",
            delivery_preference="Platform Delivery"
        )
        self.assertTrue(ok)
        ok_acc, msg_acc, order_id = accept_farmer_offer(res['id'], self.buyer_id)
        self.assertTrue(ok_acc)

        # Test build_11_stage_timeline helper
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()

        timeline = build_11_stage_timeline(order)
        self.assertEqual(len(timeline), 11)

        stage_names = [st['name'] for st in timeline]
        expected_names = [
            'Offer Submitted', 'Buyer Accepted', 'Order Confirmed',
            'Harvesting Started', 'Quality Approved', 'Pickup Scheduled',
            'Product Picked Up', 'In Transit', 'Delivered',
            'Payment Verified', 'Order Completed'
        ]
        self.assertEqual(stage_names, expected_names)

        # First 3 stages must be completed
        self.assertTrue(timeline[0]['is_completed'])
        self.assertTrue(timeline[1]['is_completed'])
        self.assertTrue(timeline[2]['is_completed'])

        # Next stage should be current/active
        self.assertTrue(timeline[3]['is_current'])

        # Test tracking page route
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp = self.client.get(f'/order/track/{order_id}')
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn("11-Stage Order Lifecycle", body)
        self.assertIn("Country Cabbage", body)
        self.assertIn("Section 7: Product Handover Verification", body)
        self.assertIn("Section 8: Payment & Billing Management", body)

    # 5. Test Harvest Progress & Quality Approval (Section 5)
    def test_harvest_and_quality_workflow(self):
        ok, res = create_farmer_offer(
            farmer_id=self.farmer_id, buyer_id=self.buyer_id,
            crop_name="Brinjal", quantity=150.0, price_per_kg=25.0, harvest_date="2026-11-05"
        )
        _, _, order_id = accept_farmer_offer(res['id'], self.buyer_id)

        # Farmer updates harvest to 'Harvesting in Progress'
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp_h1 = self.client.post('/api/order/harvest-update', json={
            'order_id': order_id,
            'harvest_status': 'Harvesting in Progress',
            'harvested_quantity': 150.0,
            'harvest_notes': 'Morning harvest started'
        })
        self.assertEqual(resp_h1.status_code, 200)

        # Farmer updates harvest to 'Ready for Quality Check'
        resp_h2 = self.client.post('/api/order/harvest-update', json={
            'order_id': order_id,
            'harvest_status': 'Ready for Quality Check',
            'harvested_quantity': 155.0,
            'harvest_notes': '155 kg harvested and sorted into crates'
        })
        self.assertEqual(resp_h2.status_code, 200)

        # Buyer approves quality
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp_qual = self.client.post('/api/order/quality-decision', json={
            'order_id': order_id,
            'decision': 'approve',
            'notes': 'Verified Grade A freshness and size'
        })
        self.assertEqual(resp_qual.status_code, 200)

        # Verify order has quality approved
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT harvest_status FROM enquiries WHERE id = ?", (order_id,))
        self.assertEqual(cursor.fetchone()[0], 'Quality Approved')
        conn.close()

    # 6. Test Pickup & Delivery Management (Section 6)
    def test_delivery_schedule_management(self):
        ok, res = create_farmer_offer(
            farmer_id=self.farmer_id, buyer_id=self.buyer_id,
            crop_name="Drumsticks", quantity=200.0, price_per_kg=40.0, harvest_date="2026-11-05"
        )
        _, _, order_id = accept_farmer_offer(res['id'], self.buyer_id)

        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp = self.client.post('/api/order/delivery-schedule', json={
            'order_id': order_id,
            'delivery_mode': 'Platform Delivery',
            'pickup_datetime': '2026-11-06T10:00',
            'delivery_partner': 'FarmFresh Rapid Tempo TN-38-C-5678',
            'delivery_status': 'In Transit'
        })
        self.assertEqual(resp.status_code, 200)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT delivery_mode, delivery_partner, delivery_status, status FROM enquiries WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row['delivery_mode'], 'Platform Delivery')
        self.assertEqual(row['delivery_partner'], 'FarmFresh Rapid Tempo TN-38-C-5678')
        self.assertEqual(row['delivery_status'], 'In Transit')
        self.assertEqual(row['status'], 'In Transit')

    # 7. Test Handover Verification via OTP & QR Token (Section 7)
    def test_handover_verification_workflow(self):
        ok, res = create_farmer_offer(
            farmer_id=self.farmer_id, buyer_id=self.buyer_id,
            crop_name="Green Chillies", quantity=100.0, price_per_kg=60.0, harvest_date="2026-11-05"
        )
        _, _, order_id = accept_farmer_offer(res['id'], self.buyer_id)

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT handover_otp, handover_qr_token FROM enquiries WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        conn.close()

        otp = order['handover_otp']

        self.set_session(self.buyer_id, 'buyer', self.buyer_email)

        # 1. Invalid OTP must fail
        resp_invalid = self.client.post('/api/order/handover-verify', json={
            'order_id': order_id,
            'otp': '999999',
            'delivered_quantity': 100.0
        })
        self.assertEqual(resp_invalid.status_code, 400)

        # 2. Correct OTP verifies handover
        resp_valid = self.client.post('/api/order/handover-verify', json={
            'order_id': order_id,
            'otp': otp,
            'delivered_quantity': 98.5
        })
        self.assertEqual(resp_valid.status_code, 200)

        # Check database records
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT handover_verified, delivered_quantity, status FROM enquiries WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertEqual(row['handover_verified'], 1)
        self.assertEqual(float(row['delivered_quantity']), 98.5)
        self.assertEqual(row['status'], 'Delivered')

        # 3. Duplicate verification must be rejected
        resp_dup = self.client.post('/api/order/handover-verify', json={
            'order_id': order_id,
            'otp': otp,
            'delivered_quantity': 98.5
        })
        self.assertEqual(resp_dup.status_code, 400)
        self.assertIn("already verified", resp_dup.get_json()['message'])

    # 8. Test Role-Based Dashboards (Section 10)
    def test_dashboards_contain_offers_and_orders(self):
        # Farmer Dashboard
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp_f = self.client.get('/farmer/dashboard')
        self.assertEqual(resp_f.status_code, 200)
        body_f = resp_f.data.decode('utf-8')
        self.assertIn("My Submitted Offers", body_f)

        # Buyer Dashboard
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp_b = self.client.get('/buyer/dashboard')
        self.assertEqual(resp_b.status_code, 200)
        body_b = resp_b.data.decode('utf-8')
        self.assertIn("Received Farmer Offers", body_b)

if __name__ == '__main__':
    unittest.main()
