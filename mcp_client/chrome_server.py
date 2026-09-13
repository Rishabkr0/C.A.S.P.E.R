"""
Chrome MCP Server Integration for casper — Real CDP Implementation
Provides browser automation via Chrome DevTools Protocol (requests + websockets).
No external npx dependency required. Launches Chrome with --remote-debugging-port
and drives it directly.
"""

import asyncio
import logging
import subprocess
import os
import json
import time
import psutil
import base64
from typing import Optional, Dict, Any, List

# Get USER_DATA_PATH for writeable config directories
USER_DATA_PATH = os.getenv("USER_DATA_PATH", os.getcwd())

logger = logging.getLogger("chrome-mcp")

# Optional: ensure requests and websockets are available
try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore


class ChromeMCPServer:
    """Chrome MCP Server for browser automation — direct CDP."""

    def __init__(
        self,
        chrome_path: Optional[str] = None,
        user_data_dir: Optional[str] = None,
        remote_debugging_port: int = 9222,
        cache_tools_list: bool = True,
        name: Optional[str] = "Chrome MCP",
    ):
        self.remote_debugging_port = remote_debugging_port
        self.name = name
        self.cache_tools_list = cache_tools_list
        self._tools_cache: Optional[List[Any]] = None

        # Resolve paths without triggering recursion
        if chrome_path:
            self.chrome_path = chrome_path
        else:
            self.chrome_path = self._find_chrome_path()

        if user_data_dir:
            self.user_data_dir = user_data_dir
        else:
            # Try to use real Chrome profile first, fallback to temp profile
            self.user_data_dir = self._get_best_profile_path()

        # Compat params dict for legacy code that inspects .params
        self.params = {
            "command": "chrome-cdp-direct",
            "args": [],
            "env": {
                "CHROME_PATH": self.chrome_path,
                "CHROME_USER_DATA_DIR": self.user_data_dir,
                "CHROME_REMOTE_DEBUGGING_PORT": str(remote_debugging_port),
            },
        }

        self.chrome_process: Optional[subprocess.Popen] = None
        self._connected = False
        # track if we launched the process (so we know whether to kill on cleanup)
        self._launched_by_us = False

    # ------------------------------------------------------------------ #
    # Compatibility shims for legacy MCPServerStdio interface
    # ------------------------------------------------------------------ #
    @property
    def connected(self) -> bool:
        return self._connected

    @connected.setter
    def connected(self, value: bool):
        self._connected = bool(value)

    # ------------------------------------------------------------------ #
    def _get_best_profile_path(self) -> str:
        """
        Get the best Chrome profile path:
        Using a temporary profile to avoid locking issues with the user's main Chrome instance.
        """
        # Fallback to temporary profile in USER_DATA_PATH to avoid permissions issues
        temp_profile = os.path.join(USER_DATA_PATH, "chrome_profile")
        logger.info(f"Using temporary Chrome profile at: {temp_profile}")
        return temp_profile

    def _find_chrome_path(self) -> str:
        """Auto-detect Chrome installation path"""
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        ]
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found Chrome/Edge at: {path}")
                return path
        raise FileNotFoundError(
            "Chrome not found. Please install Google Chrome or specify chrome_path manually."
        )

    def _is_debug_port_open(self) -> bool:
        """Check if debug port is responding via HTTP"""
        if requests is None:
            return self._is_chrome_running_with_debug()
        try:
            resp = requests.get(
                f"http://127.0.0.1:{self.remote_debugging_port}/json/version",
                timeout=1,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _is_chrome_running_with_debug(self) -> bool:
        """Check if Chrome is already running with remote debugging (psutil)"""
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                if proc.info["name"] and "chrome" in proc.info["name"].lower():
                    cmdline = proc.info.get("cmdline", [])
                    if cmdline and f"--remote-debugging-port={self.remote_debugging_port}" in " ".join(cmdline):
                        logger.info("Chrome already running with remote debugging (psutil)")
                        return True
        except Exception as e:
            logger.warning(f"Error checking Chrome process: {e}")
        return False

    async def _wait_for_debug_port(self, timeout: float = 15.0) -> bool:
        """Poll until http://127.0.0.1:port/json/version responds."""
        if requests is None:
            await asyncio.sleep(2)
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._is_debug_port_open():
                return True
            await asyncio.sleep(0.5)
        return False

    async def _launch_chrome(self):
        """Launch Chrome with remote debugging enabled"""
        if self._is_debug_port_open():
            logger.info("Chrome debug port already open — reusing existing instance")
            return

        os.makedirs(self.user_data_dir, exist_ok=True)

        chrome_args = [
            self.chrome_path,
            f"--remote-debugging-port={self.remote_debugging_port}",
            f"--user-data-dir={self.user_data_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-timer-throttling",
            "--disable-features=Translate",
            "--start-maximized",
        ]

        try:
            logger.info(f"Launching Chrome: {' '.join(chrome_args)}")
            self.chrome_process = subprocess.Popen(
                chrome_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._launched_by_us = True
            ok = await self._wait_for_debug_port(timeout=15)
            if not ok:
                raise RuntimeError(f"Chrome did not open debug port {self.remote_debugging_port} in time")
            logger.info("Chrome launched and debug port ready")

            # Log which profile is being used
            if "User Data" in self.user_data_dir:
                logger.info("✓ Using your real Chrome profile with all bookmarks, logins, and extensions")
            else:
                logger.info("⚠ Using temporary profile (your main Chrome may be open). Close Chrome and restart casper to use your real profile.")

        except Exception as e:
            logger.error(f"Failed to launch Chrome: {e}")
            
            # Kill the hanging process if it exists before falling back
            if self.chrome_process:
                logger.info("Terminating hanging Chrome process before fallback...")
                self.chrome_process.terminate()
                self.chrome_process = None

            # If we tried to use real profile and it failed, retry with temp profile
            if "User Data" in self.user_data_dir:
                logger.warning("Real Chrome profile is locked. Falling back to temporary profile...")
                self.user_data_dir = os.path.join(USER_DATA_PATH, "chrome_profile")
                os.makedirs(self.user_data_dir, exist_ok=True)

                # Retry with temp profile
                chrome_args[2] = f"--user-data-dir={self.user_data_dir}"
                # Remove profile-directory for temp profile to avoid creating unnecessary folders
                chrome_args = [arg for arg in chrome_args if not arg.startswith("--profile-directory")]
                
                try:
                    self.chrome_process = subprocess.Popen(
                        chrome_args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                    )
                    self._launched_by_us = True
                    ok = await self._wait_for_debug_port(timeout=15)
                    if not ok:
                        raise RuntimeError(f"Chrome did not open debug port {self.remote_debugging_port} in time")
                    logger.info("Chrome launched with temporary profile (no bookmarks/logins)")
                    logger.info("💡 Tip: Close all Chrome windows and restart casper to use your real profile")
                except Exception as retry_error:
                    logger.error(f"Failed to launch Chrome even with temp profile: {retry_error}")
                    raise
            else:
                raise

    # ---------------- CDP helpers ---------------- #
    def _http_get_targets(self) -> List[Dict[str, Any]]:
        if requests is None:
            raise RuntimeError("requests library required for CDP HTTP")
        resp = requests.get(f"http://127.0.0.1:{self.remote_debugging_port}/json", timeout=5)
        resp.raise_for_status()
        return resp.json()

    def _get_page_targets(self) -> List[Dict[str, Any]]:
        targets = self._http_get_targets()
        return [t for t in targets if t.get("type") == "page"]

    def _ensure_ws_url(self) -> str:
        """Return ws URL for the active page; create one if none exists."""
        pages = self._get_page_targets()
        if pages:
            # Prefer first non-chrome URL, or first page
            for p in pages:
                if p.get("url", "").startswith("http"):
                    return p["webSocketDebuggerUrl"]
            return pages[0]["webSocketDebuggerUrl"]
        # No page — create one
        if requests is None:
            raise RuntimeError("No page target and requests unavailable")
        resp = requests.get(
            f"http://127.0.0.1:{self.remote_debugging_port}/json/new?about:blank",
            timeout=5,
        )
        data = resp.json()
        ws = data.get("webSocketDebuggerUrl")
        if not ws:
            raise RuntimeError(f"Failed to create new tab: {data}")
        return ws

    async def _cdp(self, ws_url: str, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 12.0) -> Any:
        """Send a CDP command over websocket and wait for result."""
        if websockets is None:
            raise RuntimeError("websockets library required (pip install websockets)")
        params = params or {}
        msg_id = int(time.time() * 1000) % 1000000
        payload = json.dumps({"id": msg_id, "method": method, "params": params})
        async with websockets.connect(ws_url, max_size=None) as ws:
            await ws.send(payload)
            # wait for matching id
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    raise TimeoutError(f"CDP {method} timed out")
                data = json.loads(raw)
                if data.get("id") == msg_id:
                    if "error" in data:
                        raise RuntimeError(f"CDP error {method}: {data['error']}")
                    return data.get("result")
                # ignore events
            raise TimeoutError(f"CDP {method} no response for id {msg_id}")

    async def _evaluate(self, expression: str, awaitPromise: bool = False, timeout: float = 12.0) -> Any:
        ws_url = await asyncio.to_thread(self._ensure_ws_url)
        result = await self._cdp(ws_url, "Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": awaitPromise,
            "userGesture": True,
        }, timeout=timeout)
        # result = { result: { type, value, ... } }
        inner = result.get("result", {}) if isinstance(result, dict) else {}
        if inner.get("subtype") == "error":
            raise RuntimeError(inner.get("description", "JS evaluation error"))
        return inner.get("value")

    async def _navigate_via_evaluate(self, url: str) -> str:
        # Use Runtime.evaluate to navigate — reliable without Page domain enable
        js = f"window.location.href = {json.dumps(url)}; 'navigated to ' + window.location.href"
        try:
            await self._evaluate(js)
        except Exception as e:
            logger.warning(f"navigate evaluate warning: {e}")
        # wait for navigation
        await asyncio.sleep(2.5)
        # verify url
        try:
            cur = await self._evaluate("window.location.href")
            return str(cur)
        except Exception:
            return url

    # ---------------- Public API ---------------- #
    async def connect(self):
        """Connect to Chrome (launch if needed)"""
        try:
            await self._launch_chrome()
            # quick sanity check — can we get ws url?
            ws = await asyncio.to_thread(self._ensure_ws_url)
            logger.info(f"Chrome CDP ws ready: {ws[:60]}...")
            self._connected = True
            logger.info(f"Successfully connected to {self.name}")
        except Exception as e:
            logger.error(f"Failed to connect Chrome CDP: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> List[Any]:
        """List available Chrome automation tools (for MCP clients)"""
        if not self._connected:
            raise RuntimeError("Server not connected. Call connect() first.")
        # Return the high-level tool definitions for documentation / MCP listing
        # These mirror chrome_tools.py CHROME_TOOLS names
        from mcp.types import Tool as MCPTool  # type: ignore
        def _t(name: str, desc: str) -> MCPTool:
            return MCPTool(name=name, description=desc, inputSchema={"type": "object", "properties": {}})  # minimal schema
        names_descs = [
            ("navigate", "Navigate to a URL"),
            ("open_new_tab", "Open new tab"),
            ("close_tab", "Close current tab"),
            ("get_url", "Get current URL"),
            ("click", "Click element by CSS selector"),
            ("type", "Type into input field"),
            ("execute_script", "Execute JavaScript"),
            ("get_content", "Get page text content"),
            ("screenshot", "Capture screenshot"),
            ("list_tabs", "List all open tabs"),
            ("switch_tab", "Switch to a specific tab by ID"),
            ("close_other_tabs", "Close all tabs except the current one"),
            ("get_cookies", "Get browser cookies"),
            ("clear_cookies", "Clear browser cookies"),
            ("set_blocked_urls", "Block network requests to specific URLs"),
        ]
        tools = [_t(n, d) for n, d in names_descs]
        if self.cache_tools_list:
            self._tools_cache = tools
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Call a Chrome automation tool — real CDP implementation."""
        if not self._connected:
            # Try lazy connect once
            if self._is_debug_port_open():
                self._connected = True
            else:
                raise RuntimeError("Server not connected. Call connect() first.")
        arguments = arguments or {}
        try:
            logger.info(f"CDP tool: {tool_name} {arguments}")
            result = await self._dispatch(tool_name, arguments)
            # Normalize to MCP-like content dict for chrome_tools.py callers
            if isinstance(result, dict) and "content" in result:
                return result
            return {"content": [str(result) if result is not None else "OK"]}
        except Exception as e:
            logger.error(f"Error calling Chrome tool {tool_name}: {e}")
            raise

    async def _dispatch(self, tool_name: str, args: Dict[str, Any]) -> Any:
        name = tool_name.strip().lower()

        # ---- navigation ----
        if name in ("navigate",):
            url = args.get("url") or args.get("URL") or ""
            if not url:
                raise ValueError("navigate requires 'url'")
            if not url.startswith("http"):
                url = "https://" + url
            cur = await self._navigate_via_evaluate(url)
            return f"Navigated to {cur}"

        if name in ("open_new_tab", "new_tab", "create_tab"):
            url = args.get("url", "about:blank")
            if url and not url.startswith("http") and url != "about:blank":
                url = "https://" + url
            if requests is None:
                raise RuntimeError("requests required for new tab")

            # Create new tab - try with URL parameter first
            params = {"url": url} if url != "about:blank" else {}
            resp = await asyncio.to_thread(requests.get, f"http://127.0.0.1:{self.remote_debugging_port}/json/new", params=params, timeout=5)
            try:
                data = resp.json()
                tab_id = data.get('id', 'unknown')
            except Exception:
                data = {}
                tab_id = 'unknown'

            # Wait for tab to be created
            await asyncio.sleep(1.5)

            # For non-blank URLs, explicitly navigate to ensure page loads
            if url != "about:blank":
                try:
                    # Get the new tab's websocket URL
                    pages = await asyncio.to_thread(self._get_page_targets)
                    # Find the newly created tab (last one or match by id)
                    new_tab = None
                    for p in pages:
                        if p.get('id') == tab_id or (p.get('url', '').startswith('chrome://') or p.get('url') == 'about:blank'):
                            new_tab = p
                            break

                    if not new_tab and pages:
                        new_tab = pages[-1]  # Fallback to last tab

                    if new_tab:
                        # Force navigation using Runtime.evaluate on the new tab
                        ws_url = new_tab.get('webSocketDebuggerUrl')
                        if ws_url:
                            js = f"window.location.href = {json.dumps(url)}; 'navigating'"
                            await self._cdp(ws_url, "Runtime.evaluate", {
                                "expression": js,
                                "returnByValue": True,
                                "userGesture": True,
                            }, timeout=8.0)
                            # Wait for navigation to complete
                            await asyncio.sleep(2.5)

                            # Verify navigation succeeded
                            try:
                                current_url = await self._cdp(ws_url, "Runtime.evaluate", {
                                    "expression": "window.location.href",
                                    "returnByValue": True,
                                }, timeout=5.0)
                                actual_url = current_url.get("result", {}).get("value", "")
                                logger.info(f"New tab verified at: {actual_url}")
                            except Exception as e:
                                logger.warning(f"Could not verify navigation: {e}")
                except Exception as e:
                    logger.warning(f"Explicit navigation failed, tab may be blank: {e}")

            return f"Opened new tab at {url}"

        if name in ("close_tab", "close", "close_current_tab"):
            pages = await asyncio.to_thread(self._get_page_targets)
            if not pages:
                return "No tabs to close"
            target_id = pages[0]["id"]
            if requests is None:
                raise RuntimeError("requests required for close")
            await asyncio.to_thread(requests.get, f"http://127.0.0.1:{self.remote_debugging_port}/json/close/{target_id}", timeout=5)
            return "Closed tab"

        if name in ("get_url", "get_current_url"):
            val = await self._evaluate("window.location.href")
            return str(val)

        if name in ("list_tabs", "get_tabs"):
            pages = await asyncio.to_thread(self._get_page_targets)
            return [{"id": p.get("id"), "url": p.get("url"), "title": p.get("title")} for p in pages]

        if name in ("switch_tab", "activate_tab"):
            tab_id = args.get("tab_id")
            if not tab_id:
                raise ValueError("switch_tab requires 'tab_id'")
            if requests is None:
                raise RuntimeError("requests required for switch_tab")
            await asyncio.to_thread(requests.get, f"http://127.0.0.1:{self.remote_debugging_port}/json/activate/{tab_id}", timeout=5)
            return f"Switched to tab {tab_id}"

        if name in ("close_other_tabs",):
            pages = await asyncio.to_thread(self._get_page_targets)
            if not pages:
                return "No tabs to close"
            count = 0
            for p in pages[1:]:
                tab_id = p.get("id")
                try:
                    await asyncio.to_thread(requests.get, f"http://127.0.0.1:{self.remote_debugging_port}/json/close/{tab_id}", timeout=5)
                    count += 1
                except Exception:
                    pass
            return f"Closed {count} other tabs"

        if name in ("get_cookies", "clear_cookies"):
            ws_url = await asyncio.to_thread(self._ensure_ws_url)
            if name == "clear_cookies":
                await self._cdp(ws_url, "Network.clearBrowserCache")
                await self._cdp(ws_url, "Network.clearBrowserCookies")
                return "Cookies and cache cleared"
            else:
                res = await self._cdp(ws_url, "Network.getCookies")
                return res.get("cookies", []) if isinstance(res, dict) else []

        if name in ("set_blocked_urls",):
            urls = args.get("urls", [])
            ws_url = await asyncio.to_thread(self._ensure_ws_url)
            await self._cdp(ws_url, "Network.enable")
            await self._cdp(ws_url, "Network.setBlockedURLs", {"urls": urls})
            return f"Blocked URLs: {urls}"

        if name in ("get_content", "get_page_content"):
            # Large content — slice to avoid huge payload
            js = "(document.documentElement.innerText || document.body.innerText || '').slice(0,15000)"
            val = await self._evaluate(js)
            return str(val or "No content")

        if name in ("execute_script", "evaluate", "execute_javascript", "run_js"):
            script = args.get("script") or args.get("expression") or args.get("js") or ""
            if not script:
                raise ValueError("execute_script requires 'script'")
            # If caller wrapped in (async function(){...})() we awaitPromise
            is_async = "await" in script or script.strip().startswith("(async")
            val = await self._evaluate(script, awaitPromise=is_async)
            return val if val is not None else "Script executed"

        if name in ("click", "click_element"):
            selector = args.get("selector") or args.get("css") or ""
            if not selector:
                raise ValueError("click requires 'selector'")
            js = f"""(() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return 'not found: {selector}';
                el.scrollIntoView({{block:'center', behavior:'instant'}});
                el.focus();
                el.click();
                // also dispatch mouse events for frameworks
                el.dispatchEvent(new MouseEvent('mousedown', {{bubbles:true}}));
                el.dispatchEvent(new MouseEvent('mouseup', {{bubbles:true}}));
                return 'clicked: {selector}';
            }})()"""
            val = await self._evaluate(js)
            return str(val)

        if name in ("type", "type_text", "input", "fill"):
            selector = args.get("selector") or args.get("css") or ""
            text = args.get("text") or args.get("value") or ""
            if not selector:
                raise ValueError("type requires 'selector'")
            # Enhanced JS with code editor support - uses DOM-based approach
            js = f"""(() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return 'not found: {selector}';
                el.focus();
                el.scrollIntoView({{block:'center'}});

                // --- ACE EDITOR DETECTION (DOM-based, no global dependency) ---
                const aceContainer = el.closest('.ace_editor');
                if (aceContainer) {{
                    try {{
                        // ACE editors store their instance in the DOM element
                        if (aceContainer.env && aceContainer.env.editor) {{
                            const editor = aceContainer.env.editor;
                            editor.setValue({json.dumps(text)}, -1);
                            editor.clearSelection();
                            editor.focus();
                            return 'ACE editor updated via DOM instance';
                        }}

                        // Try alternate ACE storage patterns
                        if (aceContainer.aceEditor) {{
                            aceContainer.aceEditor.setValue({json.dumps(text)}, -1);
                            aceContainer.aceEditor.clearSelection();
                            return 'ACE editor updated via aceEditor property';
                        }}

                        // Fallback: Manually set ACE content by manipulating lines
                        const lines = {json.dumps(text)}.split('\\n');
                        const lineElements = aceContainer.querySelectorAll('.ace_line_group');

                        // Last resort: Clear and simulate typing
                        el.value = '';
                        el.focus();

                        // Simulate typing each character with proper events
                        const textToType = {json.dumps(text)};
                        for (let i = 0; i < textToType.length; i++) {{
                            const char = textToType[i];
                            el.value += char;

                            const inputEvent = new InputEvent('input', {{
                                bubbles: true,
                                cancelable: true,
                                data: char,
                                inputType: 'insertText'
                            }});
                            el.dispatchEvent(inputEvent);

                            const keydownEvent = new KeyboardEvent('keydown', {{
                                key: char,
                                code: char === '\\n' ? 'Enter' : 'Key' + char.toUpperCase(),
                                bubbles: true
                            }});
                            el.dispatchEvent(keydownEvent);

                            const keyupEvent = new KeyboardEvent('keyup', {{
                                key: char,
                                bubbles: true
                            }});
                            el.dispatchEvent(keyupEvent);
                        }}

                        el.dispatchEvent(new Event('change', {{bubbles: true}}));
                        return 'ACE editor content set via simulation';
                    }} catch (e) {{
                        return 'ACE editor error: ' + e.message;
                    }}
                }}

                // --- CODEMIRROR EDITOR ---
                const cmElement = el.closest('.CodeMirror');
                if (cmElement && cmElement.CodeMirror) {{
                    try {{
                        cmElement.CodeMirror.setValue({json.dumps(text)});
                        cmElement.CodeMirror.focus();
                        return 'CodeMirror editor updated';
                    }} catch (e) {{
                        return 'CodeMirror error: ' + e.message;
                    }}
                }}

                // --- MONACO EDITOR ---
                try {{
                    if (typeof monaco !== 'undefined') {{
                        const models = monaco.editor.getModels();
                        if (models.length > 0) {{
                            models[0].setValue({json.dumps(text)});
                            return 'Monaco editor updated';
                        }}
                    }}
                }} catch (e) {{
                    // Monaco not available, continue
                }}

                // --- STANDARD INPUT/TEXTAREA/CONTENTEDITABLE ---
                if (el.isContentEditable) {{
                    el.textContent = {json.dumps(text)};
                }} else {{
                    el.value = {json.dumps(text)};
                    // For React controlled inputs
                    const proto = Object.getPrototypeOf(el);
                    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (desc && desc.set) {{
                        desc.set.call(el, {json.dumps(text)});
                    }}
                }}
                el.dispatchEvent(new Event('input', {{bubbles:true}}));
                el.dispatchEvent(new Event('change', {{bubbles:true}}));
                el.dispatchEvent(new KeyboardEvent('keydown', {{bubbles:true}}));
                el.dispatchEvent(new KeyboardEvent('keyup', {{bubbles:true}}));
                return 'typed into {selector}';
            }})()"""
            val = await self._evaluate(js)
            return str(val)

        if name in ("screenshot", "capture_screenshot", "take_screenshot"):
            full = bool(args.get("full_page") or args.get("fullPage"))
            ws_url = await asyncio.to_thread(self._ensure_ws_url)
            # Try CDP screenshot
            try:
                res = await self._cdp(ws_url, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": full})
                data = res.get("data", "") if isinstance(res, dict) else ""
                # We don't save file — just confirm
                return f"Screenshot captured ({len(data)} bytes base64, full_page={full})"
            except Exception as e:
                # Fallback: evaluate page dimensions
                return f"Screenshot failed: {e}"

        # ---- generic fallback: try evaluate if tool looks like JS ----
        logger.warning(f"Unknown Chrome tool '{tool_name}', trying evaluate fallback")
        if "script" in args:
            return await self._evaluate(args["script"], awaitPromise=True)
        return f"Unknown tool: {tool_name} args={args}"

    async def cleanup(self):
        """Cleanup Chrome CDP server — keep Chrome open so user can see results."""
        logger.info("Cleaning up Chrome CDP server (keeping browser open for visibility)...")
        # Intentionally do NOT kill Chrome on cleanup — user wants to see search results.
        # Chrome will stay running with --remote-debugging-port. It can be closed manually.
        # Only mark disconnected; process stays alive.
        self._connected = False
        # Note: do not call super().cleanup() — we are not an MCPServerStdio anymore


async def create_chrome_server(
    chrome_path: Optional[str] = None,
    user_data_dir: Optional[str] = None,
    remote_debugging_port: int = 9222,
    auto_connect: bool = True
) -> ChromeMCPServer:
    """
    Factory function to create and optionally connect to Chrome CDP server
    """
    server = ChromeMCPServer(
        chrome_path=chrome_path,
        user_data_dir=user_data_dir,
        remote_debugging_port=remote_debugging_port
    )
    if auto_connect:
        await server.connect()
    return server
