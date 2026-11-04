import unittest
from unittest.mock import patch
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

    def tearDown(self):
        email_service.set_system_setting('http_email_api_key', '')
        email_service.set_system_setting('email_provider', 'auto')
        if 'HTTP_EMAIL_API_KEY' in email_service.os.environ:
            del email_service.os.environ['HTTP_EMAIL_API_KEY']
        if 'RESEND_API_KEY' in email_service.os.environ:
            del email_service.os.environ['RESEND_API_KEY']

    def test_save_smtp_config_route(self):
        """Admin can update SMTP server, port, username, password, sender name, and Cloud API key via form."""
        resp = self.client.post('/admin/smtp/save-config', data={
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': '587',
            'smtp_use_tls': '1',
            'smtp_username': 'Pp274142@gmail.com',
            'smtp_password': 'test_app_password_1234',
            'smtp_sender_name': 'FarmFresh Rescue Admin',
            'http_email_api_key': 're_test_resend_key_12345',
            'email_provider': 'resend'
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
        self.assertEqual(config['http_email_api_key'], 're_test_resend_key_12345')
        self.assertEqual(config['email_provider'], 'resend')
        self.assertTrue(config['is_configured'])

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_email_broadcast_to_farmers(self, mock_send):
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
        self.assertTrue(mock_send.called)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_email_broadcast_to_buyers(self, mock_send):
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
        self.assertTrue(mock_send.called)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_email_broadcast_to_both(self, mock_send):
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
        self.assertTrue(mock_send.called)

    @patch('email_service.send_email', return_value=(True, 'Delivered'))
    def test_single_test_email_broadcast(self, mock_send):
        """Admin can send a test broadcast to a single custom recipient."""
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'single',
            'single_email': 'custom.subscriber@gmail.com',
            'subject': 'Test Single Dispatch',
            'html_content': '<p>Hello single subscriber</p>'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_send.called)

    def test_render_network_blocked_fallback_to_in_app(self):
        """When host firewall blocks raw SMTP port 587 ([Errno 101] Network is unreachable), send_email gracefully delivers in-app."""
        with patch('smtplib.SMTP', side_effect=OSError(101, 'Network is unreachable')):
            ok, msg = email_service.send_email(
                to_email='waranlingesh35@gmail.com',
                subject='☔ Heavy Rains Test Warning',
                html_body='<p>Test Weather Warning</p>'
            )
            self.assertTrue(ok)
            self.assertIn('In-App', msg)

    def test_admin_dashboard_renders_smtp_form_and_templates(self):
        """Admin dashboard must render the editable SMTP form inputs, Cloud API key, and template buttons."""
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
        self.assertIn('name="http_email_api_key"', html)

        # Check template buttons
        self.assertIn('id="btnTmplWeather"', html)
        self.assertIn('id="btnTmplHarvest"', html)
        self.assertIn('id="btnTmplMarket"', html)

        # Check broadcast form
        self.assertIn('name="target_audience"', html)
        self.assertIn('id="broadcastSubject"', html)
        self.assertIn('id="broadcastHtmlContent"', html)
        self.assertIn('id="liveEmailPreview"', html)
        self.assertIn('id="emailProgressModal"', html)
        self.assertIn('id="emailProgressBar"', html)

    @patch('email_service.send_email', return_value=(True, 'Delivered to test recipient'))
    def test_ajax_broadcast_progress_response(self, mock_send):
        """AJAX request to broadcast returns structured JSON progress data for the modal."""
        resp = self.client.post('/admin/email-broadcast/send', data={
            'target_audience': 'single',
            'single_email': 'waranlingesh35@gmail.com',
            'subject': 'Testing Progress Engine',
            'html_content': '<p>Progress content</p>'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['sent_count'], 1)
        self.assertEqual(len(data['details']), 1)
        self.assertEqual(data['details'][0]['email'], 'waranlingesh35@gmail.com')

    def test_email_inspection_preview_route(self):
        """Admin can fetch full sent email record for the inspection modal."""
        email_id = email_service.record_sent_email(
            recipient_email='waranlingesh35@gmail.com',
            recipient_name='Lingesh',
            subject='Inspection Test Subject',
            html_content='<h1>Test HTML Body</h1>',
            status='Delivered',
            mode='Cloud HTTPS API'
        )
        self.assertIsNotNone(email_id)

        resp = self.client.get(f'/admin/emails/preview/{email_id}')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['email']['recipient_email'], 'waranlingesh35@gmail.com')
        self.assertIn('Test HTML Body', data['email']['html_content'])

if __name__ == '__main__':
    unittest.main()
