import asyncio
import logging
from typing import Optional, Tuple
from PIL import Image, ImageGrab
from livekit import rtc
from livekit.agents.voice.io import VideoInput

_global_screen_streamer: Optional['ScreenVideoInput'] = None

def get_screen_streamer() -> Optional['ScreenVideoInput']:
    return _global_screen_streamer

class ScreenVideoInput(VideoInput):
    """
    Continuous screen video streamer that captures the primary desktop
    at ~1 FPS, scales it appropriately, and streams VideoFrames into Casper's
    multimodal LiveKit / Gemini Realtime session on demand.
    """

    def __init__(self, target_fps: float = 1.0, max_dim: int = 1024):
        global _global_screen_streamer
        super().__init__(label="casper_screen_streamer")
        self.target_fps = target_fps
        self.max_dim = max_dim
        self._running = True
        self._enabled = False
        self._enable_event = asyncio.Event()
        self._last_frame_bytes: Optional[bytes] = None
        self._last_frame_w = 640
        self._last_frame_h = 360
        _global_screen_streamer = self

    def enable(self):
        """Enables screen capture streaming."""
        self._enabled = True
        self._enable_event.set()
        logging.info("[Screen Streamer] Screen vision mode ACTIVATED")

    def disable(self):
        """Pauses screen capture streaming (0% CPU)."""
        self._enabled = False
        self._enable_event.clear()
        logging.info("[Screen Streamer] Screen vision mode DEACTIVATED (dormant)")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def _capture_and_process_frame(self) -> Tuple[int, int, bytes]:
        """Runs in worker thread: captures desktop and converts to RGBA buffer."""
        try:
            screenshot = ImageGrab.grab()
        except Exception:
            # Fallback if display is momentarily inaccessible
            if self._last_frame_bytes:
                return self._last_frame_w, self._last_frame_h, self._last_frame_bytes
            blank = Image.new("RGBA", (self._last_frame_w, self._last_frame_h), color=(15, 15, 20, 255))
            return blank.width, blank.height, blank.tobytes()

        # Scale down maintaining aspect ratio for optimal Gemini real-time throughput
        orig_w, orig_h = screenshot.size
        scale = min(self.max_dim / max(orig_w, orig_h), 1.0)
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)

        # Ensure dimensions are even (required by most video pipelines)
        if new_w % 2 != 0:
            new_w -= 1
        if new_h % 2 != 0:
            new_h -= 1

        resized = screenshot.resize((new_w, new_h), Image.Resampling.BILINEAR)
        rgba_img = resized.convert("RGBA")
        raw_bytes = rgba_img.tobytes()

        self._last_frame_bytes = raw_bytes
        self._last_frame_w = new_w
        self._last_frame_h = new_h

        return new_w, new_h, raw_bytes

    async def __anext__(self) -> rtc.VideoFrame:
        if not self._running:
            raise StopAsyncIteration

        # Wait dormant until vision mode is explicitly requested by user (0% CPU)
        if not self._enabled:
            await self._enable_event.wait()
            if not self._running:
                raise StopAsyncIteration

        # Stream at steady interval (e.g. 1.0s for 1 FPS)
        interval = 1.0 / max(0.2, self.target_fps)
        await asyncio.sleep(interval)

        # Offload capture and PIL operations to background thread pool
        w, h, data = await asyncio.to_thread(self._capture_and_process_frame)

        return rtc.VideoFrame(
            width=w,
            height=h,
            type=rtc.VideoBufferType.RGBA,
            data=data
        )

    def stop(self):
        self._running = False
        logging.info("[Screen Streamer] Screen video streaming stopped")
