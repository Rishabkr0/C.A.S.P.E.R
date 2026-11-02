import time
import math
import socket
import json
import logging
import threading
import ctypes
from collections import deque
from typing import Optional, Tuple, List
from PIL import Image, ImageGrab

from .visual_memory import set_focused_region

# Ensure Windows DPI awareness so cursor coordinates match screen pixels 1:1
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_cursor_pos() -> Tuple[int, int]:
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _check_circle_geometry(points: List[Tuple[int, int]]) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """
    Evaluates whether a list of sequential points forms a deliberate closed circular loop.
    Returns (is_circle, (min_x, min_y, max_x, max_y)).
    """
    if len(points) < 18:
        return False, None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    w = max_x - min_x
    h = max_y - min_y

    # Diameter bounds (between 70px and 850px)
    if w < 70 or h < 70 or w > 850 or h > 850:
        return False, None

    # Aspect ratio check: roughly circular or elliptical
    aspect = w / h if h != 0 else 0
    if aspect < 0.38 or aspect > 2.6:
        return False, None

    # Closure check: start and end points must terminate near each other
    start_p = points[0]
    end_p = points[-1]
    closure_dist = math.hypot(end_p[0] - start_p[0], end_p[1] - start_p[1])
    if closure_dist > 0.45 * max(w, h):
        return False, None

    # Centroid of the gesture
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)

    # Calculate cumulative angular sweep around centroid
    angles = [math.atan2(p[1] - cy, p[0] - cx) for p in points]
    deltas = []
    total_angle = 0.0

    for i in range(1, len(angles)):
        d = angles[i] - angles[i - 1]
        while d > math.pi:
            d -= 2 * math.pi
        while d < -math.pi:
            d += 2 * math.pi
        deltas.append(d)
        total_angle += d

    # Must complete at least ~280 degrees in a single dominant direction
    if abs(total_angle) < (math.pi * 1.55):
        return False, None

    # Rotational direction consistency check (rules out jitter/zigzags)
    positive_count = sum(1 for d in deltas if d > 0.02)
    negative_count = sum(1 for d in deltas if d < -0.02)
    dom_count = max(positive_count, negative_count)

    if dom_count < 0.65 * len(deltas):
        return False, None

    return True, (int(min_x), int(min_y), int(max_x), int(max_y))


_global_gesture_detector: Optional['CircleGestureDetector'] = None

def get_gesture_detector() -> Optional['CircleGestureDetector']:
    return _global_gesture_detector

class CircleGestureDetector:
    """
    Background worker that monitors cursor motion and detects intentional
    circular gestures around objects or text on screen with zero keyboard interaction.
    Operates on-demand when Vision Mode is engaged.
    """

    def __init__(self, udp_port: int = 49152):
        global _global_gesture_detector
        self._running = False
        self._enabled = False
        self._thread: Optional[threading.Thread] = None
        self._points = deque(maxlen=85)
        self._last_trigger_time = 0.0
        self._cooldown_seconds = 1.4
        self._udp_port = udp_port
        _global_gesture_detector = self

    def enable(self):
        """Enables cursor tracking and gesture evaluation."""
        self._enabled = True
        logging.info("[Gesture Detector] Circle gesture tracking ACTIVATED")

    def disable(self):
        """Pauses gesture tracking (0% CPU)."""
        self._enabled = False
        self._points.clear()
        logging.info("[Gesture Detector] Circle gesture tracking DEACTIVATED (dormant)")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="CasperGestureDetector", daemon=True)
        self._thread.start()
        logging.info("[Gesture Detector] Background gesture worker started (dormant by default)")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logging.info("[Gesture Detector] Gesture tracking stopped")

    def _broadcast_circle_event(self, bbox: Tuple[int, int, int, int]):
        """Notifies the Electron/PySide transparent overlay to draw a holographic pulse."""
        try:
            min_x, min_y, max_x, max_y = bbox
            payload = json.dumps({
                "x": min_x,
                "y": min_y,
                "w": max_x - min_x,
                "h": max_y - min_y
            })
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(f"CIRCLE:{payload}".encode("utf-8"), ("127.0.0.1", self._udp_port))
            sock.close()
        except Exception as e:
            logging.debug(f"[Gesture Detector] UDP broadcast error: {e}")

    def _capture_and_store_crop(self, bbox: Tuple[int, int, int, int]):
        """Crops the focused region at 100% native resolution and stores it in VisualMemory."""
        min_x, min_y, max_x, max_y = bbox
        try:
            # Add small 20px padding around the circled area
            pad = 20
            crop_box = (
                max(0, min_x - pad),
                max(0, min_y - pad),
                max_x + pad,
                max_y + pad
            )
            # Use ImageGrab to capture the exact native pixels
            cropped_img = ImageGrab.grab(bbox=crop_box)
            set_focused_region(bbox, cropped_img)
            self._broadcast_circle_event(bbox)
        except Exception as e:
            logging.warning(f"[Gesture Detector] Failed to crop focused area: {e}")

    def _run_loop(self):
        last_eval_time = 0.0

        while self._running:
            if not self._enabled:
                time.sleep(0.1)
                continue

            time.sleep(0.018)  # ~55 Hz polling rate for smooth trajectory sampling
            try:
                pos = _get_cursor_pos()
                self._points.append(pos)

                now = time.time()
                # Run evaluation every ~50ms if cooldown expired
                if now - self._last_trigger_time < self._cooldown_seconds:
                    continue

                if now - last_eval_time < 0.05:
                    continue

                last_eval_time = now

                # Evaluate varying window lengths (between 22 and 75 samples)
                n = len(self._points)
                pts_list = list(self._points)

                for length in range(22, min(n, 75), 4):
                    sub = pts_list[-length:]
                    is_circle, bbox = _check_circle_geometry(sub)
                    if is_circle and bbox:
                        self._last_trigger_time = now
                        logging.info(f"[Gesture Detector] Deliberate circle detected at {bbox}!")
                        # Capture crop asynchronously in separate thread so tracking doesn't stutter
                        threading.Thread(
                            target=self._capture_and_store_crop,
                            args=(bbox,),
                            daemon=True
                        ).start()
                        self._points.clear()
                        break

            except Exception as e:
                # Keep loop resilient
                pass
