import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gitlab_register.browser_runtime import find_chrome


class BrowserRuntimeTests(unittest.TestCase):
    def test_existing_path_returns_latest_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            old = home / '.cloakbrowser' / 'chromium-001' / 'chrome'
            new = home / '.cloakbrowser' / 'chromium-002' / 'chrome'
            old.parent.mkdir(parents=True)
            new.parent.mkdir(parents=True)
            old.write_text('old', encoding='utf-8')
            new.write_text('new', encoding='utf-8')

            with mock.patch('pathlib.Path.home', return_value=home):
                self.assertEqual(find_chrome(), str(new))

    def test_existing_path_uses_numeric_version_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            old = home / '.cloakbrowser' / 'chromium-99' / 'chrome'
            new = home / '.cloakbrowser' / 'chromium-100' / 'chrome'
            old.parent.mkdir(parents=True)
            new.parent.mkdir(parents=True)
            old.write_text('old', encoding='utf-8')
            new.write_text('new', encoding='utf-8')

            with mock.patch('pathlib.Path.home', return_value=home):
                self.assertEqual(find_chrome(), str(new))

    def test_missing_path_installs_and_returns_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            installed = home / '.cloakbrowser' / 'chromium-003' / 'chrome'

            def fake_install(command):
                self.assertEqual(command, [sys.executable, '-m', 'cloakbrowser', 'install'])
                installed.parent.mkdir(parents=True)
                installed.write_text('chrome', encoding='utf-8')

            with mock.patch('pathlib.Path.home', return_value=home), \
                 mock.patch('subprocess.check_call', side_effect=fake_install) as check_call:
                self.assertEqual(find_chrome(), str(installed))
                check_call.assert_called_once()

    def test_still_missing_after_install_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with mock.patch('pathlib.Path.home', return_value=home), \
                 mock.patch('subprocess.check_call', return_value=0):
                with self.assertRaisesRegex(RuntimeError, 'cloakbrowser install'):
                    find_chrome()


if __name__ == '__main__':
    unittest.main()
