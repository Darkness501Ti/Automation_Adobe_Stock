import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))


class TestImportSideEffects(unittest.TestCase):
    def test_import_creates_no_run_dir(self):
        base = os.path.join(os.path.dirname(__file__), "..", "output")
        before = set(os.listdir(base)) if os.path.exists(base) else set()
        import main_ltxvideo  # noqa: F401
        after = set(os.listdir(base)) if os.path.exists(base) else set()
        self.assertEqual(before, after, "importing main_ltxvideo must not create run dirs")

    def test_build_workflow_frames_param(self):
        import main_ltxvideo as m
        wf = m.build_workflow("pos", "neg", frames=33)
        self.assertEqual(wf["20"]["inputs"]["length"], 33)
        self.assertEqual(wf["21"]["inputs"]["frames_number"], 33)
        wf_default = m.build_workflow("pos", "neg")
        self.assertEqual(wf_default["20"]["inputs"]["length"], m.FRAMES)


if __name__ == "__main__":
    unittest.main()
