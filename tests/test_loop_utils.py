import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))

from loop_utils import add_loop_guides, parse_ssim, strip_loop_keywords


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


class TestAddLoopGuides(unittest.TestCase):
    def _t2v(self):
        import main_ltxvideo as m
        return m.build_workflow("pos", "neg")

    def test_guide_nodes_and_rewiring(self):
        wf = add_loop_guides(self._t2v(), "anchor.png", 241)
        self.assertEqual(wf["6"]["class_type"], "LoadImage")
        self.assertEqual(wf["6"]["inputs"]["image"], "anchor.png")
        self.assertEqual(wf["13"]["class_type"], "LTXVAddGuide")
        self.assertEqual(wf["13"]["inputs"]["frame_idx"], 0)
        self.assertEqual(wf["13"]["inputs"]["latent"], ["20", 0])
        self.assertEqual(wf["14"]["inputs"]["frame_idx"], 240)  # 8-aligned last frame
        self.assertEqual(wf["14"]["inputs"]["latent"], ["13", 2])
        # stage 1 consumes guided latent + conditioning
        self.assertEqual(wf["22"]["inputs"]["video_latent"], ["14", 2])
        self.assertEqual(wf["23"]["inputs"]["positive"], ["14", 0])
        self.assertEqual(wf["23"]["inputs"]["negative"], ["14", 1])
        # stage 2 crops guides, upsampler consumes the CROPPED latent
        self.assertEqual(wf["32"]["inputs"]["positive"], ["14", 0])
        self.assertEqual(wf["32"]["inputs"]["negative"], ["14", 1])
        self.assertEqual(wf["30"]["inputs"]["samples"], ["32", 2])

    def test_strength_and_no_mutation(self):
        original = self._t2v()
        snapshot = repr(original)
        wf = add_loop_guides(original, "a.png", 241, strength=0.9)
        self.assertEqual(wf["13"]["inputs"]["strength"], 0.9)
        self.assertEqual(wf["14"]["inputs"]["strength"], 0.9)
        self.assertEqual(repr(original), snapshot, "input workflow must not be mutated")


if __name__ == "__main__":
    unittest.main()
