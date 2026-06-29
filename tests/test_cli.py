import json
import tempfile
import unittest
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
            accounts = json.loads((Path(tmp) / 'accounts.json').read_text(encoding='utf-8'))
            summary = json.loads((Path(tmp) / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(accounts[0]['username'], 'alice')
            self.assertEqual(summary['success'], 1)

    def test_main_writes_outputs_when_register_raises(self):
        async def failing_register_one(*, config, outputs, email=None, password=None, name=None, username=None):
            raise RuntimeError('simulated failure')

        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(['--count', '1', '--output-dir', tmp], register_one=failing_register_one)

            self.assertEqual(code, 0)
            accounts = json.loads((Path(tmp) / 'accounts.json').read_text(encoding='utf-8'))
            summary = json.loads((Path(tmp) / 'summary.json').read_text(encoding='utf-8'))
            self.assertEqual(accounts, [])
            self.assertEqual(summary['requested'], 1)
            self.assertEqual(summary['attempted'], 1)
            self.assertEqual(summary['success'], 0)

    def test_main_prints_output_paths_after_run(self):
        async def fake_register_one(*, config, outputs, email=None, password=None, name=None, username=None):
            outputs.record_attempt()
            outputs.add_success_account({'email': 'a@example.test', 'username': 'alice'})
            return 'success'

        lines = []
        with tempfile.TemporaryDirectory() as tmp:
            code = cli.main(
                ['--count', '1', '--output-dir', tmp],
                register_one=fake_register_one,
                output_func=lines.append,
            )

            self.assertEqual(code, 0)
            output = '\n'.join(lines)
            self.assertIn('成功账号文件:', output)
            self.assertIn('本批次统计:', output)
            self.assertIn(str(Path(tmp) / 'accounts.json'), output)


    def test_run_label_uses_output_root_when_output_dir_omitted(self):
        async def fake_register_one(*, config, outputs, email=None, password=None, name=None, username=None):
            outputs.record_attempt()
            outputs.add_success_account({'email': 'a@example.test', 'username': 'alice'})
            return 'success'

        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / '.env'
            env.write_text(f'OUTPUT_ROOT={tmp}\nRUN_LABEL=demo batch/01\nCOUNT=1\n', encoding='utf-8')
            code = cli.main([], register_one=fake_register_one, env_path=env)

            output_dir = Path(tmp) / 'demo_batch_01'
            self.assertEqual(code, 0)
            self.assertTrue((output_dir / 'accounts.json').is_file())
            self.assertTrue((output_dir / 'summary.json').is_file())


if __name__ == '__main__':
    unittest.main()
