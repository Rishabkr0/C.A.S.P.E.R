import logging
import pyautogui
import time
import os
import subprocess
import webbrowser
from uia_control import uia_loop, UIANotSupportedError

def normalize_app_name(target: str) -> tuple[str, list[str]]:
    """
    Normalizes app name and returns primary search term + list of search term variants to try.
    Handles hyphenation variations (e.g. anti-gravity -> antigravity), common STT phrasing.
    """
    target_clean = target.strip().lower()
    for verb in ["open ", "launch ", "start ", "run "]:
        if target_clean.startswith(verb):
            target_clean = target_clean[len(verb):].strip()

    target_clean = target_clean.replace("for me", "").strip()

    aliases = {
        "anti-gravity": "antigravity",
        "anti gravity": "antigravity",
        "visual code": "visual studio code",
        "visuals code": "visual studio code",
        "vs code": "vscode",
        "chrome browser": "chrome",
        "ms edge": "edge",
        "microsoft edge": "edge",
    }
    for k, v in aliases.items():
        if target_clean == k:
            target_clean = v
            break

    primary_search = target_clean.replace("anti-gravity", "antigravity").replace("anti gravity", "antigravity")
    variants = [primary_search]

    if "-" in target_clean:
        no_hyphen = target_clean.replace("-", "")
        if no_hyphen not in variants:
            variants.append(no_hyphen)
        space_hyphen = target_clean.replace("-", " ")
        if space_hyphen not in variants:
            variants.append(space_hyphen)

    if "antigravity" in target_clean:
        if "antigravity" not in variants:
            variants.insert(0, "antigravity")
        if "anti gravity" not in variants:
            variants.append("anti gravity")

    return primary_search, variants


def get_running_app_names_and_titles() -> set[str]:
    """Get set of lowercase names of running processes and open window titles."""
    names = set()
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            try:
                pname = p.info['name']
                if pname:
                    names.add(pname.lower())
            except Exception:
                pass
    except Exception:
        pass

    try:
        import win32gui
        def enum_win(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    names.add(title.lower())
        win32gui.EnumWindows(enum_win, None)
    except Exception:
        pass

    try:
        from pywinauto import Desktop
        for w in Desktop(backend="uia").windows():
            try:
                t = w.window_text().strip()
                if t:
                    names.add(t.lower())
            except Exception:
                pass
    except Exception:
        pass

    return names


def is_target_matched(target_keywords: list[str], current_names_and_titles: set[str]) -> bool:
    """Check if any running process or window title matches target keywords."""
    for item in current_names_and_titles:
        for kw in target_keywords:
            if len(kw) >= 3 and kw in item:
                return True
    return False


def launch_app(target: str) -> str:
    """
    Launches an app via Windows Search with normalization, fallback search terms,
    and empirical verification that the app process/window actually opened.
    Opens apps maximized.
    """
    import pyautogui
    import time

    primary_search, search_variants = normalize_app_name(target)

    keywords = [primary_search]
    if "antigravity" in primary_search or "anti-gravity" in primary_search or "anti gravity" in primary_search:
        keywords.extend(["antigravity", "anti-gravity", "anti gravity"])
    elif "code" in primary_search or "vscode" in primary_search:
        keywords.extend(["code", "vscode", "visual studio code"])
    elif "chrome" in primary_search:
        keywords.extend(["chrome"])
    elif "edge" in primary_search:
        keywords.extend(["msedge", "edge"])

    before_state = get_running_app_names_and_titles()

    # Pre-check: if already running / open, just focus it then maximize
    if is_target_matched(keywords, before_state):
        logging.info(f"App '{target}' already running. Bringing to focus.")
        pyautogui.hotkey("win")
        time.sleep(0.3)
        pyautogui.write(primary_search, interval=0.04)
        time.sleep(0.4)
        pyautogui.press("enter")
        time.sleep(1.0)
        pyautogui.hotkey("win", "up")  # Maximize
        return f"Successfully focused {target}."

    # Attempt launch using search variants
    for search_term in search_variants:
        logging.info(f"Attempting to launch app '{target}' using search term: '{search_term}'")
        pyautogui.hotkey("win")
        time.sleep(0.4)
        pyautogui.write(search_term, interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")

        # Poll for up to 3 seconds for new or matching process/window
        for _ in range(10):
            time.sleep(0.3)
            current_state = get_running_app_names_and_titles()
            new_items = current_state - before_state
            if is_target_matched(keywords, new_items) or is_target_matched(keywords, current_state):
                logging.info(f"Successfully verified app launch for '{target}' using search term '{search_term}'")
                time.sleep(0.5)          # Let the window fully render
                pyautogui.hotkey("win", "up")  # Maximize
                return f"Successfully opened {target}."

    logging.warning(f"Failed to verify launch for '{target}' after trying search terms: {search_variants}")
    return f"Failed to open '{target}'. No matching application was found on the system."



def skip_youtube_ad() -> str:
    """
    Searches for YouTube 'Skip Ad' buttons using UIA across active browser windows,
    falling back to browser focus and YouTube keyboard shortcuts if needed.
    """
    import pyautogui
    import time

    logging.info("Fast-path: Skipping YouTube Ad")

    # 1. Search UIA tree in open windows for 'Skip Ad' button
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                title = w.window_text().strip().lower()
                if any(b in title for b in ["youtube", "chrome", "edge", "firefox", "brave", "opera"]):
                    w.set_focus()
                    time.sleep(0.2)
                    for ctrl in w.descendants():
                        try:
                            ctrl_name = ctrl.window_text().strip().lower()
                            if any(k in ctrl_name for k in ["skip ad", "skip ads", "skip advert", "skip video"]) or ctrl_name == "skip":
                                if ctrl.is_visible() and ctrl.is_enabled():
                                    logging.info(f"Found Skip Ad button via UIA: '{ctrl.window_text()}'")
                                    ctrl.click_input()
                                    return "Successfully clicked Skip Ad button on YouTube."
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception as e:
        logging.warning(f"UIA Skip Ad search error: {e}")

    # 2. Fallback: Focus browser window and send YouTube keyboard shortcuts
    try:
        import win32gui
        def enum_win(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).strip().lower()
                if any(b in title for b in ["youtube", "chrome", "edge", "firefox", "brave"]):
                    win32gui.SetForegroundWindow(hwnd)
        win32gui.EnumWindows(enum_win, None)
    except Exception:
        pass

    time.sleep(0.3)
    # In YouTube web player, Tab then Enter / Space triggers Skip Ad if skippable
    pyautogui.press('tab')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(0.2)
    pyautogui.press('space')

    return "Attempted to skip YouTube ad."


def _spotify_find_window():
    """
    Returns the hwnd of the visible Spotify window, or None.
    Works even when the title shows the currently-playing song (no 'Spotify' in title).
    """
    import win32gui, win32process
    found = [None]
    def _cb(hwnd, _):
        if found[0] or not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd).lower()
        if "spotify" in title:
            found[0] = hwnd
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            import psutil
            if "spotify" in psutil.Process(pid).name().lower():
                found[0] = hwnd
        except Exception:
            pass
    win32gui.EnumWindows(_cb, None)
    return found[0]


def _spotify_pixel_scan_play(win_rect) -> tuple | None:
    """
    Scans the Spotify MAIN CONTENT AREA for Spotify-green (#1DB954) pixels.
    Excludes sidebar, right panel, top nav, and bottom player bar.
    Returns (cx, cy) screen coordinates of the button centroid, or None.
    """
    try:
        import numpy as np
        from PIL import ImageGrab
        wx_, wy_, wr_, wb_ = win_rect
        win_h = wb_ - wy_
        win_w = wr_ - wx_
        scan_x1 = wx_ + 232
        scan_x2 = wr_ - 280 if win_w > 700 else wr_
        scan_y1 = wy_ + 120
        scan_y2 = wy_ + int(win_h * 0.75)
        img = ImageGrab.grab(bbox=(scan_x1, scan_y1, scan_x2, scan_y2))
        arr = np.array(img)
        mask = (
            (arr[:, :, 0] >= 9)  & (arr[:, :, 0] <= 49)  &
            (arr[:, :, 1] >= 160) & (arr[:, :, 1] <= 210) &
            (arr[:, :, 2] >= 64)  & (arr[:, :, 2] <= 104)
        )
        ys, xs = np.where(mask)
        if len(xs) < 30:
            return None
        cx_ = int(xs.mean()) + scan_x1
        cy_ = int(ys.mean()) + scan_y1
        logging.info(f"Spotify pixel scan: found {len(xs)} green px, centroid=({cx_},{cy_})")
        return cx_, cy_
    except Exception as e:
        logging.warning(f"Pixel scan error: {e}")
        return None


async def play_spotify_playlist(task_lower: str) -> str:
    """
    Plays a Spotify playlist by name.
    Tries the user's saved playlists first (via spotipy OAuth cache),
    then falls back to public playlist search (client credentials).
    After navigating to the playlist page, uses pixel scan to click Play.
    """
    import re

    # --- Extract playlist name ---
    playlist_name = None
    patterns = [
        r"(?:shuffle|play)\s+(?:my\s+)?(.+?)\s+playlist",
        r"playlist\s+(?:called\s+|named\s+)?(.+?)(?:\s+on\s+spotify)?$",
        r"from\s+(?:my\s+)?(.+?)\s+playlist",
    ]
    for p in patterns:
        m = re.search(p, task_lower)
        if m:
            playlist_name = m.group(1).strip()
            break

    if not playlist_name:
        logging.warning("Could not extract playlist name, falling back to song search")
        return await play_spotify(task_lower)

    logging.info(f"play_spotify_playlist: searching for '{playlist_name}'")

    # --- Find playlist URI via spotipy ---
    playlist_uri = None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials

        # 1. Try user's saved playlists (uses cached OAuth token if available)
        try:
            sp_user = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
                scope="playlist-read-private playlist-read-collaborative",
                cache_path=".cache",
                open_browser=False,
            ))
            results = sp_user.current_user_playlists(limit=50)
            for pl in (results.get("items") or []):
                if pl and playlist_name.lower() in pl["name"].lower():
                    playlist_uri = pl["uri"]
                    logging.info(f"Found in user playlists: {pl['name']}")
                    break
        except Exception as e:
            logging.warning(f"User playlist lookup failed ({e}), trying public search")

        # 2. Fallback: search public playlists (no user auth needed)
        if not playlist_uri:
            sp_cc = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            ))
            res = sp_cc.search(q=playlist_name, type="playlist", limit=3)
            items = (res.get("playlists") or {}).get("items") or []
            if items:
                playlist_uri = items[0]["uri"]
                logging.info(f"Found public playlist: {items[0]['name']}")

    except Exception as e:
        logging.error(f"Spotipy playlist search error: {e}")

    if not playlist_uri:
        logging.warning(f"Playlist '{playlist_name}' not found, falling back to song search")
        return await play_spotify(task_lower)

    # --- Open the playlist in Spotify ---
    webbrowser.open(playlist_uri)
    await asyncio.sleep(3.0)

    # --- Find Spotify window ---
    import win32gui
    spotify_hwnd = _spotify_find_window()
    if not spotify_hwnd:
        return f"Could not find Spotify window for playlist '{playlist_name}'."

    win32gui.SetForegroundWindow(spotify_hwnd)
    await asyncio.sleep(0.3)
    rect = win32gui.GetWindowRect(spotify_hwnd)
    wx, wy, wr, wb = rect

    # Hard-focus via title bar click
    pyautogui.click(wx + (wr - wx) // 2, wy + 30)
    await asyncio.sleep(0.4)

    # On the playlist page the Play button is always visible (no hover needed).
    # Hover near the expected area so the button renders, then pixel scan.
    approx_x = wx + 280
    approx_y = wy + 310
    pyautogui.moveTo(approx_x, approx_y, duration=0.2)
    await asyncio.sleep(0.8)

    coords = await asyncio.to_thread(_spotify_pixel_scan_play, (wx, wy, wr, wb))
    if coords:
        cx, cy = coords
        logging.info(f"Clicking playlist play button at ({cx},{cy})")
        pyautogui.click(cx, cy)
        return f"Playing playlist '{playlist_name}' on Spotify."
    else:
        logging.warning("Green button not found on playlist page, double-clicking approx position")
        pyautogui.doubleClick(approx_x, approx_y)
        return f"Playing playlist '{playlist_name}' on Spotify (fallback)."


async def play_spotify(task_lower: str) -> str:
    """
    Hover-then-vision Spotify playback:
    1. ytmusicapi (2.5s timeout) for precise Title+Artist.
    2. Open spotify:search URI, hover at approximate card area to reveal play button.
    3. ONE vision call to identify the exact green play button coordinates.
    4. Click it.
    """
    import re
    import asyncio
    import io
    import json

    # --- Query extraction ---
    match = re.search(r"'(.*?)'|\"(.*?)\"", task_lower)
    if match:
        query = match.group(1) if match.group(1) else match.group(2)
    else:
        stop_words = {"search", "and", "play", "thing", "something", "song", "music",
                      "track", "on", "in", "spotify", "listen", "to", "for", "open",
                      "a", "the", "pause", "current", "instead", "it", "me"}
        filtered = [w for w in task_lower.split() if w not in stop_words]
        query = re.sub(r"[^\w\s]", "", " ".join(filtered)).strip()
    query = query or "top hits"

    logging.info(f"Spotify play_spotify: query='{query}'")

    # 1. ytmusicapi with timeout for precise Title + Artist
    precise_query = query
    try:
        def _yt_lookup():
            from ytmusicapi import YTMusic
            yt = YTMusic()
            results = yt.search(query, filter="songs", limit=1)
            if results:
                song = results[0]
                title = song.get("title", "")
                artists = song.get("artists", [])
                artist = artists[0].get("name", "") if artists else ""
                if title and artist:
                    return f"{title} {artist}"
            return query
        precise_query = await asyncio.wait_for(asyncio.to_thread(_yt_lookup), timeout=2.5)
        logging.info(f"ytmusicapi: '{query}' → '{precise_query}'")
    except Exception as e:
        logging.warning(f"ytmusicapi skipped ({e})")

    # 2. Open Spotify search
    webbrowser.open(f"spotify:search:{precise_query}")
    await asyncio.sleep(3.0)

    # 3. Bring Spotify to foreground — hard focus via click on title bar
    import win32gui
    spotify_hwnd = _spotify_find_window()
    if not spotify_hwnd:
        logging.error("Spotify window not found after opening search URI")
        return f"Could not find Spotify window to play '{precise_query}'."

    win32gui.SetForegroundWindow(spotify_hwnd)
    await asyncio.sleep(0.3)
    rect = win32gui.GetWindowRect(spotify_hwnd)
    wx, wy, wr, wb = rect

    # Hard-click Spotify's top bar to truly steal focus from any other app
    pyautogui.click(wx + (wr - wx) // 2, wy + 30)
    await asyncio.sleep(0.4)

    # 4. Hover at approximate Top Result card area to reveal the green play button
    approx_card_x = wx + 231 + 74
    approx_card_y = wy + 248 + 74
    pyautogui.moveTo(approx_card_x, approx_card_y, duration=0.2)
    await asyncio.sleep(1.2)

    # 5. Pixel-scan for the green play button using shared helper
    coords = await asyncio.to_thread(_spotify_pixel_scan_play, (wx, wy, wr, wb))
    if coords:
        cx, cy = coords
        logging.info(f"Clicking Spotify green play button at ({cx},{cy})")
        pyautogui.click(cx, cy)
        return f"Playing '{precise_query}' on Spotify."
    else:
        logging.warning("Green play button not found — double-clicking card position")
        pyautogui.doubleClick(approx_card_x, approx_card_y)
        return f"Playing '{precise_query}' on Spotify (double-click fallback)."



async def computer_use_loop(task: str, max_steps: int = 15) -> str:
    """
    Delegates to the text-based UIA control loop and Hybrid Vision Fallback.
    Handles universal window shortcuts (close, minimize, maximize) and app controls.
    """
    task_lower = task.lower().strip()
    
    # Universal Window Controls (Close, Minimize, Maximize)
    if "minimize" in task_lower:
        logging.info("Universal action: Minimizing active window")
        pyautogui.hotkey("win", "down")
        return "Minimized active window."

    if "maximize" in task_lower:
        logging.info("Universal action: Maximizing active window")
        pyautogui.hotkey("win", "up")
        return "Maximized active window."

    if task_lower.startswith("close ") or task_lower == "close window" or task_lower == "close app":
        logging.info(f"Universal action: Closing window ({task})")
        pyautogui.hotkey("alt", "f4")
        return "Closed active window."

    # Fast-path for media controls (Pause, Play, Next, Mute)
    media_commands = {
        "pause": "playpause",
        "stop": "playpause",
        "play": "playpause",
        "resume": "playpause",
        "next": "nexttrack",
        "change": "nexttrack",
        "skip": "nexttrack",
        "previous": "prevtrack",
        "back": "prevtrack",
        "mute": "volumemute",
        "unmute": "volumemute"
    }
    
    # We strip common filler words to check if the core command is just a media action
    core_task = task_lower.replace("the", "").replace("this", "").replace("video", "").replace("song", "").replace("music", "").replace("track", "").replace("playback", "").replace("currently", "").replace("playing", "").strip()
    
    if core_task in media_commands:
        key = media_commands[core_task]
        logging.info(f"Fast-path media control: {core_task} (mapped to {key})")
        pyautogui.press(key)
        return f"Executed media command: {core_task}"

    # Fast-path for skipping YouTube Ads
    if "skip" in task_lower and any(ad_kw in task_lower for ad_kw in ["ad", "ads", "advert"]):
        return skip_youtube_ad()


    # Fast-path for Spotify PLAYLIST requests (before generic song search)
    if "spotify" in task_lower and "playlist" in task_lower and any(act in task_lower for act in ["play", "shuffle", "listen"]):
        return await play_spotify_playlist(task_lower)

    # Fast-path for playing/searching on Spotify
    if "spotify" in task_lower and any(act in task_lower for act in ["play", "search", "listen"]):
        return await play_spotify(task_lower)

    # Fast-path for playing/searching on YouTube
    if "youtube" in task_lower and ("play" in task_lower or "search" in task_lower):
        import pywhatkit
        query = task_lower.replace("play", "").replace("search", "").replace("on youtube", "").replace("in youtube", "").replace("for", "").strip()
        if not query:
            query = "latest music"
            
        logging.info(f"Fast-path YouTube playback for query: {query}")
        try:
            pywhatkit.playonyt(query)
            return f"Successfully started playing '{query}' on YouTube."
        except Exception as e:
            return f"Failed to play on YouTube directly: {e}"

    # Fast-path for opening folder in VS Code
    if ("folder" in task_lower or "directory" in task_lower) and ("vs code" in task_lower or "vscode" in task_lower or "code" in task_lower):
        logging.info(f"Fast-path opening folder in VS Code: {task}")
        docs_path = os.path.expanduser("~/Documents")
        desktop_path = os.path.expanduser("~/Desktop")
        
        words = task_lower.replace("open", "").replace("folder", "").replace("directory", "").replace("in vs code", "").replace("in vscode", "").replace("in documents", "").replace("in document", "").strip().split()
        folder_name = words[-1] if words else ""
        
        target_path = None
        if folder_name:
            if os.path.exists(os.path.join(docs_path, folder_name)):
                target_path = os.path.join(docs_path, folder_name)
            elif os.path.exists(os.path.join(desktop_path, folder_name)):
                target_path = os.path.join(desktop_path, folder_name)
        
        if target_path:
            subprocess.Popen(f'code "{target_path}"', shell=True)
            return f"Successfully opened folder '{folder_name}' in VS Code."
        else:
            pyautogui.hotkey('ctrl', 'k')
            time.sleep(0.1)
            pyautogui.hotkey('ctrl', 'o')
            time.sleep(0.8)
            if folder_name:
                import pyperclip
                pyperclip.copy(folder_name)
                pyautogui.hotkey('ctrl', 'v')
                time.sleep(0.3)
                pyautogui.press('enter')
            return f"Attempted to open folder '{folder_name}' in VS Code."

    if any(task_lower.startswith(verb) for verb in ["open ", "launch ", "start "]) and len(task_lower.split()) <= 5:
        verb, target = task_lower.split(" ", 1)
        target = target.strip()
        
        if "youtube" in target:
            webbrowser.open("https://www.youtube.com")
            return "Opened YouTube in the default browser."
        if "google" in target and "chrome" not in target:
            webbrowser.open("https://www.google.com")
            return "Opened Google in the default browser."
            
        logging.info(f"Fast-path opening app: {target}")
        return launch_app(target)

    try:
        logging.info("Attempting task via UIA text tree")
        res = await uia_loop(task, max_steps=max_steps)
        if "Task failed" not in res:
            return res
        logging.info("UIA returned task failure, switching to Hybrid Vision Fallback...")
    except Exception as e:
        logging.warning(f"UIA loop failed ({e}), switching to Hybrid Vision Fallback...")

    from vision_fallback import vision_fallback_step
    logging.info("Executing Hybrid Vision Fallback (Single Scaled Screenshot)")
    summary, _ = await vision_fallback_step(task, [])
    return summary
