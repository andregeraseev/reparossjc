from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class CorporateLogoutCompatibilityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="logout-test", password="test-pass-123")
        self.client.force_login(self.user)

    def test_get_shows_confirmation_without_logging_out(self):
        response = self.client.get(reverse("corporate:logout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sair do portal?")
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_logs_out_and_redirects_to_login(self):
        response = self.client.post(reverse("corporate:logout"))
        self.assertRedirects(response, reverse("corporate:login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
