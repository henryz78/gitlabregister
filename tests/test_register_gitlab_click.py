import importlib
import json
import random
import sys
import types
import unittest
from pathlib import Path


class FakeButtonLocator:
    def __init__(self):
        self.clicked = False
        self.scrolled = False
        self.first = self
        self.pressed_keys = []
        self.click_kwargs = []

    async def count(self):
        return 1

    async def is_visible(self):
        return True

    async def scroll_into_view_if_needed(self):
        self.scrolled = True

    async def click(self, **kwargs):
        self.clicked = True
        self.click_kwargs.append(kwargs)

    async def press(self, key):
        self.pressed_keys.append(key)


class FakeDropdownToggleLocator:
    def __init__(self):
        self.clicked = False
        self.first = self

    async def count(self):
        return 1

    async def is_visible(self):
        return True

    async def click(self):
        self.clicked = True


class FakeCountryOptionLocator:
    def __init__(self, text):
        self.text = text
        self.clicked = False

    async def text_content(self):
        return self.text

    async def click(self):
        self.clicked = True

    async def wait_for(self, **kwargs):
        pass


class FakeCountryOptionsLocator:
    def __init__(self, options):
        self.options = options

    @property
    def first(self):
        return self.options[0]

    async def count(self):
        return len(self.options)

    def nth(self, index):
        return self.options[index]


class FakeTextFieldLocator:
    def __init__(self):
        self.first = self
        self.scrolled = False
        self.filled_values = []

    async def scroll_into_view_if_needed(self):
        self.scrolled = True

    async def fill(self, value):
        self.filled_values.append(value)


class FakeTypePage:
    def __init__(self):
        self.field = FakeTextFieldLocator()
        self.timeouts = []

    def locator(self, selector):
        return self.field

    async def wait_for_timeout(self, timeout):
        self.timeouts.append(timeout)

class FakePage:
    def __init__(self):
        self.role_calls = []
        self.button = FakeButtonLocator()

    def get_by_role(self, role, **kwargs):
        self.role_calls.append((role, kwargs))
        return self.button

    def locator(self, selector):
        return self.button


class FakeScreenshotPage:
    def __init__(self):
        self.screenshots = []

    async def screenshot(self, **kwargs):
        self.screenshots.append(kwargs)


class FakeOnboardingPage(FakePage):
    def __init__(self):
        super().__init__()
        self.url = "https://gitlab.com/users/sign_up/welcome"
        self.evaluate_scripts = []
        self.timeouts = []
        self.url_waits = []

    async def evaluate(self, script):
        self.evaluate_scripts.append(script)
        return {
            "is_onboarding": True,
            "selected_role": "Software Developer",
            "selected_reason": "My company uses GitLab",
            "created_project": True,
            "company": True,
        }

    async def wait_for_timeout(self, timeout):
        self.timeouts.append(timeout)

    async def wait_for_url(self, predicate, **kwargs):
        self.url_waits.append(kwargs)
        self.url = "https://gitlab.com/projects/new"
        return predicate(self.url)


class FakeIdentityVerificationPage(FakePage):
    def __init__(self):
        super().__init__()
        self.url = "https://gitlab.com/users/identity_verification"
        self.evaluate_scripts = []

    async def evaluate(self, script):
        self.evaluate_scripts.append(script)
        return {
            "blocked": True,
            "reason": "GitLab requires phone number or credit card verification.",
        }


class FakeEmailVerificationPage(FakePage):
    def __init__(self):
        super().__init__()
        self.url = "https://gitlab.com/users/identity_verification"
        self.evaluate_scripts = []

    async def evaluate(self, script):
        self.evaluate_scripts.append(script)
        return {
            "blocked": False,
            "reason": "",
            "email_verification": True,
        }


class FakeCompanyTrialPage(FakePage):
    def __init__(self):
        super().__init__()
        self.url = "https://gitlab.com/users/sign_up/company/new"
        self.evaluate_scripts = []
        self.timeouts = []
        self.url_waits = []
        self.country_toggle = FakeDropdownToggleLocator()
        self.country_options = FakeCountryOptionsLocator(
            [
                FakeCountryOptionLocator("Albania"),
                FakeCountryOptionLocator("Canada"),
                FakeCountryOptionLocator("United States"),
            ]
        )

    async def evaluate(self, script):
        self.evaluate_scripts.append(script)
        return {
            "is_company_trial": True,
            "company_name": "Silver Harbor Labs",
            "phone_cleared": True,
        }

    async def wait_for_timeout(self, timeout):
        self.timeouts.append(timeout)

    async def wait_for_url(self, predicate, **kwargs):
        self.url_waits.append(kwargs)
        self.url = "https://gitlab.com/dashboard"
        return predicate(self.url)

    def locator(self, selector):
        if "base-dropdown-toggle" in selector or "country-dropdown" in selector:
            return self.country_toggle
        if "base-dropdown-menu" in selector:
            return self.country_options
        return super().locator(selector)


class FakeDefaultProjectPage(FakePage):
    def __init__(self):
        super().__init__()
        self.url = "https://gitlab.com/users/sign_up/groups/new"
        self.evaluate_scripts = []
        self.timeouts = []
        self.url_waits = []

    async def evaluate(self, script):
        self.evaluate_scripts.append(script)
        return {
            "is_default_project_page": True,
            "group_name": "kdnissdds-group",
            "project_name": "kdnissdds-project",
        }

    async def wait_for_timeout(self, timeout):
        self.timeouts.append(timeout)

    async def wait_for_url(self, predicate, **kwargs):
        self.url_waits.append(kwargs)
        self.url = "https://gitlab.com/kdnissdds-group/kdnissdds-project"
        return predicate(self.url)


class RegisterGitLabClickTests(unittest.TestCase):
    def import_register_gitlab(self):
        cloakbrowser = types.ModuleType("cloakbrowser")
        cloakbrowser.launch_async = None
        sys.modules["cloakbrowser"] = cloakbrowser

        email_register = types.ModuleType("email_register")
        email_register.get_email_and_token = lambda *args, **kwargs: ("user@nimail.cn", "mail-key")
        email_register.get_verification_code = lambda *args, **kwargs: None
        sys.modules["email_register"] = email_register

        sys.modules.pop("register_gitlab", None)
        self.addCleanup(sys.modules.pop, "register_gitlab", None)
        self.addCleanup(sys.modules.pop, "cloakbrowser", None)
        self.addCleanup(sys.modules.pop, "email_register", None)
        return importlib.import_module("register_gitlab")

    def test_register_button_labels_include_continue(self):
        module = self.import_register_gitlab()

        self.assertIn("Continue", module.REGISTER_BUTTON_TEXTS)

    def test_type_value_fills_without_random_waits(self):
        module = self.import_register_gitlab()
        page = FakeTypePage()

        self.run_async(module.type_value(page, "#email", "user@example.com", "email"))

        self.assertTrue(page.field.scrolled)
        self.assertEqual(page.field.filled_values, ["user@example.com"])
        self.assertEqual(page.timeouts, [])

    def test_click_button_by_role_uses_short_click_timeout(self):
        module = self.import_register_gitlab()
        page = FakePage()

        clicked = self.run_async(module.click_button_by_role(page, ("Continue",)))

        self.assertTrue(clicked)
        self.assertEqual(page.button.click_kwargs[-1]["timeout"], 5000)

    def test_register_button_click_script_checks_button_text_and_input_value(self):
        module = self.import_register_gitlab()

        script = module.build_register_button_click_script()

        self.assertIn('input[type="button"]', module.REGISTER_BUTTON_SELECTORS)
        self.assertIn("textContent", script)
        self.assertIn("value", script)

    def test_browser_launch_help_mentions_playwright_deps_for_shared_library_error(self):
        module = self.import_register_gitlab()

        message = module.browser_launch_error_help(
            RuntimeError(
                "error while loading shared libraries: libatk-1.0.so.0: "
                "cannot open shared object file"
            )
        )

        self.assertIn("libatk-1.0.so.0", message)
        self.assertIn("python -m playwright install-deps chromium", message)
        self.assertIn("python register_gitlab.py", message)

    def test_proxy_dependency_help_mentions_pysocks(self):
        module = self.import_register_gitlab()

        message = module.email_proxy_error_help(
            RuntimeError("Missing dependencies for SOCKS support.")
        )

        self.assertIn("PySocks", message)
        self.assertIn("python -m pip install -r requirements.txt", message)

    def test_onboarding_script_selects_project_and_company_choices(self):
        module = self.import_register_gitlab()

        script = module.build_onboarding_fill_script()

        self.assertIn("Create a new project", script)
        self.assertIn("My company or team", script)
        self.assertIn("selects.slice(0, 2)", script)

    def test_generate_random_name_uses_random_first_and_last_name(self):
        module = self.import_register_gitlab()

        generated_name = module.generate_random_name(random.Random(7))

        first_name, last_name = generated_name.split()
        self.assertIn(first_name, module.RANDOM_FIRST_NAMES)
        self.assertIn(last_name, module.RANDOM_LAST_NAMES)
        self.assertNotEqual(generated_name, "Tian Dong")

    def test_identity_verification_detection_script_checks_phone_and_card_page(self):
        module = self.import_register_gitlab()

        script = module.build_identity_verification_detection_script()

        self.assertIn("help us keep gitlab secure", script)
        self.assertIn("email verification", script)
        self.assertIn("email_verification", script)
        self.assertIn("phone number verification", script)
        self.assertIn("credit card", script)

    def test_otp_field_selector_includes_email_verification_code_fields(self):
        module = self.import_register_gitlab()

        selector = module.OTP_FIELD_SELECTOR

        self.assertIn('input[name*="verification" i]', selector)
        self.assertIn("#verification_code", selector)

    def test_identity_verification_url_is_detected(self):
        module = self.import_register_gitlab()

        self.assertTrue(
            module.url_indicates_identity_verification(
                "https://gitlab.com/users/identity_verification"
            )
        )
        self.assertFalse(
            module.url_indicates_identity_verification(
                "https://gitlab.com/dashboard/projects"
            )
        )

    def test_company_trial_script_fills_company_without_select_elements(self):
        module = self.import_register_gitlab()

        script = module.build_company_trial_fill_script("Silver Harbor Labs")

        self.assertIn("Tell us about your company", script)
        self.assertIn("Silver Harbor Labs", script)
        self.assertNotIn("querySelectorAll(\"select\")", script)
        self.assertNotIn("selected_country", script)
        self.assertIn("phone_cleared", script)

    def test_generate_random_company_name_uses_word_lists(self):
        module = self.import_register_gitlab()

        company_name = module.generate_random_company_name(random.Random(7))

        self.assertRegex(company_name, r"^[A-Za-z]+ [A-Za-z]+ (Labs|Systems|Studio|Works)$")

    def test_final_url_indicates_success_only_for_app_home(self):
        module = self.import_register_gitlab()

        self.assertTrue(
            module.final_url_indicates_registration_success("https://gitlab.com/dashboard/projects")
        )
        self.assertTrue(
            module.final_url_indicates_registration_success("https://gitlab.com/groups/new")
        )
        self.assertFalse(
            module.final_url_indicates_registration_success("https://gitlab.com/users/sign_up/welcome")
        )
        self.assertFalse(
            module.final_url_indicates_registration_success("https://gitlab.com/users/sign_up/company/new")
        )
        self.assertFalse(
            module.final_url_indicates_registration_success("https://gitlab.com/users/sign_up/groups/new")
        )

    def test_module_import_does_not_require_cloakbrowser(self):
        sys.modules.pop('cloakbrowser', None)
        sys.modules.pop('register_gitlab', None)
        sys.modules.pop('gitlab_register.flow', None)
        self.addCleanup(sys.modules.pop, 'register_gitlab', None)
        self.addCleanup(sys.modules.pop, 'gitlab_register.flow', None)

        module = importlib.import_module('register_gitlab')

        self.assertTrue(hasattr(module, 'register_gitlab_async'))

    def test_prepare_email_raises_when_default_provider_missing(self):
        module = self.import_register_gitlab()
        old_provider = module.get_email_and_token
        module.get_email_and_token = None
        try:
            with self.assertRaisesRegex(RuntimeError, 'email_register'):
                module.prepare_email(None)
        finally:
            module.get_email_and_token = old_provider

    def test_prepare_email_uses_default_mail_provider(self):
        module = self.import_register_gitlab()
        calls = []

        def fake_get_email_and_token():
            calls.append("called")
            return "voiceuser@nimail.cn", "voiceuser@nimail.cn"

        module.get_email_and_token = fake_get_email_and_token

        email, mail_key = module.prepare_email(None)

        self.assertEqual(email, "voiceuser@nimail.cn")
        self.assertEqual(mail_key, "voiceuser@nimail.cn")
        self.assertEqual(calls, ["called"])

    def test_maybe_screenshot_skips_when_disabled(self):
        module = self.import_register_gitlab()
        page = FakeScreenshotPage()

        saved = self.run_async(module.maybe_screenshot(page, None, "demo.png"))

        self.assertFalse(saved)
        self.assertEqual(page.screenshots, [])

    def test_maybe_screenshot_saves_when_enabled(self):
        module = self.import_register_gitlab()
        root = self.tmp_path()
        page = FakeScreenshotPage()

        saved = self.run_async(module.maybe_screenshot(page, root, "demo.png"))

        self.assertTrue(saved)
        self.assertEqual(page.screenshots[0]["path"], str(root / "demo.png"))
        self.assertTrue(page.screenshots[0]["full_page"])

    def test_build_success_account_record_keeps_only_account_fields(self):
        module = self.import_register_gitlab()

        record = module.build_success_account_record(
            {
                "email": "user@example.com",
                "username": "voice_user",
                "password": "Secure1234!",
                "name": "Alex Reed",
                "timestamp": "2026-06-26 08:09:10",
                "email_provider": "idatariver",
                "email_id": "mailbox-id-123",
                "browser_proxy": "socks5://127.0.0.1:1080",
                "browser_proxy_mode": "text",
                "namespace_id": "136077360",
                "_gitlab_session": "session-cookie-value",
                "unused_cookie": "unused-cookie-value",
                "final_url": "https://gitlab.com/dashboard",
                "screenshot_dir": "/tmp/screenshots/demo",
            }
        )

        self.assertEqual(
            record,
            {
                "email": "user@example.com",
                "username": "voice_user",
                "password": "Secure1234!",
                "name": "Alex Reed",
                "timestamp": "2026-06-26 08:09:10",
                "email_provider": "idatariver",
                "email_id": "mailbox-id-123",
                "browser_proxy": "socks5://127.0.0.1:1080",
                "browser_proxy_mode": "text",
                "namespace_id": "136077360",
                "_gitlab_session": "session-cookie-value",
            },
        )

    def test_namespace_id_from_url_reads_gitlab_project_query(self):
        module = self.import_register_gitlab()

        self.assertEqual(
            module.namespace_id_from_url(
                "https://gitlab.com/projects/new?namespace_id=136077360"
            ),
            "136077360",
        )

    def test_namespace_id_from_url_returns_empty_when_missing(self):
        module = self.import_register_gitlab()

        self.assertEqual(module.namespace_id_from_url("https://gitlab.com/projects/new"), "")

    def test_gitlab_session_from_cookies_reads_session_cookie(self):
        module = self.import_register_gitlab()

        self.assertEqual(
            module.gitlab_session_from_cookies(
                [
                    {"name": "other", "value": "x"},
                    {"name": "_gitlab_session", "value": "session-cookie-value"},
                ]
            ),
            "session-cookie-value",
        )

    def test_gitlab_session_from_cookies_returns_empty_when_missing(self):
        module = self.import_register_gitlab()

        self.assertEqual(module.gitlab_session_from_cookies([]), "")

    def test_save_registration_result_writes_json_inside_run_dir(self):
        module = self.import_register_gitlab()
        run_dir = self.tmp_path() / "20260626_080910_voice_user"
        run_dir.mkdir()

        save_path = module.save_registration_result(
            {"email": "user@example.com", "username": "voice_user"},
            run_dir,
            "account.json",
        )

        self.assertEqual(save_path, run_dir / "account.json")
        self.assertEqual(
            json.loads(save_path.read_text(encoding="utf-8")),
            {"email": "user@example.com", "username": "voice_user"},
        )

    def test_parse_registration_count_accepts_limited_positive_count(self):
        module = self.import_register_gitlab()

        self.assertEqual(module.parse_registration_count("1"), 1)
        self.assertEqual(module.parse_registration_count("5"), 5)

    def test_parse_registration_count_rejects_out_of_range_values(self):
        module = self.import_register_gitlab()

        with self.assertRaises(module.argparse.ArgumentTypeError):
            module.parse_registration_count("0")
        with self.assertRaises(module.argparse.ArgumentTypeError):
            module.parse_registration_count("6")

    def test_validate_batch_options_rejects_shared_email_or_username(self):
        module = self.import_register_gitlab()

        with self.assertRaisesRegex(ValueError, "--email"):
            module.validate_batch_options(2, email="user@example.com", username=None)
        with self.assertRaisesRegex(ValueError, "--username"):
            module.validate_batch_options(2, email=None, username="voice_user")

    def tmp_path(self):
        from tempfile import TemporaryDirectory

        temp_dir = TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        return Path(temp_dir.name)

    def run_async(self, coro):
        import asyncio

        return asyncio.run(coro)


class RegisterGitLabAsyncClickTests(unittest.IsolatedAsyncioTestCase):
    def import_register_gitlab(self):
        return RegisterGitLabClickTests().import_register_gitlab()

    async def test_click_register_button_uses_accessible_continue_button(self):
        module = self.import_register_gitlab()
        page = FakePage()

        clicked = await module.click_register_button(page)

        self.assertTrue(clicked)
        self.assertTrue(page.button.scrolled)
        self.assertTrue(page.button.clicked)
        self.assertIn(("button", {"name": "Continue", "exact": True}), page.role_calls)

    async def test_enter_retry_runs_when_signup_form_remains_visible(self):
        module = self.import_register_gitlab()
        page = FakePage()

        retried = await module.press_enter_if_signup_form_visible(page, "#password")

        self.assertTrue(retried)
        self.assertIn("Enter", page.button.pressed_keys)

    async def test_onboarding_page_is_filled_and_continued(self):
        module = self.import_register_gitlab()
        page = FakeOnboardingPage()

        handled = await module.complete_gitlab_onboarding_if_present(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertTrue(handled)
        self.assertEqual(len(page.evaluate_scripts), 1)
        self.assertEqual(page.timeouts, [500])
        self.assertEqual(page.url_waits, [{"timeout": 15000}])
        self.assertTrue(page.button.clicked)
        self.assertIn(("button", {"name": "Continue", "exact": True}), page.role_calls)

    async def test_identity_verification_page_is_reported_as_blocked(self):
        module = self.import_register_gitlab()
        page = FakeIdentityVerificationPage()

        result = await module.detect_identity_verification_block(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertTrue(result["blocked"])
        self.assertIn("phone number", result["reason"])

    async def test_identity_verification_page_is_reported_as_blocked_by_url(self):
        module = self.import_register_gitlab()
        page = FakeIdentityVerificationPage()

        async def evaluate_without_page_text(script):
            return {"blocked": False, "reason": ""}

        page.evaluate = evaluate_without_page_text

        result = await module.detect_identity_verification_block(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertTrue(result["blocked"])
        self.assertIn("identity verification", result["reason"].lower())

    async def test_email_verification_page_on_identity_url_waits_for_otp(self):
        module = self.import_register_gitlab()
        page = FakeEmailVerificationPage()

        result = await module.detect_identity_verification_block(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertFalse(result["blocked"])

    async def test_company_trial_page_is_filled_and_continued(self):
        module = self.import_register_gitlab()
        page = FakeCompanyTrialPage()

        handled = await module.complete_gitlab_company_trial_if_present(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertTrue(handled)
        self.assertEqual(len(page.evaluate_scripts), 1)
        self.assertEqual(page.timeouts, [500])
        self.assertEqual(page.url_waits, [{"timeout": 15000}])
        self.assertTrue(page.country_toggle.clicked)
        self.assertTrue(any(option.clicked for option in page.country_options.options))
        self.assertTrue(page.button.clicked)
        self.assertIn(("button", {"name": "Continue with trial", "exact": True}), page.role_calls)

    async def test_country_dropdown_is_selected_by_playwright_click(self):
        module = self.import_register_gitlab()
        page = FakeCompanyTrialPage()

        selected_country = await module.select_country_via_playwright(page)

        self.assertIn(selected_country, {"Albania", "Canada", "United States"})
        self.assertEqual(page.timeouts, [])
        self.assertTrue(page.country_toggle.clicked)
        self.assertTrue(any(option.clicked for option in page.country_options.options))

    async def test_default_project_page_clicks_create_without_filling_fields(self):
        module = self.import_register_gitlab()
        page = FakeDefaultProjectPage()

        handled = await module.complete_gitlab_default_project_if_present(
            page,
            headless=False,
            screenshot_dir=None,
        )

        self.assertTrue(handled)
        self.assertEqual(len(page.evaluate_scripts), 1)
        self.assertEqual(page.timeouts, [500])
        self.assertEqual(page.url_waits, [{"timeout": 15000}])
        self.assertTrue(page.button.clicked)
        self.assertIn(("button", {"name": "Create project", "exact": True}), page.role_calls)

    async def test_register_one_records_success_account(self):
        module = self.import_register_gitlab()

        class Config:
            headless = True
            screenshots = False

        class Outputs:
            def __init__(self):
                self.attempted = 0
                self.accounts = []

            def record_attempt(self):
                self.attempted += 1

            def add_success_account(self, account):
                self.accounts.append(account)

        async def fake_register_gitlab_async(**kwargs):
            return {"email": "user@example.test", "username": kwargs["username"]}

        outputs = Outputs()
        old_register = module.register_gitlab_async
        module.register_gitlab_async = fake_register_gitlab_async
        try:
            status = await module.register_one(
                config=Config(),
                outputs=outputs,
                username="voice_user",
            )
        finally:
            module.register_gitlab_async = old_register

        self.assertEqual(status, module.REGISTRATION_STATUS_SUCCESS)
        self.assertEqual(outputs.attempted, 1)
        self.assertEqual(outputs.accounts, [{"email": "user@example.test", "username": "voice_user"}])

    async def test_batch_registration_runs_requested_count_serially(self):
        module = self.import_register_gitlab()
        calls = []

        async def fake_register_once(**kwargs):
            calls.append(kwargs)
            return module.REGISTRATION_STATUS_SUCCESS

        summary = await module.register_gitlab_batch_async(
            3,
            password="SharedPassword123!",
            headless=True,
            screenshots=False,
            register_once=fake_register_once,
        )

        self.assertEqual(len(calls), 3)
        self.assertEqual(summary["requested"], 3)
        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(summary[module.REGISTRATION_STATUS_SUCCESS], 3)
        self.assertTrue(all(call["email"] is None for call in calls))

    async def test_batch_registration_stops_after_identity_verification_block(self):
        module = self.import_register_gitlab()
        calls = []

        async def fake_register_once(**kwargs):
            calls.append(kwargs)
            return module.IDENTITY_VERIFICATION_STATUS

        summary = await module.register_gitlab_batch_async(
            5,
            headless=True,
            screenshots=False,
            register_once=fake_register_once,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(summary["requested"], 5)
        self.assertEqual(summary["attempted"], 1)
        self.assertEqual(summary[module.IDENTITY_VERIFICATION_STATUS], 1)

    async def test_batch_registration_counts_errors_and_continues(self):
        module = self.import_register_gitlab()
        calls = []

        async def fake_register_once(**kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise RuntimeError("temporary network failure")
            return module.REGISTRATION_STATUS_SUCCESS

        summary = await module.register_gitlab_batch_async(
            2,
            headless=True,
            screenshots=False,
            register_once=fake_register_once,
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(summary["attempted"], 2)
        self.assertEqual(summary[module.REGISTRATION_STATUS_ERROR], 1)
        self.assertEqual(summary[module.REGISTRATION_STATUS_SUCCESS], 1)


if __name__ == "__main__":
    unittest.main()
