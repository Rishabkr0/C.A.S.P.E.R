import asyncio
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, ChatContext
from livekit.plugins import noise_cancellation
from livekit.plugins import google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import get_weather, search_web, send_email, play_music, stop_music, add_to_queue, skip_song, get_queue, set_music_volume, play_obsidian_playlist
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
from mcp_client.chrome_server import create_chrome_server
from mcp_client import chrome_tools as chrome_tools_module
# Import all high-level Chrome/MCP tools for direct use
try:
    from mcp_client.chrome_tools import CHROME_TOOLS as _CHROME_TOOLS
except Exception as _e:
    _CHROME_TOOLS = []
    # logging not yet imported — will warn later if needed
    pass

from mem0 import MemoryClient

# Global mem0 client (set in entrypoint)
_mem0_client: MemoryClient | None = None
_mem0_user: str = "Rishab"

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
    try:
        # Launch the overlay with stdin pipe
        ui_process = subprocess.Popen([sys.executable, "jarvis_overlay.py"], stdin=subprocess.PIPE)
    except Exception as e:
        logging.error(f"Failed to start UI: {e}")

def update_ui(state):
    global ui_process
    if ui_process and ui_process.stdin:
        try:
            ui_process.stdin.write((state + '\n').encode('utf-8'))
            ui_process.stdin.flush()
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



class Assistant(Agent):
    def __init__(self, chat_ctx=None, lazy_load_chrome=False) -> None:
        # Build base tool list (memory tools are critical for persistence)
        _base_tools = [get_weather, search_web, send_email, play_music, stop_music, add_to_queue, skip_song, get_queue, set_music_volume, play_obsidian_playlist, control_computer, save_memory, recall_memory] + _OFFICE_TOOLS + _GOOGLE_TOOLS + _OBSIDIAN_TOOLS

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



async def entrypoint(ctx: agents.JobContext):
    global chrome_server, _mem0_client, _mem0_user

    # Initialize Chrome MCP server
    try:
        logging.info("Initializing Chrome MCP server...")
        chrome_server = await create_chrome_server(auto_connect=True)

        # Set chrome server in tools modules
        chrome_tools_module.set_chrome_server(chrome_server)
        computer_use.set_chrome_tools(chrome_tools_module)

        logging.info("Chrome MCP server initialized successfully")
    except Exception as e:
        logging.warning(f"Failed to initialize Chrome MCP (will use fallback): {e}")
        chrome_server = None

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


    session = AgentSession(
        
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
    initial_ctx.add_message(
        role="system",
        content=SESSION_INSTRUCTION
    )
    initial_ctx.add_message(
        role="user",
        content="Hello casper, please greet me and speak your greeting out loud."
    )

    agent = Assistant(chat_ctx=initial_ctx, lazy_load_chrome=False)

    # Start the overlay UI
    start_ui()

    interaction_state = {"last_active": asyncio.get_event_loop().time(), "state": "idle"}

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        print(f">>> USER STATE CHANGED: {event.new_state} <<<")
        if event.new_state == "speaking":
            print(">>> UI TRIGGER: USER SPEAKING (LISTENING) <<<")
            update_ui("listening")
            interaction_state["last_active"] = asyncio.get_event_loop().time()
            interaction_state["state"] = "listening"
        elif event.new_state == "idle":
            # User stopped speaking
            pass

    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        print(f">>> AGENT STATE CHANGED: {event.new_state} <<<")
        if event.new_state == "speaking":
            print(">>> UI TRIGGER: AGENT SPEAKING <<<")
            update_ui("speaking")
            interaction_state["last_active"] = asyncio.get_event_loop().time()
            interaction_state["state"] = "speaking"
        elif event.new_state == "thinking":
            print(">>> UI TRIGGER: AGENT COMMITTED (WAITING) <<<")
            update_ui("waiting")
            interaction_state["last_active"] = asyncio.get_event_loop().time()
            interaction_state["state"] = "waiting"
        elif event.new_state == "idle" or event.new_state == "listening":
            print(">>> UI TRIGGER: AGENT IDLE/LISTENING <<<")
            update_ui("idle")
            interaction_state["last_active"] = asyncio.get_event_loop().time()
            interaction_state["state"] = "idle"

    # Watchdog: Monitors UI state timeouts to return to idle
    async def ui_watchdog():
        import ui_state
        await asyncio.sleep(1) # Reduced from 4s to 1s for faster boot
        
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
                # If waiting and inactive for 15 seconds, go idle
                if interaction_state["state"] in ["waiting", "custom"] and now - interaction_state["last_active"] > 15.0:
                    update_ui("idle")
                    interaction_state["state"] = "idle"
            except Exception as e:
                pass

    asyncio.create_task(ui_watchdog())

    await session.start(
        room=ctx.room,
        agent=agent,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            video_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()

    update_ui("startup")
    interaction_state["state"] = "startup"
    interaction_state["last_active"] = asyncio.get_event_loop().time()



    # generate_reply is incompatible with Gemini Realtime API and omitted here.

    # Add Chrome cleanup to shutdown — use session.history (global) if available, fallback to agent ctx
    async def full_shutdown():
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
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))