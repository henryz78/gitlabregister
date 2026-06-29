import json
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from gitlab_register.outputs import create_batch_outputs


class RegistrationArtifactsTests(unittest.TestCase):
    def test_batch_outputs_create_accounts_and_summary(self):
        with TemporaryDirectory() as tmp:
            outputs = create_batch_outputs(output_dir=tmp)
            outputs.record_attempt()
            outputs.add_success_account({'email': 'user@example.test', 'username': 'voice_user'})
            outputs.write_accounts()
            outputs.write_summary(requested=1)

            self.assertEqual(
                json.loads(outputs.accounts_path.read_text(encoding='utf-8')),
                [{'email': 'user@example.test', 'username': 'voice_user'}],
            )
            self.assertEqual(
                json.loads(outputs.summary_path.read_text(encoding='utf-8'))['accounts_file'],
                str(outputs.accounts_path),
            )

    def test_screenshot_path_is_under_batch_output_dir(self):
        with TemporaryDirectory() as tmp:
            outputs = create_batch_outputs(output_dir=tmp)
            screenshot_dir = outputs.screenshot_dir('voice/user@example.com', enabled=True)

            self.assertEqual(screenshot_dir, Path(tmp) / 'screenshots' / 'voice_user_example.com')
            self.assertTrue(screenshot_dir.is_dir())


if __name__ == '__main__':
    unittest.main()
