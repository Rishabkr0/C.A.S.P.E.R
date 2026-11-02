import unittest
import math
from PIL import Image
from screen_vision.gesture_detector import _check_circle_geometry
from screen_vision.visual_memory import set_focused_region, get_active_focus
from screen_vision.screen_streamer import ScreenVideoInput
from screen_vision.tools import inspect_focused_screen_area


class TestScreenVision(unittest.TestCase):

    def test_circle_geometry_detection(self):
        # 1. Synthetic smooth circular trajectory (radius 120, 30 points)
        cx, cy, r = 400, 400, 120
        pts = [
            (int(cx + r * math.cos(2 * math.pi * i / 28)), int(cy + r * math.sin(2 * math.pi * i / 28)))
            for i in range(29)
        ]
        is_circle, bbox = _check_circle_geometry(pts)
        self.assertTrue(is_circle, "Failed to detect synthetic circular loop")
        self.assertIsNotNone(bbox)
        self.assertGreaterEqual(bbox[2] - bbox[0], 200)

        # 2. Synthetic straight horizontal line (should reject)
        line_pts = [(100 + i * 15, 200) for i in range(30)]
        is_circle_line, _ = _check_circle_geometry(line_pts)
        self.assertFalse(is_circle_line, "Incorrectly flagged a straight line as a circle")

        # 3. Small jitter (fidgeting, radius 15px - should reject)
        jitter_pts = [
            (int(200 + 15 * math.cos(2 * math.pi * i / 20)), int(200 + 15 * math.sin(2 * math.pi * i / 20)))
            for i in range(21)
        ]
        is_circle_jitter, _ = _check_circle_geometry(jitter_pts)
        self.assertFalse(is_circle_jitter, "Incorrectly flagged tiny jitter as an intentional circle")

    def test_visual_memory_buffering(self):
        test_img = Image.new("RGB", (160, 120), color=(0, 200, 100))
        bbox = (100, 100, 260, 220)
        set_focused_region(bbox, test_img, text_hint="test error widget")

        focus = get_active_focus(max_age_seconds=10.0)
        self.assertIsNotNone(focus)
        self.assertEqual(focus["bbox"], bbox)
        self.assertEqual(focus["width"], 160)
        self.assertEqual(focus["height"], 120)
        self.assertGreater(len(focus["image_bytes"]), 0)

    def test_screen_streamer_on_demand(self):
        streamer = ScreenVideoInput(target_fps=1.0, max_dim=1024)
        self.assertFalse(streamer.is_enabled)
        streamer.enable()
        self.assertTrue(streamer.is_enabled)
        streamer.disable()
        self.assertFalse(streamer.is_enabled)
        streamer.stop()

    def test_inspect_tool_attributes(self):
        from screen_vision.tools import start_screen_vision, stop_screen_vision
        self.assertTrue(callable(inspect_focused_screen_area))
        self.assertTrue(callable(start_screen_vision))
        self.assertTrue(callable(stop_screen_vision))


if __name__ == "__main__":
    unittest.main()
