"""
C.A.S.P.E.R. Screen Vision & Autonomous Gesture Tracking Package
Provides on-demand ambient screen streaming (1 FPS peripheral vision)
and kinematic circle gesture tracking for foveal high-res inspections.
"""

from .screen_streamer import ScreenVideoInput, get_screen_streamer
from .gesture_detector import CircleGestureDetector, get_gesture_detector
from .visual_memory import set_focused_region, get_active_focus, inspect_focused_image
from .tools import start_screen_vision, stop_screen_vision, inspect_focused_screen_area

__all__ = [
    "ScreenVideoInput",
    "get_screen_streamer",
    "CircleGestureDetector",
    "get_gesture_detector",
    "set_focused_region",
    "get_active_focus",
    "inspect_focused_image",
    "start_screen_vision",
    "stop_screen_vision",
    "inspect_focused_screen_area"
]
