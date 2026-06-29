from __future__ import annotations

from typing import Callable


def mask_secret(value: str | None) -> str:
    text = str(value or "")
    if len(text) <= 8:
        return "***" if text else ""
    return f"{text[:4]}***{text[-4:]}"


def status_line(*, attempted: int, requested: int, success: int, elapsed_seconds: float) -> str:
    elapsed = int(elapsed_seconds)
    return f"进度 {attempted}/{requested} | 成功 {success} | 耗时 {elapsed}s"


def log(message: str, *, output_func: Callable[[str], None] = print) -> None:
    output_func(message)


def verbose_log(message: str, *, enabled: bool = False, output_func: Callable[[str], None] = print) -> None:
    if enabled:
        output_func(message)
