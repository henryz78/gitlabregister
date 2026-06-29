import json
import tempfile
import unittest
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

            self.assertEqual(json.loads(outputs.accounts_path.read_text(encoding='utf-8'))[0]['username'], 'alice')
            summary = json.loads(outputs.summary_path.read_text(encoding='utf-8'))
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


if __name__ == '__main__':
    unittest.main()
