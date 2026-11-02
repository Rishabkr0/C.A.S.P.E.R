import asyncio
import sys
import traceback

def write_crash_log(msg):
    with open("crash.log", "a") as f:
        f.write(msg + "\n")

try:
    if sys.platform == 'win32':
        if sys.stdout is not None:
            sys.stdout.reconfigure(encoding='utf-8')
        if sys.stderr is not None:
            sys.stderr.reconfigure(encoding='utf-8')
except Exception as e:
    write_crash_log(f"reconfigure error: {e}")

from dotenv import load_dotenv

from livekit import agents, rtc
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext
from livekit.agents.voice.io import AudioInput
from livekit.plugins import noise_cancellation
from livekit.plugins import google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email, play_music, stop_music, add_to_queue, skip_song, get_queue, set_music_volume, seek_song, play_obsidian_playlist
try:
    from office_tools import OFFICE_TOOLS as _OFFICE_TOOLS
except ImportError:
    _OFFICE_TOOLS = []

try:
    from google_tools import GOOGLE_TOOLS as _GOOGLE_TOOLS
except ImportError:
    _GOOGLE_TOOLS = []

try:
    from obsidian_tools import OBSIDIAN_TOOLS as _OBSIDIAN_TOOLS
except ImportError:
    _OBSIDIAN_TOOLS = []

from livekit.agents import function_tool, RunContext
import computer_use_enhanced as computer_use
from worker_agent import delegate_heavy_task
from mcp_client.chrome_server import create_chrome_server
from mcp_client import chrome_tools as chrome_tools_module
try:
    from mcp_client.chrome_tools import CHROME_TOOLS as _CHROME_TOOLS
except Exception as _e:
    _CHROME_TOOLS = []
    pass

from mem0 import MemoryClient

# Global mem0 client (set in entrypoint)
_mem0_client: MemoryClient | None = None
_mem0_user: str = "Rishab"

import ide_control
from screen_vision import (
    ScreenVideoInput,
    CircleGestureDetector,
    start_screen_vision,
    stop_screen_vision,
    inspect_focused_screen_area
)

@function_tool()
async def fix_code_in_ide(
    context: RunContext,
    task_description: str = "",
) -> str:
    """
    Inspects the code on screen in the active IDE (VS Code, Antigravity IDE, Cursor, etc.),
    identifies all bugs, syntax errors, or issues, applies the fix directly into the editor,
    and saves the file.
    ALWAYS use this tool whenever Boss asks to:
    - 'Fix the bug in test.py' or any other file
    - 'Find the bug in my code and fix it'
    - 'Look at my screen / VS Code and fix the error'
    - 'What is wrong with my code? Fix it'
    - 'Correct this code'
    """
    return await ide_control.inspect_and_fix_code(task_description)

@function_tool()
async def inspect_code_on_screen(
    context: RunContext,
    question: str = "",
) -> str:
    """
    Visually inspects the code and error squiggles on screen in the active IDE (VS Code, Cursor, PyCharm)
    and explains the bug, syntax issue, or answers questions WITHOUT making changes to the file yet.
    """
    return await ide_control.inspect_code_only(question)

@function_tool()
async def navigate_and_edit_line(
    context: RunContext,
    line_number: int,
    fixed_code: str,
) -> str:
    """
    Directly navigates to a specific line number in the active IDE via Ctrl+G,
    replaces the line with fixed_code, and saves the file.
    """
    ide_info = ide_control.get_ide_window_info()
    hwnd = ide_info.get("hwnd")
    filename = ide_info.get("active_filename")
    file_path = ide_control.find_file_on_disk(filename) if filename else None
    success, msg = ide_control.jump_and_replace_line_in_ide(
        line_number=line_number,
        fixed_code=fixed_code,
        hwnd=hwnd,
        file_path=file_path
    )
    return msg

@function_tool()
async def stop_current_task(
    context: RunContext,
    reason: str = "",
) -> str:
    """
    IMMEDIATELY stops, halts, and cancels any active, ongoing, or running task.
    ALWAYS call this tool instantly whenever Boss says:
    - 'stop', 'stop that', 'stop the task', 'stop what you are doing'
    - 'cancel', 'cancel that', 'cancel the build', 'abort'
    - 'halt', 'hold on, stop', 'wait, stop'
    - 'ruko', 'ruk jao', 'bas karo', 'band karo', 'roko', 'abhi roko'
    This tool cancels running background worker tasks, terminates background worker processes,
    stops active media/music playback, and dismisses active task overlays immediately.
    """
    logging.info(f"stop_current_task invoked by user command (reason: '{reason}')")
    stopped_items = []

    # 1. Cancel background worker (OpenCode, DeepSeek, site building)
    try:
        from worker_agent import cancel_current_worker
        if cancel_current_worker():
            stopped_items.append("background worker")
    except Exception as e:
        logging.warning(f"Error cancelling background worker: {e}")

    # 2. Stop music/media playback
    try:
        import media_player
        if media_player._current_player_process and media_player._current_player_process.poll() is None:
            media_player.stop_song()
            stopped_items.append("music playback")
    except Exception as e:
        logging.warning(f"Error stopping music: {e}")

    # 3. Update overlay state to idle
    try:
        update_ui("idle")
    except Exception:
        pass

    if stopped_items:
        return f"Understood, Boss. I have immediately stopped {', '.join(stopped_items)} and cleared all active tasks. Standing by."
    else:
        return "Understood, Boss. All tasks halted immediately. Standing by for your command."

@function_tool()
async def control_computer(
    context: RunContext,  # type: ignore
    task: str) -> str:
    """Execute a complex task on the computer UI."""
    return await computer_use.computer_use_loop(task)


@function_tool()
async def save_memory(
    context: RunContext,
    text: str,
) -> str:
    """
    Save a memory about the user for future sessions.

    Use this whenever the user shares personal preferences, facts,
    or asks to remember something. Examples:
    - "My favorite song is Numb by Linkin Park"
    - "I like Python and Rust"
    - "Remember I am building a compiler"
    - "My birthday is in June"

    Args:
        text: The fact to remember (e.g., "User's favorite song is Numb by Linkin Park")
    """
    global _mem0_client, _mem0_user
    if _mem0_client is None:
        return "Memory service not available (no MEM0_API_KEY)"
    try:
        # Use to_thread because MemoryClient is sync
        result = await asyncio.to_thread(
            _mem0_client.add, [{"role": "user", "content": text}], user_id=_mem0_user
        )
        logging.info(f"save_memory: saved '{text}' -> {result}")
        return f"Remembered: {text}"
    except Exception as e:
        logging.error(f"save_memory failed: {e}")
        return f"Failed to save memory: {e}"


@function_tool()
async def recall_memory(
    context: RunContext,
    query: str,
) -> str:
    """
    Search memories for a query. Use when user asks about past preferences.

    Examples:
    - query="favorite song" when user asks "what is my favorite song?"
    - query="last session" or "Rust compiler" when user asks what we did

    Args:
        query: Search query
    """
    global _mem0_client, _mem0_user
    if _mem0_client is None:
        return "Memory service not available"
    try:
        res = await asyncio.to_thread(
            _mem0_client.search, query, filters={"user_id": _mem0_user}
        )
        results = res.get("results", []) if isinstance(res, dict) else res
        if not results:
            return f"No memories found for '{query}'"
        formatted = "\n".join([f"- {r.get('memory')} (updated {r.get('updated_at')})" for r in results[:5]])
        logging.info(f"recall_memory '{query}' -> {formatted}")
        return formatted
    except Exception as e:
        logging.error(f"recall_memory failed: {e}")
        return f"Failed to search memories: {e}"

# Global Chrome server instance
chrome_server = None

import os
import json
import logging
import subprocess
import atexit
import sys

load_dotenv()

# --- UI Management ---
import subprocess
import threading
import atexit

ui_process = None

def start_ui():
    global ui_process
    if os.getenv("DISABLE_PYSIDE_UI") == "1":
        return
    try:
        # Launch the overlay with stdin pipe
        ui_process = subprocess.Popen([sys.executable, "jarvis_overlay.py"], stdin=subprocess.PIPE)
    except Exception as e:
        logging.error(f"Failed to start UI: {e}")

def update_ui(state):
    global ui_process
    # Send state to old PySide6 overlay (if running)
    if ui_process and ui_process.stdin:
        try:
            ui_process.stdin.write((state + '\n').encode('utf-8'))
            ui_process.stdin.flush()
        except Exception:
            pass
    # Send state to new Electron overlay via UDP
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(state.encode('utf-8'), ('127.0.0.1', 49152))
        sock.close()
    except Exception:
        pass

def stop_ui():
    global ui_process
    if ui_process:
        try:
            ui_process.terminate()
            ui_process = None
        except Exception:
            pass

atexit.register(stop_ui)
# --------------------------------
class MuteableAudioInput(AudioInput):
    """
    Wraps session.input.audio to stream continuous silence frames when muted.
    Benefits:
    1. Keeps WebSocket to Google Gemini Realtime continuously alive with audio packets,
       preventing 1008 policy violation aborts due to idle timeouts.
    2. Keeps the PortAudio / sounddevice hardware microphone active without
       attaching/detaching, avoiding hardware re-initialization pops and latency.
    3. Guarantees Casper's voice speaking output is never interrupted.
    """
    def __init__(self, source: AudioInput):
        super().__init__(label="muteable_input", source=source)
        self.muted = False

    async def __anext__(self) -> rtc.AudioFrame:
        frame = await self.source.__anext__()
        if self.muted:
            silent_data = bytes(frame.samples_per_channel * frame.num_channels * 2)
            return rtc.AudioFrame(
                data=silent_data,
                sample_rate=frame.sample_rate,
                num_channels=frame.num_channels,
                samples_per_channel=frame.samples_per_channel
            )
        return frame


class Assistant(Agent):
    def __init__(self, chat_ctx=None, lazy_load_chrome=False) -> None:
        # Build base tool list (memory tools are critical for persistence)
        _base_tools = [
            stop_current_task,
            start_screen_vision,
            stop_screen_vision,
            inspect_focused_screen_area,
            fix_code_in_ide,
            inspect_code_on_screen,
            navigate_and_edit_line,
            delegate_heavy_task,
            get_weather,
            search_web,
            send_email,
            play_music,
            stop_music,
            add_to_queue,
            skip_song,
            get_queue,
            set_music_volume,
            seek_song,
            play_obsidian_playlist,
            control_computer,
            save_memory,
            recall_memory
        ] + _OFFICE_TOOLS + _GOOGLE_TOOLS + _OBSIDIAN_TOOLS

        # FIX: Gemini Realtime (gemini-3.1-flash-live-preview) does NOT support mid-session tool updates
        # Log warning: "has limited mid-session update support. instructions, chat context, and tool updates
        # will not be applied until the next session." So lazy-loading after session.start is broken.
        # Chrome tools MUST be registered BEFORE super().__init__ / session.start. Force eager load.
        if lazy_load_chrome and _CHROME_TOOLS:
            logging.warning(
                "lazy_load_chrome=True is incompatible with Gemini Realtime (no mid-session tool updates). "
                "Forcing eager load of Chrome tools before session start."
            )
            lazy_load_chrome = False

        if lazy_load_chrome:
            # Start with only base tools, Chrome tools will be added later (DEPRECATED - won't work with Realtime)
            _all_tools = _base_tools
            logging.info(f"Registering {len(_all_tools)} base tools (Chrome tools will lazy-load)")
        else:
            # Eager load: register all tools immediately so LLM can use Chrome MCP when needed
            _all_tools = _base_tools + list(_CHROME_TOOLS) if _CHROME_TOOLS else _base_tools
            logging.info(f"Registering {len(_all_tools)} tools with Assistant: {[getattr(t, '__name__', str(t)) for t in _all_tools]}")

        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                 instructions=AGENT_INSTRUCTION,
                 model="gemini-3.1-flash-live-preview",
                 api_key=os.getenv("GEMINI_API_KEY"),
                 voice=os.getenv("CASPER_VOICE", "Charon"),
                 temperature=0.8,
                 modalities=["AUDIO"],
            ),
            tools=_all_tools,
            chat_ctx=chat_ctx

        )
        self._chrome_tools_loaded = not lazy_load_chrome

    async def add_chrome_tools(self):
        """Lazy-load Chrome tools when first needed"""
        if self._chrome_tools_loaded or not _CHROME_TOOLS:
            return

        logging.info(f"Lazy-loading {len(_CHROME_TOOLS)} Chrome MCP tools...")
        for tool in _CHROME_TOOLS:
            self.register_tool(tool)
        self._chrome_tools_loaded = True
        logging.info("Chrome tools loaded successfully")

class UICommandProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport
        
    def datagram_received(self, data, addr):
        msg = data.decode('utf-8').strip()
        try:
            if msg == "CMD:SKIP":
                import media_player
                media_player.skip_song()
            elif msg == "CMD:PREV":
                import media_player
                media_player.prev_song()
            elif msg == "CMD:STOP":
                import media_player
                media_player.stop_song()
            elif msg == "CMD:PAUSE":
                import media_player
                media_player.pause_song()
            elif msg == "CMD:RESUME":
                import media_player
                media_player.resume_song()
            elif msg.startswith("CMD:VOLUME:"):
                import media_player
                try:
                    vol = int(msg.split("CMD:VOLUME:")[1])
                    media_player.set_music_volume(vol)
                except Exception as e:
                    logging.error(f"Failed to set volume: {e}")
            elif msg.startswith("CMD:SEEK:"):
                import media_player
                try:
                    sec = int(float(msg.split("CMD:SEEK:")[1]))
                    media_player.seek_song(sec)
                except Exception as e:
                    logging.error(f"Failed to seek: {e}")
        except Exception as e:
            logging.error(f"UI Command Error: {e}")

async def start_ui_command_listener():
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: UICommandProtocol(),
            local_addr=('127.0.0.1', 49153)
        )
        logging.info("Started UI command listener on port 49153")
    except Exception as e:
        logging.error(f"Failed to start UI command listener: {e}")

async def entrypoint(ctx: agents.JobContext):
    asyncio.create_task(start_ui_command_listener())
    global chrome_server, _mem0_client, _mem0_user

    # Initialize Chrome MCP server
    try:
        logging.info("Initializing Chrome MCP server...")
        chrome_server = await create_chrome_server(auto_connect=True)

        # Set chrome server in tools modules
        chrome_tools_module.set_chrome_server(chrome_server)
        computer_use.set_chrome_tools(chrome_tools_module)

        logging.info("Chrome MCP server initialized successfully")
        update_ui("startup")
    except Exception as e:
        logging.warning(f"Failed to initialize Chrome MCP (will use fallback): {e}")
        chrome_server = None
        update_ui("startup")

    async def shutdown_hook(chat_ctx: ChatContext, mem0, memory_str: str, user_name: str):
        if mem0 is None:
            logging.warning("Mem0 client not initialized — skipping memory save")
            return
        logging.info("Shutting down, saving chat context to memory...")

        messages_formatted = [
        ]

        messages_attr = getattr(chat_ctx, 'messages', chat_ctx.items)
        items = messages_attr() if callable(messages_attr) else messages_attr
        logging.info(f"Chat context messages: {items}")

        for item in items:
            if not hasattr(item, 'content') or not hasattr(item, 'role'):
                continue

            content_str = ''.join(item.content) if isinstance(item.content, list) else str(item.content)

            if memory_str and memory_str in content_str:
                continue

            if item.role in ['user', 'assistant']:
                messages_formatted.append({
                    "role": item.role,
                    "content": content_str.strip()
                })

        logging.info(f"Formatted messages to add to memory: {messages_formatted}")
        if messages_formatted:
            try:
                # MemoryClient is sync (blocking) — run in thread to avoid blocking event loop
                await asyncio.to_thread(mem0.add, messages_formatted, user_id=user_name)
                logging.info("Chat context saved to memory (cloud).")
            except Exception as e:
                logging.error(f"Failed to save chat context to mem0: {e}")
        else:
            logging.info("No new chat context to save to memory.")


    from livekit.agents.voice.agent_session import TurnHandlingOptions

    session = AgentSession(
        turn_handling=TurnHandlingOptions(
            interruption={"enabled": True, "mode": "vad", "min_duration": 0.15, "min_words": 1}
        )
    )

    # --- Mem0 Cloud (Option 2) — uses MEM0_API_KEY, managed embeddings/LLM ---
    # Previously used local Qdrant (Memory.from_config with gemini-2.0-flash-001 /
    # text-embedding-004) which 404s and has dims mismatch (1536 vs 768). Cloud is verified working.
    _mem0_api_key = os.getenv("MEM0_API_KEY")
    if not _mem0_api_key:
        logging.warning("MEM0_API_KEY not set — memories will not persist")
        mem0 = None
        _mem0_client = None
    else:
        try:
            mem0 = MemoryClient(api_key=_mem0_api_key)
            _mem0_client = mem0  # for save_memory/recall_memory tools
            logging.info("Mem0 cloud client initialized")
        except Exception as e:
            logging.error(f"Failed to init mem0 cloud: {e}")
            mem0 = None
            _mem0_client = None

    # Resolve user_name: prefer room metadata, then Casper_USER_ID (.env), then legacy J.A.R.V.I.S._USER_ID, fallback Rishab/Admin
    user_name = (
        ctx.room.metadata
        if ctx.room.metadata
        else os.getenv("Casper_USER_ID") or os.getenv("J.A.R.V.I.S._USER_ID") or os.getenv("CASPER_USER_ID") or "Rishab"
    )
    _mem0_user = user_name  # for save_memory/recall_memory tools

    raw_results = {} if mem0 is None else await asyncio.to_thread(mem0.get_all, filters={'user_id': user_name})
    results = raw_results.get('results', []) if isinstance(raw_results, dict) else raw_results

    initial_ctx = ChatContext()
    memory_str = ''

    if results:
        memories = [
            {
                "memory": result["memory"],
                "updated_at": result["updated_at"]
            }
            for result in results
        ]
        memory_str = json.dumps(memories)
        logging.info(f"Memories: {memory_str}")
        initial_ctx.add_message(
            role="assistant",
            content=f"The user's name is {user_name}, and this is relvant context about him: {memory_str}."
        )

    # Inject personal info defined in the dashboard if available
    personal_info = os.getenv('USER_PERSONAL_INFO')
    if personal_info:
        initial_ctx.add_message(
            role="system",
            content=f"User's Personal Background & Preferences: {personal_info}"
        )

    # Prompt the assistant to greet the user
    # Note: Gemini Realtime drops system messages in chat_ctx, so we don't add SESSION_INSTRUCTION there.
    # Instead, we will update the model's instructions directly after creating the agent.
    initial_ctx.add_message(
        role="user",
        content="Hello casper, please greet me and speak your greeting out loud."
    )

    agent = Assistant(chat_ctx=initial_ctx, lazy_load_chrome=False)
    
    # Combine all instructions and update the RealtimeModel directly
    combined_instructions = AGENT_INSTRUCTION
    if personal_info:
        combined_instructions += f"\n\nUser's Personal Background & Preferences: {personal_info}"
    combined_instructions += f"\n\n{SESSION_INSTRUCTION}"
    if hasattr(agent.llm, "update_instructions"):
        agent.llm.update_instructions(combined_instructions)

    # Start the overlay UI
    start_ui()

    interaction_state = {"last_active": asyncio.get_event_loop().time(), "state": "none"}
    mic_active = True
    user_is_speaking = False

    def refresh_ui_state():
        nonlocal user_is_speaking, mic_active
        current_agent_state = getattr(session, "agent_state", None)
        if not mic_active:
            target = "waiting"
        elif current_agent_state == "speaking":
            target = "speaking"
        elif current_agent_state == "thinking":
            target = "thinking"
        elif user_is_speaking:
            target = "listening"
        else:
            target = "idle"

        if interaction_state["state"] != target:
            update_ui(target)
            interaction_state["state"] = target
            interaction_state["last_active"] = asyncio.get_event_loop().time()

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        nonlocal user_is_speaking
        print(f">>> USER STATE CHANGED: {event.new_state} <<<")
        if event.new_state == "speaking":
            user_is_speaking = True
            refresh_ui_state()
        else:
            user_is_speaking = False
            refresh_ui_state()

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        print(f">>> AGENT STATE CHANGED: {event.new_state} <<<")
        refresh_ui_state()

    # Watchdog: Monitors UI state timeouts to return to standby (idle or waiting)
    async def ui_watchdog():
        import ui_state
        await asyncio.sleep(1) # Fast boot check
        
        while True:
            await asyncio.sleep(0.5)
            try:
                if ui_state.current_custom_text:
                    custom_text = ui_state.current_custom_text
                    ui_state.current_custom_text = None
                    update_ui(f"custom:{custom_text}")
                    interaction_state["last_active"] = asyncio.get_event_loop().time()
                    interaction_state["state"] = "custom"
                
                now = asyncio.get_event_loop().time()
                # If thinking or custom text inactive for 8 seconds, return to normal state
                if interaction_state["state"] in ["thinking", "custom"] and now - interaction_state["last_active"] > 8.0:
                    refresh_ui_state()
            except Exception as e:
                pass

    asyncio.create_task(ui_watchdog())

    # --- CONTINUOUS AMBIENT SCREEN VISION & CIRCLE GESTURE TRACKING ---
    screen_streamer = None
    try:
        screen_streamer = ScreenVideoInput(target_fps=1.0, max_dim=1024)
        session.input.video = screen_streamer
        logging.info("Continuous screen vision streamer attached to session.input.video")
    except Exception as e:
        logging.warning(f"Could not attach screen video streamer: {e}")

    gesture_detector = None
    try:
        gesture_detector = CircleGestureDetector()
        gesture_detector.start()
        logging.info("Autonomous circle gesture detector started")
    except Exception as e:
        logging.warning(f"Could not start circle gesture detector: {e}")

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # Local screen capture is streamed via ScreenVideoInput, not participant camera
            video_enabled=False,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    # --- MUTE KEY TOGGLE INITIALIZATION ---
    muteable_audio = None
    if session.input.audio:
        muteable_audio = MuteableAudioInput(session.input.audio)
        session.input.audio = muteable_audio

    mic_active = True
    refresh_ui_state()

    async def toggle_mic_worker():
        nonlocal mic_active
        try:
            import ctypes
            user32 = ctypes.windll.user32
        except Exception as e:
            logging.error(f"Cannot initialize user32 for Mute Toggle: {e}")
            return

        key_was_down = False

        while True:
            await asyncio.sleep(0.025)  # 25ms polling for responsive edge detection
            try:
                # VK_MENU = 0x12 (Alt), VK_TAB = 0x09 (Tab)
                alt_down = bool(user32.GetAsyncKeyState(0x12) & 0x8000)
                tab_down = bool(user32.GetAsyncKeyState(0x09) & 0x8000)

                # Ignore Alt if Tab is also pressed (prevents Alt-Tab from muting)
                key_down = alt_down and not tab_down

                # Rising edge trigger: only toggle on key down transition
                if key_down and not key_was_down:
                    mic_active = not mic_active
                    if muteable_audio:
                        muteable_audio.muted = not mic_active
                    refresh_ui_state()
                    logging.info(f"Mute Key Toggle: mic_active={mic_active}")

                key_was_down = key_down

            except Exception as e:
                logging.error(f"Error in toggle_mic_worker: {e}")

    asyncio.create_task(toggle_mic_worker())



    # generate_reply is incompatible with Gemini Realtime API and omitted here.

    # Add Chrome cleanup to shutdown — use session.history (global) if available, fallback to agent ctx
    async def full_shutdown():
        # Stop screen streamer and gesture detector cleanly
        if screen_streamer:
            try:
                screen_streamer.stop()
            except Exception:
                pass
        if gesture_detector:
            try:
                gesture_detector.stop()
            except Exception:
                pass

        # Try session.history (LiveKit 1.7+ holds full conversation), fallback to agent chat_ctx
        try:
            hist = getattr(session, "history", None)
            chat_for_save = hist() if callable(hist) else hist
            if chat_for_save is None:
                chat_for_save = getattr(session, "_chat_ctx", None) or session._agent.chat_ctx
        except Exception:
            chat_for_save = session._agent.chat_ctx
        await shutdown_hook(chat_for_save, mem0, memory_str, user_name)
        if chrome_server:
            try:
                await chrome_server.cleanup()
                logging.info("Chrome MCP server cleaned up")
            except Exception as e:
                logging.error(f"Error cleaning up Chrome server: {e}")

    ctx.add_shutdown_callback(full_shutdown)

if __name__ == "__main__":
    try:
        agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
    except Exception as e:
        write_crash_log(f"run_app error: {traceback.format_exc()}")


