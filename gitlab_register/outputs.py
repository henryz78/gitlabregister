from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def safe_path_part(value: str | None, default: str = "item") -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-")
    return text or default


@dataclass
class BatchOutputs:
    output_dir: Path
    accounts: list[dict[str, Any]] = field(default_factory=list)
    attempted: int = 0

    def __post_init__(self) -> None:
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @property
    def accounts_path(self) -> Path:
        return self.output_dir / "accounts.json"

    @property
    def summary_path(self) -> Path:
        return self.output_dir / "summary.json"

    def record_attempt(self) -> None:
        self.attempted += 1

    def add_success_account(self, account: dict[str, Any]) -> None:
        self.accounts.append(dict(account))

    def write_accounts(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.accounts_path.write_text(
            json.dumps(self.accounts, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.accounts_path

    def write_summary(self, requested: int) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "requested": int(requested),
            "attempted": self.attempted,
            "success": len(self.accounts),
            "output_dir": str(self.output_dir),
            "accounts_file": str(self.accounts_path),
        }
        self.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.summary_path

    def screenshot_dir(self, username: str | None, *, enabled: bool) -> Path | None:
        if not enabled:
            return None
        path = self.output_dir / "screenshots" / safe_path_part(username, default="account")
        path.mkdir(parents=True, exist_ok=True)
        return path


def create_batch_outputs(*, output_dir: str | Path) -> BatchOutputs:
    return BatchOutputs(output_dir=Path(output_dir))
