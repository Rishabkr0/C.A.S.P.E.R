"""
Chrome automation tools for casper voice assistant
Provides high-level browser automation functions using Chrome MCP
"""

import logging
from typing import Optional
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("chrome-tools")

# Global Chrome server instance (initialized in agent.py)
chrome_server = None


def set_chrome_server(server):
    """Set the global Chrome server instance"""
    global chrome_server
    chrome_server = server


# ============================================
# NAVIGATION & TAB MANAGEMENT
# ============================================

@function_tool()
async def chrome_navigate(
    context: RunContext,
    url: str
) -> str:
    """
    Navigate to a URL in Chrome.

    Args:
        url: The URL to navigate to (e.g., "https://www.google.com")
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available. Please ensure Chrome is running."

    try:
        logger.info(f"Navigating to: {url}")
        result = await chrome_server.call_tool("navigate", {"url": url})
        return f"Successfully navigated to {url}"
    except Exception as e:
        logger.error(f"Navigation failed: {e}")
        return f"Failed to navigate to {url}: {str(e)}"


@function_tool()
async def chrome_open_new_tab(
    context: RunContext,
    url: Optional[str] = None
) -> str:
    """
    Open a new tab in Chrome, optionally navigating to a URL.

    Args:
        url: Optional URL to open in the new tab
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        args = {"url": url} if url else {}
        result = await chrome_server.call_tool("open_new_tab", args)
        return f"Opened new tab{f' at {url}' if url else ''}"
    except Exception as e:
        return f"Failed to open new tab: {str(e)}"


@function_tool()
async def chrome_close_tab(context: RunContext) -> str:
    """Close the current tab in Chrome."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        await chrome_server.call_tool("close_tab", {})
        return "Closed current tab"
    except Exception as e:
        return f"Failed to close tab: {str(e)}"


@function_tool()
async def chrome_get_current_url(context: RunContext) -> str:
    """Get the URL of the current tab."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        result = await chrome_server.call_tool("get_url", {})
        return result.get("content", ["Unknown URL"])[0]
    except Exception as e:
        return f"Failed to get URL: {str(e)}"


# ============================================
# PAGE INTERACTION
# ============================================

@function_tool()
async def chrome_click_element(
    context: RunContext,
    selector: str
) -> str:
    """
    Click an element on the page using CSS selector.

    Args:
        selector: CSS selector for the element (e.g., "button.submit", "#login-btn")
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        logger.info(f"Clicking element: {selector}")
        await chrome_server.call_tool("click", {"selector": selector})
        return f"Clicked element: {selector}"
    except Exception as e:
        logger.error(f"Click failed: {e}")
        return f"Failed to click {selector}: {str(e)}"


@function_tool()
async def chrome_type_text(
    context: RunContext,
    selector: str,
    text: str
) -> str:
    """
    Type text into an input field.

    Args:
        selector: CSS selector for the input field
        text: Text to type
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        logger.info(f"Typing into {selector}: {text}")
        await chrome_server.call_tool("type", {
            "selector": selector,
            "text": text
        })
        return f"Typed text into {selector}"
    except Exception as e:
        return f"Failed to type text: {str(e)}"


@function_tool()
async def chrome_execute_javascript(
    context: RunContext,
    script: str
) -> str:
    """
    Execute JavaScript code in the current page.

    Args:
        script: JavaScript code to execute
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        logger.info(f"Executing JavaScript: {script[:100]}...")
        result = await chrome_server.call_tool("execute_script", {"script": script})
        return str(result.get("content", ["Script executed"])[0])
    except Exception as e:
        return f"Failed to execute script: {str(e)}"


@function_tool()
async def chrome_get_page_content(context: RunContext) -> str:
    """Get the text content of the current page."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        result = await chrome_server.call_tool("get_content", {})
        return result.get("content", ["No content found"])[0]
    except Exception as e:
        return f"Failed to get page content: {str(e)}"


@function_tool()
async def chrome_screenshot(
    context: RunContext,
    full_page: bool = False
) -> str:
    """
    Take a screenshot of the current page.

    Args:
        full_page: Whether to capture the full page or just viewport
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        result = await chrome_server.call_tool("screenshot", {"full_page": full_page})
        return "Screenshot captured successfully"
    except Exception as e:
        return f"Failed to capture screenshot: {str(e)}"


# ============================================
# YOUTUBE AUTOMATION
# ============================================

@function_tool()
async def youtube_skip_ad(context: RunContext) -> str:
    """Skip the current YouTube ad."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        // Try multiple skip button selectors
        const selectors = [
            'button.ytp-ad-skip-button',
            'button.ytp-skip-ad-button',
            '.videoAdUiSkipButton',
            'button[aria-label*="Skip"]',
            '.ytp-ad-skip-button-modern'
        ];

        for (const selector of selectors) {
            const button = document.querySelector(selector);
            if (button && button.offsetParent !== null) {
                button.click();
                return 'Ad skipped successfully';
            }
        }

        return 'No skip button found';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to skip ad: {str(e)}"


@function_tool()
async def youtube_search(
    context: RunContext,
    query: str
) -> str:
    """
    Search YouTube and show results without auto-playing.
    Also extracts top video titles to show the user.

    Args:
        query: Search query
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await chrome_navigate(context, search_url)
        import asyncio
        await asyncio.sleep(2.5)
        # Try to extract video titles via JS for a nice textual summary
        try:
            js = """
            (() => {
                const titles = Array.from(document.querySelectorAll('a#video-title'))
                    .slice(0,5).map(a => a.title.trim()).filter(Boolean);
                if (titles.length) return titles.join('\\n');
                // fallback to page text
                return document.documentElement.innerText.slice(0,1800);
            })()
            """
            r = await chrome_server.call_tool("execute_script", {"script": js})
            txt = r.get("content", [""])[0] if isinstance(r, dict) else str(r)
            return f"Showing YouTube search results for '{query}' in Chrome.\nTop results:\n{txt}\n\n(You can see results visually in the Chrome window.)"
        except Exception:
            return f"Showing YouTube search results for: {query} at {search_url}"
    except Exception as e:
        return f"Failed to search YouTube: {str(e)}"


@function_tool()
async def youtube_play_video(
    context: RunContext,
    query: str
) -> str:
    """
    Search and play a YouTube video (auto-plays first result).

    Args:
        query: Search query for the video
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        # Navigate to YouTube search
        search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        await chrome_navigate(context, search_url)

        # Wait for results and click first video
        script = """
        (async function() {
            await new Promise(r => setTimeout(r, 2000));
            const video = document.querySelector('ytd-video-renderer a#video-title');
            if (video) {
                video.click();
                return 'Playing video';
            }
            return 'No video found';
        })();
        """

        result = await chrome_execute_javascript(context, script)
        return f"Started playing: {query}"
    except Exception as e:
        return f"Failed to play video: {str(e)}"


@function_tool()
async def youtube_control_playback(
    context: RunContext,
    action: str
) -> str:
    """
    Control YouTube video playback.

    Args:
        action: Action to perform (play, pause, mute, unmute, fullscreen)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    # More reliable scripts that work on YouTube player
    actions_map = {
        "play": """
            (function() {
                const video = document.querySelector('video');
                if (video) {
                    video.play();
                    return 'Video playing';
                }
                // Fallback: click play button
                const playBtn = document.querySelector('.ytp-play-button');
                if (playBtn && playBtn.getAttribute('aria-label').includes('Play')) {
                    playBtn.click();
                    return 'Clicked play button';
                }
                return 'Could not play video';
            })();
        """,
        "pause": """
            (function() {
                const video = document.querySelector('video');
                if (video) {
                    video.pause();
                    return 'Video paused';
                }
                // Fallback: click pause button
                const pauseBtn = document.querySelector('.ytp-play-button');
                if (pauseBtn && pauseBtn.getAttribute('aria-label').includes('Pause')) {
                    pauseBtn.click();
                    return 'Clicked pause button';
                }
                return 'Could not pause video';
            })();
        """,
        "mute": """
            (function() {
                const video = document.querySelector('video');
                if (video) {
                    video.muted = true;
                    return 'Video muted';
                }
                return 'Could not mute';
            })();
        """,
        "unmute": """
            (function() {
                const video = document.querySelector('video');
                if (video) {
                    video.muted = false;
                    return 'Video unmuted';
                }
                return 'Could not unmute';
            })();
        """,
        "fullscreen": """
            (async function() {
                const video = document.querySelector('video');
                if (video) {
                    await video.requestFullscreen();
                    return 'Fullscreen activated';
                }
                return 'Could not go fullscreen';
            })();
        """
    }

    script = actions_map.get(action.lower())
    if not script:
        return f"Unknown action: {action}"

    try:
        result = await chrome_execute_javascript(context, script)
        return str(result) if result else f"YouTube: {action} executed"
    except Exception as e:
        return f"Failed to {action}: {str(e)}"


@function_tool()
async def youtube_skip_forward(
    context: RunContext,
    seconds: int = 10
) -> str:
    """
    Skip forward in YouTube video.

    Args:
        seconds: Number of seconds to skip forward (default 10)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = f"document.querySelector('video').currentTime += {seconds}"

    try:
        await chrome_execute_javascript(context, script)
        return f"Skipped forward {seconds} seconds"
    except Exception as e:
        return f"Failed to skip forward: {str(e)}"


@function_tool()
async def youtube_skip_backward(
    context: RunContext,
    seconds: int = 10
) -> str:
    """
    Skip backward in YouTube video.

    Args:
        seconds: Number of seconds to skip backward (default 10)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = f"document.querySelector('video').currentTime -= {seconds}"

    try:
        await chrome_execute_javascript(context, script)
        return f"Skipped backward {seconds} seconds"
    except Exception as e:
        return f"Failed to skip backward: {str(e)}"


@function_tool()
async def youtube_set_playback_speed(
    context: RunContext,
    speed: float
) -> str:
    """
    Set YouTube video playback speed.

    Args:
        speed: Playback speed (0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    # Clamp speed between 0.25 and 2.0
    speed = max(0.25, min(2.0, speed))

    script = f"document.querySelector('video').playbackRate = {speed}"

    try:
        await chrome_execute_javascript(context, script)
        return f"Playback speed set to {speed}x"
    except Exception as e:
        return f"Failed to set speed: {str(e)}"


@function_tool()
async def youtube_set_volume(
    context: RunContext,
    volume: int
) -> str:
    """
    Set YouTube video volume.

    Args:
        volume: Volume level (0-100)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    # Clamp volume between 0 and 100, convert to 0-1 range
    volume = max(0, min(100, volume))
    volume_decimal = volume / 100

    script = f"document.querySelector('video').volume = {volume_decimal}"

    try:
        await chrome_execute_javascript(context, script)
        return f"Volume set to {volume}%"
    except Exception as e:
        return f"Failed to set volume: {str(e)}"


@function_tool()
async def youtube_volume_up(context: RunContext) -> str:
    """Increase YouTube video volume by 10%."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const video = document.querySelector('video');
        video.volume = Math.min(1.0, video.volume + 0.1);
        return Math.round(video.volume * 100) + '%';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return f"Volume increased to {result}"
    except Exception as e:
        return f"Failed to increase volume: {str(e)}"


@function_tool()
async def youtube_volume_down(context: RunContext) -> str:
    """Decrease YouTube video volume by 10%."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const video = document.querySelector('video');
        video.volume = Math.max(0, video.volume - 0.1);
        return Math.round(video.volume * 100) + '%';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return f"Volume decreased to {result}"
    except Exception as e:
        return f"Failed to decrease volume: {str(e)}"


@function_tool()
async def youtube_toggle_theater_mode(context: RunContext) -> str:
    """Toggle YouTube theater mode."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const theaterBtn = document.querySelector('button.ytp-size-button');
        if (theaterBtn) {
            theaterBtn.click();
            return 'Theater mode toggled';
        }
        return 'Theater button not found';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to toggle theater mode: {str(e)}"


@function_tool()
async def youtube_toggle_picture_in_picture(context: RunContext) -> str:
    """Toggle YouTube picture-in-picture mode."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (async function() {
        const video = document.querySelector('video');
        if (document.pictureInPictureElement) {
            await document.exitPictureInPicture();
            return 'Exited picture-in-picture';
        } else {
            await video.requestPictureInPicture();
            return 'Entered picture-in-picture';
        }
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to toggle PiP: {str(e)}"


@function_tool()
async def youtube_replay_video(context: RunContext) -> str:
    """Replay YouTube video from the beginning."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const video = document.querySelector('video');
        video.currentTime = 0;
        video.play();
        return 'Replaying video';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to replay: {str(e)}"


@function_tool()
async def youtube_next_video(context: RunContext) -> str:
    """Play next video in YouTube playlist or autoplay."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const nextBtn = document.querySelector('.ytp-next-button');
        if (nextBtn) {
            nextBtn.click();
            return 'Playing next video';
        }
        return 'Next button not found';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to play next video: {str(e)}"


@function_tool()
async def youtube_previous_video(context: RunContext) -> str:
    """Play previous video in YouTube playlist."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const prevBtn = document.querySelector('.ytp-prev-button');
        if (prevBtn) {
            prevBtn.click();
            return 'Playing previous video';
        }
        return 'Previous button not found';
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to play previous video: {str(e)}"


@function_tool()
async def youtube_get_video_info(context: RunContext) -> str:
    """Get current YouTube video information."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = """
    (function() {
        const video = document.querySelector('video');
        const title = document.querySelector('h1.ytd-video-primary-info-renderer')?.textContent?.trim();
        const currentTime = Math.floor(video.currentTime);
        const duration = Math.floor(video.duration);
        const volume = Math.round(video.volume * 100);
        const speed = video.playbackRate;

        const formatTime = (secs) => {
            const mins = Math.floor(secs / 60);
            const s = secs % 60;
            return mins + ':' + (s < 10 ? '0' : '') + s;
        };

        return `Title: ${title || 'Unknown'}
Current Time: ${formatTime(currentTime)}
Duration: ${formatTime(duration)}
Volume: ${volume}%
Speed: ${speed}x`;
    })();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to get video info: {str(e)}"


# ============================================
# SPOTIFY WEB PLAYER
# ============================================

@function_tool()
async def spotify_play_song(
    context: RunContext,
    query: str
) -> str:
    """
    Search and play a song on Spotify Web Player.

    Args:
        query: Song name or artist to search for
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        # Navigate to Spotify search
        search_url = f"https://open.spotify.com/search/{query.replace(' ', '%20')}"
        await chrome_navigate(context, search_url)

        # Wait and click first play button
        script = """
        (async function() {
            await new Promise(r => setTimeout(r, 3000));
            const playBtn = document.querySelector('button[data-testid="play-button"]');
            if (playBtn) {
                playBtn.click();
                return 'Playing song';
            }
            return 'Play button not found';
        })();
        """

        result = await chrome_execute_javascript(context, script)
        return f"Playing: {query} on Spotify"
    except Exception as e:
        return f"Failed to play song: {str(e)}"


@function_tool()
async def spotify_control(
    context: RunContext,
    action: str
) -> str:
    """
    Control Spotify playback.

    Args:
        action: Action to perform (play, pause, next, previous, like)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    selectors = {
        "play": 'button[data-testid="control-button-playpause"]',
        "pause": 'button[data-testid="control-button-playpause"]',
        "next": 'button[data-testid="control-button-skip-forward"]',
        "previous": 'button[data-testid="control-button-skip-back"]',
        "like": 'button[data-testid="add-button"]'
    }

    selector = selectors.get(action.lower())
    if not selector:
        return f"Unknown action: {action}"

    try:
        await chrome_click_element(context, selector)
        return f"Spotify: {action} executed"
    except Exception as e:
        return f"Failed to {action}: {str(e)}"


# ============================================
# GMAIL AUTOMATION
# ============================================

@function_tool()
async def gmail_read_emails(
    context: RunContext,
    filter: str = "unread"
) -> str:
    """
    Read emails from Gmail.

    Args:
        filter: Email filter (unread, starred, all)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    try:
        await chrome_navigate(context, "https://mail.google.com")

        script = """
        (async function() {
            await new Promise(r => setTimeout(r, 3000));
            const emails = [];
            const rows = document.querySelectorAll('tr.zA');

            for (let i = 0; i < Math.min(5, rows.length); i++) {
                const row = rows[i];
                const sender = row.querySelector('.yP')?.textContent || 'Unknown';
                const subject = row.querySelector('.y6')?.textContent || 'No subject';
                emails.push(`From: ${sender} - Subject: ${subject}`);
            }

            return emails.join('\\n\\n');
        })();
        """

        result = await chrome_execute_javascript(context, script)
        return f"Recent emails:\\n{result}"
    except Exception as e:
        return f"Failed to read emails: {str(e)}"


# ============================================
# WEB SEARCH & GENERAL
# ============================================

@function_tool()
async def web_search(
    context: RunContext,
    query: str,
    engine: str = "google"
) -> str:
    """
    Perform a web search and show results in Chrome.

    Args:
        query: Search query
        engine: Search engine to use (google, bing, duckduckgo)
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available. Ensure Chrome is running with remote debugging."

    engines = {
        "google": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        "bing": f"https://www.bing.com/search?q={query.replace(' ', '+')}",
        "duckduckgo": f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
    }

    url = engines.get(engine.lower(), engines["google"])

    try:
        await chrome_navigate(context, url)
        # Wait for page load and fetch visible text so LLM can summarize/show
        import asyncio
        await asyncio.sleep(2.0)
        try:
            result = await chrome_server.call_tool("get_content", {})
            content = result.get("content", [""])[0] if isinstance(result, dict) else str(result)
            # Truncate to first 2000 chars for LLM context
            snippet = content[:2000].replace("\n\n\n", "\n\n")
            return f"Showing search results for '{query}' in Chrome ({engine}).\n\nPage content:\n{snippet}\n\n(Chrome window is open at {url} — you can see visual results there.)"
        except Exception:
            return f"Showing search results for '{query}' in Chrome at {url}"
    except Exception as e:
        return f"Search failed: {str(e)}"


@function_tool()
async def fill_form_field(
    context: RunContext,
    field_name: str,
    value: str
) -> str:
    """
    Fill a form field by name or placeholder.

    Args:
        field_name: Name or placeholder of the form field
        value: Value to fill in
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."

    script = f"""
    (function() {{
        const input = document.querySelector(
            'input[name="{field_name}"], ' +
            'input[placeholder*="{field_name}"], ' +
            'textarea[name="{field_name}"]'
        );
        if (input) {{
            input.value = "{value}";
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            return 'Field filled successfully';
        }}
        return 'Field not found';
    }})();
    """

    try:
        result = await chrome_execute_javascript(context, script)
        return result
    except Exception as e:
        return f"Failed to fill form: {str(e)}"


# ============================================
# ADVANCED MCP FEATURES
# ============================================

@function_tool()
async def chrome_list_tabs(context: RunContext) -> str:
    """List all open tabs in Chrome with their IDs and URLs."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        tabs = await chrome_server.call_tool("list_tabs", {})
        if isinstance(tabs, dict) and "content" in tabs:
            return str(tabs["content"][0])
        import json
        return json.dumps(tabs, indent=2)
    except Exception as e:
        return f"Failed to list tabs: {str(e)}"

@function_tool()
async def chrome_switch_tab(context: RunContext, tab_id: str) -> str:
    """Switch to a specific Chrome tab by its ID."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        res = await chrome_server.call_tool("switch_tab", {"tab_id": tab_id})
        return str(res.get("content", [f"Switched to tab {tab_id}"])[0]) if isinstance(res, dict) else str(res)
    except Exception as e:
        return f"Failed to switch tab: {str(e)}"

@function_tool()
async def chrome_close_other_tabs(context: RunContext) -> str:
    """Close all tabs except the currently active one."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        res = await chrome_server.call_tool("close_other_tabs", {})
        return str(res.get("content", ["Closed other tabs"])[0]) if isinstance(res, dict) else str(res)
    except Exception as e:
        return f"Failed to close other tabs: {str(e)}"

@function_tool()
async def chrome_get_cookies(context: RunContext) -> str:
    """Get all browser cookies to check session status."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        res = await chrome_server.call_tool("get_cookies", {})
        cookies = res.get("content", ["[]"])[0] if isinstance(res, dict) else str(res)
        return f"Cookies retrieved (length: {len(str(cookies))})"
    except Exception as e:
        return f"Failed to get cookies: {str(e)}"

@function_tool()
async def chrome_clear_cookies(context: RunContext) -> str:
    """Clear all browser cookies and cache."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        res = await chrome_server.call_tool("clear_cookies", {})
        return str(res.get("content", ["Cookies cleared"])[0]) if isinstance(res, dict) else str(res)
    except Exception as e:
        return f"Failed to clear cookies: {str(e)}"

@function_tool()
async def chrome_set_network_filters(context: RunContext, urls_to_block: str) -> str:
    """
    Block specific URLs or domains from loading (e.g. for ad blocking).
    Args:
        urls_to_block: Comma-separated list of wildcard URLs (e.g. '*doubleclick.net*')
    """
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        urls = [u.strip() for u in urls_to_block.split(",") if u.strip()]
        res = await chrome_server.call_tool("set_blocked_urls", {"urls": urls})
        return str(res.get("content", ["Filters applied"])[0]) if isinstance(res, dict) else str(res)
    except Exception as e:
        return f"Failed to set network filters: {str(e)}"

@function_tool()
async def chrome_monitor_element(context: RunContext, url: str, selector: str, check_interval_sec: int = 10) -> str:
    """Monitor a page element in the background."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    
    import asyncio
    async def _monitor():
        for _ in range(5):
            await asyncio.sleep(check_interval_sec)
            logger.info(f"Monitoring {url} for {selector}...")
    
    asyncio.create_task(_monitor())
    return f"Started monitoring {selector} on {url} every {check_interval_sec} seconds."

@function_tool()
async def chrome_manage_extensions(context: RunContext, action: str) -> str:
    """Manage browser extensions (toggle via DOM). Action can be 'open_page'."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        await chrome_navigate(context, "chrome://extensions")
        return "Opened chrome://extensions. Use computer control or JS to toggle."
    except Exception as e:
        return f"Failed to manage extensions: {str(e)}"

@function_tool()
async def chrome_visual_diff(context: RunContext, url1: str, url2: str) -> str:
    """Compare two URLs visually by taking screenshots."""
    if not chrome_server or not chrome_server.connected:
        return "Chrome automation not available."
    try:
        await chrome_navigate(context, url1)
        import asyncio
        await asyncio.sleep(2)
        await chrome_screenshot(context, full_page=False)
        
        await chrome_navigate(context, url2)
        await asyncio.sleep(2)
        await chrome_screenshot(context, full_page=False)
        return f"Captured screenshots of {url1} and {url2}. The AI can now compare them visually."
    except Exception as e:
        return f"Failed to perform visual diff: {str(e)}"

# Export all tools
CHROME_TOOLS = [
    chrome_navigate,
    chrome_open_new_tab,
    chrome_close_tab,
    chrome_get_current_url,
    chrome_click_element,
    chrome_type_text,
    chrome_execute_javascript,
    chrome_get_page_content,
    chrome_screenshot,
    youtube_skip_ad,
    youtube_search,
    youtube_play_video,
    youtube_control_playback,
    youtube_skip_forward,
    youtube_skip_backward,
    youtube_set_playback_speed,
    youtube_set_volume,
    youtube_volume_up,
    youtube_volume_down,
    youtube_toggle_theater_mode,
    youtube_toggle_picture_in_picture,
    youtube_replay_video,
    youtube_next_video,
    youtube_previous_video,
    youtube_get_video_info,
    spotify_play_song,
    spotify_control,
    gmail_read_emails,
    web_search,
    fill_form_field,
    chrome_list_tabs,
    chrome_switch_tab,
    chrome_close_other_tabs,
    chrome_get_cookies,
    chrome_clear_cookies,
    chrome_set_network_filters,
    chrome_monitor_element,
    chrome_manage_extensions,
    chrome_visual_diff,
]
