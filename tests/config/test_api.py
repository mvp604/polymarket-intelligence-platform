import unittest

from src.config.api import (
    API_SETTINGS,
    EndpointSettings,
)


class ApiSettingsTests(unittest.TestCase):

    def test_gamma_url(self):
        self.assertEqual(
            API_SETTINGS.gamma.base_url,
            "https://gamma-api.polymarket.com",
        )

    def test_data_url(self):
        self.assertEqual(
            API_SETTINGS.data.base_url,
            "https://data-api.polymarket.com",
        )

    def test_clob_url(self):
        self.assertEqual(
            API_SETTINGS.clob.base_url,
            "https://clob.polymarket.com",
        )

    def test_websocket_url(self):
        self.assertEqual(
            API_SETTINGS.websocket.base_url,
            "wss://ws-subscriptions-clob.polymarket.com/ws",
        )

    def test_default_timeout(self):
        endpoint = EndpointSettings("https://example.com")
        self.assertEqual(endpoint.timeout_seconds, 30)

    def test_default_retries(self):
        endpoint = EndpointSettings("https://example.com")
        self.assertEqual(endpoint.max_retries, 3)

    def test_default_rate_limit(self):
        endpoint = EndpointSettings("https://example.com")
        self.assertEqual(endpoint.rate_limit_per_second, 5)


if __name__ == "__main__":
    unittest.main()
