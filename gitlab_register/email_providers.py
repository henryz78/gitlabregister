from __future__ import annotations

import json
import os
import random
import re
import string
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

import requests

NIMAIL_API_BASE = "https://www.nimail.cn"
NIMAIL_DOMAIN = "nimail.cn"
IDATARIVER_API_BASE = "https://apiok.us/api/cbea"
IDATARIVER_PROVIDER = "idatariver"
NIMAIL_PROVIDER = "nimail"
DEFAULT_EMAIL_PROVIDER = IDATARIVER_PROVIDER
EMAIL_TOKEN_PREFIX = "__email_provider__:"

_config_path = Path(__file__).resolve().parent.parent / "config.json"
_conf: Dict[str, Any] = {}
if _config_path.exists():
    with _config_path.open("r", encoding="utf-8") as _f:
        _conf = json.load(_f)

PROXY = str(_conf.get("proxy", ""))
def _configured_email_provider(conf: Dict[str, Any]) -> str:
    return str(conf.get("email_provider", DEFAULT_EMAIL_PROVIDER) or DEFAULT_EMAIL_PROVIDER).strip().lower()


EMAIL_PROVIDER = _configured_email_provider(_conf)
IDATARIVER_API_KEY = str(
    _conf.get("idatariver_api_key") or os.environ.get("IDATARIVER_API_KEY") or ""
).strip()
IDATARIVER_API_BASE = str(_conf.get("idatariver_api_base", IDATARIVER_API_BASE)).rstrip("/")
IDATARIVER_POLL_INTERVAL_SECONDS = float(_conf.get("idatariver_poll_interval_seconds", 5))

DEFAULT_HEADERS = {
    "accept": "application/json",
    "accept-language": "zh-CN,zh",
    "origin": NIMAIL_API_BASE,
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)
    if PROXY:
        session.proxies = {"http": PROXY, "https": PROXY}
    return session


def _is_success(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def make_email_token(provider: str, **metadata: str) -> str:
    payload = {"provider": provider, **metadata}
    return EMAIL_TOKEN_PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def get_email_token_metadata(mail_key: Any) -> Dict[str, str]:
    if isinstance(mail_key, dict):
        return {str(key): str(value) for key, value in mail_key.items() if value is not None}

    token = str(mail_key or "")
    if token.startswith(EMAIL_TOKEN_PREFIX):
        try:
            payload = json.loads(token[len(EMAIL_TOKEN_PREFIX) :])
        except ValueError:
            return {}
        if isinstance(payload, dict):
            return {str(key): str(value) for key, value in payload.items() if value is not None}
        return {}

    if token:
        return {"provider": NIMAIL_PROVIDER, "email": token}
    return {}


def _generate_nimail_address() -> str:
    local = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"{local}@{NIMAIL_DOMAIN}"


def create_temp_email(session: Optional[requests.Session] = None) -> str:
    email = _generate_nimail_address()
    client = session or _create_session()
    response = client.post(
        f"{NIMAIL_API_BASE}/api/applymail",
        data={"mail": email},
        timeout=15,
    )
    if response.status_code != 200:
        raise Exception(f"NiMail mailbox request failed: HTTP {response.status_code}")

    data = response.json()
    if _is_success(data.get("success")):
        applied_email = str(data.get("user") or email)
        print(f"[*] NiMail temporary email ready: {applied_email}")
        return applied_email

    message = data.get("message") or "unknown error"
    raise Exception(f"NiMail mailbox request failed: {message}")


def get_email_and_token() -> Tuple[Optional[str], Optional[str]]:
    if EMAIL_PROVIDER == IDATARIVER_PROVIDER:
        email, email_id = create_idatariver_email()
        token = make_email_token(
            IDATARIVER_PROVIDER,
            email=email,
            email_id=email_id,
        )
        return email, token

    email = create_temp_email()
    return email, email


def _idatariver_api_key() -> str:
    if not IDATARIVER_API_KEY:
        raise Exception("iDataRiver API key is required. Set IDATARIVER_API_KEY in .env.")
    return IDATARIVER_API_KEY


def _ensure_idatariver_success(data: Dict[str, Any], action: str) -> Any:
    code = data.get("code")
    if code == 0 or str(code) == "0":
        return data.get("result")
    message = data.get("msg") or data.get("tip") or "unknown error"
    raise Exception(f"iDataRiver {action} failed: code={code}, message={message}")


def _first_mapping(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                return item
    return {}


def _value_from_keys(data: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if value:
            return str(value)
    return ""


def create_idatariver_email(session: Optional[requests.Session] = None) -> Tuple[str, str]:
    client = session or _create_session()
    response = client.get(
        f"{IDATARIVER_API_BASE}/generate/v1",
        params={"apikey": _idatariver_api_key(), "type": "*"},
        timeout=75,
    )
    if response.status_code != 200:
        raise Exception(f"iDataRiver mailbox request failed: HTTP {response.status_code}")

    data = response.json()
    result = _ensure_idatariver_success(data, "mailbox request")
    result_data = _first_mapping(result)
    email = _value_from_keys(result_data, ("email", "mail", "address"))
    email_id = _value_from_keys(result_data, ("id", "email_id", "mail_id", "mailId"))

    if isinstance(result, str) and "@" in result:
        email = result
    if not email:
        email = _value_from_keys(data, ("email", "mail", "address"))
    if not email_id:
        email_id = _value_from_keys(data, ("id", "email_id", "mail_id", "mailId"))

    if not email or not email_id:
        raise Exception("iDataRiver mailbox request failed: missing email or email id")

    print(f"[*] iDataRiver temporary email ready: {email}")
    return email, email_id


def fetch_idatariver_messages(
    email_id: str,
    session: Optional[requests.Session] = None,
) -> List[Dict[str, Any]]:
    client = session or _create_session()
    response = client.get(
        f"{IDATARIVER_API_BASE}/messages/v1",
        params={"apikey": _idatariver_api_key(), "id": email_id},
        timeout=75,
    )
    if response.status_code != 200:
        return []

    data = response.json()
    result = _ensure_idatariver_success(data, "message list request")
    if isinstance(result, list):
        return [message for message in result if isinstance(message, dict)]
    if isinstance(result, dict):
        for key in ("messages", "items", "list", "mail", "emails", "data"):
            messages = result.get(key)
            if isinstance(messages, list):
                return [message for message in messages if isinstance(message, dict)]
        return [result]
    return []


def fetch_idatariver_message_body(
    message_id: str,
    session: Optional[requests.Session] = None,
) -> str:
    client = session or _create_session()
    response = client.get(
        f"{IDATARIVER_API_BASE}/message/detail/v1",
        params={"apikey": _idatariver_api_key(), "id": message_id},
        timeout=75,
    )
    if response.status_code != 200:
        return ""

    data = response.json()
    result = _ensure_idatariver_success(data, "message detail request")
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        parts: List[str] = []
        for key in ("subject", "text", "html", "body", "content", "mail"):
            value = result.get(key)
            if value:
                parts.append(str(value))
        return "\n".join(parts)
    return ""


def fetch_nimail_messages(
    email: str,
    check_time: int = 0,
    session: Optional[requests.Session] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    client = session or _create_session()
    response = client.post(
        f"{NIMAIL_API_BASE}/api/getmails",
        data={
            "mail": email,
            "time": str(check_time),
            "_": str(int(time.time() * 1000)),
        },
        timeout=15,
    )
    if response.status_code != 200:
        return [], check_time

    data = response.json()
    if not _is_success(data.get("success")):
        return [], check_time

    messages = data.get("mail")
    if not isinstance(messages, list):
        messages = []

    try:
        next_time = int(data.get("time", check_time))
    except (TypeError, ValueError):
        next_time = check_time

    return messages, next_time


def fetch_nimail_message_body(
    email: str,
    message_id: str,
    session: Optional[requests.Session] = None,
) -> str:
    client = session or _create_session()
    response = client.post(
        f"{NIMAIL_API_BASE}/api/viewmail",
        data={
            "mail": message_id,
            "to": email,
            "_": str(int(time.time() * 1000)),
        },
        timeout=15,
    )
    if response.status_code == 200:
        try:
            data = response.json()
            if _is_success(data.get("success")):
                return str(data.get("mail") or "")
        except ValueError:
            pass

    safe_email = quote(email, safe="@.")
    safe_message_id = quote(str(message_id), safe="")
    for path in (
        f"/api/raw-html/{safe_email}/{safe_message_id}",
        f"/api/raw-html{safe_email}/{safe_message_id}",
    ):
        raw = client.get(f"{NIMAIL_API_BASE}{path}", timeout=15)
        if raw.status_code == 200 and raw.text.strip():
            return raw.text

    return ""


def extract_code_from_message(message: Dict[str, Any]) -> Optional[str]:
    parts: List[str] = []
    for key in ("subject", "text", "html", "mail", "body", "content"):
        value = message.get(key)
        if value:
            parts.append(str(value))
    return extract_verification_code("\n".join(parts))


def get_verification_code(mail_key: str, email: str, timeout: int = 120) -> Optional[str]:
    metadata = get_email_token_metadata(mail_key)
    if metadata.get("provider") == IDATARIVER_PROVIDER:
        email_id = metadata.get("email_id") or metadata.get("id")
        if not email_id:
            return None
        return wait_for_idatariver_verification_code(email_id=email_id, timeout=timeout)

    return wait_for_verification_code(email=email or mail_key, timeout=timeout)


def wait_for_idatariver_verification_code(
    email_id: str,
    timeout: int = 120,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    client = session or _create_session()
    start = time.time()
    seen_message_ids = set()

    while time.time() - start < timeout:
        messages = fetch_idatariver_messages(email_id, session=client)
        for message in messages:
            if not isinstance(message, dict):
                continue

            code = extract_code_from_message(message)
            if code:
                print(f"[*] iDataRiver verification code received: {code}")
                return code

            message_id = _value_from_keys(message, ("id", "message_id", "mail_id", "mailId"))
            if message_id and message_id not in seen_message_ids:
                seen_message_ids.add(message_id)
                body = fetch_idatariver_message_body(message_id, session=client)
                code = extract_verification_code(body)
                if code:
                    print(f"[*] iDataRiver verification code received: {code}")
                    return code

        time.sleep(IDATARIVER_POLL_INTERVAL_SECONDS)

    return None


def wait_for_verification_code(
    email: str,
    timeout: int = 120,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    client = session or _create_session()
    start = time.time()
    check_time = 0
    seen_message_ids = set()

    while time.time() - start < timeout:
        messages, check_time = fetch_nimail_messages(email, check_time, session=client)
        for message in messages:
            if not isinstance(message, dict):
                continue

            code = extract_code_from_message(message)
            if code:
                print(f"[*] NiMail verification code received: {code}")
                return code

            message_id = message.get("id")
            if message_id and message_id not in seen_message_ids:
                seen_message_ids.add(message_id)
                body = fetch_nimail_message_body(email, str(message_id), session=client)
                code = extract_verification_code(body)
                if code:
                    print(f"[*] NiMail verification code received: {code}")
                    return code

        time.sleep(5)

    return None

def extract_verification_code(content: str) -> Optional[str]:
    if not content:
        return None

    subject_match = re.search(r"Subject:.*?(\d{6})", content, re.IGNORECASE)
    if subject_match and subject_match.group(1) != "177010":
        return subject_match.group(1)

    labeled_match = re.search(
        r"(?:verification code|your code|code is|验证码)[:\s]*([0-9]{6})",
        content,
        re.IGNORECASE,
    )
    if labeled_match and labeled_match.group(1) != "177010":
        return labeled_match.group(1)

    for code in re.findall(r">\s*(\d{6})\s*<", content):
        if code != "177010":
            return code

    for code in re.findall(r"(?<![&#\d])(\d{6})(?![&#\d])", content):
        if code != "177010":
            return code

    return None

def configure_from_runtime(config) -> None:
    global EMAIL_PROVIDER, IDATARIVER_API_KEY, IDATARIVER_API_BASE
    global IDATARIVER_POLL_INTERVAL_SECONDS, NIMAIL_API_BASE

    EMAIL_PROVIDER = str(config.email_provider or DEFAULT_EMAIL_PROVIDER).strip().lower()
    IDATARIVER_API_KEY = str(config.idatariver_api_key or "").strip()
    IDATARIVER_API_BASE = str(config.idatariver_api_base or IDATARIVER_API_BASE).rstrip("/")
    IDATARIVER_POLL_INTERVAL_SECONDS = float(config.idatariver_poll_interval_seconds)
    NIMAIL_API_BASE = str(config.nimail_api_base or NIMAIL_API_BASE).rstrip("/")
