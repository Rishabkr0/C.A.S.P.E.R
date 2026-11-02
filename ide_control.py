import os
import sys
import time
import json
import logging
import asyncio
import io
import re
from typing import Optional, Tuple, Dict, Any

from PIL import Image
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
logger = logging.getLogger("ide_control")

IDE_PROCESS_NAMES = [
    "antigravity ide.exe",
    "code.exe",
    "cursor.exe",
    "windsurf.exe",
    "pycharm64.exe",
    "pycharm.exe",
    "idea64.exe",
    "idea.exe",
    "sublime_text.exe",
    "notepad++.exe",
    "notepad.exe",
]

def find_file_on_disk(filename: str) -> Optional[str]:
    """Searches workspace, Documents, Desktop, and Downloads for the exact source file."""
    if not filename:
        return None

    if os.path.isabs(filename) and os.path.isfile(filename):
        return filename

    basename = os.path.basename(filename).strip().lower()
    search_roots = [
        os.path.dirname(os.path.abspath(__file__)),
        os.path.join(os.path.expanduser("~"), "Documents"),
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
    ]

    for root in search_roots:
        if not os.path.exists(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            if any(skip in dirpath.lower() for skip in [".git", "node_modules", ".venv", "__pycache__", "casper_chrome_profile", "appdata"]):
                continue
            for f in filenames:
                if f.lower() == basename:
                    candidate = os.path.join(dirpath, f)
                    if os.path.isfile(candidate):
                        return candidate

    return None

def get_ide_window_info() -> Dict[str, Any]:
    """
    Finds the active IDE window (VS Code, Antigravity IDE, Cursor, PyCharm, etc.),
    extracts the HWND, window title, and active filename if present in the title.
    """
    info = {
        "hwnd": None,
        "title": "",
        "ide_name": "VS Code",
        "active_filename": "",
        "rect": None,
    }

    try:
        import win32gui
        import win32process
        import psutil
        import ctypes

        ide_windows = []

        # Check foreground window first
        fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
        if fg_hwnd:
            try:
                fg_title = win32gui.GetWindowText(fg_hwnd).strip()
                fg_low = fg_title.lower()
                if any(k in fg_low for k in ["visual studio code", "antigravity", "cursor", "windsurf", "pycharm", "sublime", "notepad++"]):
                    ide_windows.append((fg_hwnd, fg_title, "foreground_ide", None))
            except Exception:
                pass

        def enum_windows_callback(hwnd, _):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd).strip()
                    if title:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            proc = psutil.Process(pid)
                            pname = proc.name().lower()
                            for ide_proc in IDE_PROCESS_NAMES:
                                if ide_proc in pname:
                                    ide_windows.append((hwnd, title, pname, proc))
                                    break
                        except Exception:
                            title_low = title.lower()
                            if any(k in title_low for k in ["visual studio code", "antigravity", "cursor", "windsurf", "pycharm", "sublime", "notepad++"]):
                                ide_windows.append((hwnd, title, "editor", None))
            except Exception:
                pass
            return 1

        try:
            win32gui.EnumWindows(enum_windows_callback, None)
        except Exception:
            pass

        if ide_windows:
            chosen_hwnd, chosen_title, chosen_pname, _ = ide_windows[0]
            for h, t, p, _ in ide_windows:
                if any(ext in t.lower() for ext in [".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".rs", ".go", ".cpp", ".c"]):
                    chosen_hwnd, chosen_title, chosen_pname = h, t, p
                    break

            info["hwnd"] = chosen_hwnd
            info["title"] = chosen_title
            try:
                info["rect"] = win32gui.GetWindowRect(chosen_hwnd)
            except Exception:
                pass

            if "antigravity" in chosen_pname or "antigravity" in chosen_title.lower():
                info["ide_name"] = "Antigravity IDE"
            elif "cursor" in chosen_pname or "cursor" in chosen_title.lower():
                info["ide_name"] = "Cursor"
            elif "windsurf" in chosen_pname or "windsurf" in chosen_title.lower():
                info["ide_name"] = "Windsurf"
            elif "pycharm" in chosen_pname or "pycharm" in chosen_title.lower():
                info["ide_name"] = "PyCharm"
            else:
                info["ide_name"] = "Visual Studio Code"

            cleaned_title = chosen_title.lstrip("● \t")
            parts = cleaned_title.split(" - ")
            if parts:
                candidate = parts[0].strip()
                if "." in candidate and not candidate.startswith("Visual Studio"):
                    info["active_filename"] = candidate

    except Exception as e:
        logger.warning(f"Error enumerating IDE windows: {e}")

    return info

def bring_window_to_front(hwnd: int) -> bool:
    """Forces an IDE window to the foreground using Win32 API."""
    if not hwnd:
        return False
    try:
        import ctypes
        user32 = ctypes.windll.user32

        user32.ShowWindow(hwnd, 9)
        current_thread_id = user32.GetCurrentThreadId()
        window_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
        user32.AttachThreadInput(current_thread_id, window_thread_id, True)
        user32.SetForegroundWindow(hwnd)
        user32.BringWindowToTop(hwnd)
        user32.SetFocus(hwnd)
        user32.AttachThreadInput(current_thread_id, window_thread_id, False)
        time.sleep(0.15)
        return True
    except Exception as e:
        logger.warning(f"Failed to bring window to front: {e}")
        return False

def capture_screen_image(rect: Optional[Tuple[int, int, int, int]] = None) -> Tuple[Optional[bytes], int, int]:
    """Captures the IDE window or screen as high-quality JPEG bytes."""
    img = None
    try:
        from PIL import ImageGrab
        if rect and (rect[2] - rect[0] > 100) and (rect[3] - rect[1] > 100):
            img = ImageGrab.grab(bbox=rect)
        else:
            img = ImageGrab.grab()
    except Exception:
        pass

    if img is None:
        try:
            import pyautogui
            img = pyautogui.screenshot()
        except Exception:
            pass

    if img is None:
        return None, 0, 0

    w, h = img.size
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue(), w, h

def extract_filename_from_prompt(prompt: str) -> Optional[str]:
    """Extracts mentioned filename like test.py from user instruction."""
    if not prompt:
        return None
    # Avoid matching inside code blocks or deep inside code text
    search_text = prompt.split("```")[0] if "```" in prompt else prompt
    first_part = search_text[:250]
    match = re.search(r'\b(?!(?:self|this|os|sys|time|math|json|re)\.)[a-zA-Z0-9_\-]+\.(?:py|js|ts|html|css|json|cpp|jsx|tsx|rs|go)\b', first_part, re.IGNORECASE)
    if match:
        return match.group(0)
    return None

def extract_code_from_text(text: str) -> Optional[str]:
    """Extracts code if pasted directly into user prompt."""
    if not text:
        return None
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            code = parts[1].strip()
            lines = code.split("\n")
            if lines and lines[0].strip().lower() in ["python", "py", "javascript", "js", "html", "css", "ts", "json", "c", "cpp"]:
                return "\n".join(lines[1:]).strip()
            return code
    if any(k in text for k in ["import ", "def ", "class ", "from "]) and "\n" in text:
        lines = [line for line in text.split("\n") if line.strip()]
        code_lines = [l for l in lines if any(l.strip().startswith(kw) for kw in ["import ", "from ", "class ", "def ", "if ", "for ", "while ", "return ", "self.", "#"])]
        if len(code_lines) >= 3:
            return text.strip()
    return None

def jump_and_replace_line_in_ide(
    line_number: int,
    fixed_code: str,
    hwnd: Optional[int] = None,
    file_path: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Directly navigates to a specific line number in the active IDE via Ctrl+G,
    replaces the line with fixed_code, and saves the file.
    Also synchronizes to disk if file_path is provided.
    """
    import pyautogui
    import pyperclip

    try:
        if hwnd:
            bring_window_to_front(hwnd)
            time.sleep(0.12)
            # Jump to line: Ctrl+G, type line_number, Enter
            pyautogui.hotkey("ctrl", "g")
            time.sleep(0.08)
            pyautogui.write(str(line_number))
            time.sleep(0.05)
            pyautogui.press("enter")
            time.sleep(0.08)

            # Select the entire line: Home -> Shift+End
            pyautogui.press("home")
            time.sleep(0.02)
            pyautogui.hotkey("shift", "end")
            time.sleep(0.02)

            # Paste fixed code
            pyperclip.copy(fixed_code)
            time.sleep(0.02)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.05)

            # Save
            pyautogui.hotkey("ctrl", "s")
            time.sleep(0.08)

        # Sync disk file if path exists
        if file_path and os.path.isfile(file_path):
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            if 1 <= line_number <= len(lines):
                lines[line_number - 1] = fixed_code + ("\n" if not fixed_code.endswith("\n") else "")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)

        return True, f"Navigated to line {line_number}, applied the fix, and saved the file."
    except Exception as e:
        logger.error(f"Error in jump_and_replace_line_in_ide: {e}")
        return False, f"Failed to navigate and edit line {line_number}: {e}"

async def diagnose_and_fix_code(
    code_text: str,
    screenshot_bytes: Optional[bytes] = None,
    user_instruction: str = "",
    filename: str = ""
) -> Dict[str, Any]:
    """
    Performs a deep holistic architectural & syntax audit of the code using Gemini 3.5 Flash Lite.
    Identifies all concurrency race conditions, deadlocks, graph bugs, thread safety issues,
    and syntax errors, and returns the 100% complete fixed code + JARVIS voice summary.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()

    prompt = (
        "You are an elite principal software engineer and debugging specialist (acting as Casper / JARVIS).\n"
        f"Active File: '{filename or 'code'}'\n"
        f"User Prompt / Context: '{user_instruction}'\n\n"
        "SOURCE CODE CURRENTLY IN THE USER'S EDITOR:\n"
        "```\n"
        f"{code_text}\n"
        "```\n\n"
        "DEBUGGING DIRECTIVES:\n"
        "1. Perform a thorough, holistic audit of the ENTIRE script. Do NOT stop at the first error or single-line syntax issues.\n"
        "2. Check for all categories of bugs:\n"
        "   - Concurrency & Threading: Race conditions, unhandled thread synchronization, premature crashes, deadlocks, missing events/locks, unprotected shared state.\n"
        "   - Algorithmic & Graph logic: Infinite loops, cycle detection flaws, recursion issues, edge cases.\n"
        "   - Error handling & Flow control: Premature exceptions, unhandled None/missing keys, invalid dictionary/list access.\n"
        "   - Syntax & Typographical: Missing colons, unclosed brackets/parentheses, wrong variable names, indentation errors.\n"
        "3. Produce the COMPLETE, 100% WORKING FIXED CODE for the entire file. Include all imports, classes, functions, and runnable code. Ensure the fixed code runs cleanly from start to finish without raising unexpected exceptions or deadlocking.\n"
        "4. Provide a clear, natural, spoken JARVIS-style voice summary (1-3 sentences) explaining what was broken and that the complete fix has been applied to their editor.\n\n"
        "Respond ONLY with valid JSON in this exact structure (no markdown fences around the JSON):\n"
        "{\n"
        '  "has_bug": true,\n'
        '  "bugs_found": [\n'
        '    "Detailed explanation of bug 1 and its location",\n'
        '    "Detailed explanation of bug 2 and its location"\n'
        '  ],\n'
        '  "full_fixed_code": "complete working code here",\n'
        '  "voice_summary": "Boss, I analyzed your code and found [summary of issues]. I have refactored and fixed all issues across the file and saved it in your editor."\n'
        "}"
    )

    contents = []
    if screenshot_bytes:
        contents.append(types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"))
    contents.append(prompt)

    # Try gemini-3-flash-preview, fallback to gemini-3.5-flash-lite if needed
    for model_name in ["gemini-3-flash-preview", "gemini-3.5-flash-lite"]:
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(temperature=0.1)
            )
            raw_text = response.text.strip()
            
            # Robust JSON extraction
            if "```json" in raw_text:
                raw_text = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                raw_text = raw_text.split("```")[1].split("```")[0].strip()

            start_idx = raw_text.find("{")
            end_idx = raw_text.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                raw_text = raw_text[start_idx:end_idx+1]

            data = json.loads(raw_text)

            # Python syntax verification safeguard
            fixed_code = data.get("full_fixed_code", "")
            is_py = (filename and filename.endswith(".py")) or "def " in code_text or "class " in code_text or "import " in code_text
            if fixed_code and is_py:
                try:
                    compile(fixed_code, filename or "<fixed_code>", "exec")
                except SyntaxError as syn_err:
                    logger.warning(f"Generated code had syntax error ({syn_err}), requesting immediate syntax repair...")
                    fix_prompt = (
                        f"The code you generated had a Python SyntaxError on line {syn_err.lineno}: {syn_err.msg}.\n"
                        f"Code:\n```python\n{fixed_code}\n```\n"
                        "Please fix this syntax error and return the complete valid working code as valid JSON with 'has_bug': true, 'bugs_found', 'full_fixed_code', and 'voice_summary'."
                    )
                    fix_res = await asyncio.to_thread(
                        client.models.generate_content,
                        model=model_name,
                        contents=[fix_prompt],
                        config=types.GenerateContentConfig(temperature=0.1)
                    )
                    fix_raw = fix_res.text.strip()
                    s_idx = fix_raw.find("{")
                    e_idx = fix_raw.rfind("}")
                    if s_idx != -1 and e_idx != -1 and e_idx > s_idx:
                        fix_data = json.loads(fix_raw[s_idx:e_idx+1])
                        if fix_data.get("full_fixed_code"):
                            data["full_fixed_code"] = fix_data["full_fixed_code"]

            return data
        except Exception as e:
            logger.warning(f"Model {model_name} diagnosis failed: {e}")
            continue

    return {
        "has_bug": False,
        "explanation": "Could not complete diagnosis.",
        "voice_summary": "I had difficulty analyzing the code, Boss. Please ensure the code is visible on screen."
    }

async def inspect_and_fix_code(task_description: str = "") -> str:
    """
    Direct code inspection and fix workflow (Zero To-Do list UI):
    1. Finds active IDE on screen or mentioned file.
    2. Reads the actual code directly from editor buffer, disk, or user prompt.
    3. Performs holistic multi-bug diagnosis with Gemini 3.5 Flash Lite.
    4. Pastes the corrected code directly into the editor and saves (Ctrl+A -> Ctrl+V -> Ctrl+S).
    5. Synchronizes to disk if file path exists.
    6. Returns articulate voice confirmation.
    """
    import pyautogui
    import pyperclip

    # 1. Determine target file & IDE window
    mentioned_file = extract_filename_from_prompt(task_description)
    ide_info = get_ide_window_info()
    hwnd = ide_info.get("hwnd")
    ide_name = ide_info.get("ide_name", "VS Code")
    filename = mentioned_file or ide_info.get("active_filename", "active_file.py")
    rect = ide_info.get("rect")

    # Focus IDE window
    if hwnd:
        bring_window_to_front(hwnd)
        time.sleep(0.15)

    # 2. Get the actual code
    code_text = ""
    file_path = find_file_on_disk(filename)

    # Try reading from disk first if found
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code_text = f.read()
        except Exception:
            pass

    # If editor window is active, copy directly from the active editor buffer
    if hwnd:
        try:
            bring_window_to_front(hwnd)
            time.sleep(0.1)
            # Select all, copy, and restore cursor
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.08)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.08)
            pyautogui.press("left")
            editor_content = pyperclip.paste()
            if editor_content and len(editor_content.strip()) > 5:
                code_text = editor_content
        except Exception as e:
            logger.warning(f"Could not copy from editor buffer: {e}")

    # Fallback: check if user pasted code directly in task_description
    if not code_text or len(code_text.strip()) < 10:
        extracted = extract_code_from_text(task_description)
        if extracted:
            code_text = extracted

    if not code_text:
        return f"Boss, I could not find or access the code for '{filename}'. Please make sure the file is open on your screen."

    # Capture screen image if possible
    screenshot_bytes, _, _ = capture_screen_image(rect)

    # 3. LLM Diagnosis & Fix
    diagnosis = await diagnose_and_fix_code(
        code_text=code_text,
        screenshot_bytes=screenshot_bytes,
        user_instruction=task_description,
        filename=filename
    )

    if not diagnosis.get("has_bug"):
        return f"Boss, I reviewed your code in '{filename}'. Everything appears clean and syntactically sound. No errors detected."

    full_fixed_code = diagnosis.get("full_fixed_code")
    voice_summary = diagnosis.get("voice_summary", "I have identified the issues and applied the complete fix for you.")
    bugs = diagnosis.get("bugs_found", [])

    if not full_fixed_code:
        return f"{voice_summary}\nBugs noted:\n" + "\n".join([f"- {b}" for b in bugs])

    # 4. Apply Fix directly into editor
    applied_to_editor = False
    if hwnd:
        try:
            bring_window_to_front(hwnd)
            time.sleep(0.12)
            pyperclip.copy(full_fixed_code)
            time.sleep(0.05)
            # Select all in editor and paste clean fix
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.05)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            # Save file
            pyautogui.hotkey("ctrl", "s")
            time.sleep(0.1)
            applied_to_editor = True
        except Exception as e:
            logger.warning(f"Failed to paste into editor: {e}")

    # Also synchronize to disk file directly if path is known
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_fixed_code)
        except Exception as fe:
            logger.warning(f"Could not write directly to disk file: {fe}")
    elif not applied_to_editor:
        # If no editor was open and file not on disk, save in workspace
        try:
            from worker_agent import WORKER_WORKSPACE
            save_name = filename if (filename and filename != "active_file.py" and not filename.startswith("self.") and "." in filename) else "fixed_code.py"
            out_path = os.path.join(WORKER_WORKSPACE, save_name)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_fixed_code)
            voice_summary += f" I have saved the full working script to '{save_name}' for you."
        except Exception as se:
            logger.warning(f"Failed to save fallback fixed file: {se}")

    display_target = filename if (applied_to_editor or file_path) else "your code"
    bugs_text = "\n".join([f"- {b}" for b in bugs]) if bugs else ""
    return f"{voice_summary}\n\nResolved in {display_target}:\n{bugs_text}"

async def inspect_code_only(question: str = "") -> str:
    """Visually inspects code on screen without modifying the file (Zero To-Do UI)."""
    mentioned_file = extract_filename_from_prompt(question)
    ide_info = get_ide_window_info()
    hwnd = ide_info.get("hwnd")
    ide_name = ide_info.get("ide_name", "VS Code")
    filename = mentioned_file or ide_info.get("active_filename", "active_file.py")
    rect = ide_info.get("rect")

    if hwnd:
        bring_window_to_front(hwnd)
        time.sleep(0.1)

    code_text = ""
    file_path = find_file_on_disk(filename)
    if file_path and os.path.isfile(file_path):
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                code_text = f.read()
        except Exception:
            pass

    if not code_text and hwnd:
        try:
            import pyautogui, pyperclip
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.08)
            pyautogui.hotkey("ctrl", "c")
            time.sleep(0.08)
            pyautogui.press("left")
            code_text = pyperclip.paste()
        except Exception:
            pass

    if not code_text or len(code_text.strip()) < 10:
        extracted = extract_code_from_text(question)
        if extracted:
            code_text = extracted

    screenshot_bytes, _, _ = capture_screen_image(rect)

    diagnosis = await diagnose_and_fix_code(
        code_text=code_text or "Code visible in screenshot.",
        screenshot_bytes=screenshot_bytes,
        user_instruction=question or "Inspect this code and identify any bugs.",
        filename=filename
    )

    bugs = diagnosis.get("bugs_found", [])
    if diagnosis.get("has_bug") and bugs:
        bugs_str = "\n".join([f"- {b}" for b in bugs])
        return f"Boss, looking at '{filename}', I identified the following issues:\n{bugs_str}\n\nWould you like me to apply the complete fix and save it in your editor?"
    else:
        return f"Boss, I reviewed '{filename}'. Everything appears clean and error-free."
