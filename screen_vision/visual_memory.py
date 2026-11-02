import time
import io
import os
import base64
import logging
import asyncio
from typing import Optional, Tuple, Dict, Any
from PIL import Image

_active_focus: Optional[Dict[str, Any]] = None
_cached_genai_client = None

def _get_genai_client(api_key: str):
    global _cached_genai_client
    if _cached_genai_client is None:
        from google import genai
        _cached_genai_client = genai.Client(api_key=api_key)
    return _cached_genai_client

def set_focused_region(
    bbox: Tuple[int, int, int, int],
    image: Image.Image,
    text_hint: str = ""
) -> None:
    """
    Stores the most recently circled screen region into visual working memory.
    bbox is (min_x, min_y, max_x, max_y).
    """
    global _active_focus
    try:
        img_buffer = io.BytesIO()
        rgb_img = image.convert("RGB")
        # Ensure crop is not unnecessarily massive while preserving crisp legibility
        if rgb_img.width > 900 or rgb_img.height > 900:
            rgb_img.thumbnail((900, 900), Image.Resampling.BILINEAR)
        rgb_img.save(img_buffer, format="JPEG", quality=80)
        img_bytes = img_buffer.getvalue()

        _active_focus = {
            "bbox": bbox,
            "width": rgb_img.width,
            "height": rgb_img.height,
            "image_bytes": img_bytes,
            "timestamp": time.time(),
            "text_hint": text_hint
        }
        logging.info(
            f"[Visual Memory] Saved active focus bbox={bbox} ({rgb_img.width}x{rgb_img.height}) at {time.strftime('%X')}"
        )
    except Exception as e:
        logging.error(f"[Visual Memory] Failed to store focused region: {e}")

def get_active_focus(max_age_seconds: float = 30.0) -> Optional[Dict[str, Any]]:
    """
    Returns the active visual focus if it was captured within the last max_age_seconds.
    """
    global _active_focus
    if not _active_focus:
        return None
    
    age = time.time() - _active_focus.get("timestamp", 0)
    if age <= max_age_seconds:
        return _active_focus
    return None

def _capture_screen() -> Optional[Image.Image]:
    """Capture the active desktop with multiple fallback mechanisms."""
    try:
        from PIL import ImageGrab
        return ImageGrab.grab()
    except Exception as e:
        logging.debug(f"[Visual Memory] ImageGrab failed ({e}), trying mss fallback...")

    try:
        import mss
        with mss.MSS() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            sct_img = sct.grab(mon)
            return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    except Exception as e2:
        logging.error(f"[Visual Memory] Screen capture failed across all providers: {e2}")
        return None

async def inspect_focused_image(question: str = "") -> str:
    """
    Captures the user's active desktop screen in high resolution and sends it
    to Gemini Vision to answer the user's question with full screen context.
    """
    img_bytes = None
    context_prefix = ""

    # Primary: Capture Full Screen in High Definition
    try:
        import ctypes

        # Get current mouse cursor position on screen
        class _POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = _POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        cursor_pos = (int(pt.x), int(pt.y))

        screenshot = _capture_screen()
        if screenshot:
            orig_w, orig_h = screenshot.size
            img_buffer = io.BytesIO()
            rgb_img = screenshot.convert("RGB")

            # Scale preserving aspect ratio up to 1600px for sharp text & code readability
            if rgb_img.width > 1600 or rgb_img.height > 1200:
                rgb_img.thumbnail((1600, 1200), Image.Resampling.BILINEAR)

            rgb_img.save(img_buffer, format="JPEG", quality=85)
            img_bytes = img_buffer.getvalue()

            context_prefix = (
                f"This is the user's full active desktop screen (original resolution: {orig_w}x{orig_h}). "
                f"The user's mouse cursor is currently positioned at ({cursor_pos[0]}, {cursor_pos[1]}).\n"
            )
    except Exception as e:
        logging.error(f"[Visual Memory] Full screen capture processing error: {e}")

    # Fallback to cached focused crop if full screen was unavailable
    if not img_bytes:
        focus = get_active_focus(max_age_seconds=15.0)
        if focus:
            img_bytes = focus["image_bytes"]
            context_prefix = "Cached focused crop.\n"

    if not img_bytes:
        return "I was unable to capture your screen, Boss. Please make sure the window is visible."

    prompt_text = (
        f"{context_prefix}"
        f"User query / context: {question if question else 'Explain what is shown here in detail and identify any errors, text, code, or notable elements.'}\n"
        f"Respond articulately, concisely, and directly as Casper (the British JARVIS-style assistant). "
        f"Get straight to the answer without generic preamble."
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Visual inspection requires GEMINI_API_KEY to be configured in settings."

    try:
        from google.genai import types

        client = _get_genai_client(api_key)
        image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

        model_candidates = [
            os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview"),
            "gemini-3-flash-preview",
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]
        unique_models = list(dict.fromkeys(model_candidates))

        gen_config = types.GenerateContentConfig(temperature=0.2, max_output_tokens=300)

        for model_name in unique_models:
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_name,
                        contents=[prompt_text, image_part],
                        config=gen_config
                    ),
                    timeout=4.5
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as model_err:
                logging.warning(f"[Visual Memory] Model {model_name} failed or timed out: {model_err}")
                continue
    except Exception as e:
        logging.warning(f"[Visual Memory] Gemini vision direct call failed ({e}). Trying fallback...")

    # Optional OpenRouter fallback if configured
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            import requests
            b64_img = base64.b64encode(img_bytes).decode("utf-8")
            headers = {"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.0-flash-001",
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                        ]
                    }
                ]
            }
            res = await asyncio.to_thread(
                requests.post, "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=5.0
            )
            data = res.json()
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e2:
            logging.error(f"[Visual Memory] OpenRouter vision fallback failed: {e2}")

    return "I can see your active display, Boss, but the visual analysis encountered a brief delay. Please circle the specific item again or ask me directly."
