import unittest
from pathlib import Path


class ScriptBoundaryTests(unittest.TestCase):
    def test_start_initializes_only(self):
        text = Path('start.sh').read_text(encoding='utf-8')

        self.assertIn('init_env.py', text)
        self.assertIn('bash run.sh', text)
        self.assertNotIn('register_gitlab.py "$@"', text)

    def test_shell_scripts_start_with_plain_shebang(self):
        for script in ('start.sh', 'run.sh', 'setup.sh'):
            data = Path(script).read_bytes()
            self.assertTrue(data.startswith(b'#!/bin/bash'), script)

    def test_shell_scripts_are_committed_with_lf_eol(self):
        text = Path('.gitattributes').read_text(encoding='utf-8')
        self.assertIn('*.sh text eol=lf', text)

    def test_run_executes_register(self):
        text = Path('run.sh').read_text(encoding='utf-8')

        self.assertIn('[ ! -d .venv ]', text)
        self.assertIn('[ ! -f .env ]', text)
        self.assertIn('exec .venv/bin/python register_gitlab.py "$@"', text)


if __name__ == '__main__':
    unittest.main()
