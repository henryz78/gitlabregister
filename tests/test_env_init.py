import tempfile
import unittest
from pathlib import Path

import init_env


def parse_env(text):
    out = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith('#'):
            key, _, value = line.partition('=')
            out[key] = value
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
            self.assertEqual(parse_env(path.read_text(encoding='utf-8'))['COUNT'], '1')


if __name__ == '__main__':
    unittest.main()
