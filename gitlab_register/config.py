from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency during tests
    load_dotenv = None


@dataclass(frozen=True)
class RuntimeConfig:
    email_provider: str = "idatariver"
    idatariver_api_key: str = ""
    idatariver_api_base: str = "https://apiok.us/api/cbea"
    idatariver_poll_interval_seconds: float = 5.0
    nimail_api_base: str = "https://www.nimail.cn"
    count: int = 1
    run_label: str = ""
    output_root: str = "registration_results"
    output_dir: str = ""
    headless: bool = True
    screenshots: bool = False
    log_verbose: bool = False


def _load_env_file_fallback(path: Path) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def env_bool(value: str | None, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def env_int(value: str | None, default: int) -> int:
    try:
        return int(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def env_float(value: str | None, default: float) -> float:
    try:
        return float(str(value or "").strip())
    except (TypeError, ValueError):
        return default


def make_run_label(now: float | None = None, pid: int | None = None) -> str:
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now or time.time()))
    return f"run_{stamp}_{pid or os.getpid()}"


def safe_run_label(label: str | None = None) -> str:
    text = str(label or "").strip()
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text or make_run_label()


def load_config(env_path: str | os.PathLike = ".env") -> RuntimeConfig:
    path = Path(env_path)
    if path.exists():
        if load_dotenv is not None:
            load_dotenv(path, override=False)
        else:
            _load_env_file_fallback(path)

    return RuntimeConfig(
        email_provider=(os.environ.get("EMAIL_PROVIDER") or "idatariver").strip().lower(),
        idatariver_api_key=(os.environ.get("IDATARIVER_API_KEY") or "").strip(),
        idatariver_api_base=(os.environ.get("IDATARIVER_API_BASE") or "https://apiok.us/api/cbea").strip().rstrip("/"),
        idatariver_poll_interval_seconds=env_float(os.environ.get("IDATARIVER_POLL_INTERVAL_SECONDS"), 5.0),
        nimail_api_base=(os.environ.get("NIMAIL_API_BASE") or "https://www.nimail.cn").strip().rstrip("/"),
        count=max(1, env_int(os.environ.get("COUNT"), 1)),
        run_label=(os.environ.get("RUN_LABEL") or "").strip(),
        output_root=(os.environ.get("OUTPUT_ROOT") or "registration_results").strip() or "registration_results",
        output_dir=(os.environ.get("OUTPUT_DIR") or "").strip(),
        headless=env_bool(os.environ.get("HEADLESS"), True),
        screenshots=env_bool(os.environ.get("SCREENSHOTS"), False),
        log_verbose=env_bool(os.environ.get("LOG_VERBOSE"), False),
    )


def apply_cli_overrides(
    config: RuntimeConfig,
    *,
    count: int | None = None,
    run_label: str | None = None,
    output_dir: str | None = None,
    headed: bool = False,
    screenshots: bool = False,
    verbose: bool = False,
) -> RuntimeConfig:
    updates = {}
    if count is not None:
        updates["count"] = max(1, int(count))
    if run_label:
        updates["run_label"] = str(run_label).strip()
    if output_dir:
        updates["output_dir"] = str(output_dir).strip()
    if headed:
        updates["headless"] = False
    if screenshots:
        updates["screenshots"] = True
    if verbose:
        updates["log_verbose"] = True
    return replace(config, **updates)
