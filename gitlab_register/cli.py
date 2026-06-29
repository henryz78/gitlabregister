from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Awaitable, Callable

from gitlab_register.config import apply_cli_overrides, load_config, safe_run_label
from gitlab_register.outputs import BatchOutputs, create_batch_outputs

RegisterOne = Callable[..., Awaitable[str]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitLab Account Registration Tool")
    parser.add_argument("--email", default=None, help="Email address to register with")
    parser.add_argument("--password", default=None, help="Password, auto-generated when omitted")
    parser.add_argument("--name", default=None, help="Profile name, auto-generated when omitted")
    parser.add_argument("--username", default=None, help="Username, auto-generated when omitted")
    parser.add_argument("--headed", action="store_true", help="Launch headed browser")
    parser.add_argument("--screenshots", action="store_true", help="Save step screenshots")
    parser.add_argument("--verbose", action="store_true", help="Print verbose logs")
    parser.add_argument("--count", type=int, default=None, help="Number of serial registrations")
    parser.add_argument("--run-label", default=None, help="Output batch label")
    parser.add_argument("--output-dir", default=None, help="Exact output directory")
    return parser


def resolve_output_dir(config) -> Path:
    if config.output_dir:
        return Path(config.output_dir)
    return Path(config.output_root) / safe_run_label(config.run_label)


async def default_register_one(**kwargs: Any) -> str:
    from gitlab_register.flow import register_one

    return await register_one(**kwargs)


def configure_runtime_email(config) -> None:
    from gitlab_register.email_providers import configure_from_runtime

    configure_from_runtime(config)


async def run_async(
    args: argparse.Namespace,
    *,
    register_one: RegisterOne = default_register_one,
    env_path: str | Path = ".env",
) -> int:
    config = load_config(env_path=env_path)
    config = apply_cli_overrides(
        config,
        count=args.count,
        run_label=args.run_label,
        output_dir=args.output_dir,
        headed=args.headed,
        screenshots=args.screenshots,
        verbose=args.verbose,
    )
    if register_one is default_register_one:
        configure_runtime_email(config)

    outputs: BatchOutputs = create_batch_outputs(output_dir=resolve_output_dir(config))

    try:
        for _ in range(config.count):
            before_attempted = outputs.attempted
            try:
                await register_one(
                    config=config,
                    outputs=outputs,
                    email=args.email,
                    password=args.password,
                    name=args.name,
                    username=args.username,
                )
            except SystemExit as exc:
                if outputs.attempted == before_attempted:
                    outputs.record_attempt()
                print(f"[!] Registration exited early: {exc}")
            except Exception as exc:
                if outputs.attempted == before_attempted:
                    outputs.record_attempt()
                print(f"[!] Registration failed: {exc}")
    finally:
        outputs.write_accounts()
        outputs.write_summary(requested=config.count)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    register_one: RegisterOne = default_register_one,
    env_path: str | Path = ".env",
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_async(args, register_one=register_one, env_path=env_path))


if __name__ == "__main__":
    raise SystemExit(main())
