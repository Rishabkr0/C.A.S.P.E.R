import asyncio
import base64
import io
import json
import logging
import os
import pyautogui
from PIL import Image
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

VISION_SCHEMA = """
CRITICAL RULE: IGNORE the transparent 'casper Studio' overlay banner at the top of the screen! Do NOT attempt to click or close 'casper Studio'. Interact ONLY with the target app window (e.g. VS Code, Chrome, etc.).
FOLDER DIALOG RULE: When a File Open or Folder Select dialog is open, do NOT scroll! Type the folder/file name directly into the 'Folder:' or 'File name:' box and press Enter.

Respond ONLY with valid JSON, no other text:
{
  "reasoning": "what you see on the screen and why this action",
  "action": "click | double_click | right_click | type | key | scroll | done",
  "x": 640,
  "y": 360,
  "text": "text or full multiline code snippet to paste into active window (for type action)",
  "keys": "shortcut like 'ctrl+n' for new file, 'ctrl+s' for save, 'ctrl+k, ctrl+o' for open folder",
  "scroll_direction": "up | down",
  "scroll_amount": 3,
  "done_summary": "summary of what was accomplished (for done action)"
}
"""

def _capture_screen_scaled(max_dim=1280):
    """Captures the primary monitor and resizes for fast API transmission."""
    screenshot = pyautogui.screenshot()
    orig_w, orig_h = screenshot.size
    
    # Calculate scale factor
    scale = min(max_dim / max(orig_w, orig_h), 1.0)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)
    
    resized = screenshot.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    img_byte_arr = io.BytesIO()
    resized.save(img_byte_arr, format='JPEG', quality=85)
    img_bytes = img_byte_arr.getvalue()
    
    return img_bytes, orig_w, orig_h, new_w, new_h

async def vision_fallback_step(task: str, history: list) -> tuple[str, bool]:
    """
    Executes a single visual step using screen capture and Gemini/OpenRouter vision.
    Returns (summary, is_done).
    """
    try:
        # Auto-focus and restore target app dynamically for ANY application on PC
        task_lower = task.lower()
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                t = w.window_text().strip()
                if not t:
                    continue
                t_words = [word.lower() for word in t.split() if len(word) > 2 and word.lower() not in ("the", "and", "for", "with", "app", "window", "casper", "studio", "dashboard")]
                if any(w_word in task_lower for w_word in t_words):
                    if w.is_minimized():
                        w.restore()
                    w.set_focus()
                    await asyncio.sleep(0.3)
                    break
            except Exception:
                pass

        img_bytes, orig_w, orig_h, new_w, new_h = await asyncio.to_thread(_capture_screen_scaled)
        
        prompt = (
            f"You are visually controlling a Windows desktop to accomplish: {task}\n"
            f"Screen Resolution: {orig_w}x{orig_h} (Image provided scaled to {new_w}x{new_h}).\n"
            f"IMPORTANT: Return 'x' and 'y' coordinates in terms of the ORIGINAL {orig_w}x{orig_h} resolution!\n\n"
            f"History: {json.dumps(history[-3:])}\n\n"
            f"{VISION_SCHEMA}"
        )
        
        # Use ultra-fast Gemini 1.5 Flash Vision for sub-second responses (<1s)
        try:
            from google.genai import types
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            
            response = await client.aio.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[prompt, image_part],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            action = json.loads(response.text)
        except Exception as e:
            logging.warning(f"Gemini vision failed ({e}), checking OpenRouter fallback...")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                import requests
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                headers = {"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "openrouter/free",
                    "messages": [
                        {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]}
                    ],
                    "response_format": {"type": "json_object"}
                }
                resp = await asyncio.to_thread(requests.post, "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
                res_json = resp.json()
                content = res_json['choices'][0]['message']['content'].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                action = json.loads(content)

        logging.info(f"Vision Fallback Action: {action}")
        
        act_type = action.get("action")
        if act_type == "done":
            return action.get("done_summary", "Completed task visually."), True

        if act_type in ("click", "double_click", "right_click"):
            x = int(action.get("x", orig_w // 2))
            y = int(action.get("y", orig_h // 2))
            if act_type == "click":
                pyautogui.click(x, y)
            elif act_type == "double_click":
                pyautogui.doubleClick(x, y)
            elif act_type == "right_click":
                pyautogui.rightClick(x, y)
            
            # Immediately paste text if provided in same click step
            text_to_type = action.get("text", "").strip()
            if text_to_type:
                import time, pyperclip
                time.sleep(0.2)
                pyperclip.copy(text_to_type)
                pyautogui.hotkey("ctrl", "v")

        elif act_type == "type":
            import time
            text_to_type = action.get("text", "")
            if "\n" in text_to_type or len(text_to_type) > 10 or any(c in text_to_type for c in "{}[]()'\"=<>#;/\\"):
                try:
                    import pyperclip
                    pyperclip.copy(text_to_type)
                    time.sleep(0.1)
                    pyautogui.hotkey("ctrl", "v")
                except Exception:
                    pyautogui.write(text_to_type, interval=0.01)
            else:
                pyautogui.write(text_to_type, interval=0.03)

        elif act_type == "key":
            import time
            keys_str = action.get("keys", "")
            if "," in keys_str:
                for combo in keys_str.split(","):
                    combo = combo.strip()
                    if combo:
                        pyautogui.hotkey(*[k.strip() for k in combo.split("+")])
                        time.sleep(0.2)
            else:
                pyautogui.hotkey(*[k.strip() for k in keys_str.split("+")])

        elif act_type == "scroll":
            amt = action.get("scroll_amount", 3)
            direction = action.get("scroll_direction", "down")
            pyautogui.scroll(amt if direction == "up" else -amt)

        return action.get("reasoning", "Executed visual step."), False

    except Exception as e:
        logging.error(f"Vision Fallback Error: {e}")
        return f"Visual action failed: {str(e)}", True


SPOTIFY_VISION_PROMPT_HOVER = """
You are looking at a Spotify Desktop window showing search results for '{query}'.

YOUR TASK: Find the "Top result" card in the SEARCH RESULTS area (upper/center of screen) and return the coordinates of its CENTER so we can hover over it to reveal the play button.

CRITICAL RULES:
- The Spotify window has 3 zones from top to bottom:
  1. TOP BAR: Search box, navigation arrows, user avatar (very top ~60px)
  2. SEARCH RESULTS: "Top result" card on the left, "Songs" list on the right (this is the MAIN CONTENT area, roughly the middle 70% of the window)
  3. PLAYER BAR: Album art thumbnail, song progress bar, play/pause/skip buttons (the BOTTOM ~90px strip)

- You MUST click in zone 2 (SEARCH RESULTS area). NEVER return coordinates in the bottom player bar (zone 3)!
- The "Top result" is a large card on the LEFT side of the search results. It shows an artist/album image with the name below it.
- Return the CENTER coordinates of the "Top result" card image/artwork area.
- If there is NO "Top result" card, return coordinates of the FIRST song row in the "Songs" list on the right side.
- If search results are still loading, respond with action "wait".
- Return coordinates in the ORIGINAL {orig_w}x{orig_h} resolution.

Respond ONLY with valid JSON:
{{
  "reasoning": "describe what you see in the search results area",
  "action": "click | wait",
  "x": 640,
  "y": 360
}}
"""

SPOTIFY_VISION_PROMPT_CLICK = """
You are looking at a Spotify Desktop window. We just hovered over the Top Result card and a green circular Play button should now be visible on it.

YOUR TASK: Click the GREEN CIRCULAR PLAY BUTTON on the Top Result card to start playing '{query}'.

CRITICAL RULES:
- Look for the GREEN CIRCLE play button (▶) that appeared ON TOP of the "Top result" card artwork after hovering.
- This green button is IN THE SEARCH RESULTS AREA (upper/center of the screen), NOT at the bottom.
- DO NOT click the play/pause button in the BOTTOM PLAYER BAR (the thin strip at the very bottom with the progress bar). That would just resume the OLD song!
- The green play button on the Top Result card is larger and sits on top of the card artwork/image.
- If you see a green play button on the Top Result card, click it.
- If you DON'T see a green play button but see song rows in the "Songs" list, click the FIRST song title text.
- Return coordinates in the ORIGINAL {orig_w}x{orig_h} resolution.

Respond ONLY with valid JSON:
{{
  "reasoning": "describe where you see the green play button or first song",
  "action": "click | double_click",
  "x": 640,
  "y": 360
}}
"""


async def spotify_vision_play(query: str, max_steps: int = 3) -> str:
    """
    Uses vision to locate and click the Spotify Top Result / first song
    after opening a search via the spotify: URI scheme.
    Two-step approach: hover over Top Result card, then click the revealed play button.
    Returns a human-readable summary string.
    """
    import webbrowser

    # 1. Open Spotify search via URI
    webbrowser.open(f"spotify:search:{query}")
    await asyncio.sleep(3.5)

    # 2. Bring Spotify window to foreground
    try:
        import win32gui
        def _enum(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and "spotify" in win32gui.GetWindowText(hwnd).lower():
                win32gui.SetForegroundWindow(hwnd)
        win32gui.EnumWindows(_enum, None)
    except Exception:
        pass
    await asyncio.sleep(0.5)

    async def _call_vision(prompt_text: str, img_bytes: bytes):
        """Send screenshot + prompt to Gemini Vision (with OpenRouter fallback)."""
        action = None
        try:
            from google.genai import types
            image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
            response = await client.aio.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[prompt_text, image_part],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            action = json.loads(response.text)
        except Exception as e:
            logging.warning(f"Spotify vision Gemini failed ({e}), trying OpenRouter...")
            openrouter_key = os.getenv("OPENROUTER_API_KEY")
            if openrouter_key:
                import requests
                base64_image = base64.b64encode(img_bytes).decode('utf-8')
                headers = {"Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "openrouter/free",
                    "messages": [
                        {"role": "user", "content": [
                            {"type": "text", "text": prompt_text},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]}
                    ],
                    "response_format": {"type": "json_object"}
                }
                resp = await asyncio.to_thread(
                    requests.post, "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers, json=payload, timeout=15
                )
                res_json = resp.json()
                content = res_json['choices'][0]['message']['content'].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                action = json.loads(content)
        return action

    # 3. Vision loop with hover-then-click strategy
    for attempt in range(max_steps):
        try:
            # --- Step A: Capture screen and find the Top Result card to hover ---
            img_bytes, orig_w, orig_h, new_w, new_h = await asyncio.to_thread(_capture_screen_scaled)

            hover_prompt = (
                SPOTIFY_VISION_PROMPT_HOVER.format(query=query, orig_w=orig_w, orig_h=orig_h)
                + f"\nScreen: {orig_w}x{orig_h} (image scaled to {new_w}x{new_h})."
                + f"\nReturn x,y in ORIGINAL {orig_w}x{orig_h} resolution!"
            )

            hover_action = await _call_vision(hover_prompt, img_bytes)
            if not hover_action:
                logging.error("Spotify vision hover step: no model response")
                continue

            logging.info(f"Spotify Vision hover attempt {attempt}: {hover_action}")

            if hover_action.get("action") == "wait":
                logging.info("Spotify vision: search still loading, waiting...")
                await asyncio.sleep(2.5)
                continue

            hx = int(hover_action.get("x", orig_w // 3))
            hy = int(hover_action.get("y", orig_h // 3))

            # Sanity check: reject if coordinates are in the bottom 15% (player bar zone)
            player_bar_threshold = int(orig_h * 0.85)
            if hy > player_bar_threshold:
                logging.warning(f"Spotify vision: hover target ({hx},{hy}) is in player bar zone (y>{player_bar_threshold}), adjusting...")
                # Move to the center of the search results area instead
                hy = int(orig_h * 0.45)
                hx = int(orig_w * 0.30)

            # Hover over the Top Result card to reveal the green play button
            logging.info(f"Spotify vision: hovering over Top Result at ({hx}, {hy})")
            pyautogui.moveTo(hx, hy)
            await asyncio.sleep(1.0)  # Wait for hover state to render the green play button

            # --- Step B: Capture screen AGAIN and click the now-visible green play button ---
            img_bytes2, orig_w2, orig_h2, new_w2, new_h2 = await asyncio.to_thread(_capture_screen_scaled)

            click_prompt = (
                SPOTIFY_VISION_PROMPT_CLICK.format(query=query, orig_w=orig_w2, orig_h=orig_h2)
                + f"\nScreen: {orig_w2}x{orig_h2} (image scaled to {new_w2}x{new_h2})."
                + f"\nReturn x,y in ORIGINAL {orig_w2}x{orig_h2} resolution!"
            )

            click_action = await _call_vision(click_prompt, img_bytes2)
            if not click_action:
                logging.error("Spotify vision click step: no model response, falling back to hover position click")
                pyautogui.click(hx, hy)
                return f"Played '{query}' on Spotify (fallback click at {hx},{hy})."

            logging.info(f"Spotify Vision click attempt {attempt}: {click_action}")

            cx = int(click_action.get("x", hx))
            cy = int(click_action.get("y", hy))

            # Sanity check again: reject player bar clicks
            if cy > player_bar_threshold:
                logging.warning(f"Spotify vision: click target ({cx},{cy}) in player bar, using hover position instead")
                cx, cy = hx, hy

            act_type = click_action.get("action", "click")
            logging.info(f"Spotify vision: clicking play button at ({cx}, {cy})")
            if act_type == "double_click":
                pyautogui.doubleClick(cx, cy)
            else:
                pyautogui.click(cx, cy)

            return f"Played '{query}' on Spotify (vision click at {cx},{cy})."

        except Exception as e:
            logging.error(f"Spotify vision attempt {attempt} error: {e}")
            continue

    return f"Spotify vision: could not locate play button for '{query}' after {max_steps} attempts."

