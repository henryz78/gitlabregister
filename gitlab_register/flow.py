import argparse
import asyncio
import json
import os
import random
import re
import string
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from gitlab_register.email_providers import get_email_and_token, get_email_token_metadata, get_verification_code
except ImportError:
    get_email_and_token, get_verification_code = None, None
    get_email_token_metadata = None

from browser_proxy_pool import record_browser_proxy_result, select_browser_proxy
from gitlab_register.browser_runtime import launch_browser
from gitlab_register.outputs import safe_path_part


REGISTER_BUTTON_TEXTS = ("Continue", "Register", "Create account", "Sign up", "注册")
VERIFY_BUTTON_TEXTS = ("Verify", "Submit", "Continue", "验证", "提交")
ONBOARDING_CONTINUE_TEXTS = ("Continue",)
ONBOARDING_NEW_PROJECT_TEXT = "Create a new project"
ONBOARDING_COMPANY_TEXT = "My company or team"
COMPANY_TRIAL_CONTINUE_TEXTS = ("Continue with trial", "Continue")
DEFAULT_PROJECT_CREATE_TEXTS = ("Create project", "Create")
BROWSER_DEPS_COMMAND = "python -m playwright install-deps chromium"
REGISTRATION_STATUS_SUCCESS = "success"
REGISTRATION_STATUS_UNCLEAR = "unclear"
REGISTRATION_STATUS_ERROR = "error"
IDENTITY_VERIFICATION_STATUS = "identity_verification_required"
MAX_REGISTRATION_COUNT = 5
LOG_VERBOSE = False


def set_log_verbose(enabled):
    global LOG_VERBOSE
    LOG_VERBOSE = bool(enabled)
    try:
        from gitlab_register import email_providers

        email_providers.set_log_verbose(enabled)
    except Exception:
        pass


def user_log(message):
    print(message)


def debug_log(message):
    if LOG_VERBOSE:
        print(message)


RANDOM_FIRST_NAMES = (
    "Alex",
    "Jordan",
    "Taylor",
    "Morgan",
    "Casey",
    "Riley",
    "Avery",
    "Quinn",
    "Cameron",
    "Drew",
)


def parse_registration_count(value):
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(
            f"--count must be an integer from 1 to {MAX_REGISTRATION_COUNT}."
        ) from exc

    if count < 1 or count > MAX_REGISTRATION_COUNT:
        raise argparse.ArgumentTypeError(
            f"--count must be between 1 and {MAX_REGISTRATION_COUNT}."
        )
    return count


def validate_batch_options(count, email=None, username=None):
    if count <= 1:
        return
    if email:
        raise ValueError("--email can only be used when --count is 1.")
    if username:
        raise ValueError("--username can only be used when --count is 1.")


def screenshot_path(run_dir, filename):
    return str(Path(run_dir) / filename)


def artifact_path(run_dir, filename):
    return str(Path(run_dir) / filename)


async def maybe_screenshot(page, screenshot_dir, filename):
    if not screenshot_dir:
        return False
    await page.screenshot(
        path=screenshot_path(screenshot_dir, filename),
        full_page=True,
    )
    return True


RANDOM_LAST_NAMES = (
    "Parker",
    "Reed",
    "Hayes",
    "Brooks",
    "Miller",
    "Cooper",
    "Bennett",
    "Sullivan",
    "Foster",
    "Gray",
)
RANDOM_COMPANY_ADJECTIVES = (
    "Silver",
    "Bright",
    "North",
    "Clear",
    "Rapid",
    "Green",
    "Blue",
    "Prime",
    "Open",
    "Urban",
)
RANDOM_COMPANY_NOUNS = (
    "Harbor",
    "Bridge",
    "River",
    "Summit",
    "Signal",
    "Field",
    "Stone",
    "Vector",
    "Circuit",
    "Maple",
)
RANDOM_COMPANY_SUFFIXES = ("Labs", "Systems", "Studio", "Works")
REGISTER_BUTTON_SELECTORS = (
    'button[data-testid="new-user-register-button"]',
    '[data-testid="new-user-register-button"]',
    'button[type="submit"]',
    'input[type="submit"]',
    'input[type="button"]',
    'button',
    '[role="button"]',
)
VERIFY_BUTTON_SELECTORS = (
    'button[type="submit"]',
    'input[type="submit"]',
    'input[type="button"]',
    'button',
    '[role="button"]',
)
OTP_FIELD_SELECTOR = (
    'input[name="user[otp_attempt]"], '
    "#user_otp_attempt, "
    'input[autocomplete="one-time-code"], '
    'input[name*="verification" i], '
    "#verification_code, "
    'input[id*="verification" i], '
    'input[aria-label*="Verification code" i], '
    'input[placeholder*="Verification code" i]'
)


def browser_launch_error_help(error):
    message = str(error)
    shared_library_error = (
        "error while loading shared libraries" in message
        or "cannot open shared object file" in message
    )
    if not shared_library_error:
        return None

    library_match = re.search(r"loading shared libraries:\s*([^:]+):", message)
    lines = [
        "[!] CloakBrowser Chromium needs Linux system libraries.",
    ]
    if library_match:
        lines.append(f"    Missing library: {library_match.group(1)}")
    lines.extend(
        [
            "[*] Run this once in Codespaces/Linux:",
            f"    {BROWSER_DEPS_COMMAND}",
            "[*] Then run:",
            "    python register_gitlab.py",
        ]
    )
    return "\n".join(lines)


def email_proxy_error_help(error):
    message = str(error)
    socks_dependency_error = (
        "Missing dependencies for SOCKS support" in message
        or "No module named 'socks'" in message
        or 'No module named "socks"' in message
    )
    if not socks_dependency_error:
        return None

    return "\n".join(
        [
            "[!] The email API proxy uses SOCKS and needs PySocks.",
            "[*] Run:",
            "    python -m pip install -r requirements.txt",
            "[*] Or install the missing package directly:",
            "    python -m pip install PySocks",
            "[*] Then run:",
            "    python register_gitlab.py",
        ]
    )


def load_browser_proxy():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg.get("browser_proxy", "") or cfg.get("proxy", "") or ""
        except Exception:
            return ""
    return ""


def generate_random_password(length=14, exclude_words=None):
    exclude_words = exclude_words or []
    special = "!@#$%"
    digits = string.digits
    safe_bases = ["Secure", "Protect", "Shield", "Fortress", "Guard", "Castle", "Defend"]

    while True:
        base = random.choice(safe_bases)
        suffix = "".join(random.choices(digits, k=4)) + random.choice(special)
        password = f"{base}{suffix}"

        if all(
            not word or len(word) < 3 or word.lower() not in password.lower()
            for word in exclude_words
        ):
            return password


def generate_random_name(rng=None):
    chooser = rng or random
    return f"{chooser.choice(RANDOM_FIRST_NAMES)} {chooser.choice(RANDOM_LAST_NAMES)}"


def generate_random_company_name(rng=None):
    chooser = rng or random
    return " ".join(
        (
            chooser.choice(RANDOM_COMPANY_ADJECTIVES),
            chooser.choice(RANDOM_COMPANY_NOUNS),
            chooser.choice(RANDOM_COMPANY_SUFFIXES),
        )
    )


def get_clean_username(email):
    prefix = email.split("@")[0]
    clean = "".join(c for c in prefix if c.isalnum() or c == "_")
    return clean[:20]


async def type_value(page, selector, value, label):
    field = page.locator(selector).first
    await field.scroll_into_view_if_needed()
    await field.fill(value)
    debug_log(f"[*] 已填写: {label}")


def build_button_click_script(button_texts, preferred_selectors):
    labels = json.dumps(list(button_texts))
    selectors = json.dumps(list(preferred_selectors))
    return f"""
        () => {{
            const labels = {labels};
            const selectors = {selectors};
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const wanted = labels.map(normalize);
            const candidates = [];
            const seen = new Set();

            for (const selector of selectors) {{
                for (const element of Array.from(document.querySelectorAll(selector))) {{
                    if (!seen.has(element)) {{
                        seen.add(element);
                        candidates.push(element);
                    }}
                }}
            }}

            const isVisible = element => {{
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== "none"
                    && style.visibility !== "hidden"
                    && rect.width > 0
                    && rect.height > 0;
            }};
            const isUsable = element => !element.disabled
                && element.getAttribute("aria-disabled") !== "true"
                && isVisible(element);
            const labelFor = element => normalize(
                element.textContent
                || element.value
                || element.getAttribute("aria-label")
                || element.getAttribute("title")
            );

            const byLabel = candidates.find(element =>
                isUsable(element) && wanted.some(label => labelFor(element).includes(label))
            );
            const byPreferredSelector = candidates.find(element => isUsable(element));
            const button = byLabel || byPreferredSelector;

            if (button) {{
                button.scrollIntoView({{ block: "center", inline: "center" }});
                button.click();
                return true;
            }}
            return false;
        }}
    """


def build_register_button_click_script():
    return build_button_click_script(REGISTER_BUTTON_TEXTS, REGISTER_BUTTON_SELECTORS)


def build_verify_button_click_script():
    return build_button_click_script(VERIFY_BUTTON_TEXTS, VERIFY_BUTTON_SELECTORS)


def build_onboarding_fill_script():
    new_project_text = json.dumps(ONBOARDING_NEW_PROJECT_TEXT)
    company_text = json.dumps(ONBOARDING_COMPANY_TEXT)
    return f"""
        () => {{
            const newProjectText = {new_project_text};
            const companyText = {company_text};
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const isVisible = element => {{
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== "none"
                    && style.visibility !== "hidden"
                    && rect.width > 0
                    && rect.height > 0;
            }};
            const emitChange = element => {{
                element.dispatchEvent(new Event("input", {{ bubbles: true }}));
                element.dispatchEvent(new Event("change", {{ bubbles: true }}));
            }};
            const selects = Array.from(document.querySelectorAll("select")).filter(isVisible);
            const radios = Array.from(document.querySelectorAll('input[type="radio"]')).filter(isVisible);
            const pageText = normalize(document.body.innerText);
            const isOnboarding = pageText.includes("welcome to gitlab")
                && selects.length >= 2
                && radios.length >= 2;

            if (!isOnboarding) {{
                return {{ is_onboarding: false }};
            }}

            const chooseFirstRealOption = select => {{
                const options = Array.from(select.options || []);
                const chosen = options.find((option, index) =>
                    index > 0
                    && !option.disabled
                    && option.value
                    && !normalize(option.textContent).includes("please select")
                    && !normalize(option.textContent).includes("select a role")
                ) || options.find((option, index) => index > 0 && !option.disabled);

                if (!chosen) {{
                    return "";
                }}

                select.value = chosen.value;
                emitChange(select);
                return (chosen.textContent || chosen.value || "").trim();
            }};

            const selectedTexts = selects.slice(0, 2).map(chooseFirstRealOption);

            const radioText = input => {{
                const directLabel = input.closest("label");
                const forLabel = input.id
                    ? document.querySelector(`label[for="${{CSS.escape(input.id)}}"]`)
                    : null;
                const container = input.closest("label, div, li, fieldset") || input.parentElement;
                return normalize([
                    directLabel && directLabel.innerText,
                    forLabel && forLabel.innerText,
                    container && container.innerText,
                ].filter(Boolean).join(" "));
            }};

            const chooseRadio = labelText => {{
                const target = normalize(labelText);
                const input = radios.find(radio => radioText(radio).includes(target));
                if (!input) {{
                    return false;
                }}

                input.checked = true;
                input.click();
                emitChange(input);
                return true;
            }};

            return {{
                is_onboarding: true,
                selected_role: selectedTexts[0] || "",
                selected_reason: selectedTexts[1] || "",
                created_project: chooseRadio(newProjectText),
                company: chooseRadio(companyText),
            }};
        }}
    """


def build_default_project_detection_script():
    return """
        () => {
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const pageText = normalize(document.body.innerText);
            const path = window.location.pathname;
            const isDefaultProjectPage = path.includes("/users/sign_up/groups/new")
                || (
                    pageText.includes("create or import your first project")
                    && pageText.includes("group name")
                    && pageText.includes("project name")
                );

            if (!isDefaultProjectPage) {
                return { is_default_project_page: false };
            }

            const groupInput = document.querySelector(
                'input[name*="group" i], input[id*="group" i], input[aria-label*="Group name" i]'
            );
            const projectInput = document.querySelector(
                'input[name*="project" i], input[id*="project" i], input[aria-label*="Project name" i]'
            );

            return {
                is_default_project_page: true,
                group_name: groupInput ? groupInput.value || "" : "",
                project_name: projectInput ? projectInput.value || "" : "",
            };
        }
    """


def build_company_trial_fill_script(company_name):
    heading_text = json.dumps("Tell us about your company")
    company_label = json.dumps("Company name")
    country_label = json.dumps("Country or region")
    phone_label = json.dumps("Telephone number")
    company_value = json.dumps(company_name)
    return f"""
        () => {{
            const headingText = {heading_text};
            const companyLabel = {company_label};
            const countryLabel = {country_label};
            const phoneLabel = {phone_label};
            const companyValue = {company_value};
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const isVisible = element => {{
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return style.display !== "none"
                    && style.visibility !== "hidden"
                    && rect.width > 0
                    && rect.height > 0;
            }};
            const emitInput = element => {{
                element.dispatchEvent(new Event("input", {{ bubbles: true }}));
                element.dispatchEvent(new Event("change", {{ bubbles: true }}));
                element.dispatchEvent(new Event("blur", {{ bubbles: true }}));
            }};
            const setNativeValue = (element, value) => {{
                const prototype = Object.getPrototypeOf(element);
                const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");
                if (descriptor && descriptor.set) {{
                    descriptor.set.call(element, value);
                }} else {{
                    element.value = value;
                }}
            }};
            const pageText = normalize(document.body.innerText);
            const isCompanyTrial = pageText.includes(normalize(headingText))
                && pageText.includes(normalize(companyLabel))
                && pageText.includes(normalize(countryLabel));

            if (!isCompanyTrial) {{
                return {{ is_company_trial: false }};
            }}

            const visibleInputs = Array.from(document.querySelectorAll("input")).filter(isVisible);
            const visibleLabels = Array.from(document.querySelectorAll("label")).filter(isVisible);

            const inputByLabel = labelText => {{
                const target = normalize(labelText);
                const label = visibleLabels.find(candidate => normalize(candidate.innerText).includes(target));
                if (label) {{
                    if (label.htmlFor) {{
                        const direct = document.getElementById(label.htmlFor);
                        if (direct && isVisible(direct)) {{
                            return direct;
                        }}
                    }}
                    const nearby = label.parentElement && label.parentElement.querySelector("input");
                    if (nearby && isVisible(nearby)) {{
                        return nearby;
                    }}
                }}

                return visibleInputs.find(input =>
                    normalize(input.placeholder).includes(target)
                    || normalize(input.name).includes(target.replace(/\\s+/g, "_"))
                    || normalize(input.id).includes(target.replace(/\\s+/g, "_"))
                );
            }};

            const companyInput = inputByLabel(companyLabel)
                || visibleInputs.find(input => normalize(input.type) !== "tel");
            if (companyInput) {{
                setNativeValue(companyInput, companyValue);
                emitInput(companyInput);
            }}

            const phoneInput = inputByLabel(phoneLabel)
                || visibleInputs.find(input => normalize(input.type) === "tel");
            let phoneCleared = false;
            if (phoneInput) {{
                setNativeValue(phoneInput, "");
                emitInput(phoneInput);
                phoneCleared = true;
            }}

            return {{
                is_company_trial: true,
                company_name: companyInput ? companyValue : "",
                phone_cleared: phoneCleared,
            }};
        }}
    """


def build_identity_verification_detection_script():
    return """
        () => {
            const normalize = value => (value || "").replace(/\\s+/g, " ").trim().toLowerCase();
            const text = normalize(document.body.innerText);
            const securityHeading = text.includes("help us keep gitlab secure");
            const emailVerification = (
                text.includes("email verification")
                && text.includes("verification code")
            ) || text.includes("verify email address")
                || text.includes("we've sent a verification code")
                || text.includes("we have sent a verification code");
            const requiresPhone = text.includes("phone number verification")
                || text.includes("phone number");
            const acceptsCard = text.includes("credit card")
                || text.includes("verify with a credit card instead");
            const blocked = (securityHeading && (requiresPhone || acceptsCard))
                || (
                    text.includes("protecting your account")
                    && text.includes("phone number")
                    && text.includes("send code")
                );

            if (emailVerification && !requiresPhone && !acceptsCard) {
                return { blocked: false, reason: "", email_verification: true };
            }

            if (!blocked) {
                return { blocked: false, reason: "", email_verification: false };
            }

            let reason = "GitLab requires additional identity verification.";
            if (requiresPhone && acceptsCard) {
                reason = "GitLab requires phone number or credit card verification.";
            } else if (requiresPhone) {
                reason = "GitLab requires phone number verification.";
            } else if (acceptsCard) {
                reason = "GitLab accepts credit card verification on this page.";
            }

            return { blocked: true, reason };
        }
    """


def url_indicates_identity_verification(current_url):
    normalized = (current_url or "").lower()
    return "/users/identity_verification" in normalized


async def click_button_by_role(page, button_texts):
    for text in button_texts:
        for options in ({"name": text, "exact": True}, {"name": text}):
            try:
                button = page.get_by_role("button", **options).first
                if await button.count() > 0 and await button.is_visible():
                    await button.scroll_into_view_if_needed()
                    await button.click(timeout=5000)
                    debug_log(f"[*] 已点击按钮: {text}")
                    return True
            except Exception:
                continue
    return False


async def click_register_button(page):
    if await click_button_by_role(page, REGISTER_BUTTON_TEXTS):
        return True

    clicked = await page.evaluate(build_register_button_click_script())
    if clicked:
        debug_log("[*] 已通过脚本点击提交按钮")
    return bool(clicked)


async def click_verify_button(page):
    if await click_button_by_role(page, VERIFY_BUTTON_TEXTS):
        return True

    clicked = await page.evaluate(build_verify_button_click_script())
    if clicked:
        debug_log("[*] 已通过脚本点击验证码按钮")
    return bool(clicked)


async def signup_form_still_visible(page, password_selector):
    try:
        password_field = page.locator(password_selector).first
        if await password_field.count() == 0 or not await password_field.is_visible():
            return False

        continue_button = page.get_by_role("button", name="Continue", exact=True).first
        if await continue_button.count() == 0 or not await continue_button.is_visible():
            return False

        return True
    except Exception:
        return False


async def press_enter_if_signup_form_visible(page, password_selector):
    try:
        if not await signup_form_still_visible(page, password_selector):
            return False

        password_field = page.locator(password_selector).first
        await password_field.scroll_into_view_if_needed()
        await password_field.press("Enter")
        debug_log("[*] 页面仍停在注册表单，已按 Enter 兜底提交")
        return True
    except Exception:
        return False


async def submit_signup_form(page, password_selector, progress_checks=5, progress_interval_ms=1000):
    if not await click_register_button(page):
        return False

    debug_log("[+] 提交按钮已点击")
    for _ in range(progress_checks):
        await page.wait_for_timeout(progress_interval_ms)
        if not await signup_form_still_visible(page, password_selector):
            return True

    await press_enter_if_signup_form_visible(page, password_selector)
    return True


async def complete_gitlab_onboarding_if_present(page, headless, screenshot_dir):
    result = await page.evaluate(build_onboarding_fill_script())
    if not isinstance(result, dict) or not result.get("is_onboarding"):
        return False

    user_log("[*] 处理 GitLab 新手引导...")
    debug_log(f"[*] Selected role: {result.get('selected_role') or 'first available option'}")
    debug_log(f"[*] Selected signup reason: {result.get('selected_reason') or 'first available option'}")
    debug_log(f"[*] Selected onboarding action: {ONBOARDING_NEW_PROJECT_TEXT}")
    debug_log(f"[*] Selected GitLab usage: {ONBOARDING_COMPANY_TEXT}")

    await maybe_screenshot(page, screenshot_dir, "onboarding_form_filled.png")

    clicked = await click_button_by_role(page, ONBOARDING_CONTINUE_TEXTS)
    if not clicked:
        clicked = await page.evaluate(
            build_button_click_script(ONBOARDING_CONTINUE_TEXTS, VERIFY_BUTTON_SELECTORS)
        )
        if clicked:
            debug_log("[*] 已通过脚本点击继续按钮")

    if not clicked:
        print("[!] Onboarding Continue button not found.")
        return False

    try:
        await page.wait_for_url(
            lambda url: "sign_up/welcome" not in str(url),
            timeout=15000,
        )
    except Exception:
        await page.wait_for_timeout(3000)
    await page.wait_for_timeout(500)
    await maybe_screenshot(page, screenshot_dir, "onboarding_submitted.png")
    return True


async def complete_gitlab_default_project_if_present(page, headless, screenshot_dir):
    result = await page.evaluate(build_default_project_detection_script())
    if not isinstance(result, dict) or not result.get("is_default_project_page"):
        return False

    user_log("[*] 创建默认项目...")
    group_name = result.get("group_name") or "default"
    project_name = result.get("project_name") or "default"
    debug_log(f"[*] 使用默认 group: {group_name}")
    debug_log(f"[*] 使用默认 project: {project_name}")

    await maybe_screenshot(page, screenshot_dir, "default_project_form_ready.png")

    clicked = await click_button_by_role(page, DEFAULT_PROJECT_CREATE_TEXTS)
    if not clicked:
        clicked = await page.evaluate(
            build_button_click_script(DEFAULT_PROJECT_CREATE_TEXTS, VERIFY_BUTTON_SELECTORS)
        )
        if clicked:
            debug_log("[*] 已通过脚本点击继续按钮")

    if not clicked:
        print("[!] Default project create button not found.")
        return False

    try:
        await page.wait_for_url(
            lambda url: "sign_up/groups" not in str(url),
            timeout=15000,
        )
    except Exception:
        await page.wait_for_timeout(3000)
    await page.wait_for_timeout(500)
    await maybe_screenshot(page, screenshot_dir, "default_project_submitted.png")
    return True


async def select_country_via_playwright(page):
    try:
        toggle = page.locator(
            '[data-testid="base-dropdown-toggle"][aria-haspopup="listbox"], '
            '[data-testid="country-dropdown"] button'
        ).first
        if await toggle.count() == 0 or not await toggle.is_visible():
            return ""

        await toggle.click()

        items = page.locator(
            '[data-testid="base-dropdown-menu"] [role="option"], '
            '[data-testid="base-dropdown-menu"] ul li'
        )
        try:
            await items.first.wait_for(state="visible", timeout=5000)
        except Exception:
            return ""

        count = await items.count()
        if count == 0:
            return ""

        chosen = items.nth(random.randint(0, count - 1))
        text = (await chosen.text_content() or "").strip()
        await chosen.click()
        return text
    except Exception:
        return ""


async def fill_gitlab_company_trial_form(page, company_name):
    last_result = {}
    for attempt in range(6):
        result = await page.evaluate(build_company_trial_fill_script(company_name))
        if not isinstance(result, dict) or not result.get("is_company_trial"):
            return result

        selected_country = await select_country_via_playwright(page)
        last_result = {**result, "selected_country": selected_country}
        if result.get("company_name") and selected_country:
            return last_result

        if attempt < 5:
            await page.wait_for_timeout(1000)

    return last_result


async def complete_gitlab_company_trial_if_present(page, headless, screenshot_dir):
    company_name = generate_random_company_name()
    result = await fill_gitlab_company_trial_form(page, company_name)
    if not isinstance(result, dict) or not result.get("is_company_trial"):
        return False

    selected_country = result.get("selected_country") or ""
    user_log("[*] 填写公司试用信息...")
    debug_log(f"[*] 公司名称: {result.get('company_name') or company_name}")
    if selected_country:
        debug_log(f"[*] 已选国家: {selected_country}")
    debug_log("[*] 电话保持为空")

    if not result.get("company_name") or not selected_country:
        print("[!] Company trial form could not be completed.")
        await maybe_screenshot(page, screenshot_dir, "company_trial_fill_failed.png")
        return False

    await maybe_screenshot(page, screenshot_dir, "company_trial_form_filled.png")

    clicked = await click_button_by_role(page, COMPANY_TRIAL_CONTINUE_TEXTS)
    if not clicked:
        clicked = await page.evaluate(
            build_button_click_script(COMPANY_TRIAL_CONTINUE_TEXTS, VERIFY_BUTTON_SELECTORS)
        )
        if clicked:
            debug_log("[*] 已通过脚本点击试用继续按钮")

    if not clicked:
        print("[!] Company trial Continue button not found.")
        return False

    try:
        await page.wait_for_url(
            lambda url: "sign_up/company" not in str(url),
            timeout=15000,
        )
    except Exception:
        await page.wait_for_timeout(3000)
    await page.wait_for_timeout(500)
    await maybe_screenshot(page, screenshot_dir, "company_trial_submitted.png")
    return True


async def detect_identity_verification_block(page, headless, screenshot_dir):
    result = await page.evaluate(build_identity_verification_detection_script())
    if isinstance(result, dict) and result.get("email_verification"):
        return {"blocked": False, "reason": ""}

    if not isinstance(result, dict) or not result.get("blocked"):
        if not url_indicates_identity_verification(page.url):
            return {"blocked": False, "reason": ""}
        result = {
            "blocked": True,
            "reason": "GitLab redirected this signup to the identity verification page.",
        }

    reason = result.get("reason") or "GitLab requires additional identity verification."
    print("[!] GitLab identity verification is required.")
    print(f"[*] Reason: {reason}")
    print("[*] This account will be skipped in the success account list.")

    await maybe_screenshot(page, screenshot_dir, "identity_verification_required.png")

    return {"blocked": True, "reason": reason}


async def has_captcha(page):
    iframe_sources = await page.locator("iframe").evaluate_all(
        """
        frames => frames.map(frame => frame.getAttribute('src') || '')
        """
    )
    if any(
        "arkose" in src or "challenges.cloudflare.com" in src or "funcaptcha" in src
        for src in iframe_sources
    ):
        return True
    return await page.locator("#arkose_labs_container").count() > 0


async def wait_for_otp_field(page, headless, screenshot_dir):
    for attempt in range(12):
        locator = page.locator(OTP_FIELD_SELECTOR).first
        if await locator.count() > 0 and await locator.is_visible():
            return locator
        await page.wait_for_timeout(5000)
        await maybe_screenshot(page, screenshot_dir, f"waiting_otp_{attempt}.png")
    return None


def prepare_email(email):
    if email:
        print("[*] Custom email provided. Verification code will be entered in this terminal.")
        return email, None

    if not get_email_and_token:
        print("[!] email_register module not found and no email provided.")
        raise RuntimeError("email_register module not found and no email provided.")

    user_log("[*] 准备临时邮箱...")
    generated_email, mail_key = get_email_and_token()
    if not generated_email:
        print("[!] Failed to create temporary email.")
        raise RuntimeError("Failed to create temporary email.")
    return generated_email, mail_key


def save_registration_result(account_info, run_dir, filename):
    """Legacy helper kept for compatibility; new runs write accounts.json through BatchOutputs."""
    save_path = Path(artifact_path(run_dir, filename))
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(account_info, f, indent=4, ensure_ascii=False)
    print(f"[+] Registration data saved to {save_path.resolve()}")
    return save_path


def build_success_account_record(account_info):
    keys = (
        "email",
        "username",
        "password",
        "name",
        "timestamp",
        "email_provider",
        "email_id",
        "browser_proxy",
        "browser_proxy_mode",
        "namespace_id",
        "_gitlab_session",
    )
    return {key: account_info[key] for key in keys if key in account_info}


def namespace_id_from_url(final_url):
    query = parse_qs(urlparse(final_url or "").query)
    values = query.get("namespace_id") or []
    return values[0] if values else ""


def gitlab_session_from_cookies(cookies):
    for cookie in cookies or []:
        if cookie.get("name") == "_gitlab_session":
            return cookie.get("value") or ""
    return ""


def final_url_indicates_registration_success(final_url):
    normalized = (final_url or "").lower()
    if "gitlab.com" not in normalized:
        return False
    if "/users/sign_up/" in normalized:
        return False

    success_markers = (
        "/dashboard",
        "/projects",
        "/groups",
        "/-/profile",
        "/-/dashboard",
    )
    return any(marker in normalized for marker in success_markers)


async def register_gitlab_async(
    email=None,
    password=None,
    name=None,
    username=None,
    headless=True,
    screenshots=False,
    output_dir=None,
    verbose=False,
):
    set_log_verbose(verbose)
    browser_proxy_selection = select_browser_proxy()
    browser_proxy = browser_proxy_selection.proxy
    email, mail_key = prepare_email(email)
    email_metadata = get_email_token_metadata(mail_key) if mail_key and get_email_token_metadata else {}
    if not name:
        name = generate_random_name()
        debug_log(f"[*] 已生成姓名: {name}")

    if not username:
        username = f"{get_clean_username(email)}_{random.randint(1000, 9999)}"

    batch_output_dir = Path(output_dir) if output_dir else Path("registration_results") / time.strftime("run_%Y%m%d_%H%M%S")
    screenshot_dir = None
    if screenshots:
        screenshot_dir = batch_output_dir / "screenshots" / safe_path_part(username, default="account")
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    first_name = name.split()[0] if " " in name else name
    last_name = name.split()[1] if " " in name and len(name.split()) > 1 else "User"
    exclude_list = [first_name, last_name, username, email.split("@")[0]]

    if not password:
        password = generate_random_password(exclude_words=exclude_list)
        user_log("[*] 密码已生成，会保存到 accounts.json。")

    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    account_info_base = {
        "email": email,
        "username": username,
        "password": password,
        "name": name,
        "timestamp": timestamp,
    }
    if email_metadata.get("provider"):
        account_info_base["email_provider"] = email_metadata["provider"]
    if email_metadata.get("email_id"):
        account_info_base["email_id"] = email_metadata["email_id"]
    if browser_proxy:
        account_info_base["browser_proxy"] = browser_proxy
        account_info_base["browser_proxy_mode"] = browser_proxy_selection.mode

    user_log("[*] 开始注册 GitLab 账号...")
    user_log(f"    邮箱: {email}")
    user_log(f"    用户名: {username}")
    debug_log(f"    姓名: {first_name} {last_name}")
    debug_log(f"    密码: {'***'}")
    debug_log(f"    浏览器: {'Headless' if headless else 'Headed'}")
    debug_log(f"    输出目录: {os.path.abspath(batch_output_dir)}")
    if screenshot_dir:
        debug_log(f"    截图目录: {os.path.abspath(screenshot_dir)}")
    else:
        debug_log("    截图: 关闭")

    launch_args = {"headless": headless}
    if browser_proxy:
        launch_args["proxy"] = {"server": browser_proxy}
        debug_log(f"[*] 浏览器代理: {browser_proxy}")
    elif browser_proxy_selection.count:
        debug_log("[*] 代理池当前选择直连")

    browser = None
    context = None
    browser_proxy_recorded = False

    def record_browser_proxy_once(success, error=""):
        nonlocal browser_proxy_recorded
        if browser_proxy and not browser_proxy_recorded:
            record_browser_proxy_result(browser_proxy, success=success, error=error)
            browser_proxy_recorded = True

    try:
        user_log("[*] 启动浏览器...")
        browser = await launch_browser(**launch_args)
        context = await browser.new_context(viewport={"width": 1280, "height": 1024})
        page = await context.new_page()

        debug_log("[*] 打开 GitLab 注册页...")
        await page.goto("https://gitlab.com/users/sign_up")
        await page.wait_for_timeout(3000)

        await maybe_screenshot(page, screenshot_dir, "signup_page_loaded.png")

        first_name_selector = '#new_user_first_name, input[name="new_user[first_name]"], input[name="user[first_name]"]'
        last_name_selector = '#new_user_last_name, input[name="new_user[last_name]"], input[name="user[last_name]"]'
        username_selector = '#new_user_username, input[name="new_user[username]"], input[name="user[username]"]'
        email_selector = '#new_user_email, input[name="new_user[email]"], input[name="user[email]"]'
        password_selector = '#new_user_password, input[name="new_user[password]"], input[name="user[password]"]'

        if await page.locator(first_name_selector).count() == 0:
            print("[!] Could not locate signup fields.")
            await maybe_screenshot(page, screenshot_dir, "signup_fields_not_found.png")
            record_browser_proxy_once(False, "Could not locate signup fields.")
            return REGISTRATION_STATUS_ERROR

        await type_value(page, first_name_selector, first_name, "first name")
        await type_value(page, last_name_selector, last_name, "last name")
        await type_value(page, username_selector, username, "username")
        await type_value(page, email_selector, email, "email")
        await type_value(page, password_selector, password, "password")

        error_locator = page.locator(".invalid-feedback, .gl-field-error-anchored, .validation-error").first
        if await error_locator.count() > 0 and await error_locator.is_visible():
            err_text = await error_locator.text_content()
            print(f"[!] Validation error: {err_text}")
            if err_text and any(term in err_text.lower() for term in ("password", "phrase", "name")):
                print("[*] Re-generating a stronger password...")
                password = generate_random_password(exclude_words=exclude_list + ["Tian", "Dong"])
                account_info_base["password"] = password
                await type_value(page, password_selector, password, "password")

        accept_button = page.locator("#onetrust-accept-btn-handler, #btn-accept-all").first
        if await accept_button.count() > 0 and await accept_button.is_visible():
            await accept_button.click()
            debug_log("[*] 已关闭 Cookie 弹窗")
            await page.wait_for_timeout(1500)

        await maybe_screenshot(page, screenshot_dir, "signup_form_filled.png")

        if await has_captcha(page):
            print("[!] CAPTCHA verification detected.")
            await maybe_screenshot(page, screenshot_dir, "captcha_challenge.png")
            input(">>> Press Enter here once the CAPTCHA is solved to submit the form...")

        user_log("[*] 提交注册表单...")
        if not await submit_signup_form(page, password_selector):
            print("[!] Submit button not found.")

        await page.wait_for_timeout(6000)
        debug_log(f"[*] 当前 URL: {page.url}")
        await maybe_screenshot(page, screenshot_dir, "post_submit_status.png")

        identity_block = await detect_identity_verification_block(
            page,
            headless,
            screenshot_dir,
        )
        if identity_block["blocked"]:
            print("[*] Skipping email OTP because GitLab already requested identity verification.")
        else:
            otp_field = await wait_for_otp_field(page, headless, screenshot_dir)

        if identity_block["blocked"]:
            pass
        elif otp_field:
            user_log("[*] 已进入邮箱验证码步骤。")
            otp_code = None
            if mail_key:
                provider_name = email_metadata.get("provider") or "temporary email provider"
                user_log(f"[*] 正在从 {provider_name} 获取验证码...")
                otp_code = get_verification_code(mail_key, email, timeout=120)
                if otp_code:
                    user_log("[+] 验证码已获取。")
                else:
                    print("[!] Failed to get OTP code automatically.")

            if not otp_code:
                otp_code = input(f">>> Enter the 6-digit verification code sent to {email}: ").strip()

            await otp_field.fill(otp_code)
            await page.wait_for_timeout(1000)

            if await click_verify_button(page):
                debug_log("[+] 验证码按钮已点击")
            else:
                await page.keyboard.press("Enter")

            user_log("[*] 验证码已提交，等待跳转...")
            await page.wait_for_timeout(8000)
        else:
            print("[*] Verification code field not detected.")

        completed_post_signup_steps = []
        for _ in range(3):
            identity_block = await detect_identity_verification_block(
                page,
                headless,
                screenshot_dir,
            )
            if identity_block["blocked"]:
                break

            handled_step = False
            if await complete_gitlab_onboarding_if_present(page, headless, screenshot_dir):
                completed_post_signup_steps.append("onboarding")
                handled_step = True

            identity_block = await detect_identity_verification_block(
                page,
                headless,
                screenshot_dir,
            )
            if identity_block["blocked"]:
                break

            if await complete_gitlab_company_trial_if_present(page, headless, screenshot_dir):
                completed_post_signup_steps.append("company_trial")
                handled_step = True

            if await complete_gitlab_default_project_if_present(page, headless, screenshot_dir):
                completed_post_signup_steps.append("default_project")
                handled_step = True

            if not handled_step:
                break

        final_url = page.url
        debug_log(f"[*] 最终 URL: {final_url}")
        await maybe_screenshot(page, screenshot_dir, "registration_final_state.png")

        success = (
            not identity_block["blocked"]
            and final_url_indicates_registration_success(final_url)
        )

        account_info = {
            **account_info_base,
            "final_url": final_url,
            "completed_post_signup_steps": completed_post_signup_steps,
        }
        if screenshot_dir:
            account_info["screenshot_dir"] = os.path.abspath(screenshot_dir)

        if identity_block["blocked"]:
            account_info.update(
                {
                    "status": IDENTITY_VERIFICATION_STATUS,
                    "reason": identity_block["reason"],
                }
            )
            record_browser_proxy_once(False, IDENTITY_VERIFICATION_STATUS)
            return IDENTITY_VERIFICATION_STATUS
        elif success:
            account_info["namespace_id"] = namespace_id_from_url(final_url)
            try:
                account_info["_gitlab_session"] = gitlab_session_from_cookies(
                    await context.cookies()
                )
            except Exception as exc:
                account_info["_gitlab_session"] = ""
                print(f"[!] Could not read GitLab session cookie: {exc}")

            if account_info["namespace_id"]:
                debug_log(f"[*] Namespace ID: {account_info['namespace_id']}")
            if account_info["_gitlab_session"]:
                debug_log("[*] 已获取 GitLab session cookie")
            user_log("[+] 注册成功。")
            success_record = build_success_account_record(account_info)
            record_browser_proxy_once(True)
            return success_record
        else:
            account_info["status"] = REGISTRATION_STATUS_UNCLEAR
            record_browser_proxy_once(False, REGISTRATION_STATUS_UNCLEAR)
            if screenshot_dir:
                print("[-] Registration status unclear. Please check screenshots.")
            else:
                print("[-] Registration status unclear.")
            return REGISTRATION_STATUS_UNCLEAR
    except Exception as exc:
        print(f"[!] Error during registration: {exc}")
        for help_text in (email_proxy_error_help(exc), browser_launch_error_help(exc)):
            if help_text:
                print(help_text)
        error_info = {
            **account_info_base,
            "status": REGISTRATION_STATUS_ERROR,
            "error": str(exc),
        }
        record_browser_proxy_once(False, str(exc))
        return REGISTRATION_STATUS_ERROR
    finally:
        if context:
            await context.close()
        if browser:
            await browser.close()


async def register_one(*, config, outputs, email=None, password=None, name=None, username=None):
    outputs.record_attempt()
    result = await register_gitlab_async(
        email=email,
        password=password,
        name=name,
        username=username,
        headless=config.headless,
        screenshots=config.screenshots,
        output_dir=getattr(outputs, "output_dir", None),
        verbose=getattr(config, "log_verbose", False),
    )
    if isinstance(result, dict):
        outputs.add_success_account(result)
        return REGISTRATION_STATUS_SUCCESS
    return result


def create_batch_summary(count):
    return {
        "requested": count,
        "attempted": 0,
        REGISTRATION_STATUS_SUCCESS: 0,
        IDENTITY_VERIFICATION_STATUS: 0,
        REGISTRATION_STATUS_UNCLEAR: 0,
        REGISTRATION_STATUS_ERROR: 0,
    }


def normalize_registration_status(status):
    if isinstance(status, dict):
        return REGISTRATION_STATUS_SUCCESS

    known_statuses = {
        REGISTRATION_STATUS_SUCCESS,
        IDENTITY_VERIFICATION_STATUS,
        REGISTRATION_STATUS_UNCLEAR,
        REGISTRATION_STATUS_ERROR,
    }
    if status in known_statuses:
        return status
    return REGISTRATION_STATUS_ERROR


def print_batch_summary(summary):
    print("[*] Batch summary:")
    print(f"    Requested: {summary['requested']}")
    print(f"    Attempted: {summary['attempted']}")
    print(f"    Success: {summary[REGISTRATION_STATUS_SUCCESS]}")
    print(f"    Identity verification required: {summary[IDENTITY_VERIFICATION_STATUS]}")
    print(f"    Unclear: {summary[REGISTRATION_STATUS_UNCLEAR]}")
    print(f"    Error: {summary[REGISTRATION_STATUS_ERROR]}")


async def register_gitlab_batch_async(
    count,
    email=None,
    password=None,
    name=None,
    username=None,
    headless=True,
    screenshots=False,
    register_once=None,
    verbose=False,
):
    count = parse_registration_count(count)
    validate_batch_options(count, email=email, username=username)
    register_once = register_once or register_gitlab_async
    summary = create_batch_summary(count)

    for index in range(1, count + 1):
        print("")
        print(f"[*] Starting serial registration {index}/{count}...")
        try:
            status = await register_once(
                email=email,
                password=password,
                name=name,
                username=username,
                headless=headless,
                screenshots=screenshots,
                verbose=verbose,
            )
        except Exception as exc:
            print(f"[!] Serial registration {index}/{count} error: {exc}")
            status = REGISTRATION_STATUS_ERROR
        status = normalize_registration_status(status)
        summary["attempted"] += 1
        summary[status] += 1
        print(f"[*] Serial registration {index}/{count} status: {status}")

        if status == IDENTITY_VERIFICATION_STATUS:
            print("[!] Stopping serial registration because GitLab requested identity verification.")
            break

    print_batch_summary(summary)
    return summary


def register_gitlab(
    email=None,
    password=None,
    name=None,
    username=None,
    headless=True,
    screenshots=False,
    count=1,
    verbose=False,
):
    count = parse_registration_count(count)
    validate_batch_options(count, email=email, username=username)

    if count == 1:
        return asyncio.run(
            register_gitlab_async(
                email,
                password,
                name,
                username,
                headless=headless,
                screenshots=screenshots,
                verbose=verbose,
            )
        )

    return asyncio.run(
        register_gitlab_batch_async(
            count,
            email=email,
            password=password,
            name=name,
            username=username,
            headless=headless,
            screenshots=screenshots,
            verbose=verbose,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitLab Account Registration Tool")
    parser.add_argument("--email", default=None, help="Email address to register with (omitted to use NiMail API)")
    parser.add_argument("--password", default=None, help="Password (optional, auto-generated if omitted)")
    parser.add_argument("--name", default=None, help="Profile name (optional, auto-generated if omitted)")
    parser.add_argument("--username", default=None, help="Username (optional, auto-generated from email if omitted)")
    parser.add_argument("--headed", action="store_true", help="Launch headed browser (default is headless)")
    parser.add_argument("--verbose", action="store_true", help="Print verbose logs")
    parser.add_argument(
        "--screenshots",
        action="store_true",
        help="Save step screenshots inside each registration result directory",
    )
    parser.add_argument(
        "--count",
        type=parse_registration_count,
        default=1,
        help=f"Number of serial registrations to run, 1-{MAX_REGISTRATION_COUNT} (default: 1)",
    )

    args = parser.parse_args()
    try:
        validate_batch_options(args.count, email=args.email, username=args.username)
    except ValueError as exc:
        parser.error(str(exc))

    register_gitlab(
        args.email,
        args.password,
        args.name,
        args.username,
        headless=not args.headed,
        screenshots=args.screenshots,
        count=args.count,
        verbose=args.verbose,
    )
