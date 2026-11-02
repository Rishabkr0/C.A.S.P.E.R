import os
import sys
import time
import json
import shutil
import socket
import subprocess
import asyncio
import logging
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("worker_agent")

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WORKER_WORKSPACE = os.path.join(PROJECT_ROOT, "worker_workspace")
os.makedirs(WORKER_WORKSPACE, exist_ok=True)

# Lock to ensure only one heavy background worker task executes at a time
_worker_lock = asyncio.Lock()
_current_worker_task: Optional[asyncio.Task] = None
_current_worker_proc: Optional[asyncio.subprocess.Process] = None

def cancel_current_worker() -> bool:
    """Cancels any running background worker task and terminates its subprocess tree immediately."""
    global _current_worker_task, _current_worker_proc
    stopped_anything = False

    # 1. Terminate running subprocess tree (OpenCode / node / python)
    if _current_worker_proc and _current_worker_proc.returncode is None:
        try:
            pid = _current_worker_proc.pid
            logger.info(f"Terminating background worker subprocess tree PID: {pid}")
            subprocess.run(f"taskkill /pid {pid} /T /F", shell=True, capture_output=True)
            stopped_anything = True
        except Exception as e:
            logger.warning(f"Error terminating worker process: {e}")
        finally:
            _current_worker_proc = None

    # 2. Cancel the asyncio task
    if _current_worker_task and not _current_worker_task.done():
        logger.info("Cancelling background worker asyncio task")
        _current_worker_task.cancel()
        _current_worker_task = None
        stopped_anything = True

    # 3. Dismiss To-Do card in Dynamic Island overlay
    broadcast_todo_state({
        "title": "Task Cancelled",
        "model": "Casper",
        "status": "Task halted by Boss.",
        "todos": [],
        "all_done": True
    })

    return stopped_anything

def broadcast_todo_state(data: dict):
    """Broadcasts todo checklist JSON to Electron Dynamic Island overlay via UDP 49152."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        payload = f"TODO:{json.dumps(data)}"
        sock.sendto(payload.encode('utf-8'), ('127.0.0.1', 49152))
        sock.close()
    except Exception as e:
        logger.warning(f"Failed to broadcast todo state: {e}")

def _resolve_path(path: str) -> str:
    """
    Resolves a path:
    - If path is absolute or starts with ~ or %, expands and returns it.
    - If path starts with common user dirs (Desktop, Downloads, Documents, etc.), resolves to user's home.
    - Otherwise (e.g. 'script.py', 'temp.txt'), resolves into WORKER_WORKSPACE to keep project root clean.
    """
    raw = os.path.expanduser(os.path.expandvars(path.strip()))
    if os.path.isabs(raw):
        return os.path.normpath(raw)
    
    first_part = raw.replace('\\', '/').split('/')[0].lower()
    if first_part in ['desktop', 'downloads', 'documents', 'pictures', 'videos']:
        return os.path.normpath(os.path.join(os.path.expanduser('~'), raw))
        
    return os.path.normpath(os.path.join(WORKER_WORKSPACE, raw))

def speak_text(text: str):
    """Speaks text using a female system voice if available."""
    try:
        import win32com.client
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        voices = speaker.GetVoices()
        for v in voices:
            if "Zira" in v.GetDescription():
                speaker.Voice = v
                break
        speaker.Speak(text)
    except Exception as e:
        logger.error(f"TTS failed: {e}")

def create_directory(path: str) -> str:
    """Creates a directory/folder if it doesn't already exist."""
    try:
        target = _resolve_path(path)
        os.makedirs(target, exist_ok=True)
        return f"Successfully created directory: {target}"
    except Exception as e:
        return f"Error creating directory: {e}"

def delete_file_or_dir(path: str) -> str:
    """Deletes a file or directory."""
    try:
        target = _resolve_path(path)
        if not os.path.exists(target):
            return f"Path does not exist: {target}"
        if os.path.isdir(target):
            shutil.rmtree(target)
            return f"Successfully deleted directory: {target}"
        else:
            os.remove(target)
            return f"Successfully deleted file: {target}"
    except Exception as e:
        return f"Error deleting path: {e}"

def read_file(path: str) -> str:
    """Reads the contents of a text file."""
    try:
        target = _resolve_path(path)
        if not os.path.exists(target):
            return f"File not found: {target}"
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str) -> str:
    """Writes content to a file, creating parent directories if needed."""
    try:
        target = _resolve_path(path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote {len(content)} characters to {target}"
    except Exception as e:
        return f"Error writing file: {e}"

def list_dir(path: str = ".") -> str:
    """Lists the files and folders in a directory."""
    try:
        target = _resolve_path(path)
        if not os.path.exists(target):
            return f"Directory not found: {target}"
        entries = os.listdir(target)
        result = []
        for e in entries:
            full = os.path.join(target, e)
            tag = "[DIR]" if os.path.isdir(full) else "[FILE]"
            result.append(f"{tag} {e}")
        return "\n".join(result) if result else "Directory is empty."
    except Exception as e:
        return f"Error listing directory: {e}"

def run_python_script(script_path: str) -> str:
    """Executes a Python script located at script_path and returns stdout and stderr."""
    try:
        target = _resolve_path(script_path)
        if not os.path.exists(target):
            return f"Script file not found: {target}"
        res = subprocess.run([sys.executable, target], capture_output=True, text=True, timeout=60, cwd=os.path.dirname(target))
        output = ""
        if res.stdout:
            output += f"STDOUT:\n{res.stdout}\n"
        if res.stderr:
            output += f"STDERR:\n{res.stderr}\n"
        return output if output else "Script executed with no output."
    except Exception as e:
        return f"Error executing Python script: {e}"

def open_in_notepad(path: str) -> str:
    """Opens a text file in Windows Notepad so the user can see and edit it."""
    try:
        target = _resolve_path(path)
        if not os.path.exists(target):
            return f"File does not exist: {target}"
        subprocess.Popen(["notepad.exe", target])
        return f"Successfully opened {target} in Notepad."
    except Exception as e:
        return f"Error opening Notepad: {e}"

def find_design_image(task_instruction: str = "") -> tuple[str, str]:
    """
    Finds the active visual design screenshot and original filename.
    Only attaches an image if:
    1. A specific filename (e.g. 1.png) is mentioned in task_instruction.
    2. The user's instruction explicitly expresses intent to clone/replicate a design or screenshot.
    3. An image was uploaded very recently (within 15 minutes) and design intent is indicated.
    Prevents attaching stale images from previous sessions when building new websites from scratch.
    """
    uploads_dir = os.path.join(WORKER_WORKSPACE, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    keywords = ["design", "screenshot", "image", "clone", "replicate", "reference", "photo", "look like", "ui", "mockup", "wireframe", "attachment"]
    instruction_lower = task_instruction.lower()
    has_design_intent = any(k in instruction_lower for k in keywords)

    # 1. Check if a specific file name like '1.png' was mentioned in user instruction
    import re
    mentioned = re.findall(r'[\w\-.]+\.(?:png|jpg|jpeg|webp)', task_instruction, re.IGNORECASE)
    search_dirs = [
        uploads_dir,
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
        WORKER_WORKSPACE
    ]
    for filename in mentioned:
        for sdir in search_dirs:
            candidate = os.path.join(sdir, filename)
            if os.path.exists(candidate) and os.path.isfile(candidate):
                logger.info(f"Found mentioned design image: {candidate}")
                return candidate, filename

    # 2. Check explicit latest_design only if uploaded recently (< 15 mins) OR user indicated design intent
    latest_png = os.path.join(uploads_dir, "latest_design.png")
    latest_meta = os.path.join(uploads_dir, "latest_design.json")
    if os.path.exists(latest_png):
        mtime = os.path.getmtime(latest_png)
        is_recent = (time.time() - mtime) < 900
        if is_recent or has_design_intent:
            orig_name = "latest_design.png"
            try:
                if os.path.exists(latest_meta):
                    with open(latest_meta, "r", encoding="utf-8") as mf:
                        orig_name = json.load(mf).get("filename", orig_name)
            except Exception:
                pass
            return latest_png, orig_name

    # 3. Check newest image in uploads ONLY if user instruction explicitly requests design cloning
    if has_design_intent and os.path.exists(uploads_dir):
        all_imgs = [
            os.path.join(uploads_dir, f)
            for f in os.listdir(uploads_dir)
            if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
        ]
        if all_imgs:
            all_imgs.sort(key=os.path.getmtime, reverse=True)
            chosen = all_imgs[0]
            if (time.time() - os.path.getmtime(chosen)) < 3600:
                logger.info(f"Using newest uploaded design image for explicit design request: {chosen}")
                return chosen, os.path.basename(chosen)

    return "", ""

async def extract_visual_blueprint(image_path: str) -> dict:
    """Uses Gemini to extract a structured visual design blueprint in 3-5 seconds."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {}

        client = genai.Client(api_key=api_key)
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        part = types.Part.from_bytes(
            data=img_bytes,
            mime_type="image/jpeg" if image_path.lower().endswith((".jpg", ".jpeg")) else "image/png"
        )
        prompt = (
            "Analyze this website / UI design screenshot and extract an exact visual blueprint:\n"
            "Respond ONLY with valid JSON formatted as:\n"
            "{\n"
            '  "theme": "dark | light | minimal | creative",\n'
            '  "color_palette": {"background": "#hex", "primary": "#hex", "accent": "#hex", "text": "#hex", "card": "#hex"},\n'
            '  "typography": {"font_family_serif": "...", "font_family_sans": "...", "headings": "...", "body": "..."},\n'
            '  "layout_structure": ["Navbar with logo & links", "Hero section (split layout)", "Featured projects/cards", "Footer"],\n'
            '  "exact_content": {"headline": "...", "subheadline": "...", "navigation_items": ["..."], "cta_buttons": ["..."]},\n'
            '  "css_styling_notes": "Key gradients, border radii, shadows, spacing, and micro-interactions"\n'
            "}"
        )

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.5-flash-lite",
            contents=[part, prompt]
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)
    except Exception as e:
        logger.warning(f"Fast visual blueprint extraction skipped ({e})")
        return {}

async def run_opencode_task(task_instruction: str) -> str:
    """
    Executes a heavy agentic task using DeepSeek V4.1 Flash via OpenCode CLI.
    Runs non-interactively in worker_workspace with automatic tool approvals.
    Demands that DeepSeek first generates a To-Do checklist in todo.json and updates it live.
    """
    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop").replace("\\", "/")
    workspace_dir = WORKER_WORKSPACE.replace("\\", "/")
    model_id = os.getenv("OPENCODE_WORKER_MODEL", "opencode/deepseek-v4.1-flash-free")
    todo_file = os.path.join(WORKER_WORKSPACE, "todo.json")

    # Clean up previous todo.json if any
    try:
        if os.path.exists(todo_file):
            os.remove(todo_file)
    except Exception:
        pass

    short_title = task_instruction.strip()
    if len(short_title) > 36:
        short_title = short_title[:33] + "..."

    uploads_dir = os.path.join(WORKER_WORKSPACE, "uploads")
    design_image_path, orig_name = find_design_image(task_instruction)
    
    design_attachment_section = ""
    extra_files = []
    blueprint = {}

    if design_image_path and os.path.exists(design_image_path):
        broadcast_todo_state({
            "title": short_title,
            "model": "DeepSeek V4.1",
            "status": "Analyzing visual screenshot...",
            "todos": [
                {"id": 1, "text": f"Analyzing '{orig_name}' (palette, fonts & layout)...", "status": "in_progress"},
                {"id": 2, "text": "Create index.html with semantic structure", "status": "pending"},
                {"id": 3, "text": "Build styles.css with matching aesthetic & colors", "status": "pending"},
                {"id": 4, "text": "Add interactive features & finalize deliverable", "status": "pending"}
            ],
            "all_done": False
        })

        blueprint = await extract_visual_blueprint(design_image_path)
        blueprint_md = ""
        if blueprint:
            blueprint_path = os.path.join(WORKER_WORKSPACE, "design_blueprint.json")
            try:
                with open(blueprint_path, "w", encoding="utf-8") as bf:
                    json.dump(blueprint, bf, indent=2)
                extra_files.append(blueprint_path)
            except Exception:
                pass
            blueprint_md = f"\nEXTRACTED VISUAL DESIGN BLUEPRINT:\n```json\n{json.dumps(blueprint, indent=2)}\n```\n"

        initial_todos = {
            "title": short_title,
            "model": "DeepSeek V4.1",
            "todos": [
                {"id": 1, "text": f"Visual design analyzed ({orig_name})", "status": "done"},
                {"id": 2, "text": "Create index.html with semantic structure", "status": "in_progress"},
                {"id": 3, "text": "Build styles.css with matching aesthetic & colors", "status": "pending"},
                {"id": 4, "text": "Add interactive features & finalize deliverable", "status": "pending"}
            ],
            "all_done": False
        }
        try:
            with open(todo_file, "w", encoding="utf-8") as tf:
                json.dump(initial_todos, tf, indent=2)
        except Exception:
            pass
        broadcast_todo_state(initial_todos)

        design_attachment_section = (
            f"\nATTACHED VISUAL DESIGN / SCREENSHOT REFERENCE: '{orig_name}'\n"
            f"Image File Path: '{design_image_path.replace('\\', '/')}'\n"
            f"{blueprint_md}"
            "CRITICAL VISUAL CLONING INSTRUCTIONS:\n"
            "An image and pre-computed visual blueprint have been attached.\n"
            "- Recreate this exact design faithfully in clean, modern, responsive HTML, CSS, and JS.\n"
            "- Apply the extracted color palette, typography font pairings, and layout hierarchy.\n"
            "- Place the resulting website files in the target directory (e.g. on Desktop if requested).\n"
        )
    else:
        broadcast_todo_state({
            "title": short_title,
            "model": "DeepSeek V4.1",
            "status": "Generating To-Do checklist...",
            "todos": [
                {"id": 1, "text": "Analyzing task & generating action plan...", "status": "in_progress"}
            ],
            "all_done": False
        })

    prompt = (
        "You are Casper's dedicated background system engineer powered by DeepSeek V4.1 Flash via OpenCode CLI.\n"
        f"Your working directory is: '{workspace_dir}'. User's Desktop: '{desktop_dir}'.\n\n"
        "MANDATORY PROTOCOL:\n"
        "1. LIVE TO-DO CHECKLIST: Before taking any action, you MUST create a 'todo.json' file in your current directory with 3-5 clear tasks:\n"
        '   Format:\n'
        '   {\n'
        f'     "title": "{short_title}",\n'
        '     "model": "DeepSeek V4.1",\n'
        '     "todos": [\n'
        '       {"id": 1, "text": "Task description 1", "status": "in_progress"},\n'
        '       {"id": 2, "text": "Task description 2", "status": "pending"}\n'
        '     ],\n'
        '     "all_done": false\n'
        '   }\n'
        "   As you complete each step, update 'todo.json' by changing status to 'done' and the next to 'in_progress'.\n"
        "2. FULL EXECUTION: Write complete code files, modern HTML/CSS/JS web pages, automation scripts, or folder structures directly.\n"
        "3. When finished, set all statuses to 'done', set 'all_done': true in 'todo.json', and summarize what was accomplished.\n\n"
        f"{design_attachment_section}\n"
        f"USER TASK INSTRUCTION:\n{task_instruction}\n"
    )

    prompt_file = os.path.join(WORKER_WORKSPACE, "task_prompt.md")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)

    opencode_bin = shutil.which("opencode")
    if not opencode_bin:
        appdata_npm = os.path.join(os.environ.get("APPDATA", ""), "npm", "opencode.cmd")
        if os.path.exists(appdata_npm):
            opencode_bin = appdata_npm
        else:
            opencode_bin = "opencode"

    args = [
        opencode_bin, "run", "--standalone", "--auto",
        "--model", model_id,
        "--file", prompt_file,
        f"Execute the task in {prompt_file} immediately. First write todo.json, update it live, and perform all actions directly."
    ]

    logger.info(f"Spawning OpenCode worker with model: {model_id} using {opencode_bin}")
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=WORKER_WORKSPACE,
        stdin=subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    global _current_worker_proc
    _current_worker_proc = proc

    stop_watcher = asyncio.Event()

    async def watch_todo():
        last_seen = ""
        while not stop_watcher.is_set():
            if os.path.exists(todo_file):
                try:
                    with open(todo_file, "r", encoding="utf-8") as f:
                        raw = f.read().strip()
                    if raw and raw != last_seen:
                        last_seen = raw
                        data = json.loads(raw)
                        for item in data.get("todos", []):
                            t = item.get("text") or item.get("task") or "Task"
                            item["text"] = t
                            item["task"] = t
                        broadcast_todo_state(data)
                except Exception:
                    pass
            await asyncio.sleep(0.35)

    watcher_task = asyncio.create_task(watch_todo())

    timeout_seconds = int(os.getenv("OPENCODE_TIMEOUT", "480"))
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, TimeoutError):
        logger.warning(f"OpenCode DeepSeek task timed out after {timeout_seconds} seconds. Terminating process tree and falling back to Gemini...")
        try:
            # On Windows, kill entire process tree so node.exe / opencode.exe are not left orphaned
            subprocess.run(f"taskkill /pid {proc.pid} /T /F", shell=True, capture_output=True)
        except Exception as e:
            logger.warning(f"Failed to taskkill opencode tree: {e}")
        try:
            proc.kill()
        except Exception:
            pass
        return await run_gemini_worker_task(task_instruction, blueprint=blueprint)
    finally:
        _current_worker_proc = None
        stop_watcher.set()
        await watcher_task

    out_text = stdout.decode("utf-8", errors="replace").strip()
    stderr_text = stderr.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        logger.warning(f"OpenCode returned non-zero code {proc.returncode}. Stderr: {stderr_text}. Falling back to Gemini...")
        return await run_gemini_worker_task(task_instruction, blueprint=blueprint)

    if os.path.exists(todo_file):
        try:
            with open(todo_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("todos", []):
                item["status"] = "done"
            data["all_done"] = True
            data["status"] = "All tasks completed!"
            broadcast_todo_state(data)
        except Exception:
            pass
    else:
        broadcast_todo_state({
            "title": short_title,
            "model": "DeepSeek V4.1",
            "status": "All tasks completed!",
            "todos": [
                {"id": 1, "text": "Task executed successfully", "status": "done"}
            ],
            "all_done": True
        })

    clean_lines = [
        line for line in out_text.splitlines()
        if not line.strip().startswith("> build")
    ]
    result = "\n".join(clean_lines).strip()
    return result if result else out_text

async def run_gemini_worker_task(task_instruction: str, blueprint: dict = None) -> str:
    """Worker implementation using Google Gemini as fallback."""
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key) if api_key else genai.Client()
    model_id = "gemini-3.5-flash-lite"

    desktop_dir = os.path.join(os.path.expanduser("~"), "Desktop").replace("\\", "/")
    workspace_dir = WORKER_WORKSPACE.replace("\\", "/")

    blueprint_instructions = ""
    if blueprint:
        blueprint_instructions = (
            f"\nVISUAL DESIGN BLUEPRINT TO CLONE (EXACT COLORS & STRUCTURE):\n"
            f"```json\n{json.dumps(blueprint, indent=2)}\n```\n"
            "Build the complete, polished website using the exact color palette, typography font pairings, and layout from this blueprint.\n"
        )

    broadcast_todo_state({
        "title": "Building Website (Gemini)",
        "model": "Gemini 3.5 Flash",
        "status": "Generating code & writing files...",
        "todos": [
            {"id": 1, "text": "Visual design blueprint ready", "status": "done"},
            {"id": 2, "text": "Writing index.html, styles.css & assets", "status": "in_progress"},
            {"id": 3, "text": "Finalizing responsive styling & interactions", "status": "pending"}
        ],
        "all_done": False
    })

    chat = client.chats.create(
        model=model_id,
        config=types.GenerateContentConfig(
            tools=[create_directory, delete_file_or_dir, read_file, write_file, list_dir, run_python_script, open_in_notepad],
            system_instruction=(
                "You are Casper's dedicated background worker agent. "
                "Your job is to perform local system tasks like folder creation, file management, "
                "deep file inspection, and writing/running complex scripts.\n"
                f"- User's Desktop directory is: '{desktop_dir}'\n"
                f"- Your dedicated workspace directory is: '{workspace_dir}'\n"
                f"{blueprint_instructions}"
                "RULES:\n"
                "1. DIRECT TOOLS FIRST: For basic folder and file operations (creating folders, deleting, listing), "
                "ALWAYS use `create_directory`, `delete_file_or_dir`, and `list_dir` directly. "
                "DO NOT write python scripts just to create or delete directories.\n"
                "2. SCRIPTS & CODE: When the user asks you to write code/scripts or you need Python for multi-step logic, "
                "save them in your dedicated workspace (`worker_workspace/`) unless the user explicitly specified a location like Desktop. "
                "Relative filenames automatically save inside your workspace.\n"
                "3. IN-PLACE EDITING: When asked to edit, update, fix, or modify an existing file, "
                "ALWAYS overwrite the EXACT existing file path with write_file.\n"
                "4. When finished, clearly summarize what you did and where any files were saved."
            ),
            temperature=0.2,
        )
    )
    logger.info(f"Worker agent starting Gemini task: {task_instruction}")
    response = await asyncio.to_thread(chat.send_message, task_instruction)
    logger.info("Worker agent finished task.")

    broadcast_todo_state({
        "title": "Task Completed",
        "model": "Gemini 3.5 Flash",
        "status": "All tasks finished!",
        "todos": [
            {"id": 1, "text": "Visual design blueprint ready", "status": "done"},
            {"id": 2, "text": "Writing index.html, styles.css & assets", "status": "done"},
            {"id": 3, "text": "Finalizing responsive styling & interactions", "status": "done"}
        ],
        "all_done": True
    })
    return response.text

async def _execute_worker_job(task_instruction: str):
    global _current_worker_task
    try:
        async with _worker_lock:
            worker_engine = os.getenv("WORKER_ENGINE", "opencode").lower()

            # 1. Try DeepSeek V4.1 Flash via OpenCode by default
            if worker_engine in ("opencode", "deepseek", "auto"):
                try:
                    logger.info(f"Worker agent executing task via DeepSeek V4.1 Flash (OpenCode): {task_instruction}")
                    res = await run_opencode_task(task_instruction)
                    if res:
                        speak_text("The background task is complete, Boss. Your files are ready.")
                        return res
                except asyncio.CancelledError:
                    logger.info("Worker task cancelled during OpenCode execution.")
                    raise
                except Exception as e:
                    logger.warning(f"OpenCode DeepSeek execution failed ({e}), falling back to Gemini...")

            # 2. Fallback to Gemini
            try:
                res = await run_gemini_worker_task(task_instruction)
                speak_text("The background task is complete, Boss. Your files are ready.")
                return res
            except asyncio.CancelledError:
                logger.info("Worker task cancelled during Gemini execution.")
                raise
            except Exception as e:
                logger.error(f"Worker agent failed: {e}")
                return f"The background task encountered an error: {e}"
    except asyncio.CancelledError:
        logger.info("Background worker job cancelled by user command.")
    finally:
        _current_worker_task = None

@function_tool()
async def delegate_heavy_task(
    context: RunContext,  # type: ignore
    task_instruction: str) -> str:
    """
    Spins up Casper's dedicated background worker agent (powered by DeepSeek V4.1 Flash via OpenCode)
    to build websites or scaffold brand new applications from scratch.
    ONLY use this tool when the user asks to:
    - Build, create, code, or clone a new website, web page, or 3D web experience from scratch (e.g. 'Build an AI portfolio website').
    - Scaffold an entirely new multi-file application from scratch.
    CRITICAL: NEVER use this tool for fixing code, debugging errors, finding bugs, or editing files in VS Code / IDE.
    For all code debugging and bug fixing, ALWAYS use `fix_code_in_ide`.
    """
    global _current_worker_task
    if _worker_lock.locked():
        logger.warning(f"Worker is already busy with an active task: {task_instruction}")
        return "I am already actively building that project for you on your system, Boss. The background worker is running right now—please allow it a moment to finish."

    short_title = task_instruction.strip()
    if len(short_title) > 36:
        short_title = short_title[:33] + "..."

    # Immediately pop open the To-Do checklist on screen so user gets instant visual confirmation
    broadcast_todo_state({
        "title": short_title,
        "model": "DeepSeek V4.1",
        "status": "Starting background worker...",
        "todos": [
            {"id": 1, "text": "Analyzing request & setting up workspace...", "status": "in_progress"},
            {"id": 2, "text": "Building website files & styles...", "status": "pending"},
            {"id": 3, "text": "Finalizing deliverables...", "status": "pending"}
        ],
        "all_done": False
    })

    # Run the worker asynchronously in the background so Casper replies immediately without blocking speech
    _current_worker_task = asyncio.create_task(_execute_worker_job(task_instruction))

    return "I have initiated the background worker to build this project for you right now, Boss. The live progress steps are displayed on your Dynamic Island."
