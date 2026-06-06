import unittest
from utils.sanitize import escape_markdown

class TestSanitize(unittest.TestCase):
    def test_escape_markdown_empty_string(self):
        """Test with empty strings and None."""
        self.assertEqual(escape_markdown(""), "")
        self.assertEqual(escape_markdown(None), None)

    def test_escape_markdown_no_special_chars(self):
        """Test with a string containing no markdown characters."""
        self.assertEqual(escape_markdown("hello world"), "hello world")
        self.assertEqual(escape_markdown("12345"), "12345")

    def test_escape_markdown_backslashes(self):
        """Test escaping of backslashes to prevent bypasses."""
        self.assertEqual(escape_markdown("\\"), "\\\\")
        self.assertEqual(escape_markdown("path\\to\\file"), "path\\\\to\\\\file")

    def test_escape_markdown_specifiers(self):
        """Test escaping of individual markdown specifiers."""
        self.assertEqual(escape_markdown("*"), "\\*")
        self.assertEqual(escape_markdown("_"), "\\_")
        self.assertEqual(escape_markdown("`"), "\\`")
        self.assertEqual(escape_markdown("["), "\\[")
        self.assertEqual(escape_markdown("]"), "\\]")
        self.assertEqual(escape_markdown("~"), "\\~")
        self.assertEqual(escape_markdown("|"), "\\|")

    def test_escape_markdown_mixed(self):
        """Test with mixed text and markdown characters."""
        self.assertEqual(escape_markdown("hello *world*"), "hello \\*world\\*")
        self.assertEqual(escape_markdown("my_file_name.txt"), "my\\_file\\_name.txt")
        self.assertEqual(escape_markdown("code `var`"), "code \\`var\\`")
        self.assertEqual(escape_markdown("[link]"), "\\[link\\]")

    def test_escape_markdown_complex_payload(self):
        """Test with complex combined payloads."""
        payload = "\\*[__test__]\\`"
        expected = "\\\\\\*\\[\\_\\_test\\_\\_\\]\\\\\\`"
        self.assertEqual(escape_markdown(payload), expected)

if __name__ == "__main__":
    unittest.main()
