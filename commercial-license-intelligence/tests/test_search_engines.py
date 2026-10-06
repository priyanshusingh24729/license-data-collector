"""Unit and integration tests for search engines, fallback chain, and circuit breaker."""

import unittest
from unittest.mock import patch, MagicMock
import httpx

from backend.search_engines.base import SearchEngine, load_official_domains
from backend.search_engines.searxng_engine import SearXNGEngine
from backend.search_engines.yacy_engine import YaCyEngine
from backend.search_engines.duckduckgo_engine import DuckDuckGoEngine
from backend.search_engines.chain import SearchEngineChain, SearchEngineError, NoResultsFoundError
from backend.validation.searxng_evidence_validator import SearxngEvidenceValidator


class TestSearXNGEngine(unittest.TestCase):
    @patch("httpx.Client.get")
    def test_searxng_success_and_domain_filtering(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [
                {
                    "title": "Adobe Acrobat Official Licensing",
                    "url": "https://www.adobe.com/legal/licenses-terms.html",
                    "content": "Official Acrobat Pro terms and user metrics.",
                    "engine": "google"
                },
                {
                    "title": "Third-party Blog",
                    "url": "https://random-tech-blog.org/adobe-license",
                    "content": "Unverified commentary.",
                    "engine": "bing"
                }
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        engine = SearXNGEngine(base_url="http://127.0.0.1:8080")
        results = engine.search("Adobe Acrobat licensing", official_domains=["adobe.com"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Adobe Acrobat Official Licensing")
        self.assertEqual(results[0]["url"], "https://www.adobe.com/legal/licenses-terms.html")

    @patch("httpx.Client.get")
    def test_searxng_http_failure_raises(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Bad Gateway", request=MagicMock(), response=mock_resp)
        mock_get.return_value = mock_resp

        engine = SearXNGEngine()
        with self.assertRaises(httpx.HTTPStatusError):
            engine.search("test query")


class TestYaCyEngine(unittest.TestCase):
    @patch("httpx.Client.get")
    def test_yacy_success_and_json_parsing(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "channels": [
                {
                    "title": "YaCy Search",
                    "totalResults": "2",
                    "items": [
                        {
                            "title": "Oracle Java Licensing Guide",
                            "link": "https://www.oracle.com/java/technologies/javase/jdk-faqs.html",
                            "description": "Commercial licensing metrics for Oracle Java SE."
                        },
                        {
                            "title": "Unrelated Forum",
                            "link": "https://forum.free-software-fans.org/thread-123",
                            "description": "Discussion on Java."
                        }
                    ]
                }
            ]
        }
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        engine = YaCyEngine(base_url="http://127.0.0.1:8090")
        results = engine.search("Oracle Java licensing", official_domains=["oracle.com"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Oracle Java Licensing Guide")
        self.assertEqual(results[0]["url"], "https://www.oracle.com/java/technologies/javase/jdk-faqs.html")

    @patch("httpx.Client.get")
    def test_yacy_timeout_raises(self, mock_get):
        mock_get.side_effect = httpx.TimeoutException("Connection timed out")

        engine = YaCyEngine()
        with self.assertRaises(httpx.TimeoutException):
            engine.search("test timeout")


class TestDuckDuckGoEngine(unittest.TestCase):
    SAMPLE_HTML = """
    <html>
      <body>
        <div class="result results_links">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Flearn.microsoft.com%2Fvisualstudio%2Flicensing&rut=123">
              Visual Studio Licensing Whitepaper
            </a>
          </h2>
          <div class="result__snippet">
            Comprehensive whitepaper outlining Visual Studio subscriber benefits and server access.
          </div>
        </div>
        <div class="result results_links">
          <h2 class="result__title">
            <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Funauthorized-pirate-site.com%2Fkeys&rut=456">
              Free Keys
            </a>
          </h2>
          <div class="result__snippet">
            Spam site.
          </div>
        </div>
      </body>
    </html>
    """

    @patch("httpx.Client.post")
    def test_duckduckgo_html_scrape_and_redirect_unpack(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.SAMPLE_HTML
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        engine = DuckDuckGoEngine()
        results = engine.search("Visual Studio licensing", official_domains=["microsoft.com", "learn.microsoft.com"])

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "Visual Studio Licensing Whitepaper")
        self.assertEqual(results[0]["url"], "https://learn.microsoft.com/visualstudio/licensing")
        self.assertIn("Comprehensive whitepaper", results[0]["snippet"])

    @patch("httpx.Client.post")
    def test_duckduckgo_malformed_html_graceful_empty(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><div>Unexpected blank content</div></body></html>"
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp

        engine = DuckDuckGoEngine()
        results = engine.search("no results query", official_domains=["adobe.com"])
        self.assertEqual(results, [])


class TestSearchEngineChain(unittest.TestCase):
    def test_fallback_order_searxng_succeeds(self):
        engine1 = MagicMock(spec=SearchEngine)
        engine1.name = "searxng"
        engine1.search.return_value = [{"title": "SearXNG Result", "url": "https://adobe.com/terms", "snippet": "..."}]

        engine2 = MagicMock(spec=SearchEngine)
        engine2.name = "yacy"

        engine3 = MagicMock(spec=SearchEngine)
        engine3.name = "duckduckgo"

        chain = SearchEngineChain(engines=[engine1, engine2, engine3], official_domains=["adobe.com"])
        res = chain.search("Adobe terms")

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "SearXNG Result")
        engine1.search.assert_called_once()
        engine2.search.assert_not_called()
        engine3.search.assert_not_called()

    def test_fallback_order_searxng_fails_yacy_succeeds(self):
        engine1 = MagicMock(spec=SearchEngine)
        engine1.name = "searxng"
        engine1.search.side_effect = httpx.ConnectError("SearXNG down")

        engine2 = MagicMock(spec=SearchEngine)
        engine2.name = "yacy"
        engine2.search.return_value = [{"title": "YaCy Result", "url": "https://adobe.com/terms", "snippet": "..."}]

        engine3 = MagicMock(spec=SearchEngine)
        engine3.name = "duckduckgo"

        chain = SearchEngineChain(engines=[engine1, engine2, engine3], official_domains=["adobe.com"], max_retries_per_engine=0)
        res = chain.search("Adobe terms")

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "YaCy Result")
        engine1.search.assert_called_once()
        engine2.search.assert_called_once()
        engine3.search.assert_not_called()

    def test_fallback_order_searxng_and_yacy_fail_duckduckgo_succeeds(self):
        engine1 = MagicMock(spec=SearchEngine)
        engine1.name = "searxng"
        engine1.search.side_effect = httpx.TimeoutException("SearXNG timeout")

        engine2 = MagicMock(spec=SearchEngine)
        engine2.name = "yacy"
        engine2.search.return_value = []  # Zero results after domain filter

        engine3 = MagicMock(spec=SearchEngine)
        engine3.name = "duckduckgo"
        engine3.search.return_value = [{"title": "DDG Result", "url": "https://adobe.com/terms", "snippet": "..."}]

        chain = SearchEngineChain(engines=[engine1, engine2, engine3], official_domains=["adobe.com"], max_retries_per_engine=0)
        res = chain.search("Adobe terms")

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["title"], "DDG Result")
        engine1.search.assert_called_once()
        engine2.search.assert_called_once()
        engine3.search.assert_called_once()

    def test_circuit_breaker_skips_after_threshold_failures(self):
        engine1 = MagicMock(spec=SearchEngine)
        engine1.name = "flaky_engine"
        engine1.search.side_effect = httpx.ConnectError("Connection refused")

        engine2 = MagicMock(spec=SearchEngine)
        engine2.name = "backup_engine"
        engine2.search.return_value = [{"title": "Backup Result", "url": "https://adobe.com", "snippet": "ok"}]

        chain = SearchEngineChain(
            engines=[engine1, engine2],
            circuit_failure_threshold=2,
            circuit_cooldown_seconds=60,
            max_retries_per_engine=0
        )

        # Query 1: engine1 fails, engine2 succeeds
        chain.search("query 1")
        self.assertEqual(engine1.search.call_count, 1)

        # Query 2: engine1 fails again (reaches threshold of 2), engine2 succeeds
        chain.search("query 2")
        self.assertEqual(engine1.search.call_count, 2)
        self.assertTrue(chain.is_circuit_broken("flaky_engine"))

        # Query 3: circuit breaker is OPEN for flaky_engine, it is skipped WITHOUT calling search()
        chain.search("query 3")
        self.assertEqual(engine1.search.call_count, 2)  # Still 2, was skipped!


class TestSearxngEvidenceValidatorWithChain(unittest.TestCase):
    def test_validator_with_injected_search_chain(self):
        mock_chain = MagicMock()
        mock_chain.search.return_value = [
            {
                "title": "Docker Desktop Subscription Terms",
                "url": "https://www.docker.com/legal/docker-subscription-service-agreement/",
                "snippet": "Commercial use of Docker Desktop requires a paid subscription (Pro, Team, or Business) for larger enterprises."
            }
        ]

        evidence = SearxngEvidenceValidator.validate_application(
            app_name="Docker Desktop",
            vendor="Docker",
            version="4.30.0",
            scrape_page=False,
            search_chain=mock_chain
        )

        self.assertEqual(evidence.application, "Docker Desktop")
        self.assertEqual(evidence.evidence_status, "VERIFIED")
        self.assertEqual(evidence.evidence_url, "https://www.docker.com/legal/docker-subscription-service-agreement/")
        self.assertIn("docker", evidence.evidence_url)


if __name__ == "__main__":
    unittest.main()
