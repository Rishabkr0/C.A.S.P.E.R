"""
Enhanced computer use with Chrome MCP integration
Routes browser tasks to Chrome MCP for faster, more reliable automation
"""

import logging
import asyncio
from typing import Optional

# Import existing functions
from computer_use_original import (
    normalize_app_name,
    get_running_app_names_and_titles,
    is_target_matched,
    launch_app,
    _spotify_find_window,
    _spotify_pixel_scan_play,
)

logger = logging.getLogger("computer_use_enhanced")

import re

# Common sites for general browser navigation
COMMON_SITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "spotify": "https://open.spotify.com",
    "twitter": "https://twitter.com",
    "facebook": "https://www.facebook.com",
    "linkedin": "https://www.linkedin.com",
    "instagram": "https://www.instagram.com",
    "reddit": "https://www.reddit.com",
    "github": "https://github.com",
    "netflix": "https://www.netflix.com",
    "amazon": "https://www.amazon.com",
}

# Chrome tools will be imported after initialization
chrome_tools = None


def set_chrome_tools(tools_module):
    """Set the Chrome tools module"""
    global chrome_tools
    chrome_tools = tools_module


def is_browser_task(task: str) -> bool:
    """Determine if a task should use Chrome automation"""
    task_lower = task.lower()

    # Fast-path: YouTube ad skip is ALWAYS a browser task even without "youtube" keyword
    if "skip" in task_lower and "ad" in task_lower:
        return True

    browser_keywords = [
        "youtube", "tube", "spotify web", "gmail", "email", "search",
        "google", "website", "web page", "browser", "chrome",
        "open.spotify.com", "mail.google.com", "twitter",
        "facebook", "linkedin", "instagram", "reddit",
        "netflix", "prime video", "amazon", "flipkart",
        "shopping", "form", "login", "sign in",
        "tab", "tabs", "cookie", "cookies", "block ads",
        "extension", "extensions", "monitor",
    ]

    # Check if it's specifically for Spotify desktop app
    if "spotify" in task_lower and "app" in task_lower:
        return False

    return any(keyword in task_lower for keyword in browser_keywords)


async def handle_youtube_task(task: str) -> str:
    """Handle YouTube-specific tasks using Chrome MCP"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Skip ad
        if "skip" in task_lower and "ad" in task_lower:
            return await chrome_tools.youtube_skip_ad(None)

        # Volume controls (check before play/pause to avoid conflicts)
        if "volume up" in task_lower or "increase volume" in task_lower:
            return await chrome_tools.youtube_volume_up(None)
        if "volume down" in task_lower or "decrease volume" in task_lower:
            return await chrome_tools.youtube_volume_down(None)
        if "volume" in task_lower and ("set" in task_lower or any(char.isdigit() for char in task_lower)):
            # Extract volume number
            match = re.search(r'\d+', task_lower)
            if match:
                volume = int(match.group())
                return await chrome_tools.youtube_set_volume(None, volume)

        # Skip forward/backward
        if "skip forward" in task_lower or "forward" in task_lower:
            match = re.search(r'\d+', task_lower)
            seconds = int(match.group()) if match else 10
            return await chrome_tools.youtube_skip_forward(None, seconds)
        if "skip backward" in task_lower or "backward" in task_lower or "rewind" in task_lower:
            match = re.search(r'\d+', task_lower)
            seconds = int(match.group()) if match else 10
            return await chrome_tools.youtube_skip_backward(None, seconds)

        # Playback speed
        if "speed" in task_lower:
            match = re.search(r'(\d+\.?\d*)', task_lower)
            if match:
                speed = float(match.group())
                return await chrome_tools.youtube_set_playback_speed(None, speed)

        # Playback control - check for pause/play BEFORE searching
        if task_lower in ["pause", "pause video", "pause the video", "pause this", "pause it"]:
            return await chrome_tools.youtube_control_playback(None, "pause")
        if task_lower in ["play", "play video", "play the video", "resume", "continue"]:
            return await chrome_tools.youtube_control_playback(None, "play")

        # Mute/unmute
        if "mute" in task_lower and "unmute" not in task_lower:
            return await chrome_tools.youtube_control_playback(None, "mute")
        if "unmute" in task_lower:
            return await chrome_tools.youtube_control_playback(None, "unmute")

        # Fullscreen
        if "fullscreen" in task_lower or "full screen" in task_lower:
            return await chrome_tools.youtube_control_playback(None, "fullscreen")

        # Theater mode
        if "theater" in task_lower:
            return await chrome_tools.youtube_toggle_theater_mode(None)

        # Picture in picture
        if "picture" in task_lower or "pip" in task_lower:
            return await chrome_tools.youtube_toggle_picture_in_picture(None)

        # Next/Previous video
        if "next video" in task_lower or "next" in task_lower:
            return await chrome_tools.youtube_next_video(None)
        if "previous video" in task_lower or "previous" in task_lower or "last video" in task_lower:
            return await chrome_tools.youtube_previous_video(None)

        # Replay
        if "replay" in task_lower or "restart" in task_lower:
            return await chrome_tools.youtube_replay_video(None)

        # Get info
        if "info" in task_lower or "information" in task_lower:
            return await chrome_tools.youtube_get_video_info(None)

        # Search (show results, don't auto-play) - must NOT contain "play"
        if ("search" in task_lower or "find" in task_lower or "look for" in task_lower or "show me" in task_lower) and "play" not in task_lower:
            # Extract query
            query = task_lower
            for word in ["search", "find", "look for", "show me", "show", "on youtube", "youtube", "for", "results", "videos of", "videos about"]:
                query = query.replace(word, "")
            query = query.strip()
            if query:
                return await chrome_tools.youtube_search(None, query)

        # Play video (auto-play first result) - only if contains "play"
        if "play" in task_lower:
            # Extract query
            query = task_lower.replace("play", "")
            query = query.replace("on youtube", "").replace("youtube", "").strip()
            if query:
                return await chrome_tools.youtube_play_video(None, query)

        return "YouTube task not recognized"

    except Exception as e:
        logger.error(f"YouTube task failed: {e}")
        return f"Failed to complete YouTube task: {str(e)}"


async def handle_spotify_web_task(task: str) -> str:
    """Handle Spotify Web Player tasks using Chrome MCP"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Play song/artist
        if "play" in task_lower or "search" in task_lower:
            query = task_lower.replace("play", "").replace("search", "")
            query = query.replace("on spotify", "").replace("spotify", "").strip()
            if query:
                return await chrome_tools.spotify_play_song(None, query)

        # Playback control
        if "pause" in task_lower or "stop" in task_lower:
            return await chrome_tools.spotify_control(None, "pause")
        if "next" in task_lower or "skip" in task_lower:
            return await chrome_tools.spotify_control(None, "next")
        if "previous" in task_lower or "back" in task_lower:
            return await chrome_tools.spotify_control(None, "previous")
        if "like" in task_lower or "save" in task_lower:
            return await chrome_tools.spotify_control(None, "like")

        return "Spotify task not recognized"

    except Exception as e:
        logger.error(f"Spotify task failed: {e}")
        return f"Failed to complete Spotify task: {str(e)}"


async def handle_gmail_task(task: str) -> str:
    """Handle Gmail tasks using Chrome MCP"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Read emails
        if "read" in task_lower or "check" in task_lower or "show" in task_lower:
            filter_type = "unread"
            if "starred" in task_lower:
                filter_type = "starred"
            elif "all" in task_lower:
                filter_type = "all"

            return await chrome_tools.gmail_read_emails(None, filter_type)

        # Open Gmail
        return await chrome_tools.chrome_navigate(None, "https://mail.google.com")

    except Exception as e:
        logger.error(f"Gmail task failed: {e}")
        return f"Failed to complete Gmail task: {str(e)}"


async def handle_web_search_task(task: str) -> str:
    """Handle web search tasks using Chrome MCP"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Extract search query
        query = task_lower
        for word in ["search", "google", "find", "look up", "for"]:
            query = query.replace(word, "")
        query = query.strip()

        # Determine search engine
        engine = "google"
        if "bing" in task_lower:
            engine = "bing"
        elif "duckduckgo" in task_lower:
            engine = "duckduckgo"

        if query:
            return await chrome_tools.web_search(None, query, engine)

        return "No search query provided"

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Failed to search: {str(e)}"

async def handle_advanced_browser_task(task: str) -> str:
    """Handle advanced Chrome tasks like tabs, cookies, extensions"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Tabs
        if "list tabs" in task_lower or "show tabs" in task_lower or "open tabs" in task_lower:
            return await chrome_tools.chrome_list_tabs(None)
        if "close other tabs" in task_lower:
            return await chrome_tools.chrome_close_other_tabs(None)
        if "switch to tab" in task_lower or "go to tab" in task_lower:
            match = re.search(r'tab\s+([a-zA-Z0-9_]+)', task_lower)
            if match:
                return await chrome_tools.chrome_switch_tab(None, match.group(1))
            return "Please provide the tab ID"

        # Cookies
        if "clear cookies" in task_lower or "delete cookies" in task_lower:
            return await chrome_tools.chrome_clear_cookies(None)
        if "get cookies" in task_lower or "show cookies" in task_lower:
            return await chrome_tools.chrome_get_cookies(None)

        # Network filters
        if "block ads" in task_lower or "block ad" in task_lower:
            return await chrome_tools.chrome_set_network_filters(None, "*doubleclick.net*,*googleadservices.com*,*googlesyndication.com*")
        
        # Extensions
        if "extension" in task_lower or "extensions" in task_lower:
            return await chrome_tools.chrome_manage_extensions(None, "open")

        return "Advanced task not recognized"

    except Exception as e:
        logger.error(f"Advanced browser task failed: {e}")
        return f"Failed to complete advanced task: {str(e)}"


async def handle_general_browser_task(task: str) -> str:
    """Handle general browser navigation tasks"""
    if not chrome_tools:
        return "Chrome automation not available"

    task_lower = task.lower()

    try:
        # Extract URL or website name
        if "open" in task_lower:
            for site, url in COMMON_SITES.items():
                if site in task_lower:
                    return await chrome_tools.chrome_navigate(None, url)

            # Try to extract URL
            words = task_lower.split()
            for word in words:
                if "." in word and not word.startswith("."):
                    url = word if word.startswith("http") else f"https://{word}"
                    return await chrome_tools.chrome_navigate(None, url)

        return "Could not determine website to open"

    except Exception as e:
        logger.error(f"Browser task failed: {e}")
        return f"Failed to complete browser task: {str(e)}"


async def chrome_automation(task: str) -> str:
    """
    Route browser tasks to appropriate Chrome MCP handler

    Args:
        task: The task description

    Returns:
        Result message
    """
    if not chrome_tools:
        logger.warning("Chrome tools not available, falling back to traditional automation")
        raise Exception("Chrome tools not initialized")

    task_lower = task.lower()

    # Route to specific handlers
    if "youtube" in task_lower:
        return await handle_youtube_task(task)

    if "spotify" in task_lower and "web" not in task_lower:
        # Prefer web player for better reliability
        return await handle_spotify_web_task(task)

    if "gmail" in task_lower or "email" in task_lower:
        return await handle_gmail_task(task)

    if "search" in task_lower or "google" in task_lower:
        return await handle_web_search_task(task)

    if any(k in task_lower for k in ["tab", "tabs", "cookie", "cookies", "block ads", "extension", "extensions", "monitor"]):
        result = await handle_advanced_browser_task(task)
        if result != "Advanced task not recognized":
            return result

    # General browser navigation
    return await handle_general_browser_task(task)


# Import original computer_use_loop for fallback
async def computer_use_loop_original(task: str, max_steps: int = 15) -> str:
    """Original computer use loop - imported from computer_use.py"""
    # This will be the original implementation
    from computer_use_original import computer_use_loop as original_loop
    return await original_loop(task, max_steps)


async def computer_use_loop(task: str, max_steps: int = 15) -> str:
    """
    Enhanced computer use loop with Chrome MCP integration

    Priority:
    1. Chrome MCP for browser tasks (fastest, most reliable)
    2. Original UIA + Vision fallback for desktop apps

    Args:
        task: The task to accomplish
        max_steps: Maximum automation steps

    Returns:
        Task result message
    """
    task_lower = task.lower().strip()

    # Check if this is a browser task and Chrome is available
    if is_browser_task(task_lower) and chrome_tools:
        try:
            logger.info(f"Routing browser task to Chrome MCP: {task}")
            result = await chrome_automation(task_lower)

            # If Chrome automation succeeded, return result
            if "not available" not in result.lower() and "failed" not in result.lower():
                return result

            logger.info("Chrome MCP failed, falling back to original automation")

        except Exception as e:
            logger.warning(f"Chrome automation failed: {e}, falling back to original")

    # Fall back to original computer use loop
    logger.info(f"Using original automation for: {task}")
    from computer_use_original import computer_use_loop as original_loop
    return await original_loop(task, max_steps)
