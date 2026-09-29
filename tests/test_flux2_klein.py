import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "script"))

import main_flux2_klein as m


SAMPLE = {
    "name": "blue_data_background",
    "title": "Blue data background with copy space",
    "keywords": "abstract background, blue, data, copy space",
    "category": 8,
    "positive": "A clean blue network of light points with an empty right half.",
    "negative": "text, logo, watermark",
}


class TestFlux2KleinWorkflow(unittest.TestCase):
    def test_uses_base_model_and_correct_flux2_nodes(self):
        wf = m.build_workflow(SAMPLE, seed=123, image_index=1)
        self.assertEqual(wf["1"]["inputs"]["unet_name"], m.MODEL_NAME)
        self.assertEqual(wf["2"]["inputs"]["type"], "flux2")
        self.assertEqual(wf["12"]["class_type"], "EmptyFlux2LatentImage")
        self.assertEqual(wf["16"]["class_type"], "Flux2Scheduler")
        self.assertEqual(wf["16"]["inputs"]["steps"], m.STEPS)
        self.assertEqual(wf["13"]["inputs"]["noise_seed"], 123)
        self.assertEqual(wf["14"]["inputs"]["cfg"], m.CFG)
        self.assertEqual(wf["14"]["inputs"]["negative"], ["11", 0])
        self.assertEqual(wf["20"]["inputs"]["images"], ["19", 0])

    def test_rejects_invalid_metadata_before_generation(self):
        bad = dict(SAMPLE, category=0)
        with self.assertRaisesRegex(ValueError, "category"):
            m.validate_prompts([bad])
        with self.assertRaisesRegex(ValueError, "nonempty"):
            m.validate_prompts([])


if __name__ == "__main__":
    unittest.main()
