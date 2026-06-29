from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
CONFIG_EXAMPLE_PATH = ROOT / "config.example.json"
DATA_DIR = ROOT / "data"
DEFAULT_STATE_PATH = DATA_DIR / "browser_proxy_state.json"
SUPPORTED_PROXY_SCHEMES = {"http", "https", "socks5", "socks5h"}
SUPPORTED_SOURCE_SCHEMES = {"http", "https"}
PROXY_MODES = {"single", "text", "url"}
DEFAULT_REFRESH_INTERVAL_SECONDS = 120
SOFT_COOLDOWN_SECONDS = 15 * 60
HARD_COOLDOWN_SECONDS = 24 * 60 * 60
PROXY_SOURCE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/plain,*/*",
}


@dataclass(frozen=True)
class BrowserProxyConfig:
    mode: str
    single_proxy: str
    list_text: str
    source_url: str
    refresh_interval_seconds: int


@dataclass(frozen=True)
class BrowserProxySelection:
    proxy: str
    mode: str
    count: int
    index: int
    reason: str
    last_error: str = ""


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_proxy_url(value: Any) -> str:
    proxy = str(value or "").strip()
    if not proxy:
        return ""
    parsed = urlparse(proxy)
    if parsed.scheme in SUPPORTED_PROXY_SCHEMES and parsed.netloc:
        return proxy
    return ""


def parse_proxy_lines(text: Any) -> List[str]:
    proxies: List[str] = []
    seen = set()
    for raw_line in str(text or "").replace(",", "\n").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("//"):
            continue
        proxy = normalize_proxy_url(line)
        if proxy and proxy not in seen:
            seen.add(proxy)
            proxies.append(proxy)
    return proxies


def normalize_browser_proxy_config(config: Dict[str, Any]) -> BrowserProxyConfig:
    mode = str(config.get("browser_proxy_mode") or "").strip().lower()
    if mode not in PROXY_MODES:
        if str(config.get("browser_proxy_url") or "").strip():
            mode = "url"
        elif str(config.get("browser_proxy_list_text") or "").strip():
            mode = "text"
        else:
            mode = "single"
    refresh = max(
        10,
        _safe_int(
            config.get("browser_proxy_refresh_interval_seconds"),
            DEFAULT_REFRESH_INTERVAL_SECONDS,
        ),
    )
    return BrowserProxyConfig(
        mode=mode,
        single_proxy=normalize_proxy_url(config.get("browser_proxy")),
        list_text=str(config.get("browser_proxy_list_text") or ""),
        source_url=str(config.get("browser_proxy_url") or "").strip(),
        refresh_interval_seconds=refresh,
    )


def _empty_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "updated_at": 0.0,
        "next_index": 0,
        "last_fetch": 0.0,
        "last_error": "",
        "fetched_proxies": [],
        "proxies": {},
    }


def classify_proxy_error(error: Any) -> str:
    text = str(error or "").lower()
    if "err_socks" in text or ("socks" in text and "failed" in text):
        return "hard"
    if "proxy" in text and ("closed" in text or "connect" in text or "failed" in text):
        return "hard"
    if "timeout" in text or "timed out" in text:
        return "hard"
    if "identity_verification" in text or "unclear" in text:
        return "neutral"
    return "soft"


class BrowserProxyPool:
    def __init__(self, state_path: Path = DEFAULT_STATE_PATH) -> None:
        self.state_path = state_path
        self.config = BrowserProxyConfig("single", "", "", "", DEFAULT_REFRESH_INTERVAL_SECONDS)
        self.state = self._load_state()

    def configure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        self.config = normalize_browser_proxy_config(config)
        if self.config.mode in {"single", "text"}:
            self.state["last_error"] = ""
        return self.snapshot()

    def current_proxy_list(self) -> List[str]:
        if self.config.mode == "single":
            proxies = [self.config.single_proxy] if self.config.single_proxy else []
            return [proxy for proxy in proxies if not self._is_proxy_disabled(proxy)]
        if self.config.mode == "text":
            return [
                proxy
                for proxy in parse_proxy_lines(self.config.list_text)
                if not self._is_proxy_disabled(proxy)
            ]
        return [
            proxy
            for proxy in self.state.get("fetched_proxies", [])
            if normalize_proxy_url(proxy)
            and not self._is_proxy_disabled(proxy)
        ]

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        if self.config.mode != "url":
            return self.snapshot()
        now = time.time()
        last_fetch = float(self.state.get("last_fetch") or 0.0)
        if (
            not force
            and last_fetch
            and now - last_fetch < self.config.refresh_interval_seconds
        ):
            return self.snapshot()
        parsed = urlparse(self.config.source_url)
        if parsed.scheme not in SUPPORTED_SOURCE_SCHEMES or not parsed.netloc:
            self.state["last_error"] = "browser_proxy_url must be a valid HTTP or HTTPS URL"
            self._save_state()
            return self.snapshot()
        try:
            request = urllib.request.Request(
                self.config.source_url,
                headers=PROXY_SOURCE_HEADERS,
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                text = response.read().decode("utf-8", errors="replace")
            self.state["fetched_proxies"] = parse_proxy_lines(text)
            self.state["last_fetch"] = now
            self.state["last_error"] = (
                "" if self.state["fetched_proxies"] else "proxy URL returned no valid proxies"
            )
        except Exception as exc:
            self.state["last_error"] = f"failed to fetch browser proxy URL: {exc}"
        self._save_state()
        return self.snapshot()

    def next_proxy(self) -> BrowserProxySelection:
        if self.config.mode == "url":
            self.refresh(force=False)
        proxies = self.current_proxy_list()
        if not proxies:
            return BrowserProxySelection(
                "",
                self.config.mode,
                0,
                -1,
                "direct",
                self.state.get("last_error", ""),
            )
        now = time.time()
        proxy_states = self.state.setdefault("proxies", {})
        start = int(self.state.get("next_index") or 0) % len(proxies)
        available = []
        cooling = []
        for offset in range(len(proxies)):
            index = (start + offset) % len(proxies)
            proxy = proxies[index]
            item = proxy_states.get(proxy, {})
            cooldown_until = float(item.get("cooldown_until") or 0.0)
            if cooldown_until > now:
                cooling.append((cooldown_until, -float(item.get("score") or 0.0), index, proxy))
            else:
                available.append((index, proxy))
        if available:
            index, proxy = available[0]
            reason = "selected"
        else:
            _cooldown_until, _score, index, proxy = min(cooling)
            reason = "fallback_cooling"
        self.state["next_index"] = (index + 1) % len(proxies)
        item = proxy_states.setdefault(proxy, {})
        item["last_selected_at"] = now
        item.setdefault("score", 0.0)
        self._save_state()
        return BrowserProxySelection(
            proxy,
            self.config.mode,
            len(proxies),
            index,
            reason,
            self.state.get("last_error", ""),
        )

    def record_result(self, proxy: str, success: bool, error: Any = "") -> Dict[str, Any]:
        proxy = normalize_proxy_url(proxy)
        if not proxy:
            return {"bucket": "direct", "cooldown_seconds": 0}
        now = time.time()
        proxy_states = self.state.setdefault("proxies", {})
        item = proxy_states.setdefault(proxy, {"score": 0.0})
        item["last_seen"] = now
        if success:
            item["success_count"] = int(item.get("success_count") or 0) + 1
            item["score"] = round(float(item.get("score") or 0.0) + 3.0, 3)
            item["cooldown_until"] = 0.0
            item["last_error"] = ""
            bucket = "success"
            cooldown_seconds = 0
        else:
            bucket = classify_proxy_error(error)
            item["failure_count"] = int(item.get("failure_count") or 0) + 1
            item["last_error"] = str(error or "")[:500]
            if bucket == "hard":
                item["disabled_until"] = now + HARD_COOLDOWN_SECONDS
                self._remove_proxy_from_active_source(proxy)
                item["score"] = round(float(item.get("score") or 0.0) - 5.0, 3)
                cooldown_seconds = HARD_COOLDOWN_SECONDS
            elif bucket == "soft":
                item["score"] = round(float(item.get("score") or 0.0) - 1.0, 3)
                cooldown_seconds = SOFT_COOLDOWN_SECONDS
            else:
                cooldown_seconds = 0
            if cooldown_seconds:
                item["cooldown_until"] = now + cooldown_seconds
        self._save_state()
        return {"bucket": bucket, "cooldown_seconds": cooldown_seconds}

    def _is_proxy_disabled(self, proxy: str) -> bool:
        item = self.state.get("proxies", {}).get(proxy, {})
        return float(item.get("disabled_until") or 0.0) > time.time()

    def _remove_proxy_from_active_source(self, proxy: str) -> None:
        if self.config.mode == "text":
            proxies = [
                item
                for item in parse_proxy_lines(self.config.list_text)
                if item != proxy
            ]
            self.config = BrowserProxyConfig(
                self.config.mode,
                self.config.single_proxy,
                "\n".join(proxies),
                self.config.source_url,
                self.config.refresh_interval_seconds,
            )
        elif self.config.mode == "url":
            self.state["fetched_proxies"] = [
                item
                for item in self.state.get("fetched_proxies", [])
                if normalize_proxy_url(item) != proxy
            ]

    def reset_state(self) -> Dict[str, Any]:
        removed = len(self.state.get("proxies", {}))
        fetched = list(self.state.get("fetched_proxies", []))
        self.state = _empty_state()
        self.state["fetched_proxies"] = fetched
        self._save_state()
        return {"removed": removed, **self.snapshot()}

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        proxies = self.current_proxy_list()
        proxy_states = self.state.get("proxies", {})
        visible = []
        cooling_count = 0
        for proxy in proxies:
            item = proxy_states.get(proxy, {})
            cooldown_until = float(item.get("cooldown_until") or 0.0)
            if cooldown_until > now:
                cooling_count += 1
            visible.append(
                {
                    "proxy": proxy,
                    "score": float(item.get("score") or 0.0),
                    "success_count": int(item.get("success_count") or 0),
                    "failure_count": int(item.get("failure_count") or 0),
                    "cooldown_until": cooldown_until,
                    "last_error": item.get("last_error", ""),
                }
            )
        return {
            "mode": self.config.mode,
            "count": len(proxies),
            "cooling_count": cooling_count,
            "last_fetch": float(self.state.get("last_fetch") or 0.0),
            "last_error": self.state.get("last_error", ""),
            "proxies": visible,
        }

    def _load_state(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else _empty_state()
        except Exception:
            return _empty_state()

    def _save_state(self) -> None:
        self.state["updated_at"] = time.time()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.state_path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(self.state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temp.replace(self.state_path)


def load_json_config(
    config_path: Path = CONFIG_PATH,
    example_path: Path = CONFIG_EXAMPLE_PATH,
) -> Dict[str, Any]:
    path = config_path if config_path.exists() else example_path
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


DEFAULT_POOL = BrowserProxyPool()


def configure_default_pool(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return DEFAULT_POOL.configure(config or load_json_config())


def select_browser_proxy(config: Optional[Dict[str, Any]] = None) -> BrowserProxySelection:
    DEFAULT_POOL.configure(config or load_json_config())
    return DEFAULT_POOL.next_proxy()


def record_browser_proxy_result(
    proxy: str,
    success: bool,
    error: Any = "",
) -> Dict[str, Any]:
    return DEFAULT_POOL.record_result(proxy, success=success, error=error)
