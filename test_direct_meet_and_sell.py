import unittest
import json
import os
from app import app
from database import (
    get_db, init_db, create_rescue_product, get_shared_rescue_products,
    get_rescue_product_by_id, create_direct_meeting, get_meeting_by_id,
    respond_direct_meeting, record_direct_inspection, record_direct_negotiation,
    confirm_direct_negotiation_agreement, initiate_or_update_direct_sale,
    confirm_direct_sale_step, get_direct_sale_by_id, get_direct_sales_for_user,
    send_direct_chat_message, get_direct_chat_messages
)
import auth_service

class DirectMeetAndSellTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False

        conn = get_db()
        cursor = conn.cursor()

        # 1. Setup Test Farmer
        cursor.execute("SELECT id, email, name, phone, location FROM users WHERE role = 'farmer' AND is_active = 1 LIMIT 1")
        farmer_row = cursor.fetchone()
        if not farmer_row:
            ok, res = auth_service.create_user_account(
                name="Test Meet Farmer",
                email="meet.farmer@test.org",
                phone="9876543210",
                password="password123",
                role="farmer",
                location="Pollachi, Coimbatore"
            )
            cls.farmer_id = res['id']
            cls.farmer_email = "meet.farmer@test.org"
            cls.farmer_name = "Test Meet Farmer"
        else:
            cls.farmer_id = farmer_row['id']
            cls.farmer_email = farmer_row['email']
            cls.farmer_name = farmer_row['name']

        # 2. Setup Test Buyer
        cursor.execute("SELECT id, email, name, phone, location FROM users WHERE role = 'buyer' AND is_active = 1 LIMIT 1")
        buyer_row = cursor.fetchone()
        if not buyer_row:
            ok, res = auth_service.create_user_account(
                name="Test Meet Buyer",
                email="meet.buyer@test.org",
                phone="9876500002",
                password="password123",
                role="buyer",
                location="Gandhipuram, Coimbatore"
            )
            cls.buyer_id = res['id']
            cls.buyer_email = "meet.buyer@test.org"
            cls.buyer_name = "Test Meet Buyer"
        else:
            cls.buyer_id = buyer_row['id']
            cls.buyer_email = buyer_row['email']
            cls.buyer_name = buyer_row['name']

        conn.commit()
        conn.close()

    def setUp(self):
        self.client = app.test_client()
        self.farmer_id = self.__class__.farmer_id
        self.farmer_email = self.__class__.farmer_email
        self.buyer_id = self.__class__.buyer_id
        self.buyer_email = self.__class__.buyer_email

    def set_session(self, user_id, role, email):
        with self.client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['user_role'] = role
            sess['user_email'] = email

    # Test 1: Shared Rescue Products upload by farmer -> instant visibility for buyer
    def test_01_farmer_publishes_rescue_product_and_buyer_views(self):
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)

        # Farmer submits product via POST
        post_data = {
            'product_name': 'Organic Farm Bell Peppers',
            'category': 'Vegetables',
            'quantity': '250',
            'original_price': '45',
            'rescue_price': '25',
            'quality_grade': 'Grade A',
            'harvest_date': '2026-11-03',
            'expiry_date': '2026-11-10',
            'farm_location': 'Pollachi Farmgate',
            'district': 'Coimbatore',
            'pin_code': '642001',
            'description': 'Direct harvest crisp green bell peppers ready for farmgate pickup.',
            'whatsapp_number': '9876543210'
        }
        resp = self.client.post('/farmer/rescue-product/add', data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn('Organic Farm Bell Peppers', body)

        # Buyer checks /rescue-products and sees the exact item
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp_buyer = self.client.get('/rescue-products')
        self.assertEqual(resp_buyer.status_code, 200)
        buyer_body = resp_buyer.data.decode('utf-8')
        self.assertIn('Organic Farm Bell Peppers', buyer_body)
        self.assertIn('Pollachi Farmgate', buyer_body)

        # Store test product id
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM rescue_products WHERE product_name = 'Organic Farm Bell Peppers' ORDER BY id DESC LIMIT 1")
        prod = cursor.fetchone()
        conn.close()
        self.__class__.test_product_id = prod['id']

    # Test 2: Category, district, and search filtering on /rescue-products
    def test_02_rescue_products_filtering(self):
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)

        # Filter by search term
        resp = self.client.get('/rescue-products?q=Bell+Peppers')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Organic Farm Bell Peppers', resp.data.decode('utf-8'))

        # Filter by category
        resp = self.client.get('/rescue-products?category=Vegetables')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Organic Farm Bell Peppers', resp.data.decode('utf-8'))

        # Non-matching filter
        resp = self.client.get('/rescue-products?q=NonExistentExoticCropXYZ')
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Organic Farm Bell Peppers', resp.data.decode('utf-8'))

    # Test 3: Product detail page rendering with farmer specs and contact options
    def test_03_rescue_product_detail(self):
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)

        product_id = getattr(self.__class__, 'test_product_id', None)
        if not product_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM rescue_products WHERE product_name = 'Organic Farm Bell Peppers' ORDER BY id DESC LIMIT 1")
            product_id = cursor.fetchone()['id']
            conn.close()

        resp = self.client.get(f'/rescue-product/{product_id}')
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn('Organic Farm Bell Peppers', body)
        self.assertIn('Schedule Direct Meeting', body)
        self.assertIn('Contact Farmer', body)

    # Test 4: Find Sellers Buyer View (Section 1)
    def test_04_find_sellers_page(self):
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp = self.client.get('/find-sellers')
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn('Direct Meet & Sell', body)
        self.assertIn('Find Sellers', body)
        self.assertIn('Organic Farm Bell Peppers', body)

    # Test 5: Buyer schedules direct meeting (Section 3) -> generates MTG-2026-XXXX
    def test_05_schedule_direct_meeting(self):
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)

        product_id = getattr(self.__class__, 'test_product_id', None)
        if not product_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM rescue_products WHERE product_name = 'Organic Farm Bell Peppers' ORDER BY id DESC LIMIT 1")
            product_id = cursor.fetchone()['id']
            conn.close()

        meeting_data = {
            'required_quantity': '100',
            'proposed_date': '2026-11-05',
            'proposed_time': '10:30 AM',
            'meeting_location': 'Pollachi Farmgate Shed 2',
            'buyer_notes': 'Bringing digital weighing scale and inspection crates.'
        }
        resp = self.client.post(f'/meetings/schedule/{product_id}', data=meeting_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        body = resp.data.decode('utf-8')
        self.assertIn('MTG-', body)
        self.assertIn('Meeting Management', body)

        # Store test meeting id
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, meeting_code FROM direct_meetings WHERE rescue_product_id = ? ORDER BY id DESC LIMIT 1", (product_id,))
        mtg = cursor.fetchone()
        conn.close()
        self.__class__.test_meeting_id = mtg['id']

    # Test 6: Farmer views and responds to meeting (Section 3 & 4)
    def test_06_farmer_responds_to_meeting(self):
        meeting_id = getattr(self.__class__, 'test_meeting_id', None)
        if not meeting_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id, meeting_code FROM direct_meetings ORDER BY id DESC LIMIT 1")
            mtg = cursor.fetchone()
            conn.close()
            meeting_id = mtg['id']
            meeting_code = mtg['meeting_code']
        else:
            mtg = get_meeting_by_id(meeting_id)
            meeting_code = mtg['meeting_code']

        # Farmer views meeting list
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp = self.client.get('/meetings')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(meeting_code, resp.data.decode('utf-8'))

        # Farmer accepts meeting
        resp_accept = self.client.post(f'/api/meeting/{meeting_id}/respond', data={
            'action': 'accept',
            'notes': 'Confirmed! I will have the bell peppers harvested and ready.'
        }, follow_redirects=True)
        self.assertEqual(resp_accept.status_code, 200)

        # Verify status in database
        updated_mtg = get_meeting_by_id(meeting_id)
        self.assertEqual(updated_mtg['status'], 'Confirmed')

    # Test 7: Direct Product Inspection recording (Section 5)
    def test_07_record_direct_inspection(self):
        meeting_id = getattr(self.__class__, 'test_meeting_id', None)
        if not meeting_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM direct_meetings ORDER BY id DESC LIMIT 1")
            meeting_id = cursor.fetchone()['id']
            conn.close()

        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        inspection_data = {
            'product_freshness': 'Freshly Harvested Crisp',
            'product_quality': 'Grade A',
            'actual_weight': '100',
            'available_quantity': '250',
            'packaging_condition': 'Clean aerated crates',
            'status': 'Approved',
            'buyer_notes': 'Weight calibrated on digital scale. Excellent freshness.',
            'farmer_notes': 'Inspected together at farmgate.'
        }
        resp = self.client.post(f'/meeting/{meeting_id}/inspect', data=inspection_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        mtg_after = get_meeting_by_id(meeting_id)
        self.assertIsNotNone(mtg_after['inspection'])
        self.assertEqual(mtg_after['inspection']['status'], 'Approved')
        self.assertEqual(mtg_after['inspection']['actual_weight'], 100.0)

    # Test 8: Direct Price Negotiation and Dual Agreement (Section 6)
    def test_08_direct_negotiation_and_dual_agreement(self):
        meeting_id = getattr(self.__class__, 'test_meeting_id', None)
        if not meeting_id:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM direct_meetings ORDER BY id DESC LIMIT 1")
            meeting_id = cursor.fetchone()['id']
            conn.close()

        # Buyer proposes price
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        neg_data = {
            'farmer_initial_price': '25.0',
            'buyer_proposed_price': '22.0',
            'counter_price': '23.0',
            'final_agreed_price': '23.0',
            'final_quantity': '100',
            'notes': 'Agreed on Rs 23/kg for 100kg batch.'
        }
        resp = self.client.post(f'/meeting/{meeting_id}/negotiate', data=neg_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Buyer confirms agreement
        resp_b_conf = self.client.post(f'/api/meeting/{meeting_id}/confirm-negotiation', follow_redirects=True)
        self.assertEqual(resp_b_conf.status_code, 200)

        # Farmer confirms agreement
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp_f_conf = self.client.post(f'/api/meeting/{meeting_id}/confirm-negotiation', follow_redirects=True)
        self.assertEqual(resp_f_conf.status_code, 200)

        mtg_after = get_meeting_by_id(meeting_id)
        self.assertIsNotNone(mtg_after['negotiation'])
        self.assertEqual(mtg_after['negotiation']['status'], 'Agreed')
        self.assertEqual(mtg_after['negotiation']['final_agreed_price'], 23.0)
        self.assertEqual(mtg_after['negotiation']['total_amount'], 2300.0)

    # Test 9: Direct Sale Initiation, Dual Confirmation, Stock Decrement & Receipt (Sections 7, 8, 9)
    def test_09_direct_sale_confirmation_stock_sync_and_receipt(self):
        meeting_id = getattr(self.__class__, 'test_meeting_id', None)
        conn = get_db()
        cursor = conn.cursor()
        if not meeting_id:
            cursor.execute("SELECT id, rescue_product_id FROM direct_meetings ORDER BY id DESC LIMIT 1")
            mtg = cursor.fetchone()
            meeting_id = mtg['id']
            product_id = mtg['rescue_product_id']
        else:
            cursor.execute("SELECT rescue_product_id FROM direct_meetings WHERE id = ?", (meeting_id,))
            product_id = cursor.fetchone()['rescue_product_id']

        # Check initial product quantity
        cursor.execute("SELECT quantity FROM rescue_products WHERE id = ?", (product_id,))
        initial_qty = cursor.fetchone()['quantity']
        conn.close()

        # Step 1: Record Direct Sale Details (Cash payment)
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        sale_data = {
            'payment_method': 'Cash',
            'payment_reference': 'CASH-PAID-ON-SPOT',
            'payment_notes': 'Cash handed over in person after weighing.'
        }
        resp_sale = self.client.post(f'/direct-sale/confirm/{meeting_id}', data=sale_data, follow_redirects=True)
        self.assertEqual(resp_sale.status_code, 200)

        # Step 2: Buyer confirms handoff
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, sale_code FROM direct_sales WHERE meeting_id = ?", (meeting_id,))
        sale_row = cursor.fetchone()
        conn.close()
        self.assertIsNotNone(sale_row)
        sale_id = sale_row['id']
        self.assertTrue(sale_row['sale_code'].startswith('DIR-2026-'))

        resp_b_confirm = self.client.post(f'/api/direct-sale/{sale_id}/confirm', data={
            'notes': 'Goods received in excellent condition.'
        }, follow_redirects=True)
        self.assertEqual(resp_b_confirm.status_code, 200)

        # Verify sale is not yet marked Completed before farmer verifies payment
        sale_pending = get_direct_sale_by_id(sale_id)
        self.assertNotEqual(sale_pending['status'], 'Completed')

        # Step 3: Farmer confirms receipt and verifies payment
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp_f_confirm = self.client.post(f'/api/direct-sale/{sale_id}/confirm', data={
            'payment_verified': '1',
            'notes': 'Cash payment counted and verified. Goods handed over.'
        }, follow_redirects=True)
        self.assertEqual(resp_f_confirm.status_code, 200)

        # Step 4: Verify sale completion and receipt generation
        sale_completed = get_direct_sale_by_id(sale_id)
        self.assertEqual(sale_completed['status'], 'Completed')
        self.assertTrue(sale_completed['receipt_number'].startswith('REC-2026-'))

        # Check receipt page
        resp_rcpt = self.client.get(f'/direct-sale/{sale_id}/receipt')
        self.assertEqual(resp_rcpt.status_code, 200)
        receipt_body = resp_rcpt.data.decode('utf-8')
        self.assertIn(sale_completed['receipt_number'], receipt_body)
        self.assertIn('2300', receipt_body)
        self.assertIn('Cash', receipt_body)

        # Step 5: Verify stock decrement in rescue_products
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM rescue_products WHERE id = ?", (product_id,))
        new_qty = cursor.fetchone()['quantity']
        conn.close()
        self.assertEqual(new_qty, initial_qty - 100.0)

        # Step 6: Verify duplicate prevention on confirm
        resp_dup = self.client.post(f'/api/direct-sale/{sale_id}/confirm', data={
            'payment_verified': '1'
        }, follow_redirects=True)
        self.assertEqual(resp_dup.status_code, 200)
        # Quantity must remain unchanged
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM rescue_products WHERE id = ?", (product_id,))
        dup_qty = cursor.fetchone()['quantity']
        conn.close()
        self.assertEqual(dup_qty, new_qty)

    # Test 10: In-app direct chat message exchange between buyer and farmer (Section 2)
    def test_10_in_app_direct_messaging(self):
        # Buyer sends message to Farmer
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        send_resp = self.client.post(f'/api/direct-messages/{self.farmer_id}', json={
            'message': 'Hello farmer, I have reached your farm gate!'
        })
        self.assertEqual(send_resp.status_code, 200)
        data = send_resp.get_json()
        self.assertTrue(data['success'])

        # Farmer checks messages
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        get_resp = self.client.get(f'/api/direct-messages/{self.buyer_id}')
        self.assertEqual(get_resp.status_code, 200)
        chat_data = get_resp.get_json()
        self.assertTrue(chat_data['success'])
        found = any('reached your farm gate' in m['message'] for m in chat_data['messages'])
        self.assertTrue(found)

        # Farmer views HTML page
        html_resp = self.client.get(f'/direct-messages/{self.buyer_id}')
        self.assertEqual(html_resp.status_code, 200)
        self.assertIn('reached your farm gate', html_resp.data.decode('utf-8'))

    # Test 11: Role-based Dashboard Integrations
    def test_11_role_based_dashboards(self):
        # Farmer Dashboard has rescue products and direct meetings
        self.set_session(self.farmer_id, 'farmer', self.farmer_email)
        resp_farmer = self.client.get('/farmer/dashboard')
        self.assertEqual(resp_farmer.status_code, 200)
        f_body = resp_farmer.data.decode('utf-8')
        self.assertIn('rescueProductsSection', f_body)
        self.assertIn('meetingsSection', f_body)
        self.assertIn('directSalesSection', f_body)

        # Buyer Dashboard has shared rescue produce highlights and meetings
        self.set_session(self.buyer_id, 'buyer', self.buyer_email)
        resp_buyer = self.client.get('/buyer/dashboard')
        self.assertEqual(resp_buyer.status_code, 200)
        b_body = resp_buyer.data.decode('utf-8')
        self.assertIn('sharedRescueSection', b_body)
        self.assertIn('meetingsSection', b_body)
        self.assertIn('directPurchasesSection', b_body)

if __name__ == '__main__':
    unittest.main()
