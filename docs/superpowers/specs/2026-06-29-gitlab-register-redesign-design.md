# GitLab Register 分层重设计方案

## 背景

当前 GitLab 注册项目位于独立仓库，主流程集中在 `register_gitlab.py`。项目已经具备可用的 GitLab 页面自动化、iDataRiver / NiMail 邮箱验证码、单账号结果保存、截图保存、身份验证阻塞识别、串行批量注册等能力。

当前 Grok 项目提供了一套更适合日常使用和维护的工程规范：`start.sh` 负责初始化，`run.sh` 负责运行，配置统一走 `.env`，输出按批次目录组织，日志默认面向使用者，测试覆盖配置、路径、脚本边界和运行时行为。

本设计目标是把 GitLab 项目重做成类似 Grok 项目的工程体验，同时保持 GitLab 注册页面流程和提交顺序。

## 目标

1. GitLab 项目保持独立仓库和独立运行入口。
2. 注册流程顺序保持：创建邮箱、打开 GitLab 注册页、填写表单、提交、等待验证码、填写验证码、处理 onboarding、处理 company trial、处理默认项目、识别身份验证阻塞、保存结果。
3. 项目入口对标 Grok：`bash start.sh` 初始化，`bash run.sh` 运行。
4. 配置对标 Grok：`.env.example` 模板，`init_env.py` 交互式生成 `.env`。
5. 输出对标 Grok：每次运行都有独立 `run_label` 批次目录。
6. 结果管理对标 Grok：批次级 `accounts.json`、`summary.json` 和可选截图目录。
7. 测试覆盖对标 Grok：配置、路径、邮箱解析、输出、脚本边界、页面 helper 行为均有单元测试。

## 设计边界

- 页面自动化选择器、按钮点击策略、验证码填写、onboarding、company trial、default project 处理逻辑作为现有流程迁移进 `flow.py`。
- 第一阶段聚焦工程结构、配置、输出、日志、测试和浏览器启动体验。
- 浏览器代理池、并行注册、跨服务统一平台放到后续阶段。
- 现有 `python register_gitlab.py` 作为兼容入口保留。

## 目标目录结构

```text
gitlab-register/
  start.sh
  run.sh
  setup.sh
  init_env.py
  .env.example
  register_gitlab.py
  requirements.txt
  README.md
  gitlab_register/
    __init__.py
    cli.py
    config.py
    browser_runtime.py
    email_providers.py
    flow.py
    outputs.py
    logging.py
  tests/
    test_env_init.py
    test_script_boundary.py
    test_browser_runtime.py
    test_email_providers.py
    test_outputs.py
    test_gitlab_flow_helpers.py
```

## 入口设计

### `start.sh`

职责：

1. 进入项目目录。
2. 检查 `.venv`，缺失时执行 `setup.sh`。
3. 检查 CloakBrowser Chromium，缺失时自动安装。
4. `.env` 缺失或传入 `--init` 时运行 `init_env.py`。
5. 输出下一步命令：`bash run.sh`。

### `run.sh`

职责：

1. 检查 `.venv`。
2. 检查 `.env`。
3. 执行 `.venv/bin/python register_gitlab.py "$@"`。

### `register_gitlab.py`

保留为薄入口：

```python
from gitlab_register.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

## 配置设计

配置统一进入 `.env`：

```env
EMAIL_PROVIDER=idatariver
IDATARIVER_API_KEY=
IDATARIVER_API_BASE=https://apiok.us/api/cbea
IDATARIVER_POLL_INTERVAL_SECONDS=5
NIMAIL_API_BASE=https://www.nimail.cn

COUNT=1
RUN_LABEL=
OUTPUT_ROOT=registration_results
OUTPUT_DIR=

HEADLESS=1
SCREENSHOTS=0
LOG_VERBOSE=0
```

CLI 覆盖规则：

```text
--count 覆盖 COUNT
--run-label 覆盖 RUN_LABEL
--output-dir 覆盖 OUTPUT_DIR
--screenshots 覆盖 SCREENSHOTS=1
--headed 覆盖 HEADLESS=0
--verbose 覆盖 LOG_VERBOSE=1
--email / --password / --name / --username 保留现有语义
```

## 模块设计

### `gitlab_register.config`

负责：

- 加载 `.env`。
- 提供 typed config 数据结构。
- 处理 CLI 覆盖。
- 提供 `env_bool`、`env_int`、`safe_run_label`。

### `gitlab_register.browser_runtime`

负责：

- `find_chrome()`。
- CloakBrowser Chromium 缺失时自动安装。
- 统一创建 Playwright browser。
- 浏览器启动错误输出人性化修复命令。

### `gitlab_register.email_providers`

负责：

- 保留当前 iDataRiver / NiMail 邮箱能力。
- `create_email()` 返回统一结构：`email`、`provider`、`email_id`、`mail_key`。
- `wait_for_verification_code()` 保留当前验证码提取和轮询逻辑。
- 自定义邮箱保留终端输入验证码路径。

### `gitlab_register.flow`

负责：

- 承载现有 GitLab 页面流程。
- 保留现有 selector、JS helper、点击 helper 和页面判断函数。
- 对外提供 `register_one(config, account_input, outputs) -> RegistrationResult`。

### `gitlab_register.outputs`

负责：

- 创建批次目录。
- 创建可选截图目录。
- 写入本批次成功账号清单 `accounts.json`。
- 维护本批次统计文件 `summary.json`。
- 提供路径安全和文件写入工具。

### `gitlab_register.logging`

负责：

- 默认简洁日志。
- `LOG_VERBOSE=1` 时显示详细页面阶段、邮箱轮询和错误堆栈。
- 对包含密码、API key、session cookie 的字段脱敏。

## 输出设计

每次运行创建一个批次目录：

```text
registration_results/<run_label>/
  accounts.json
  summary.json
  screenshots/                  # 只有开启 --screenshots 时生成
    <username>/
      signup_page_loaded.png
      registration_final_state.png
```

`accounts.json` 是本批次唯一的账号清单，只保存注册成功的账号。它是一个 JSON 数组：

```json
[
  {
    "email": "user@example.com",
    "username": "user1234",
    "password": "...",
    "email_provider": "idatariver",
    "email_id": "...",
    "namespace_id": "...",
    "_gitlab_session": "..."
  }
]
```

`summary.json` 是本批次统计文件，用来快速看这次运行目标数量、成功数量和成功账号文件位置，不保存账号密码和 session。示例：

```json
{
  "requested": 3,
  "attempted": 3,
  "success": 2,
  "output_dir": "registration_results/test_001",
  "accounts_file": "registration_results/test_001/accounts.json"
}
```

## 运行流程

```text
bash start.sh
  → setup.sh 创建 .venv 并安装依赖
  → cloakbrowser install
  → init_env.py 生成 .env

bash run.sh --count 3 --run-label test_001
  → cli.py 解析配置
  → outputs.py 创建批次目录
  → browser_runtime.py 启动 CloakBrowser
  → flow.py 串行执行 3 次现有注册流程
  → outputs.py 写入成功账号清单
  → outputs.py 写 summary.json
```

## 迁移步骤

1. 添加 `start.sh`、`run.sh`、`setup.sh`、`init_env.py`、`.env.example`。
2. 添加 `gitlab_register/` 包和基础模块。
3. 把旧输出路径逻辑迁入 `gitlab_register.outputs`，删除旧输出脚本。
4. 把 `email_register.py` 迁入 `gitlab_register.email_providers`。
5. 把 `register_gitlab.py` 的页面流程迁入 `gitlab_register.flow`。
6. 把 `register_gitlab.py` 改成兼容薄入口。
7. 更新 README，让新手按 `bash start.sh`、`bash run.sh` 使用。
8. 增加测试并保持现有测试通过。

## 测试计划

- `tests/test_env_init.py`：默认 `.env`、自定义 `.env`、条件提示。
- `tests/test_script_boundary.py`：`start.sh` 只初始化，`run.sh` 只运行。
- `tests/test_browser_runtime.py`：已有浏览器直接返回，缺浏览器自动安装，安装后仍缺失时报清晰错误。
- `tests/test_email_providers.py`：iDataRiver / NiMail 响应解析、验证码提取、email_id 保留。
- `tests/test_outputs.py`：批次目录、`accounts.json` 写入、summary 统计、截图路径安全。
- `tests/test_gitlab_flow_helpers.py`：按钮脚本、身份验证识别、namespace/session 提取。

## 验收标准

1. `bash start.sh` 可完成初始化。
2. `bash run.sh --count 1` 可走现有 GitLab 注册流程。
3. `python register_gitlab.py` 兼容旧入口。
4. 批次目录只保存成功账号；身份验证阻塞、状态不明确、异常结果只进入运行日志。
5. `summary.json` 统计 requested、attempted、success 和 `accounts.json` 文件路径。
6. 单元测试覆盖新增配置、输出和浏览器运行时边界。
7. README 以新手视角说明安装、初始化、运行和结果位置。