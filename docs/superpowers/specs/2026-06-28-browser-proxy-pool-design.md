# Browser Proxy Pool Design

## Goal

Add a lightweight browser proxy pool for GitLab registration. The pool is used only for browser traffic. Email APIs keep using the existing `proxy` setting.

## Configuration

Existing field:

- `proxy`: email API proxy. iDataRiver and other email providers continue to use this value.

Browser proxy pool fields:

- `browser_proxy_mode`: one of `single`, `text`, `url`.
- `browser_proxy`: single browser proxy for `single` mode.
- `browser_proxy_list_text`: newline or comma separated proxy list for `text` mode.
- `browser_proxy_url`: HTTP/HTTPS URL returning a plain text proxy list for `url` mode.
- `browser_proxy_refresh_interval_seconds`: minimum seconds between URL refreshes.

Supported proxy schemes:

- `http://`
- `https://`
- `socks5://`
- `socks5h://`

The current `browser_proxy` field remains valid. Existing configs behave as `browser_proxy_mode = "single"`.

## Runtime Behavior

Before each registration attempt:

1. Load browser proxy pool settings.
2. Pick one browser proxy.
3. Pass that proxy to `cloakbrowser.launch_async`.
4. Record the proxy used in the current result JSON.
5. Record success or failure for that proxy.

Email verification calls continue through the existing email provider code and the existing `proxy` field.

## Selection Rules

The lightweight pool uses simple scoring:

- Successful proxy: score increases.
- Network failure or browser launch failure: score decreases.
- Proxy in cooldown is skipped while other available proxies exist.
- If every proxy is cooling down, the pool picks the least-bad proxy so a run can still continue.

The pool rotates through available proxies while favoring proxies with better scores.

## Cooldown Rules

Hard connection errors trigger a longer cooldown:

- SOCKS handshake failure
- Proxy connection failure
- Proxy closed connection
- Network timeout

Other registration failures trigger a short cooldown or no cooldown depending on the error text. Identity verification, unclear signup status, and GitLab form changes are recorded as account-flow outcomes rather than hard proxy failures.

## State File

Proxy state is stored in:

```text
data/browser_proxy_state.json
```

The file stores:

- proxy URL
- score
- success count
- failure count
- last error
- last selected time
- cooldown until timestamp

The state file is local runtime state and should be ignored by Git.

## Out Of Scope

- Changing the email API proxy behavior.
- Adding concurrent browser sessions.
- Adding CAPTCHA solving.
- Changing CloakBrowser subscription or license handling.
- Adding browser fingerprint controls beyond the existing CloakBrowser defaults.
