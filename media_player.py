import os
import subprocess
import threading
import urllib.request
import zipfile
import shutil
import yt_dlp
import sys
import logging
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
FFPLAY_PATH = os.path.join(BIN_DIR, "ffplay.exe")

_current_player_process = None
_music_queue = []
_worker_running = False
_worker_thread = None

def download_ffplay_if_needed():
    if os.path.exists(FFPLAY_PATH):
        return True
        
    logger.info("ffplay not found. Downloading it automatically (this only happens once)...")
    os.makedirs(BIN_DIR, exist_ok=True)
    zip_path = os.path.join(BIN_DIR, "ffmpeg.zip")
    extract_path = os.path.join(BIN_DIR, "ffmpeg_extract")
    
    try:
        logger.info(f"Downloading FFmpeg from {FFMPEG_URL}...")
        urllib.request.urlretrieve(FFMPEG_URL, zip_path)
        logger.info("Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
            
        extracted_ffplay = None
        for root, dirs, files in os.walk(extract_path):
            if "ffplay.exe" in files:
                extracted_ffplay = os.path.join(root, "ffplay.exe")
                break
                
        if extracted_ffplay:
            shutil.move(extracted_ffplay, FFPLAY_PATH)
            logger.info(f"Successfully installed ffplay to {FFPLAY_PATH}")
        else:
            return False
    except Exception as e:
        logger.error(f"Failed to setup ffplay: {e}")
        return False
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path, ignore_errors=True)
            
    return os.path.exists(FFPLAY_PATH)

def get_audio_stream_url(search_query: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=False)
        if 'entries' in info and len(info['entries']) > 0:
            return info['entries'][0]['url']
        elif 'url' in info:
            return info['url']
    raise ValueError(f"Could not find stream URL for: {search_query}")

def _playback_worker():
    global _current_player_process, _worker_running, _music_queue
    while _worker_running:
        # Check if process finished
        if _current_player_process:
            if _current_player_process.poll() is not None:
                _current_player_process = None
        
        # Play next song if available
        if _current_player_process is None and len(_music_queue) > 0:
            next_song = _music_queue.pop(0)
            try:
                stream_url = get_audio_stream_url(next_song)
                creationflags = 0x08000000 if sys.platform == "win32" else 0
                cmd = [FFPLAY_PATH, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "error", stream_url]
                _current_player_process = subprocess.Popen(
                    cmd, 
                    creationflags=creationflags,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                logger.info(f"Queue worker started playing: {next_song}")
            except Exception as e:
                logger.error(f"Queue worker failed to play {next_song}: {e}")
                
        time.sleep(1)

def _ensure_worker_running():
    global _worker_running, _worker_thread
    if not _worker_running:
        if not download_ffplay_if_needed():
            raise RuntimeError("Could not setup media player binary.")
        _worker_running = True
        _worker_thread = threading.Thread(target=_playback_worker, daemon=True)
        _worker_thread.start()

def add_to_queue(search_query: str):
    """Adds a song to the playback queue."""
    _ensure_worker_running()
    _music_queue.append(search_query)
    return f"Added to queue: {search_query}"

def get_queue():
    """Returns the current queue."""
    if not _music_queue:
        return "The music queue is currently empty."
    return "Queue:\n" + "\n".join([f"{i+1}. {song}" for i, song in enumerate(_music_queue)])

def play_song(search_query: str):
    """Clears the queue and immediately plays a song."""
    global _music_queue, _current_player_process
    _ensure_worker_running()
    
    _music_queue.clear()
    _music_queue.append(search_query)
    
    if _current_player_process and _current_player_process.poll() is None:
        _current_player_process.terminate()
        
    return f"Now playing: {search_query}"

def skip_song():
    """Skips the currently playing song."""
    global _current_player_process
    if _current_player_process and _current_player_process.poll() is None:
        _current_player_process.terminate()
        return "Song skipped."
    return "Nothing is currently playing to skip."

def stop_song():
    """Stops playback and clears the queue."""
    global _music_queue, _current_player_process
    _music_queue.clear()
    if _current_player_process and _current_player_process.poll() is None:
        _current_player_process.terminate()
        _current_player_process.wait(timeout=2)
        _current_player_process = None
        return "Playback stopped and queue cleared."
    return "Nothing is currently playing."

def set_music_volume(level: int):
    """Sets the volume of the background music player (0-100)."""
    try:
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        found = False
        for session in sessions:
            if session.Process and session.Process.name().lower() == "ffplay.exe":
                volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                volume.SetMasterVolume(max(0.0, min(1.0, level / 100.0)), None)
                found = True
        if found:
            return f"Music volume set to {level}%."
        else:
            return "Could not find an active music player process. Please ensure a song is playing first."
    except Exception as e:
        logger.error(f"Failed to set volume: {e}")
        return f"Error setting volume: {e}"
