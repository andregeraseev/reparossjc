from django.test import TestCase
from django.urls import reverse


class CorporateHealthCorsTests(TestCase):
    def test_health_allows_android_webview_file_origin(self):
        response = self.client.get(
            reverse("corporate:health"),
            HTTP_ORIGIN="null",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response["Access-Control-Allow-Origin"], "*")
