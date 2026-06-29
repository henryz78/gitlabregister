import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import browser_proxy_pool


class BrowserProxyParserTests(unittest.TestCase):
    def test_parse_proxy_lines_accepts_supported_schemes_and_deduplicates(self):
        proxies = browser_proxy_pool.parse_proxy_lines(
            """
            socks5://127.0.0.1:1080
            http://127.0.0.1:8080
            socks5://127.0.0.1:1080
            ftp://127.0.0.1:21
            # comment
            """
        )

        self.assertEqual(
            proxies,
            [
                "socks5://127.0.0.1:1080",
                "http://127.0.0.1:8080",
            ],
        )

    def test_normalize_config_keeps_existing_browser_proxy_as_single_mode(self):
        config = browser_proxy_pool.normalize_browser_proxy_config(
            {"browser_proxy": "socks5://10.0.0.1:1080"}
        )

        self.assertEqual(config.mode, "single")
        self.assertEqual(config.single_proxy, "socks5://10.0.0.1:1080")
        self.assertEqual(config.refresh_interval_seconds, 120)


class BrowserProxyPoolTests(unittest.TestCase):
    def test_single_mode_selects_single_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )

            pool.configure({"browser_proxy": "http://127.0.0.1:8080"})
            selection = pool.next_proxy()

            self.assertEqual(selection.proxy, "http://127.0.0.1:8080")
            self.assertEqual(selection.mode, "single")
            self.assertEqual(selection.count, 1)

    def test_text_mode_rotates_and_skips_cooling_proxy(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure(
                {
                    "browser_proxy_mode": "text",
                    "browser_proxy_list_text": (
                        "http://127.0.0.1:8001\n"
                        "http://127.0.0.1:8002\n"
                    ),
                }
            )

            first = pool.next_proxy()
            pool.record_result(
                first.proxy,
                success=False,
                error="token_login_failed",
            )
            second = pool.next_proxy()

            self.assertEqual(first.proxy, "http://127.0.0.1:8001")
            self.assertEqual(second.proxy, "http://127.0.0.1:8002")
            self.assertEqual(pool.snapshot()["cooling_count"], 1)

    def test_hard_failure_removes_proxy_from_runtime_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure(
                {
                    "browser_proxy_mode": "text",
                    "browser_proxy_list_text": (
                        "http://127.0.0.1:8001\n"
                        "http://127.0.0.1:8002\n"
                    ),
                }
            )

            first = pool.next_proxy()
            pool.record_result(
                first.proxy,
                success=False,
                error="Page.goto: Timeout 30000ms exceeded.",
            )

            self.assertEqual(pool.current_proxy_list(), ["http://127.0.0.1:8002"])

    def test_url_mode_keeps_hard_failed_proxy_disabled_after_refresh(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"http://127.0.0.1:9001\nhttp://127.0.0.1:9002\n"

        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure(
                {
                    "browser_proxy_mode": "url",
                    "browser_proxy_url": "https://example.test/proxies.txt",
                }
            )

            with patch.object(
                browser_proxy_pool.urllib.request,
                "urlopen",
                return_value=FakeResponse(),
            ):
                pool.refresh(force=True)
                pool.record_result(
                    "http://127.0.0.1:9001",
                    success=False,
                    error="Page.goto: Timeout 30000ms exceeded.",
                )
                pool.refresh(force=True)

            self.assertEqual(pool.current_proxy_list(), ["http://127.0.0.1:9002"])

    def test_success_increases_score_and_state_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "browser_proxy_state.json"
            pool = browser_proxy_pool.BrowserProxyPool(state_path=state_path)
            pool.configure({"browser_proxy": "http://127.0.0.1:8080"})

            selection = pool.next_proxy()
            pool.record_result(selection.proxy, success=True)
            reloaded = browser_proxy_pool.BrowserProxyPool(state_path=state_path)
            reloaded.configure({"browser_proxy": "http://127.0.0.1:8080"})

            proxy_state = reloaded.snapshot()["proxies"][0]
            self.assertEqual(proxy_state["success_count"], 1)
            self.assertGreater(proxy_state["score"], 0)

    def test_reset_clears_proxy_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure({"browser_proxy": "http://127.0.0.1:8080"})
            selection = pool.next_proxy()
            pool.record_result(selection.proxy, success=False, error="network timeout")

            reset = pool.reset_state()

            self.assertEqual(reset["removed"], 1)
            self.assertEqual(pool.snapshot()["cooling_count"], 0)

    def test_url_mode_refreshes_proxy_list(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"http://127.0.0.1:9001\nhttp://127.0.0.1:9002\n"

        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure(
                {
                    "browser_proxy_mode": "url",
                    "browser_proxy_url": "https://example.test/proxies.txt",
                }
            )

            with patch.object(
                browser_proxy_pool.urllib.request,
                "urlopen",
                return_value=FakeResponse(),
            ):
                state = pool.refresh(force=True)

            self.assertEqual(state["count"], 2)
            self.assertEqual(pool.next_proxy().proxy, "http://127.0.0.1:9001")

    def test_url_mode_uses_browser_headers(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b"http://127.0.0.1:9001\n"

        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp:
            pool = browser_proxy_pool.BrowserProxyPool(
                state_path=Path(tmp) / "browser_proxy_state.json"
            )
            pool.configure(
                {
                    "browser_proxy_mode": "url",
                    "browser_proxy_url": "https://example.test/proxies.txt",
                }
            )

            with patch.object(browser_proxy_pool.urllib.request, "urlopen", side_effect=fake_urlopen):
                state = pool.refresh(force=True)

            self.assertEqual(state["count"], 1)
            self.assertEqual(captured["timeout"], 15)
            self.assertIn("Mozilla/5.0", captured["request"].headers["User-agent"])


if __name__ == "__main__":
    unittest.main()
