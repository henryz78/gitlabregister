import unittest

from gitlab_register.logging import mask_secret, status_line


class LoggingTests(unittest.TestCase):
    def test_mask_secret(self):
        self.assertEqual(mask_secret('abcdef123456'), 'abcd***3456')

    def test_status_line(self):
        text = status_line(attempted=2, requested=5, success=1, elapsed_seconds=12)
        self.assertIn('\u8fdb\u5ea6 2/5', text)
        self.assertIn('\u6210\u529f 1', text)


if __name__ == '__main__':
    unittest.main()
