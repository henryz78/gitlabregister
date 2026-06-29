from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _chrome_version_key(path: Path) -> tuple[tuple[int, ...], str]:
    version_parts = tuple(int(part) for part in re.findall(r"\d+", path.parent.name))
    return version_parts, path.parent.name


def _latest_chrome() -> Path | None:
    root = Path.home() / ".cloakbrowser"
    paths = sorted(root.glob("chromium-*/chrome"), key=_chrome_version_key)
    return paths[-1] if paths else None


def find_chrome() -> str:
    chrome = _latest_chrome()
    if chrome:
        return str(chrome)

    try:
        subprocess.check_call([sys.executable, "-m", "cloakbrowser", "install"])
    except Exception as exc:
        raise RuntimeError(
            "CloakBrowser Chromium ????????????: "
            ".venv/bin/python -m cloakbrowser install"
        ) from exc

    chrome = _latest_chrome()
    if chrome:
        return str(chrome)

    raise RuntimeError(
        "CloakBrowser Chromium ?????????????: "
        ".venv/bin/python -m cloakbrowser install"
    )


async def launch_browser(**kwargs: Any) -> Any:
    from cloakbrowser import launch_async

    return await launch_async(**kwargs)
