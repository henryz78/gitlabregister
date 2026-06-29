import unittest
from pathlib import Path


class ReadmeTests(unittest.TestCase):
    def test_readme_keeps_chinese_quickstart_text(self):
        text = Path('readme.md').read_text(encoding='utf-8')

        self.assertIn('\u5feb\u901f\u5f00\u59cb', text)
        self.assertIn('bash start.sh', text)
        self.assertIn('accounts.json', text)
        self.assertNotIn('????', text)


if __name__ == '__main__':
    unittest.main()
