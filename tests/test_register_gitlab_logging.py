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

    def test_run_script_suppresses_cloakbrowser_font_warning(self):
        text = Path("run.sh").read_text(encoding="utf-8")

        self.assertIn("CLOAKBROWSER_SUPPRESS_FONT_WARNING=1", text)


if __name__ == "__main__":
    unittest.main()
