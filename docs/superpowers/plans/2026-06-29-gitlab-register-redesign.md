# GitLab Register Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the standalone GitLab register project into the Grok-style structure with `start.sh`, `run.sh`, `.env` initialization, package modules, `accounts.json`, and `summary.json` while preserving the GitLab registration flow.

**Architecture:** Keep the current browser registration sequence intact. Move setup, config, browser runtime, outputs, email providers, logging, and CLI orchestration into focused modules under `gitlab_register/`.

**Tech Stack:** Python 3.10+, asyncio, CloakBrowser/Playwright, requests, python-dotenv, Bash, unittest/pytest.

---

## File Structure

- Create `start.sh`: initialization only.
- Create `run.sh`: runtime only.
- Create `setup.sh`: dependency and CloakBrowser install.
- Create `.env.example`: GitLab register config template.
- Create `init_env.py`: interactive `.env` generator.
- Create `gitlab_register/__init__.py`.
- Create `gitlab_register/config.py`: typed config, env load, CLI overrides, safe run labels.
- Create `gitlab_register/browser_runtime.py`: `find_chrome()` and browser launch helper.
- Create `gitlab_register/outputs.py`: batch output directory, `accounts.json`, `summary.json`, screenshot directory.
- Create `gitlab_register/logging.py`: concise logs and secret masking.
- Move `email_register.py` logic to `gitlab_register/email_providers.py`; keep `email_register.py` as compatibility wrapper.
- Move `register_gitlab.py` logic to `gitlab_register/flow.py`; keep `register_gitlab.py` as compatibility wrapper and CLI entry.
- Create `gitlab_register/cli.py`: parse args, load config, run serial registrations, write outputs.
- Remove old output script after migration.
- Update `readme.md`.
- Add tests for env init, scripts, config, browser runtime, outputs, logging, CLI, flow helpers.

---

### Task 1: Init scripts and `.env` generator

**Files:**
- Create: `.env.example`, `init_env.py`, `setup.sh`, `start.sh`, `run.sh`
- Modify: `requirements.txt`
- Test: `tests/test_env_init.py`, `tests/test_script_boundary.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_env_init.py` with these assertions:

```python
import tempfile, unittest
from pathlib import Path
import init_env

def parse_env(text):
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith('#'):
            k, _, v = line.partition('=')
            out[k] = v
    return out

class EnvInitTests(unittest.TestCase):
    def test_default_env_contains_gitlab_keys(self):
        values = parse_env(init_env.render_env(init_env.default_values()))
        self.assertEqual(values['EMAIL_PROVIDER'], 'idatariver')
        self.assertEqual(values['COUNT'], '1')
        self.assertEqual(values['OUTPUT_ROOT'], 'registration_results')
        self.assertEqual(values['HEADLESS'], '1')
        self.assertEqual(values['SCREENSHOTS'], '0')

    def test_main_writes_default_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '.env'
            code = init_env.main(['--output', str(path), '--default'], output_func=lambda _='': None)
            self.assertEqual(code, 0)
            self.assertEqual(parse_env(path.read_text())['COUNT'], '1')
```

Create `tests/test_script_boundary.py`:

```python
import unittest
from pathlib import Path

class ScriptBoundaryTests(unittest.TestCase):
    def test_start_initializes_only(self):
        text = Path('start.sh').read_text(encoding='utf-8')
        self.assertIn('init_env.py', text)
        self.assertIn('bash run.sh', text)
        self.assertNotIn('register_gitlab.py "$@"', text)

    def test_run_executes_register(self):
        text = Path('run.sh').read_text(encoding='utf-8')
        self.assertIn('[ ! -d .venv ]', text)
        self.assertIn('[ ! -f .env ]', text)
        self.assertIn('exec .venv/bin/python register_gitlab.py "$@"', text)
```

Run:

```bash
python -m unittest tests.test_env_init tests.test_script_boundary -v
```

Expected: failure due missing files.

- [ ] **Step 2: Implement files**

Use the Grok project versions as source shape. Required `.env.example` keys:

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

`run.sh` must end with:

```bash
exec .venv/bin/python register_gitlab.py "$@"
```

`setup.sh` must install requirements and run:

```bash
.venv/bin/python -m cloakbrowser install
```

`requirements.txt` must contain:

```text
cloakbrowser>=0.3.0
requests>=2.31.0
PySocks>=1.7.1
python-dotenv>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.24.0
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_env_init tests.test_script_boundary -v
git diff --check
```

Commit:

```bash
git add .env.example init_env.py setup.sh start.sh run.sh requirements.txt tests/test_env_init.py tests/test_script_boundary.py
git commit -m "Add GitLab init and run entrypoints"
```

---

### Task 2: Runtime config module

**Files:**
- Create: `gitlab_register/__init__.py`, `gitlab_register/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_config.py`:

```python
import tempfile, unittest
from pathlib import Path
from gitlab_register.config import RuntimeConfig, apply_cli_overrides, load_config, safe_run_label

class ConfigTests(unittest.TestCase):
    def test_safe_run_label(self):
        self.assertEqual(safe_run_label('demo batch/01'), 'demo_batch_01')
        self.assertTrue(safe_run_label(''))

    def test_load_config_reads_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text('EMAIL_PROVIDER=nimail\nCOUNT=3\nHEADLESS=0\nSCREENSHOTS=1\n')
            cfg = load_config(env_path=env)
            self.assertEqual(cfg.email_provider, 'nimail')
            self.assertEqual(cfg.count, 3)
            self.assertFalse(cfg.headless)
            self.assertTrue(cfg.screenshots)

    def test_cli_overrides(self):
        cfg = RuntimeConfig(count=1, run_label='env')
        got = apply_cli_overrides(cfg, count=4, run_label='cli', output_dir='out', headed=True, screenshots=True, verbose=True)
        self.assertEqual(got.count, 4)
        self.assertEqual(got.run_label, 'cli')
        self.assertEqual(got.output_dir, 'out')
        self.assertFalse(got.headless)
        self.assertTrue(got.screenshots)
        self.assertTrue(got.log_verbose)
```

- [ ] **Step 2: Implement config module**

Create `gitlab_register/config.py` with `RuntimeConfig` dataclass fields from `.env.example`, plus:

```python
# safe_run_label('demo batch/01') returns 'demo_batch_01'.
# load_config('.env') returns RuntimeConfig populated from environment values.
# apply_cli_overrides(config, count, run_label, output_dir, headed, screenshots, verbose) returns a new RuntimeConfig with CLI values applied.
```

The loader must call `dotenv.load_dotenv(path, override=False)` when `python-dotenv` exists.

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_config -v
git diff --check
```

Commit:

```bash
git add gitlab_register/__init__.py gitlab_register/config.py tests/test_config.py
git commit -m "Add GitLab runtime config module"
```

---

### Task 3: Batch outputs module

**Files:**
- Create: `gitlab_register/outputs.py`
- Test: `tests/test_outputs.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_outputs.py`:

```python
import json, tempfile, unittest
from pathlib import Path
from gitlab_register.outputs import create_batch_outputs, safe_path_part

class OutputTests(unittest.TestCase):
    def test_accounts_json_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = create_batch_outputs(output_dir=tmp)
            outputs.record_attempt()
            outputs.add_success_account({'email': 'a@example.test', 'username': 'alice'})
            outputs.write_accounts()
            outputs.write_summary(requested=3)
            self.assertEqual(json.loads(outputs.accounts_path.read_text())[0]['username'], 'alice')
            summary = json.loads(outputs.summary_path.read_text())
            self.assertEqual(summary['requested'], 3)
            self.assertEqual(summary['attempted'], 1)
            self.assertEqual(summary['success'], 1)
            self.assertEqual(summary['accounts_file'], str(outputs.accounts_path))

    def test_screenshot_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            outputs = create_batch_outputs(output_dir=tmp)
            self.assertIsNone(outputs.screenshot_dir('alice', enabled=False))
            self.assertTrue(outputs.screenshot_dir('alice', enabled=True).is_dir())

    def test_safe_path_part(self):
        self.assertEqual(safe_path_part('a/b c'), 'a_b_c')
```

- [ ] **Step 2: Implement outputs**

Create `BatchOutputs` with `output_dir`, `accounts`, `attempted`, `accounts_path`, `summary_path`, `record_attempt()`, `add_success_account()`, `write_accounts()`, `write_summary(requested: int)`, `screenshot_dir(username, enabled: bool)`.

`accounts.json` must be a JSON array, not JSONL.

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_outputs -v
git diff --check
```

Commit:

```bash
git add gitlab_register/outputs.py tests/test_outputs.py
git commit -m "Add GitLab accounts json outputs"
```

---

### Task 4: Browser runtime and logging helpers

**Files:**
- Create: `gitlab_register/browser_runtime.py`, `gitlab_register/logging.py`
- Test: `tests/test_browser_runtime.py`, `tests/test_logging.py`

- [ ] **Step 1: Write tests**

`tests/test_browser_runtime.py` should cover:

```python
# latest ~/.cloakbrowser/chromium-*/chrome wins
# missing browser calls [sys.executable, '-m', 'cloakbrowser', 'install']
# still missing raises RuntimeError containing 'cloakbrowser install'
```

`tests/test_logging.py` should cover:

```python
from gitlab_register.logging import mask_secret, status_line
assert mask_secret('abcdef123456') == 'abcd***3456'
assert '进度 2/5' in status_line(attempted=2, requested=5, success=1, elapsed_seconds=12)
```

- [ ] **Step 2: Implement modules**

`browser_runtime.find_chrome()` must match the Grok behavior:

```python
subprocess.check_call([sys.executable, '-m', 'cloakbrowser', 'install'])
```

`logging.py` must expose `log()`, `verbose_log()`, `mask_secret()`, `status_line()`.

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_browser_runtime tests.test_logging -v
git diff --check
```

Commit:

```bash
git add gitlab_register/browser_runtime.py gitlab_register/logging.py tests/test_browser_runtime.py tests/test_logging.py
git commit -m "Add GitLab browser runtime and logging helpers"
```

---

### Task 5: Move email provider code

**Files:**
- Move: `email_register.py` to `gitlab_register/email_providers.py`
- Create: `email_register.py` compatibility wrapper
- Test: existing `tests/test_email_register.py`

- [ ] **Step 1: Move and wrap**

Run:

```bash
git mv email_register.py gitlab_register/email_providers.py
```

Create `email_register.py`:

```python
from gitlab_register.email_providers import *
```

- [ ] **Step 2: Add runtime adapter**

In `gitlab_register/email_providers.py`, add:

```python
def configure_from_runtime(config):
    global EMAIL_PROVIDER, IDATARIVER_API_KEY, IDATARIVER_API_BASE
    global IDATARIVER_POLL_INTERVAL_SECONDS, NIMAIL_API_BASE
    EMAIL_PROVIDER = config.email_provider
    IDATARIVER_API_KEY = config.idatariver_api_key
    IDATARIVER_API_BASE = config.idatariver_api_base.rstrip('/')
    IDATARIVER_POLL_INTERVAL_SECONDS = float(config.idatariver_poll_interval_seconds)
    NIMAIL_API_BASE = config.nimail_api_base.rstrip('/')
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_email_register -v
git diff --check
```

Commit:

```bash
git add email_register.py gitlab_register/email_providers.py tests/test_email_register.py
git commit -m "Move GitLab email providers into package"
```

---

### Task 6: Move GitLab flow code

**Files:**
- Move: `register_gitlab.py` to `gitlab_register/flow.py`
- Create: `register_gitlab.py` wrapper
- Test: existing flow helper tests

- [ ] **Step 1: Move flow**

Run:

```bash
git mv register_gitlab.py gitlab_register/flow.py
```

Update imports in `gitlab_register/flow.py`:

```python
from gitlab_register.email_providers import get_email_and_token, get_email_token_metadata, get_verification_code
```

- [ ] **Step 2: Add flow adapter**

In `gitlab_register/flow.py`, add:

```python
async def register_one(*, config, outputs, email=None, password=None, name=None, username=None):
    outputs.record_attempt()
    result = await register_gitlab_async(
        email=email,
        password=password,
        name=name,
        username=username,
        headless=config.headless,
        screenshots=config.screenshots,
    )
    if isinstance(result, dict):
        outputs.add_success_account(result)
        return REGISTRATION_STATUS_SUCCESS
    return result
```

Modify the success branch of `register_gitlab_async()` to return `build_success_account_record(account_info)`.

- [ ] **Step 3: Create wrapper**

Create `register_gitlab.py` with a lazy CLI import so Task 6 tests can import flow helpers before `gitlab_register.cli` exists:

```python
from gitlab_register.flow import *

if __name__ == '__main__':
    from gitlab_register.cli import main
    raise SystemExit(main())
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
python -m unittest tests.test_register_gitlab_click -v
git diff --check
```

Commit:

```bash
git add register_gitlab.py gitlab_register/flow.py tests/test_register_gitlab_click.py
git commit -m "Move GitLab registration flow into package"
```

---

### Task 7: CLI orchestration

**Files:**
- Create: `gitlab_register/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI test**

Create `tests/test_cli.py`:

```python
import json, tempfile, unittest
from pathlib import Path
from gitlab_register import cli

class CliTests(unittest.TestCase):
    def test_main_writes_success_outputs_with_fake_register(self):
        async def fake_register_one(*, config, outputs, email=None, password=None, name=None, username=None):
            outputs.record_attempt()
            outputs.add_success_account({'email': 'a@example.test', 'username': username or 'alice'})
            return 'success'

        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(['--count', '1', '--output-dir', tmp, '--username', 'alice'], register_one=fake_register_one)
            self.assertEqual(code, 0)
            accounts = json.loads((Path(tmp) / 'accounts.json').read_text())
            summary = json.loads((Path(tmp) / 'summary.json').read_text())
            self.assertEqual(accounts[0]['username'], 'alice')
            self.assertEqual(summary['success'], 1)
```

- [ ] **Step 2: Implement CLI**

`gitlab_register/cli.py` must:

```python
# parse --email --password --name --username --headed --screenshots --verbose --count --run-label --output-dir
# load config
# apply overrides
# configure email provider
# create BatchOutputs
# call register_one serially count times
# write accounts.json and summary.json
# return 0
```

Expose:

```python
# build_parser() returns an argparse.ArgumentParser with --email, --password, --name, --username, --headed, --screenshots, --verbose, --count, --run-label, and --output-dir.
# run_async(args, register_one=default_register_one) loads config, creates outputs, runs registrations, writes accounts.json, writes summary.json, and returns 0.
# main(argv=None, register_one=default_register_one) parses args and returns asyncio.run(run_async(args, register_one=register_one)).
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m unittest tests.test_cli -v
git diff --check
```

Commit:

```bash
git add gitlab_register/cli.py tests/test_cli.py
git commit -m "Add GitLab CLI orchestration"
```

---

### Task 8: Remove old output script and update README

**Files:**
- Delete: `registration_artifacts.py`
- Modify: `tests/test_registration_artifacts.py`
- Modify: `readme.md`

- [ ] **Step 1: Replace old artifact test**

Replace `tests/test_registration_artifacts.py` content with tests importing `gitlab_register.outputs` and asserting `accounts.json`, `summary.json`, and screenshot paths.

- [ ] **Step 2: Delete old output script**

Run:

```bash
git rm registration_artifacts.py
```

- [ ] **Step 3: Replace README workflow**

README must include:

```markdown
bash start.sh
bash run.sh
bash run.sh --count 3
bash run.sh --run-label test_001
```

and output:

```text
registration_results/<run_label>/
  accounts.json
  summary.json
  screenshots/
```

- [ ] **Step 4: Verify and commit**

Run:

```bash
python -m unittest tests.test_registration_artifacts -v
git diff --check
```

Commit:

```bash
git add readme.md tests/test_registration_artifacts.py
git commit -m "Document GitLab register workflow"
```

---

### Task 9: Full verification

**Files:**
- Modify files revealed by test failures.

- [ ] **Step 1: Run targeted suite**

```bash
python -m unittest \
  tests.test_env_init \
  tests.test_script_boundary \
  tests.test_config \
  tests.test_outputs \
  tests.test_browser_runtime \
  tests.test_logging \
  tests.test_email_register \
  tests.test_register_gitlab_click \
  tests.test_cli \
  tests.test_registration_artifacts \
  -v
```

Expected: PASS.

- [ ] **Step 2: Run discovery**

```bash
python -m unittest discover -s tests
```

Expected: PASS.

- [ ] **Step 3: Run pytest**

```bash
python -m pytest tests -q
```

Expected: PASS after installing `requirements.txt`.

- [ ] **Step 4: Run diff check**

```bash
git diff --check
git status --short
```

Expected: clean after commits.

---

## Self-Review

- Spec coverage: initialization, config, browser runtime, outputs, email migration, flow migration, CLI, docs, and tests are covered.
- Output shape: plan uses `accounts.json` and `summary.json`; single-account `account.json` output is excluded.
- Scope: browser proxy pool, cross-service platform, and GitLab parallel registration stay outside this plan.
- Task size: each task has tests, implementation, verification, and commit.
