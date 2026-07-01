import unittest
from pathlib import Path


SOURCE_FILES = (
    Path("gitlab_register/flow.py"),
    Path("gitlab_register/cli.py"),
    Path("tests/test_cli.py"),
)


class RegisterGitLabLoggingTests(unittest.TestCase):
    def test_default_logs_hide_low_level_duplicate_actions(self):
        source = Path("gitlab_register/flow.py").read_text(encoding="utf-8")

        self.assertNotIn("Clicking submit button", source)
        self.assertNotIn("Submit button clicked", source)
        self.assertNotIn("Clicked button by role", source)
        self.assertNotIn("Registration form is still visible; pressed Enter to submit", source)
        self.assertNotIn("OTP verification button clicked", source)
        self.assertNotIn("OTP submitted. Waiting for redirection", source)

    def test_default_logs_do_not_print_plain_password(self):
        source = Path("gitlab_register/flow.py").read_text(encoding="utf-8")

        self.assertNotIn("Generated a secure password: {password}", source)
        self.assertNotIn("Password: {password}", source)
        self.assertIn("密码已生成", source)

    def test_source_files_do_not_contain_replacement_question_marks(self):
        replacement_marker = "?" * 4
        for path in SOURCE_FILES:
            with self.subTest(path=str(path)):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn(replacement_marker, text)

    def test_flow_verbose_enables_email_provider_details(self):
        import sys
        import types

        if "requests" not in sys.modules:
            requests_stub = types.ModuleType("requests")

            class DummySession:
                def __init__(self):
                    self.headers = {}
                    self.proxies = {}

            requests_stub.Session = DummySession
            sys.modules["requests"] = requests_stub

        import email_register as email_module
        from gitlab_register import flow

        old_flow_verbose = flow.LOG_VERBOSE
        old_email_verbose = email_module.LOG_VERBOSE
        try:
            flow.set_log_verbose(True)
            self.assertTrue(email_module.LOG_VERBOSE)
        finally:
            flow.set_log_verbose(old_flow_verbose)
            email_module.set_log_verbose(old_email_verbose)

    def test_run_script_suppresses_cloakbrowser_font_warning(self):
        text = Path("run.sh").read_text(encoding="utf-8")

        self.assertIn("CLOAKBROWSER_SUPPRESS_FONT_WARNING=1", text)


if __name__ == "__main__":
    unittest.main()
