from django.test import TestCase, Client
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_health_check_endpoint(self):
        client = Client()
        response = client.get(reverse("health-check"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["database"], "connected")
        self.assertEqual(data["service"], "public-speaking-workshop")
