import os
os.environ['MONGODB_URI'] = ''
import unittest
import sqlite3
import datetime
import uuid
import database
import auth_service
from razorpay_gateway import create_razorpay_order, verify_razorpay_signature

class TestRescheduleVerificationReviews(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        auth_service.MONGODB_URI = ''
        database.init_db()

    def setUp(self):
        self.suffix = uuid.uuid4().hex
        self.farmer_email = f"farmer_{self.suffix}@test.com"
        self.buyer_email = f"buyer_{self.suffix}@test.com"

        ok_f, res_f = auth_service.create_user_account(
            name=f"Farmer {self.suffix[:6]}",
            email=self.farmer_email,
            plain_password="Password123!",
            role="farmer",
            phone="9876543210",
            location="Thanjavur, Tamil Nadu"
        )
        self.assertTrue(ok_f, f"Failed to create farmer: {res_f}")
        self.farmer_id = res_f['id']

        ok_b, res_b = auth_service.create_user_account(
            name=f"Buyer {self.suffix[:6]}",
            email=self.buyer_email,
            plain_password="Password123!",
            role="buyer",
            phone="9876543211",
            location="Chennai, Tamil Nadu"
        )
        self.assertTrue(ok_b, f"Failed to create buyer: {res_b}")
        self.buyer_id = res_b['id']

        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO listings (
                farmer_id, crop_name, category, quantity, unit, price_per_unit,
                harvest_date, village_town, district, state, pin_code,
                farmer_name, farmer_phone, status
            ) VALUES (
                ?, 'Ponni Rice Harvest', 'Grains', 500, 'kg', 38.0,
                '2026-11-20', 'Thanjavur', 'Thanjavur', 'Tamil Nadu', '613001',
                'Farmer Test', '9876543210', 'Available'
            )
        """, (self.farmer_id,))
        self.listing_id = cur.lastrowid
        conn.commit()
        conn.close()

    def test_01_seller_verification_flow(self):
        """Test seller document submission, admin approve, reject with reason, and badge updates."""
        # 1. Initial status should be 'Not Verified'
        user = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(user['verification_status'], 'Not Verified')
        self.assertEqual(user['is_verified_seller'], 0)

        # 2. Farmer submits verification documents
        ok, msg, v_id = database.submit_seller_verification(
            farmer_id=self.farmer_id,
            seller_name=f"Farmer {self.suffix[:6]}",
            mobile_number="9876543210",
            farm_name="Cauvery Delta Green Farms",
            farm_address="12 Farm Road, Thanjavur",
            farm_location="Thanjavur Rural",
            district="Thanjavur",
            document_type="Uzhavar Attai / Farmer ID",
            document_number="TN-FARM-984712",
            document_file="static/uploads/verifications/test_uzhavar.pdf"
        )
        self.assertTrue(ok, msg)
        self.assertIsNotNone(v_id)

        # Status should now be 'Verification Pending'
        user = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(user['verification_status'], 'Verification Pending')
        self.assertEqual(user['is_verified_seller'], 0)

        # 3. Admin approves verification
        ok_rev, msg_rev = database.admin_review_seller_verification(
            verification_id=v_id,
            admin_id=1,
            action='Approve'
        )
        self.assertTrue(ok_rev, msg_rev)

        user_approved = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(user_approved['verification_status'], 'Verified')
        self.assertEqual(user_approved['is_verified_seller'], 1)

        # 4. Re-submitting and Admin Rejection with Reason
        ok2, msg2, v_id2 = database.submit_seller_verification(
            farmer_id=self.farmer_id,
            seller_name=f"Farmer {self.suffix[:6]}",
            mobile_number="9876543210",
            farm_name="Cauvery Delta Green Farms",
            farm_address="12 Farm Road, Thanjavur",
            farm_location="Thanjavur Rural",
            district="Thanjavur",
            document_type="Aadhaar Card",
            document_number="XXXX-XXXX-1234",
            document_file="static/uploads/verifications/test_aadhaar.pdf"
        )
        self.assertTrue(ok2, msg2)

        ok_rej, msg_rej = database.admin_review_seller_verification(
            verification_id=v_id2,
            admin_id=1,
            action='Reject',
            rejection_reason="Identity document image is blurred and unreadable"
        )
        self.assertTrue(ok_rej, msg_rej)

        user_rejected = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(user_rejected['verification_status'], 'Rejected')
        self.assertEqual(user_rejected['is_verified_seller'], 0)

    def test_02_meeting_scheduling_and_rescheduling(self):
        """Test scheduling meeting, rescheduling proposal, conflict prevention, and counterparty acceptance."""
        m_code = f"MEET-{self.suffix[:6].upper()}"
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, farmer_id, buyer_id, buyer_name, buyer_phone,
                farmer_name, farmer_phone, product_name, required_quantity,
                proposed_date, proposed_time, meeting_location, status, buyer_notes
            ) VALUES (
                ?, ?, ?, ?, 'Buyer Test', '9876543211',
                'Farmer Test', '9876543210', 'Ponni Rice Harvest', 50.0,
                '2026-11-25', '10:00 AM', 'Thanjavur Mandi Yard', 'Confirmed', 'Quality inspection'
            )
        """, (m_code, self.listing_id, self.farmer_id, self.buyer_id))
        meeting_id = cur.lastrowid
        conn.commit()
        conn.close()

        # 1. Prevent conflicting meeting at the same date and time
        has_conflict, c_msg = database.check_meeting_conflict(
            farmer_id=self.farmer_id,
            date_str='2026-11-25',
            time_str='10:00 AM',
            exclude_meeting_id=None
        )
        self.assertTrue(has_conflict)

        # Non-conflicting time should pass
        no_conflict, nc_msg = database.check_meeting_conflict(
            farmer_id=self.farmer_id,
            date_str='2026-11-26',
            time_str='02:00 PM',
            exclude_meeting_id=meeting_id
        )
        self.assertFalse(no_conflict)

        # 2. Buyer requests reschedule to 2026-11-27 11:30 AM
        ok_res, res_msg, req_id = database.request_meeting_reschedule(
            meeting_id=meeting_id,
            requester_id=self.buyer_id,
            requester_role='buyer',
            proposed_date='2026-11-27',
            proposed_time='11:30 AM',
            reason='Transport delayed due to heavy rain'
        )
        self.assertTrue(ok_res, res_msg)
        self.assertIsNotNone(req_id)

        # 3. Farmer accepts reschedule request
        ok_accept, accept_msg = database.respond_meeting_reschedule(
            reschedule_id=req_id,
            responder_id=self.farmer_id,
            responder_role='farmer',
            action='Accept'
        )
        self.assertTrue(ok_accept, accept_msg)

        # Meeting date and time should now be updated to proposed values, status confirmed
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("SELECT proposed_date, proposed_time, status FROM direct_meetings WHERE id = ?", (meeting_id,))
        m_updated = cur.fetchone()
        conn.close()
        self.assertEqual(m_updated['proposed_date'], '2026-11-27')
        self.assertEqual(m_updated['proposed_time'], '11:30 AM')
        self.assertEqual(m_updated['status'], 'Confirmed')

    def test_03_buyer_reviews_and_ratings(self):
        """Test buyer review submission, 1 review per transaction constraint, and rating summary recalculation."""
        m_code1 = f"MEET-REV1-{self.suffix[:6].upper()}"
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, farmer_id, buyer_id, buyer_name, buyer_phone,
                farmer_name, farmer_phone, product_name, required_quantity,
                proposed_date, proposed_time, meeting_location, status, buyer_notes
            ) VALUES (
                ?, ?, ?, ?, 'Buyer Test', '9876543211',
                'Farmer Test', '9876543210', 'Ponni Rice Harvest', 100.0,
                '2026-11-10', '10:00 AM', 'Kumbakonam Farm', 'Completed', 'Procured 100 kg'
            )
        """, (m_code1, self.listing_id, self.farmer_id, self.buyer_id))
        meeting_id = cur.lastrowid
        conn.commit()
        conn.close()

        # 1. Buyer submits review for completed meeting
        ok_rev, msg_rev, r_id = database.submit_buyer_review(
            buyer_id=self.buyer_id,
            farmer_id=self.farmer_id,
            rating=5.0,
            comment="Excellent harvest quality! Produce was remarkably fresh and farmer was very helpful.",
            quality_rating=5.0,
            freshness_rating=5.0,
            communication_rating=4.0,
            price_rating=5.0,
            overall_rating=5.0,
            meeting_id=meeting_id
        )
        self.assertTrue(ok_rev, msg_rev)
        self.assertIsNotNone(r_id)

        # Check farmer rating summary
        farmer = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(farmer['total_reviews'], 1)
        self.assertEqual(float(farmer['seller_rating']), 5.0)

        # 2. Prevent duplicate review for the same transaction
        ok_dup, msg_dup, _ = database.submit_buyer_review(
            buyer_id=self.buyer_id,
            farmer_id=self.farmer_id,
            rating=4.0,
            comment="Attempting duplicate review",
            meeting_id=meeting_id
        )
        self.assertFalse(ok_dup)
        self.assertIn("already reviewed", msg_dup)

        # 3. Add a second review from another buyer to verify average calculation
        ok_b2, res_b2 = auth_service.create_user_account(
            name=f"Buyer2 {self.suffix[:6]}",
            email=f"buyer2_{self.suffix}@test.com",
            plain_password="Password123!",
            role="buyer",
            phone="9876543212",
            location="Madurai, Tamil Nadu"
        )
        self.assertTrue(ok_b2)
        buyer2_id = res_b2['id']

        m_code2 = f"MEET-REV2-{self.suffix[:6].upper()}"
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, farmer_id, buyer_id, buyer_name, buyer_phone,
                farmer_name, farmer_phone, product_name, required_quantity,
                proposed_date, proposed_time, meeting_location, status
            ) VALUES (
                ?, ?, ?, ?, 'Buyer 2', '9876543212',
                'Farmer Test', '9876543210', 'Ponni Rice Harvest', 80.0,
                '2026-11-12', '03:00 PM', 'Madurai Mandi', 'Completed'
            )
        """, (m_code2, self.listing_id, buyer2_id, self.farmer_id))
        meeting2_id = cur.lastrowid
        conn.commit()
        conn.close()

        ok_rev2, _, _ = database.submit_buyer_review(
            buyer_id=buyer2_id,
            farmer_id=self.farmer_id,
            rating=3.0,
            comment="Decent produce, delivery was a bit late.",
            quality_rating=4.0,
            freshness_rating=4.0,
            communication_rating=3.0,
            price_rating=3.0,
            overall_rating=3.0,
            meeting_id=meeting2_id
        )
        self.assertTrue(ok_rev2)

        # Average should now be (5 + 3) / 2 = 4.0, total reviews = 2
        farmer_updated = auth_service.get_user_by_id(self.farmer_id)
        self.assertEqual(farmer_updated['total_reviews'], 2)
        self.assertEqual(float(farmer_updated['seller_rating']), 4.0)

    def test_04_razorpay_order_and_simulation(self):
        """Test Razorpay order creation and signature validation fallback."""
        order_res = create_razorpay_order(
            amount_in_rupees=250.0,
            receipt_id=f"rec_test_{self.suffix[:6]}",
            notes={"test": "reschedule_verification_test"}
        )
        self.assertTrue(order_res['success'])
        self.assertTrue('order_id' in order_res)
        self.assertGreaterEqual(order_res['amount'], 25000)

        # Verify simulation signature
        order_id = order_res['order_id']
        is_valid, reason = verify_razorpay_signature(
            razorpay_order_id=order_id,
            razorpay_payment_id="pay_test_123456",
            razorpay_signature="mock_sig_123456"
        )
        self.assertTrue(is_valid)

    def test_05_update_buyer_review(self):
        """Test buyer review editing and authorization checks."""
        # 1. Create a meeting and initial review
        m_code = f"MEET-EDIT-{self.suffix[:6].upper()}"
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, farmer_id, buyer_id, buyer_name, buyer_phone,
                farmer_name, farmer_phone, product_name, required_quantity,
                proposed_date, proposed_time, meeting_location, status
            ) VALUES (
                ?, ?, ?, ?, 'Buyer Test', '9876543211',
                'Farmer Test', '9876543210', 'Ponni Rice Harvest', 50.0,
                '2026-11-15', '11:00 AM', 'Farm Site', 'Completed'
            )
        """, (m_code, self.listing_id, self.farmer_id, self.buyer_id))
        meeting_id = cur.lastrowid
        conn.commit()
        conn.close()

        ok, msg, r_id = database.submit_buyer_review(
            buyer_id=self.buyer_id,
            farmer_id=self.farmer_id,
            rating=5.0,
            comment="Initial rating was perfect.",
            meeting_id=meeting_id
        )
        self.assertTrue(ok, msg)

        # 2. Buyer updates the review
        ok_edit, msg_edit, _ = database.update_buyer_review(
            review_id=r_id,
            buyer_id=self.buyer_id,
            rating=4.0,
            comment="Updated: Quality was very good overall.",
            quality_rating=4.0,
            freshness_rating=4.0,
            communication_rating=4.0,
            price_rating=4.0,
            overall_rating=4.0
        )
        self.assertTrue(ok_edit, msg_edit)

        # Verify review row has updated values
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("SELECT rating, comment, updated_at FROM buyer_reviews WHERE id = ?", (r_id,))
        row = cur.fetchone()
        conn.close()
        self.assertEqual(float(row['rating']), 4.0)
        self.assertEqual(row['comment'], "Updated: Quality was very good overall.")
        self.assertIsNotNone(row['updated_at'])

        # 3. Another user should NOT be able to edit this review
        other_buyer_id = 999999
        ok_unauth, msg_unauth, _ = database.update_buyer_review(
            review_id=r_id,
            buyer_id=other_buyer_id,
            rating=1.0,
            comment="Hacked review"
        )
        self.assertFalse(ok_unauth)
        self.assertIn("Unauthorized", msg_unauth)

    def test_06_seller_verification_email(self):
        """Test that seller verification stores and retains email address."""
        ok, msg, v_id = database.submit_seller_verification(
            farmer_id=self.farmer_id,
            seller_name="Farmer Email Test",
            mobile_number="9876543210",
            farm_name="Organic Acres",
            farm_address="123 Farm Rd",
            district="Salem",
            document_type="Aadhaar Card",
            document_file="static/uploads/verifications/test.pdf",
            email=self.farmer_email
        )
        self.assertTrue(ok, msg)
        v = database.get_seller_verification_by_farmer_id(self.farmer_id)
        self.assertIsNotNone(v)
        self.assertEqual(v['email'], self.farmer_email)

    def test_07_seller_profile_and_routes(self):
        """Test GET /seller/<id> and GET /farmer/<id> profile views."""
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()

        res = client.get(f"/seller/{self.farmer_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Seller Profile:", res.data)

        res2 = client.get(f"/farmer/{self.farmer_id}")
        self.assertEqual(res2.status_code, 200)

    def test_08_meeting_detail_view_with_reschedule(self):
        """Test GET /meetings/<id> view includes reschedule history and controls."""
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()

        # Login as farmer in test session
        with client.session_transaction() as sess:
            sess['user_id'] = self.farmer_id
            sess['user_role'] = 'farmer'

        # Create meeting with reschedule request
        m_code = f"MEET-DET-{self.suffix[:6].upper()}"
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO direct_meetings (
                meeting_code, listing_id, farmer_id, buyer_id, buyer_name, buyer_phone,
                farmer_name, farmer_phone, product_name, required_quantity,
                proposed_date, proposed_time, meeting_location, status
            ) VALUES (
                ?, ?, ?, ?, 'Buyer Test', '9876543211',
                'Farmer Test', '9876543210', 'Ponni Rice Harvest', 50.0,
                '2026-11-28', '02:00 PM', 'Farm Yard', 'Confirmed'
            )
        """, (m_code, self.listing_id, self.farmer_id, self.buyer_id))
        meeting_id = cur.lastrowid
        conn.commit()
        conn.close()

        # Buyer requests reschedule
        ok_res, _, req_id = database.request_meeting_reschedule(
            meeting_id=meeting_id,
            requester_id=self.buyer_id,
            requester_role='buyer',
            proposed_date='2026-11-29',
            proposed_time='04:00 PM',
            reason='Logistics adjustment'
        )
        self.assertTrue(ok_res)

        res = client.get(f"/meetings/{meeting_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Reschedule", res.data)
        self.assertIn(b"Logistics adjustment", res.data)

        # Also test singular /meeting/<id> route
        res2 = client.get(f"/meeting/{meeting_id}")
        self.assertEqual(res2.status_code, 200)

    def test_09_buyer_reviews_and_ratings_ui(self):
        """Test product reviews, summary calculation, photo persistence, and page UI rendering."""
        # 1. Submit a buyer review with produce photo
        ok, msg, rev_id = database.submit_buyer_review(
            buyer_id=self.buyer_id,
            farmer_id=self.farmer_id,
            rating=5,
            comment="Outstanding fresh harvest directly from farmgate! High quality produce.",
            meeting_id=None,
            transaction_id=None,
            product_id=self.listing_id,
            quality_rating=5.0,
            freshness_rating=5.0,
            communication_rating=4.5,
            price_rating=5.0,
            review_photo="tomatoes.jpg"
        )
        self.assertTrue(ok, msg)
        self.assertIsNotNone(rev_id)

        # 2. Verify get_product_reviews
        p_reviews = database.get_product_reviews(product_id=self.listing_id, crop_name="Ponni Rice Harvest", farmer_id=self.farmer_id)
        self.assertTrue(len(p_reviews) >= 1)
        rev = next(r for r in p_reviews if r['id'] == rev_id)
        self.assertEqual(rev['rating'], 5.0)
        self.assertEqual(rev['review_photo'], "tomatoes.jpg")
        self.assertEqual(rev['buyer_id'], self.buyer_id)

        # 3. Verify get_product_rating_summary
        summary = database.get_product_rating_summary(product_id=self.listing_id, crop_name="Ponni Rice Harvest", farmer_id=self.farmer_id)
        self.assertGreaterEqual(summary['total_reviews'], 1)
        self.assertGreaterEqual(summary['average_rating'], 4.0)
        self.assertIn(5, summary['star_counts'])
        self.assertGreaterEqual(summary['star_counts'][5], 1)

        # 4. Check UI rendering on Produce Listing Detail page
        from app import app
        app.config['TESTING'] = True
        client = app.test_client()

        res_listing = client.get(f"/listing/{self.listing_id}")
        self.assertEqual(res_listing.status_code, 200)
        self.assertIn(b"Customer Reviews", res_listing.data)
        self.assertIn(b"Verified Buyer Feedback", res_listing.data)
        self.assertIn(b"Produce Quality Breakdown", res_listing.data)
        self.assertIn(b"Outstanding fresh harvest", res_listing.data)

        # 5. Insert rescue product and check UI rendering on Rescue Product Detail page
        conn = database.get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO rescue_products (
                farmer_id, product_name, category, quantity, initial_quantity, unit,
                original_price, rescue_price, discount_percent, quality_grade, harvest_date, expiry_date,
                farm_location, district, pin_code, farmer_name, farmer_phone, photo, status
            ) VALUES (
                ?, 'Fresh Country Tomatoes', 'Vegetables', 100, 100, 'kg',
                25.0, 18.0, 28.0, 'Grade A', date('now'), date('now', '+3 days'),
                'Delta Agro Zone', 'Thanjavur', '613001', 'Farmer Test', '9876543210', 'tomatoes.jpg', 'Available'
            )
        """, (self.farmer_id,))
        rescue_id = cur.lastrowid
        conn.commit()
        conn.close()

        res_rescue = client.get(f"/rescue-product/{rescue_id}")
        self.assertEqual(res_rescue.status_code, 200)
        self.assertIn(b"Customer Reviews", res_rescue.data)
        self.assertIn(b"Verified Buyer Feedback", res_rescue.data)
        self.assertIn(b"Produce Quality Breakdown", res_rescue.data)

        # 6. Check Seller Profile reviews rendering
        res_seller = client.get(f"/seller/{self.farmer_id}")
        self.assertEqual(res_seller.status_code, 200)
        self.assertIn(b"Buyer Reviews", res_seller.data)
        self.assertIn(b"Outstanding fresh harvest", res_seller.data)

if __name__ == '__main__':
    unittest.main()
