"""
Chrome MCP Integration - Visual Architecture Diagram

This file shows how all components work together
"""

# ============================================
# SYSTEM ARCHITECTURE
# ============================================

"""
┌─────────────────────────────────────────────────────────────────┐
│                        USER INTERACTION                          │
│                                                                  │
│  Voice: "Skip this YouTube ad"                                  │
│  Voice: "Play music on Spotify"                                 │
│  Voice: "Read my emails"                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENT.PY (Main Entry)                        │
│                                                                  │
│  • Initializes Chrome MCP Server                                │
│  • Loads all tools (weather, search, email, computer_use)      │
│  • Manages LiveKit session                                      │
│  • Handles memory (Mem0)                                        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│            CONTROL_COMPUTER Tool (Function Tool)                │
│                                                                  │
│  Delegates to: computer_use_enhanced.computer_use_loop()        │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         COMPUTER_USE_ENHANCED.PY (Smart Router)                 │
│                                                                  │
│  ┌─────────────────────────────────────────────┐               │
│  │  is_browser_task(task)?                     │               │
│  │                                              │               │
│  │  Checks for: youtube, spotify, gmail,       │               │
│  │             search, website, browser, etc.   │               │
│  └───────┬─────────────────────────┬────────────┘               │
│          │ YES                     │ NO                         │
└──────────┼─────────────────────────┼────────────────────────────┘
           │                         │
           ▼                         ▼
┌────────────────────────┐  ┌───────────────────────────────────┐
│   CHROME AUTOMATION    │  │   ORIGINAL AUTOMATION             │
│   (Fast & Reliable)    │  │   (Desktop Apps)                  │
│                        │  │                                   │
│  • chrome_automation() │  │  • UIA (Windows UI Automation)   │
│  • YouTube handlers    │  │  • Vision fallback                │
│  • Spotify handlers    │  │  • PyAutoGUI                      │
│  • Gmail handlers      │  │  • Desktop app control            │
│  • Web search          │  │                                   │
└───────────┬────────────┘  └───────────────┬───────────────────┘
            │                               │
            │ If fails                      │
            └───────────────┬───────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │ RETURN RESULT │
                    └───────────────┘
"""

# ============================================
# CHROME MCP DETAILED FLOW
# ============================================

"""
BROWSER TASK DETECTED: "Skip this YouTube ad"

Step 1: Browser Task Detection
┌────────────────────────────────────────┐
│  is_browser_task("skip youtube ad")    │
│  → Contains "youtube" → TRUE           │
└────────────────┬───────────────────────┘
                 │
                 ▼
Step 2: Route to Handler
┌────────────────────────────────────────┐
│  chrome_automation(task)               │
│  → Detects "youtube" in task          │
│  → Routes to: handle_youtube_task()   │
└────────────────┬───────────────────────┘
                 │
                 ▼
Step 3: YouTube-Specific Logic
┌────────────────────────────────────────┐
│  handle_youtube_task("skip ad")        │
│  → Detects "skip" + "ad"              │
│  → Calls: youtube_skip_ad(context)    │
└────────────────┬───────────────────────┘
                 │
                 ▼
Step 4: Chrome Tool Execution
┌────────────────────────────────────────┐
│  youtube_skip_ad() in chrome_tools.py  │
│  → Checks chrome_server.connected      │
│  → Executes JavaScript:                │
│     document.querySelector(            │
│       '.ytp-ad-skip-button'            │
│     ).click()                          │
└────────────────┬───────────────────────┘
                 │
                 ▼
Step 5: Chrome MCP Server
┌────────────────────────────────────────┐
│  chrome_server.call_tool()             │
│  → Sends to Chrome DevTools Protocol  │
│  → Chrome executes JavaScript          │
│  → Returns result                      │
└────────────────┬───────────────────────┘
                 │
                 ▼
Step 6: Result
┌────────────────────────────────────────┐
│  Return: "Ad skipped successfully"     │
│  Time: <500ms                          │
│  Status: ✅ Success                    │
└────────────────────────────────────────┘
"""

# ============================================
# COMPONENT RELATIONSHIPS
# ============================================

"""
agent.py
  │
  ├─► Imports: computer_use_enhanced (as computer_use)
  ├─► Imports: chrome_tools module
  ├─► Imports: chrome_server.create_chrome_server
  │
  └─► entrypoint():
       │
       ├─► chrome_server = create_chrome_server()
       │    └─► Launches Chrome with debugging
       │         └─► Starts MCP server (npx)
       │
       ├─► chrome_tools.set_chrome_server(chrome_server)
       │    └─► Makes server available to all tools
       │
       └─► computer_use.set_chrome_tools(chrome_tools)
            └─► Enables Chrome routing in computer_use


computer_use_enhanced.py
  │
  ├─► is_browser_task() → Detects browser keywords
  │
  ├─► chrome_automation() → Routes to specific handlers
  │    ├─► handle_youtube_task()
  │    ├─► handle_spotify_web_task()
  │    ├─► handle_gmail_task()
  │    ├─► handle_web_search_task()
  │    └─► handle_general_browser_task()
  │
  └─► computer_use_loop() → Main entry point
       │
       ├─ if browser_task → chrome_automation()
       └─ else → original_loop() from computer_use_original.py


mcp_client/
  │
  ├─► chrome_server.py
  │    ├─► ChromeMCPServer class
  │    │    ├─► _find_chrome_path()
  │    │    ├─► _launch_chrome()
  │    │    ├─► _launch_mcp_server()
  │    │    └─► call_tool()
  │    │
  │    └─► create_chrome_server() → Factory function
  │
  └─► chrome_tools.py
       ├─► 17 @function_tool() decorated functions
       │    ├─► Navigation: navigate, open_tab, close_tab
       │    ├─► Interaction: click, type, execute_js
       │    ├─► YouTube: skip_ad, play_video, control
       │    ├─► Spotify: play_song, control
       │    ├─► Gmail: read_emails
       │    └─► General: web_search, fill_form
       │
       └─► CHROME_TOOLS list → Exports all tools
"""

# ============================================
# DATA FLOW EXAMPLE
# ============================================

"""
USER COMMAND: "Play Bohemian Rhapsody on Spotify"

1. Voice Recognition (LiveKit)
   ↓
2. Agent.py receives text
   ↓
3. LLM (Gemini) decides to use control_computer tool
   ↓
4. control_computer(task="Play Bohemian Rhapsody on Spotify")
   ↓
5. computer_use_enhanced.computer_use_loop(task)
   ↓
6. is_browser_task("play bohemian rhapsody on spotify")
   → Contains "spotify" → TRUE
   ↓
7. chrome_automation(task)
   → Routes to handle_spotify_web_task()
   ↓
8. handle_spotify_web_task("play bohemian rhapsody...")
   → Detects "play" action
   → Extracts query: "bohemian rhapsody"
   ↓
9. spotify_play_song(context, "bohemian rhapsody")
   ↓
10. chrome_navigate(context, "https://open.spotify.com/search/...")
    ↓
11. chrome_execute_javascript(context, "click play button script")
    ↓
12. chrome_server.call_tool("execute_script", {...})
    ↓
13. Chrome DevTools Protocol executes JavaScript
    ↓
14. Spotify plays the song
    ↓
15. Return "Playing: bohemian rhapsody on Spotify"
    ↓
16. Agent speaks result to user

Total time: ~2 seconds (vs 6 seconds before)
"""

# ============================================
# FAILURE HANDLING
# ============================================

"""
Chrome MCP Failure Scenarios:

Scenario 1: Chrome MCP Not Available
┌────────────────────────────────────┐
│ chrome_server is None or          │
│ not connected                      │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Return: "Chrome automation         │
│         not available"             │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ computer_use_loop catches this     │
│ Falls back to original_loop()      │
└────────────────────────────────────┘


Scenario 2: JavaScript Execution Fails
┌────────────────────────────────────┐
│ chrome_execute_javascript()        │
│ throws exception                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Exception caught in chrome_tools   │
│ Returns error message              │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ computer_use_loop detects "failed" │
│ in result                          │
│ Falls back to original_loop()      │
└────────────────────────────────────┘


Scenario 3: Network/Timeout
┌────────────────────────────────────┐
│ Navigation or script times out     │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Exception propagates               │
│ Caught by try/except in router     │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│ Log warning                        │
│ Fall back to original automation   │
└────────────────────────────────────┘
"""

# ============================================
# INITIALIZATION SEQUENCE
# ============================================

"""
Application Startup:

1. agent.py main()
   ↓
2. agents.cli.run_app()
   ↓
3. entrypoint(ctx: JobContext)
   ↓
4. Initialize Chrome MCP:

   try:
       chrome_server = await create_chrome_server(auto_connect=True)
       │
       ├─► ChromeMCPServer.__init__()
       │    ├─► _find_chrome_path()
       │    └─► Setup params
       │
       ├─► server.connect()
       │    ├─► _launch_chrome()
       │    │    └─► Chrome starts with --remote-debugging-port=9222
       │    │
       │    └─► _launch_mcp_server()
       │         └─► npx @modelcontextprotocol/server-chrome
       │
       └─► chrome_tools.set_chrome_server(chrome_server)
            └─► computer_use.set_chrome_tools(chrome_tools)

   except Exception:
       log warning, chrome_server = None
       (Will fall back to original automation)

5. Continue normal initialization:
   ├─► Setup mem0 memory
   ├─► Create Agent with tools
   ├─► Start LiveKit session
   └─► Add shutdown callbacks

6. Ready to accept voice commands!
"""

# ============================================
# SHUTDOWN SEQUENCE
# ============================================

"""
Application Shutdown:

1. User exits or agent stops
   ↓
2. ctx.add_shutdown_callback() triggered
   ↓
3. full_shutdown() async function:

   ├─► shutdown_hook(...)
   │    └─► Save chat context to mem0
   │
   └─► if chrome_server:
        await chrome_server.cleanup()
        │
        ├─► Terminate MCP server process
        │    └─► mcp_process.terminate()
        │
        └─► Chrome continues running
             (User might still be using it)

4. Exit cleanly
"""

# ============================================
# FILE DEPENDENCIES
# ============================================

"""
Import Graph:

agent.py
  ├─► computer_use_enhanced (as computer_use)
  │    ├─► computer_use_original (fallback)
  │    └─► mcp_client.chrome_tools
  │         └─► Uses global chrome_server
  │
  └─► mcp_client.chrome_server
       └─► mcp_client.server (base classes)

No circular dependencies!
Clean separation of concerns!
"""

# ============================================
# EXTENSION POINTS
# ============================================

"""
Easy Extension Points:

1. Add New Browser Tool:
   └─► Edit: mcp_client/chrome_tools.py

        @function_tool()
        async def my_new_tool(context, param: str) -> str:
            '''My custom automation'''
            script = "/* JavaScript */"
            return await chrome_execute_javascript(context, script)

2. Add New Website Handler:
   └─► Edit: computer_use_enhanced.py

        async def handle_my_site_task(task: str) -> str:
            # Custom logic for your site
            return await chrome_tools.chrome_navigate(None, "...")

3. Add Browser Task Keywords:
   └─► Edit: computer_use_enhanced.py

        def is_browser_task(task: str) -> bool:
            browser_keywords = [
                "existing keywords...",
                "your_keyword_here"
            ]

4. Custom Chrome Server Configuration:
   └─► Edit: agent.py entrypoint()

        chrome_server = await create_chrome_server(
            chrome_path="/custom/path/chrome",
            remote_debugging_port=9999,
            auto_connect=True
        )
"""

print(__doc__)
