import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))

from loop_utils import parse_ssim, strip_loop_keywords


class TestStripLoopKeywords(unittest.TestCase):
    def test_strips_loop_terms_preserves_order(self):
        kw = "motion background, seamless loop, technology, looping, teal, loop"
        self.assertEqual(strip_loop_keywords(kw), "motion background, technology, teal")

    def test_case_insensitive(self):
        self.assertEqual(strip_loop_keywords("Seamless Loop, glow, LOOPING"), "glow")

    def test_untouched_when_no_loop_terms(self):
        kw = "motion background, abstract background, animation"
        self.assertEqual(strip_loop_keywords(kw), kw)

    def test_normalizes_whitespace(self):
        self.assertEqual(strip_loop_keywords("a ,  seamless loop ,b"), "a, b")


class TestParseSsim(unittest.TestCase):
    def test_parses_all_value(self):
        stderr = ("[Parsed_ssim_0 @ 000001] SSIM Y:0.981234 (17.2) U:0.995 V:0.994 "
                  "All:0.987654 (19.1)")
        self.assertAlmostEqual(parse_ssim(stderr), 0.987654)

    def test_raises_without_value(self):
        with self.assertRaises(ValueError):
            parse_ssim("frame=  240 fps=0.0 q=-1.0")


if __name__ == "__main__":
    unittest.main()
