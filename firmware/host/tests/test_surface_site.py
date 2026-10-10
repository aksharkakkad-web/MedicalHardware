"""Temperature site must describe what the low-resolution thermal frame supports."""
import unittest

import body_model


class SurfaceSiteTests(unittest.TestCase):
    def test_narrow_region_above_shoulders_can_be_labelled_neck_region(self):
        pixels = [22.0] * 768
        for row in range(3, 6):
            for col in range(14, 18):
                pixels[row * 32 + col] = 32.0
        for row in range(6, 9):
            for col in range(15, 17):
                pixels[row * 32 + col] = 34.0
        for row in range(9, 13):
            for col in range(10, 22):
                pixels[row * 32 + col] = 29.0
        result = body_model.analyse(pixels, 0.8)
        self.assertEqual(result["surface_temp"]["site"], "neck region")
        self.assertEqual(result["surface_temp"]["estimate_f"], 93.2)
        self.assertFalse(result["surface_temp"]["skin_verified"])

    def test_clipped_head_uses_unidentified_body_surface(self):
        pixels = [22.0] * 768
        for row in range(0, 12):
            for col in range(10, 22):
                pixels[row * 32 + col] = 31.0
        result = body_model.analyse(pixels, 0.8)
        self.assertEqual(result["surface_temp"]["site"], "visible body surface")
        self.assertIn("material unverified", result["surface_temp"]["note"])
        self.assertFalse(result["surface_temp"]["skin_verified"])

    def test_flat_frame_has_no_person_temperature(self):
        self.assertIsNone(body_model.analyse([22.0] * 768, 0.8))

    def test_tiny_warm_patch_has_no_temperature_site(self):
        pixels = [22.0] * 768
        for row in range(8, 10):
            for col in range(14, 18):
                pixels[row * 32 + col] = 31.0
        result = body_model.analyse(pixels, 0.8)
        self.assertIsNotNone(result)
        self.assertIsNone(result["surface_temp"])
