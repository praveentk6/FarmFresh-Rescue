import unittest
import auth_service
from app import app
import email_service
from database import get_db

class TestSmtpConfigAndBroadcast(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Login as real admin
        admin = auth_service.get_user_by_email('pp274142@gmail.com')
        self.admin_id = admin['id'] if admin else 103

        with self.client.session_transaction() as sess:
            sess['user_id'] = self.admin_id
            sess['user_name'] = 'Platform Administrator'
            sess['user_role'] = 'admin'

    def test_save_smtp_config_route(self):
        """Admin can update SMTP server, port, username, password, and sender name via form."""
        resp = self.client.post('/admin/smtp/save-config', data={
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'smtp_use_tls': '1',
            'smtp_username': 'Pp274142@gmail.com',
            'smtp_password': 'test_app_password_1234',
            'smtp_sender_name': 'FarmFresh Rescue Admin'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Check that settings are persisted in database
        config = email_service.get_smtp_config()
        self.assertEqual(config['server'], 'smtp.gmail.com')
        self.assertEqual(config['port'], 587)
        self.assertEqual(config['username'], 'Pp274142@gmail.com')
        self.assertEqual(config['password'], 'test_app_password_1234')
        self.assertTrue(config['use_tls'])
        self.assertEqual(config['sender_name'], 'FarmFresh Rescue Admin')
        self.assertTrue(config['is_configured'])

    def test_email_broadcast_to_farmers(self):
        """Admin can dispatch targeted email broadcast to all farmers."""
        tmpl = email_service.DEFAULT_COMMUNICATION_TEMPLATES['weather_farmer']
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'farmer',
            'subject': tmpl['subject'],
            'html_content': tmpl['html']
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('Broadcast complete', html)

    def test_email_broadcast_to_buyers(self):
        """Admin can dispatch targeted email broadcast to all buyers."""
        tmpl = email_service.DEFAULT_COMMUNICATION_TEMPLATES['harvest_buyer']
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'buyer',
            'subject': tmpl['subject'],
            'html_content': tmpl['html']
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('Broadcast complete', html)

    def test_email_broadcast_to_both(self):
        """Admin can dispatch targeted email broadcast to both farmers and buyers."""
        tmpl = email_service.DEFAULT_COMMUNICATION_TEMPLATES['market_both']
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'both',
            'subject': tmpl['subject'],
            'html_content': tmpl['html']
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('Broadcast complete', html)

    def test_single_test_email_broadcast(self):
        """Admin can send a test broadcast to a single custom recipient."""
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'single',
            'single_email': 'custom.subscriber@gmail.com',
            'subject': 'Test Single Dispatch',
            'html_content': '<p>Hello single subscriber</p>'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

    def test_admin_dashboard_renders_smtp_form_and_templates(self):
        """Admin dashboard must render the editable SMTP form inputs and template buttons."""
        resp = self.client.get('/admin/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check input fields
        self.assertIn('name="smtp_server"', html)
        self.assertIn('name="smtp_port"', html)
        self.assertIn('name="smtp_use_tls"', html)
        self.assertIn('name="smtp_username"', html)
        self.assertIn('name="smtp_password"', html)
        self.assertIn('name="smtp_sender_name"', html)

        # Check template buttons
        self.assertIn('id="btnTmplWeather"', html)
        self.assertIn('id="btnTmplHarvest"', html)
        self.assertIn('id="btnTmplMarket"', html)

        # Check broadcast form
        self.assertIn('name="target_audience"', html)
        self.assertIn('id="broadcastSubject"', html)
        self.assertIn('id="broadcastHtmlContent"', html)
        self.assertIn('id="liveEmailPreview"', html)

if __name__ == '__main__':
    unittest.main()

