import unittest
import sys
import types
from unittest.mock import Mock, patch


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")

    class DummySession:
        def __init__(self):
            self.headers = {}
            self.proxies = {}

    requests_stub.Session = DummySession
    sys.modules["requests"] = requests_stub

import email_register as email_module
from email_register import (
    create_temp_email,
    extract_code_from_message,
    extract_verification_code,
    fetch_nimail_messages,
    get_email_token_metadata,
    get_email_and_token,
    get_verification_code,
)


class EmailRegisterTests(unittest.TestCase):
    def test_default_email_provider_is_idatariver(self):
        self.assertEqual(
            email_module._configured_email_provider({}),
            "idatariver",
        )

    def test_configure_from_runtime_sets_provider_values(self):
        class Config:
            email_provider = "nimail"
            idatariver_api_key = "idr_key"
            idatariver_api_base = "https://example.test/api/"
            idatariver_poll_interval_seconds = 7.5
            nimail_api_base = "https://mail.example.test/"

        old_values = (
            email_module.EMAIL_PROVIDER,
            email_module.IDATARIVER_API_KEY,
            email_module.IDATARIVER_API_BASE,
            email_module.IDATARIVER_POLL_INTERVAL_SECONDS,
            email_module.NIMAIL_API_BASE,
        )
        try:
            email_module.configure_from_runtime(Config())

            self.assertEqual(email_module.EMAIL_PROVIDER, "nimail")
            self.assertEqual(email_module.IDATARIVER_API_KEY, "idr_key")
            self.assertEqual(email_module.IDATARIVER_API_BASE, "https://example.test/api")
            self.assertEqual(email_module.IDATARIVER_POLL_INTERVAL_SECONDS, 7.5)
            self.assertEqual(email_module.NIMAIL_API_BASE, "https://mail.example.test")
        finally:
            (
                email_module.EMAIL_PROVIDER,
                email_module.IDATARIVER_API_KEY,
                email_module.IDATARIVER_API_BASE,
                email_module.IDATARIVER_POLL_INTERVAL_SECONDS,
                email_module.NIMAIL_API_BASE,
            ) = old_values

    def test_extracts_gitlab_six_digit_code(self):
        self.assertEqual(
            extract_verification_code("Your GitLab verification code is 123456."),
            "123456",
        )

    def test_ignores_three_by_three_codes(self):
        self.assertIsNone(extract_verification_code("Your code is MM0-SF3."))

    def test_create_temp_email_applies_nimail_address(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": "true",
            "user": "voiceuser@nimail.cn",
        }
        session = Mock()
        session.post.return_value = response

        with patch.object(email_module, "_generate_nimail_address", return_value="voiceuser@nimail.cn"):
            self.assertEqual(create_temp_email(session=session), "voiceuser@nimail.cn")

        session.post.assert_called_once()
        self.assertEqual(session.post.call_args.kwargs["data"]["mail"], "voiceuser@nimail.cn")

    def test_create_temp_email_does_not_print_mailbox_by_default(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": "true",
            "user": "voiceuser@nimail.cn",
        }
        session = Mock()
        session.post.return_value = response

        with patch.object(
            email_module,
            "_generate_nimail_address",
            return_value="voiceuser@nimail.cn",
        ), patch("builtins.print") as printed:
            self.assertEqual(create_temp_email(session=session), "voiceuser@nimail.cn")

        printed.assert_not_called()

    def test_create_idatariver_email_does_not_print_mailbox_by_default(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 0,
            "result": {
                "email": "voiceuser@uselesss.org",
                "id": "mailbox-id-123",
            },
        }
        session = Mock()
        session.get.return_value = response

        with patch.object(
            email_module,
            "IDATARIVER_API_KEY",
            "idr_test_key",
        ), patch("builtins.print") as printed:
            email, email_id = email_module.create_idatariver_email(session=session)

        self.assertEqual(email, "voiceuser@uselesss.org")
        self.assertEqual(email_id, "mailbox-id-123")
        printed.assert_not_called()

    def test_wait_for_verification_code_does_not_print_code_by_default(self):
        session = Mock()
        with patch.object(
            email_module,
            "fetch_nimail_messages",
            return_value=([{"id": "abc", "subject": "GitLab code 654321"}], 123),
        ), patch("builtins.print") as printed:
            code = email_module.wait_for_verification_code(
                "voiceuser@nimail.cn",
                timeout=10,
                session=session,
            )

        self.assertEqual(code, "654321")
        printed.assert_not_called()

    def test_fetch_nimail_messages_returns_mail_list(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "success": "true",
            "time": 123,
            "mail": [{"id": "abc", "subject": "GitLab verification code 654321"}],
        }
        session = Mock()
        session.post.return_value = response

        messages, next_time = fetch_nimail_messages("voiceuser@nimail.cn", session=session)

        self.assertEqual(next_time, 123)
        self.assertEqual(messages[0]["id"], "abc")

    def test_extract_code_from_nimail_message(self):
        message = {
            "subject": "GitLab verification code 654321",
            "from": "gitlab.com",
        }

        self.assertEqual(extract_code_from_message(message), "654321")

    def test_get_email_and_token_uses_nimail(self):
        with patch.object(email_module, "EMAIL_PROVIDER", "nimail"), patch.object(
            email_module, "create_temp_email", return_value="voiceuser@nimail.cn"
        ):
            email, token = get_email_and_token()

        self.assertEqual(email, "voiceuser@nimail.cn")
        self.assertEqual(token, "voiceuser@nimail.cn")

    def test_get_email_and_token_uses_idatariver_and_keeps_email_id(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "code": 0,
            "credits": 0,
            "result": {
                "email": "voiceuser@uselesss.org",
                "id": "mailbox-id-123",
            },
        }
        session = Mock()
        session.get.return_value = response

        with patch.object(email_module, "EMAIL_PROVIDER", "idatariver"), patch.object(
            email_module, "IDATARIVER_API_KEY", "idr_test_key"
        ), patch.object(email_module, "_create_session", return_value=session):
            email, token = get_email_and_token()

        self.assertEqual(email, "voiceuser@uselesss.org")
        self.assertEqual(
            get_email_token_metadata(token),
            {
                "provider": "idatariver",
                "email": "voiceuser@uselesss.org",
                "email_id": "mailbox-id-123",
            },
        )
        session.get.assert_called_once()
        self.assertEqual(session.get.call_args.kwargs["params"]["apikey"], "idr_test_key")
        self.assertEqual(session.get.call_args.kwargs["params"]["type"], "*")

    def test_get_verification_code_uses_nimail_mailbox(self):
        with patch.object(email_module, "wait_for_verification_code", return_value="778899") as wait_for_code:
            code = get_verification_code(
                "voiceuser@nimail.cn",
                "voiceuser@nimail.cn",
                timeout=10,
            )

        self.assertEqual(code, "778899")
        wait_for_code.assert_called_once_with(
            email="voiceuser@nimail.cn",
            timeout=10,
        )

    def test_get_verification_code_uses_idatariver_email_id(self):
        token = email_module.make_email_token(
            "idatariver",
            email="voiceuser@uselesss.org",
            email_id="mailbox-id-123",
        )
        with patch.object(email_module, "wait_for_idatariver_verification_code", return_value="445566") as wait_for_code:
            code = get_verification_code(token, "voiceuser@uselesss.org", timeout=10)

        self.assertEqual(code, "445566")
        wait_for_code.assert_called_once_with(
            email_id="mailbox-id-123",
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
