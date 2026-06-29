from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class EnvField:
    group: str
    key: str
    default: str
    prompt: str


CONFIG_FIELDS: tuple[EnvField, ...] = (
    EnvField("邮箱服务", "EMAIL_PROVIDER", "idatariver", "邮箱服务 idatariver/nimail"),
    EnvField("邮箱服务", "IDATARIVER_API_KEY", "", "iDataRiver API key"),
    EnvField("邮箱服务", "IDATARIVER_API_BASE", "https://apiok.us/api/cbea", "iDataRiver API 地址"),
    EnvField("邮箱服务", "IDATARIVER_POLL_INTERVAL_SECONDS", "5", "iDataRiver 轮询间隔秒"),
    EnvField("邮箱服务", "NIMAIL_API_BASE", "https://www.nimail.cn", "NiMail API 地址"),
    EnvField("运行目标", "COUNT", "1", "串行注册数量"),
    EnvField("输出批次", "RUN_LABEL", "", "本次运行批次名，留空自动生成"),
    EnvField("输出批次", "OUTPUT_ROOT", "registration_results", "批次输出根目录"),
    EnvField("输出批次", "OUTPUT_DIR", "", "指定完整输出目录，留空使用 OUTPUT_ROOT/RUN_LABEL"),
    EnvField("浏览器和日志", "HEADLESS", "1", "1=无头浏览器，0=显示浏览器窗口"),
    EnvField("浏览器和日志", "SCREENSHOTS", "0", "1=保存关键步骤截图"),
    EnvField("浏览器和日志", "LOG_VERBOSE", "0", "1=显示详细日志"),
)


def should_ask_field(field: EnvField, values: dict[str, str]) -> bool:
    provider = (values.get("EMAIL_PROVIDER") or "").strip().lower()
    if field.key.startswith("IDATARIVER_"):
        return provider == "idatariver"
    if field.key.startswith("NIMAIL_"):
        return provider == "nimail"
    return True


def default_values() -> dict[str, str]:
    return {field.key: field.default for field in CONFIG_FIELDS}


def _clean_value(value: str) -> str:
    return str(value).replace("\r", "").replace("\n", "").strip()


def _ask(input_func: Callable[[str], str], prompt: str, default: str) -> str:
    try:
        answer = input_func(f"{prompt} [{default}]: ")
    except EOFError:
        return default
    value = _clean_value(answer)
    return value if value else default


def collect_custom_values(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> dict[str, str]:
    values = default_values()
    current_group = ""
    for field in CONFIG_FIELDS:
        if not should_ask_field(field, values):
            continue
        if field.group != current_group:
            current_group = field.group
            output_func("")
            output_func(f"## {current_group}")
        values[field.key] = _ask(input_func, f"{field.key} {field.prompt}", field.default)
    return values


def collect_values(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> dict[str, str]:
    output_func("选择配置方式:")
    output_func("  [1] 使用默认配置生成 .env")
    output_func("  [2] 逐项自定义全部配置")
    try:
        mode = _clean_value(input_func("输入 1 或 2 [1]: ")) or "1"
    except EOFError:
        mode = "1"
    if mode == "2":
        return collect_custom_values(input_func=input_func, output_func=output_func)
    return default_values()


def render_env(values: dict[str, str]) -> str:
    resolved = default_values()
    resolved.update({key: _clean_value(value) for key, value in values.items()})
    lines = [
        "# gitlab-register 正式配置",
        "# 由 bash start.sh 初始化生成；修改后执行 bash run.sh 生效。",
    ]
    current_group = ""
    for field in CONFIG_FIELDS:
        if field.group != current_group:
            current_group = field.group
            lines.extend(["", f"# {current_group}"])
        lines.append(f"{field.key}={resolved[field.key]}")
    lines.append("")
    return "\n".join(lines)


def write_env(path: str | Path, *, force: bool = False, values: dict[str, str] | None = None) -> bool:
    env_path = Path(path)
    if env_path.exists() and not force:
        return False
    env_path.write_text(render_env(values or default_values()), encoding="utf-8")
    return True


def main(
    argv: Iterable[str] | None = None,
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
) -> int:
    parser = argparse.ArgumentParser(description="初始化 gitlab-register .env 配置")
    parser.add_argument("--output", default=".env", help="输出 .env 路径")
    parser.add_argument("--force", action="store_true", help="覆盖已有 .env")
    parser.add_argument("--default", action="store_true", help="直接写入默认配置")
    parser.add_argument("--custom", action="store_true", help="逐项自定义全部配置")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.default and args.custom:
        parser.error("--default 和 --custom 只能选择一个")

    path = Path(args.output)
    if path.exists() and not args.force:
        output_func("[*] 已存在 .env，保留当前配置。需要重置请执行: bash start.sh --init")
        return 0

    if args.default:
        values = default_values()
    elif args.custom:
        values = collect_custom_values(input_func=input_func, output_func=output_func)
    else:
        values = collect_values(input_func=input_func, output_func=output_func)

    write_env(path, force=True, values=values)
    output_func(f"[*] 已写入 {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
