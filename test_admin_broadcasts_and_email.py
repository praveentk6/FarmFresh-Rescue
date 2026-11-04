import unittest
import json
import auth_service
from app import app
from database import get_db, create_broadcast_announcement, generate_user_email_verification_token

class TestAdminBroadcastsAndEmail(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Login as real admin from database
        admin = auth_service.get_user_by_email('pp274142@gmail.com')
        self.admin_id = admin['id'] if admin else 103

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['user_name'] = 'Platform Administrator'
            sess['user_role'] = 'admin'

    def test_admin_dashboard_renders_sidebar_tabs(self):
        """Admin dashboard must render with Left Sidebar elements and tab sections."""
        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        
        # Verify sidebar elements
        self.assertIn('admin-sidebar', html)
        self.assertIn('admin-main-area', html)
        self.assertIn('data-tab="overview"', html)
        self.assertIn('data-tab="broadcasts"', html)
        self.assertIn('data-tab="users"', html)
        self.assertIn('data-tab="listings"', html)
        self.assertIn('data-tab="orders"', html)
        self.assertIn('data-tab="payments"', html)
        self.assertIn('data-tab="meetings"', html)
        self.assertIn('data-tab="smtp"', html)
        self.assertIn('data-tab="logs"', html)
        self.assertIn('data-tab="sample-data"', html)

        # Verify panes
        self.assertIn('id="pane-overview"', html)
        self.assertIn('id="pane-broadcasts"', html)
        self.assertIn('id="pane-users"', html)
        self.assertIn('id="pane-smtp"', html)

    def test_create_and_manage_broadcast_announcement(self):
        """Test creating, toggling, and deleting a platform broadcast alert."""
        # 1. Create
        create_resp = self.client.post('/admin/announcements/create', data={
            'title': 'Unit Test Heavy Rain Warning',
            'message': 'Test bulletin warning for Thanjavur delta farmers.',
            'category': 'Weather Alert',
            'severity': 'Warning',
            'target_role': 'farmer',
            'target_district': 'Thanjavur',
            'action_link': '/nearby-buyers',
            'action_text': 'Find Buyers',
            'expires_days': '5'
        }, follow_redirects=True)
        self.assertEqual(create_resp.status_code, 200)

        # Check DB
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM broadcast_announcements WHERE title = ?", ('Unit Test Heavy Rain Warning',))
        ann = cursor.fetchone()
        self.assertIsNotNone(ann)
        ann_id = ann['id']
        self.assertEqual(ann['category'], 'Weather Alert')
        self.assertEqual(ann['severity'], 'Warning')
        self.assertEqual(ann['is_active'], 1)

        # 2. Toggle status
        toggle_resp = self.client.post(f'/admin/announcements/toggle/{ann_id}', follow_redirects=True)
        self.assertEqual(toggle_resp.status_code, 200)
        cursor.execute("SELECT is_active FROM broadcast_announcements WHERE id = ?", (ann_id,))
        updated_status = cursor.fetchone()['is_active']
        self.assertEqual(updated_status, 0)

        # Toggle back to active
        self.client.post(f'/admin/announcements/toggle/{ann_id}', follow_redirects=True)
        cursor.execute("SELECT is_active FROM broadcast_announcements WHERE id = ?", (ann_id,))
        self.assertEqual(cursor.fetchone()['is_active'], 1)

        # 3. Delete
        delete_resp = self.client.post(f'/admin/announcements/delete/{ann_id}', follow_redirects=True)
        self.assertEqual(delete_resp.status_code, 200)
        cursor.execute("SELECT * FROM broadcast_announcements WHERE id = ?", (ann_id,))
        self.assertIsNone(cursor.fetchone())
        conn.close()

    def test_farmer_dashboard_shows_active_broadcast(self):
        """Active broadcast targeted to farmers must render on Farmer Dashboard."""
        # Create broadcast for farmers
        ok, msg, ann_id = create_broadcast_announcement(
            title="Monsoon Advisory for Farmers",
            message="Secure stored grains and pulses in covered warehouses.",
            category="Weather Alert",
            severity="Advisory",
            target_role="farmer",
            target_district="All Tamil Nadu",
            expires_days=3
        )
        self.assertTrue(ok)

        # Log in as farmer
        farmer_client = self.app.test_client()
        with farmer_client.session_transaction() as sess:
            sess['user_id'] = 2  # farmer user
            sess['user_name'] = 'Muthu Vel'
            sess['user_role'] = 'farmer'

        resp = farmer_client.get('/farmer/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('Monsoon Advisory for Farmers', html)
        self.assertIn('platform-broadcasts-wrapper', html)

        # Cleanup
        conn = get_db()
        conn.cursor().execute("DELETE FROM broadcast_announcements WHERE id = ?", (ann_id,))
        conn.commit()
        conn.close()

    def test_email_verification_flow(self):
        """Test verification token validation, admin manual verification, and resend."""
        conn = get_db()
        cursor = conn.cursor()
        
        # Create a test unverified user
        cursor.execute("""
            INSERT OR REPLACE INTO users (id, name, email, password_hash, role, phone, location, email_verified)
            VALUES (999, 'Test Unverified User', 'unverified.test@gmail.com', 'pbkdf2:sha256:dummy', 'farmer', '9876543210', 'Madurai', 0)
        """)
        conn.commit()

        # 1. Generate token
        token = generate_user_email_verification_token(999)
        self.assertIsNotNone(token)

        # 2. Visit verification link
        anon_client = self.app.test_client()
        verif_resp = anon_client.get(f'/verify-email/{token}', follow_redirects=True)
        self.assertEqual(verif_resp.status_code, 200)

        # Check in DB that user is now verified
        cursor.execute("SELECT email_verified, verified_at FROM users WHERE id = 999")
        u = cursor.fetchone()
        self.assertEqual(u['email_verified'], 1)
        self.assertIsNotNone(u['verified_at'])

        # 3. Admin 1-click toggle back to unverified
        toggle_resp = self.client.post('/admin/verify-user/999', follow_redirects=True)
        self.assertEqual(toggle_resp.status_code, 200)
        cursor.execute("SELECT email_verified FROM users WHERE id = 999")
        self.assertEqual(cursor.fetchone()['email_verified'], 0)

        # 4. Admin 1-click toggle back to verified
        toggle_resp2 = self.client.post('/admin/verify-user/999', follow_redirects=True)
        self.assertEqual(toggle_resp2.status_code, 200)
        cursor.execute("SELECT email_verified FROM users WHERE id = 999")
        self.assertEqual(cursor.fetchone()['email_verified'], 1)

        # 5. Admin trigger verification email dispatch
        admin_send_resp = self.client.post('/admin/send-verification/999', follow_redirects=True)
        self.assertEqual(admin_send_resp.status_code, 200)

        # Cleanup test user
        cursor.execute("DELETE FROM users WHERE id = 999")
        conn.commit()
        conn.close()

    def test_smtp_diagnostic_test_route(self):
        """Admin can trigger an SMTP diagnostic test without errors."""
        resp = self.client.post('/admin/test-smtp', data={
            'recipient_email': 'diagnostic.test@gmail.com'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('SMTP Diagnostic', html)

if __name__ == '__main__':
    unittest.main()
