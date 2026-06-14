import unittest

from reportlab.platypus import HRFlowable, Paragraph, XPreformatted

from services.pdf_gen import _get_styles, _markdown_inline, _markdown_to_flowables


class MarkdownToFlowablesTest(unittest.TestCase):
    def setUp(self):
        self.styles = _get_styles()

    def test_inline_markdown(self):
        result = _markdown_inline(
            "**bold** *italic* `code` [site](https://example.com?a=1&b=2)"
        )

        self.assertIn("<b>bold</b>", result)
        self.assertIn("<i>italic</i>", result)
        self.assertIn(">code</font>", result)
        self.assertIn('<link href="https://example.com?a=1&amp;b=2"', result)

    def test_block_markdown(self):
        flowables = _markdown_to_flowables(
            "# Title\n\n#### Detail\n\n- first\n2. second\n\n> quote\n\n```python\nprint('ok')\n```",
            self.styles,
        )

        self.assertIsInstance(flowables[0], Paragraph)
        self.assertIsInstance(flowables[1], HRFlowable)
        paragraphs = [
            item for item in flowables
            if isinstance(item, Paragraph) and not isinstance(item, XPreformatted)
        ]
        self.assertEqual(len(paragraphs), 5)
        self.assertIsInstance(flowables[-1], XPreformatted)

    def test_plain_text_is_still_supported(self):
        flowables = _markdown_to_flowables("first line\nsecond line", self.styles)

        self.assertEqual(len(flowables), 1)
        self.assertIsInstance(flowables[0], Paragraph)


if __name__ == "__main__":
    unittest.main()
