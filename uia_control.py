import asyncio, json, logging, os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
_uia_lock = asyncio.Lock()
_uia_cancel = asyncio.Event()

UIA_SCHEMA = """
CRITICAL RULE: IGNORE the transparent 'casper Studio' overlay banner at the top of the screen! Do NOT attempt to click or focus 'casper Studio'. Interact ONLY with the target app window (e.g. VS Code, Chrome, etc.).
FOLDER DIALOG RULE: When a File Open or Folder Select dialog is open, do NOT scroll! Type the folder/file name directly into the 'Folder:' or 'File name:' box and press Enter.

Respond ONLY with valid JSON, no other text:
{
  "reasoning": "what you observe and why this action",
  "action": "focus_window | click | double_click | right_click | type | key | scroll | open_app | done",
  "window_title": "title of window to focus (for focus_window)",
  "app_name": "name of application or command like 'code <folder_path>' (for open_app)",
  "element_name": "exact name of UI element (for click/double_click/right_click)",
  "element_type": "Button | Edit | TreeItem | ListItem | MenuItem (optional)",
  "text": "text or full multiline code snippet to paste into active window (for type)",
  "keys": "shortcut like 'ctrl+n' for new file, 'ctrl+s' for save, 'ctrl+k, ctrl+o' for open folder",
  "scroll_direction": "up | down",
  "scroll_amount": 3,
  "done_summary": "summary of what was accomplished (for done)"
}
"""

def _get_ui_state(focused_window_title: str = None, task: str = "") -> tuple[str, object]:
    """Read current UI state as structured text. Returns (description, window_ref)."""
    from pywinauto import Desktop
    desktop = Desktop(backend="uia")

    # List all visible windows
    windows = []
    for w in desktop.windows():
        try:
            title = w.window_text().strip()
            if title:
                windows.append(title)
        except Exception:
            pass
    window_list = "\n".join(f'  - "{t}"' for t in windows[:15])

    # If no window explicitly focused yet, auto-match dynamically from task for ANY app
    if not focused_window_title and task:
        task_lower = task.lower()
        for t in windows:
            t_words = [word.lower() for word in t.split() if len(word) > 2 and word.lower() not in ("the", "and", "for", "with", "app", "window", "casper", "studio", "dashboard")]
            if any(w_word in task_lower for w_word in t_words):
                focused_window_title = t
                break

    # Get controls for the focused window
    controls_text = ""
    window_ref = None
    if focused_window_title:
        try:
            window_ref = desktop.window(title_re=f".*{focused_window_title}.*")
            try:
                if window_ref.is_minimized():
                    window_ref.restore()
            except Exception:
                pass
            window_ref.set_focus()
            controls = []
            for ctrl in window_ref.descendants():
                try:
                    name = ctrl.window_text().strip()
                    ctype = ctrl.friendly_class_name()
                    if name and ctrl.is_visible():
                        controls.append(f'  {ctype}: "{name}"' + ('' if ctrl.is_enabled() else ' [disabled]'))
                except Exception:
                    pass
            if controls:
                controls_text = f"\nControls in \"{focused_window_title}\":\n" + "\n".join(controls[:50])
        except Exception as e:
            controls_text = f"\n(Could not read controls for \"{focused_window_title}\": {e})"

    return f"Open Windows:\n{window_list}{controls_text}", window_ref


def _execute_uia(action: dict, window_ref) -> object:
    """Execute a UIA action. Returns updated window_ref if window changed."""
    from pywinauto import Desktop
    import pyautogui

    a = action["action"]

    if a == "focus_window":
        title = action.get("window_title", "")
        w = Desktop(backend="uia").window(title_re=f".*{title}.*")
        try:
            if w.is_minimized():
                w.restore()
        except Exception:
            pass
        w.set_focus()
        return w

    elif a in ("click", "double_click", "right_click"):
        if window_ref is None:
            raise ValueError("No window focused — use focus_window first")
        name = action.get("element_name", "")
        ctype = action.get("element_type")
        kwargs = {"title": name}
        if ctype:
            kwargs["control_type"] = ctype
        ctrl = window_ref.child_window(**kwargs)
        ctrl.set_focus()
        if a == "click":
            ctrl.click_input()
        elif a == "double_click":
            ctrl.double_click_input()
        elif a == "right_click":
            ctrl.right_click_input()

    elif a == "type":
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

    elif a == "key":
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

    elif a == "open_app":
        app_name = action.get("app_name", "")
        from computer_use import launch_app
        launch_app(app_name)

    elif a == "scroll":
        amt = action.get("scroll_amount", 3)
        pyautogui.scroll(amt if action.get("scroll_direction") == "up" else -amt)

    return window_ref


async def uia_loop(task: str, max_steps: int = 20) -> str:
    """
    Control the PC using Windows UI Automation — reads actual UI element tree,
    no screenshot, no vision model, no coordinate guessing.
    Falls back with UIANotSupportedError if the target app doesn't support UIA.
    """
    if _uia_lock.locked():
        _uia_cancel.set()          # signal the running loop to stop
        await asyncio.sleep(0.3)   # give it a moment to notice

    _uia_cancel.clear()
    async with _uia_lock:
        history = []
        focused_window = None
        window_ref = None

        for step in range(max_steps):
            if _uia_cancel.is_set():
                logging.info("UIA loop cancelled — new task incoming")
                return "Previous task cancelled."

            state_text, window_ref = await asyncio.to_thread(_get_ui_state, focused_window, task)

            prompt = (
                f"You are controlling a Windows PC to accomplish: {task}\n\n"
                f"Current UI state (no screenshot — this is the actual element tree):\n{state_text}\n\n"
                f"Steps so far: {json.dumps(history[-5:])}\n\n"
                f"To interact with an app: first 'focus_window', then 'click' using the exact "
                f"element name from the controls list above.\n\n"
                f"{UIA_SCHEMA}"
            )

            try:
                api_task = asyncio.create_task(
                    client.aio.models.generate_content(
                        model="gemini-3.5-flash-lite",
                        contents=[prompt],  # text only — no image at all
                        config=genai.types.GenerateContentConfig(
                            response_mime_type="application/json"
                        )
                    )
                )
                cancel_task = asyncio.create_task(_uia_cancel.wait())

                done, pending = await asyncio.wait(
                    [api_task, cancel_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                if cancel_task in done:
                    api_task.cancel()
                    logging.info("UIA loop cancelled during API call.")
                    return "Previous task cancelled."

                response = api_task.result()
                action = json.loads(response.text)
            except json.JSONDecodeError as e:
                logging.error(f"UIA bad JSON at step {step}: {e}")
                continue
            except Exception as e:
                error_str = str(e)
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    logging.warning(f"Gemini 503 at step {step}, retrying in 3s...")
                    await asyncio.sleep(3)
                    continue
                if "429" in error_str:
                    return "Task failed: Tell Sir that you have reached the daily quota limit for the Gemini API."
                if "404" in error_str:
                    return "Task failed: Tell Sir that the Gemini model assigned to you is currently unsupported or offline on Google's servers."
                logging.error(f"UIA API error: {error_str}")
                return f"Task failed: {error_str}"

            logging.info(f"UIA Step {step}: {action}")
            history.append({"action": action.get("action"), "reasoning": action.get("reasoning", "")})

            if action["action"] == "done":
                return action.get("done_summary", "Task completed.")

            if action["action"] == "focus_window":
                focused_window = action.get("window_title", focused_window)

            try:
                window_ref = await asyncio.to_thread(_execute_uia, action, window_ref)
            except Exception as e:
                logging.warning(f"UIA action failed at step {step}: {e}")
                history[-1]["error"] = str(e)

            await asyncio.sleep(0.5)

        return "Reached max steps without completing. Stopped for safety."


class UIANotSupportedError(Exception):
    pass
