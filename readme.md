# GitLab Register

这是一个基于 CloakBrowser 的 GitLab 账号注册辅助工具。它会打开浏览器、填写 GitLab 注册表单、读取临时邮箱验证码，并把成功账号集中保存到批次结果目录。

## 快速开始

第一次使用先初始化：

```bash
bash start.sh
```

`start.sh` 只做初始化：安装 Python 依赖、下载 CloakBrowser Chromium、生成 `.env` 配置文件。

开始注册：

```bash
bash run.sh
```

注册 3 个账号：

```bash
bash run.sh --count 3
```

指定批次名称：

```bash
bash run.sh --run-label test_001
```

## 输出文件

每次运行会生成一个批次目录：

```text
registration_results/<run_label>/
  accounts.json
  summary.json
  screenshots/
```

`accounts.json` 是成功账号列表，格式是 JSON 数组。

```json
[
  {
    "email": "example@uselesss.org",
    "username": "example_1234",
    "password": "Secure1234!",
    "name": "Alex Reed",
    "timestamp": "2026-06-26 08:09:10",
    "email_provider": "idatariver",
    "email_id": "mailbox-id",
    "namespace_id": "136077360",
    "_gitlab_session": "gitlab-session-cookie-value"
  }
]
```

`summary.json` 是本批次统计：

```json
{
  "requested": 3,
  "attempted": 3,
  "success": 2,
  "output_dir": "registration_results/test_001",
  "accounts_file": "registration_results/test_001/accounts.json"
}
```

| 字段 | 说明 |
|------|------|
| `requested` | 计划注册数量 |
| `attempted` | 已尝试注册数量 |
| `success` | 成功账号数量 |
| `output_dir` | 本批次输出目录 |
| `accounts_file` | 成功账号文件路径 |

## `.env` 配置

`bash start.sh` 会根据 `.env.example` 生成 `.env`。常用配置：

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

| 配置 | 说明 |
|------|------|
| `EMAIL_PROVIDER` | 邮箱服务，支持 `idatariver`、`nimail` |
| `IDATARIVER_API_KEY` | iDataRiver API key |
| `COUNT` | 默认注册数量 |
| `RUN_LABEL` | 默认批次名称 |
| `OUTPUT_ROOT` | 默认输出根目录 |
| `OUTPUT_DIR` | 指定完整输出目录 |
| `HEADLESS` | `1` 为无头浏览器，`0` 为可视化浏览器 |
| `SCREENSHOTS` | `1` 保存截图，`0` 关闭截图 |

## 命令参数

```bash
bash run.sh --email your_email@example.com --name "Alex Reed"
bash run.sh --headed
bash run.sh --screenshots
bash run.sh --count 3
bash run.sh --run-label test_001
bash run.sh --output-dir registration_results/custom_batch
```

| 参数 | 说明 |
|------|------|
| `--email` | 使用指定邮箱注册 |
| `--password` | 使用指定密码 |
| `--name` | 使用指定姓名 |
| `--username` | 使用指定用户名 |
| `--headed` | 打开可视化浏览器窗口 |
| `--screenshots` | 保存关键步骤截图 |
| `--count` | 本次注册数量 |
| `--run-label` | 本批次名称 |
| `--output-dir` | 本批次完整输出目录 |
| `--verbose` | 输出详细日志 |

## CloakBrowser 手动修复

Codespaces 或新机器首次运行会自动下载 CloakBrowser Chromium。需要手动修复时运行：

```bash
.venv/bin/python -m cloakbrowser install
.venv/bin/python -m cloakbrowser info
```

Linux/Codespaces 缺系统库时运行：

```bash
python -m playwright install-deps chromium
```

## 项目结构

```text
start.sh                 # 初始化
run.sh                   # 运行注册
setup.sh                 # 安装依赖
gitlab_register/cli.py   # CLI 编排
gitlab_register/flow.py  # GitLab 注册流程
gitlab_register/outputs.py # accounts.json / summary.json
```
