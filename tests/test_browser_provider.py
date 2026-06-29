import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrowserProviderTests(unittest.TestCase):
    def test_register_gitlab_uses_browser_runtime_only(self):
        wrapper_source = (ROOT / "register_gitlab.py").read_text(encoding="utf-8")
        flow_source = (ROOT / "gitlab_register" / "flow.py").read_text(encoding="utf-8")
        runtime_source = (ROOT / "gitlab_register" / "browser_runtime.py").read_text(encoding="utf-8")
        combined_source = wrapper_source + flow_source + runtime_source

        self.assertIn("from cloakbrowser import launch_async", runtime_source)
        self.assertIn("launch_browser", flow_source)
        self.assertNotIn("from cloakbrowser import launch_async", flow_source)
        self.assertNotIn("Drission" + "Page", combined_source)
        self.assertNotIn("async_" + "play" + "wright", combined_source)
        self.assertNotIn("play" + "wright" + ".async_api", combined_source)
        self.assertNotIn("Chrom" + "ium" + "Options", combined_source)

    def test_requirements_use_cloakbrowser_runtime(self):
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("cloakbrowser", requirements)
        self.assertNotIn("Drission" + "Page", requirements)
        self.assertNotIn("play" + "wright", requirements.lower())


if __name__ == "__main__":
    unittest.main()
