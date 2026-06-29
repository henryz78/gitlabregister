import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gitlab_register.config import RuntimeConfig, apply_cli_overrides, load_config, safe_run_label


class ConfigTests(unittest.TestCase):
    def test_safe_run_label(self):
        self.assertEqual(safe_run_label('demo batch/01'), 'demo_batch_01')
        self.assertTrue(safe_run_label(''))

    def test_load_config_reads_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text('EMAIL_PROVIDER=nimail\nCOUNT=3\nHEADLESS=0\nSCREENSHOTS=1\n', encoding='utf-8')
            with mock.patch.dict(os.environ, {}, clear=True):
                cfg = load_config(env_path=env)

            self.assertEqual(cfg.email_provider, 'nimail')
            self.assertEqual(cfg.count, 3)
            self.assertFalse(cfg.headless)
            self.assertTrue(cfg.screenshots)

    def test_cli_overrides(self):
        cfg = RuntimeConfig(count=1, run_label='env')

        got = apply_cli_overrides(
            cfg,
            count=4,
            run_label='cli',
            output_dir='out',
            headed=True,
            screenshots=True,
            verbose=True,
        )

        self.assertEqual(got.count, 4)
        self.assertEqual(got.run_label, 'cli')
        self.assertEqual(got.output_dir, 'out')
        self.assertFalse(got.headless)
        self.assertTrue(got.screenshots)
        self.assertTrue(got.log_verbose)


if __name__ == '__main__':
    unittest.main()
