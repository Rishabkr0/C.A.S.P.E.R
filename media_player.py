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
import socket
import psutil

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
BIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin")
FFPLAY_PATH = os.path.join(BIN_DIR, "ffplay.exe")

_current_player_process = None
_music_queue = []
_song_history = []
_current_song = None
_current_stream_url = None
_current_duration = 0
_current_title = ""
_current_thumbnail = ""
_is_seeking = False
_worker_running = False
_worker_thread = None
_is_paused = False
_current_volume = 80

def _send_ui_message(msg: str):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(msg.encode('utf-8'), ('127.0.0.1', 49152))
        sock.close()
    except Exception as e:
        logger.error(f"Failed to send UI message: {e}")


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

def get_audio_stream_url(search_query: str) -> dict:
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch1'
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=False)
        entry = info['entries'][0] if 'entries' in info and len(info['entries']) > 0 else info
        if 'url' in entry:
            return {
                'url': entry['url'],
                'title': entry.get('title', search_query),
                'thumbnail': entry.get('thumbnail', ''),
                'duration': int(entry.get('duration', 0) or 0)
            }
    raise ValueError(f"Could not find stream URL for: {search_query}")

def _playback_worker():
    global _current_player_process, _worker_running, _music_queue, _is_paused, _current_song, _song_history, _current_volume
    global _current_stream_url, _current_duration, _current_title, _current_thumbnail, _is_seeking
    while _worker_running:
        try:
            # Check if process finished (skip if currently seeking)
            if _current_player_process and not _is_seeking:
                if _current_player_process.poll() is not None:
                    if not _is_seeking:
                        _current_player_process = None
                        _current_stream_url = None
                        _current_duration = 0
                        if len(_music_queue) == 0:
                            _send_ui_message("MUSIC:STOP")
            
            # Play next song if available
            if _current_player_process is None and len(_music_queue) > 0 and not _is_seeking:
                next_song = _music_queue.pop(0)
                if _current_song:
                    _song_history.append(_current_song)
                _current_song = next_song
                try:
                    media_info = get_audio_stream_url(next_song)
                    _current_stream_url = media_info['url']
                    _current_title = media_info['title']
                    _current_thumbnail = media_info['thumbnail']
                    _current_duration = int(media_info.get('duration', 0) or 0)
                    
                    creationflags = 0x08000000 if sys.platform == "win32" else 0
                    cmd = [FFPLAY_PATH, "-nodisp", "-autoexit", "-hide_banner", "-loglevel", "error", "-volume", str(_current_volume), _current_stream_url]
                    _current_player_process = subprocess.Popen(
                        cmd, 
                        creationflags=creationflags,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    _is_paused = False
                    logger.info(f"Queue worker started playing: {_current_title} (duration: {_current_duration}s)")
                    _send_ui_message(f"MUSIC:{_current_title}|IMG:{_current_thumbnail}|DUR:{_current_duration}")
                except Exception as e:
                    logger.error(f"Queue worker failed to play {next_song}: {e}")
        except Exception as err:
            logger.error(f"Error in playback worker: {err}")
                    
        time.sleep(1)

def _ensure_worker_running():
    global _worker_running, _worker_thread
    if not _worker_running or (_worker_thread is not None and not _worker_thread.is_alive()):
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
    global _music_queue, _current_player_process, _is_seeking
    _ensure_worker_running()
    
    _is_seeking = False
    _music_queue.clear()
    _music_queue.append(search_query)
    
    if _current_player_process and _current_player_process.poll() is None:
        _current_player_process.terminate()
        
    return f"Now playing: {search_query}"

def skip_song():
    """Skips the currently playing song."""
    global _current_player_process, _is_paused, _is_seeking
    _is_seeking = False
    if _current_player_process and _current_player_process.poll() is None:
        try:
            if _is_paused:
                psutil.Process(_current_player_process.pid).resume()
        except Exception:
            pass
        _current_player_process.terminate()
        _is_paused = False
        return "Song skipped."
    return "Nothing is currently playing to skip."

def prev_song():
    """Plays the previous song or restarts the current song."""
    global _song_history, _current_song, _music_queue, _current_player_process, _is_paused, _is_seeking
    _ensure_worker_running()
    _is_seeking = False
    if _song_history:
        prev = _song_history.pop()
        if _current_song:
            _music_queue.insert(0, _current_song)
        _music_queue.insert(0, prev)
        if _current_player_process and _current_player_process.poll() is None:
            try:
                if _is_paused:
                    psutil.Process(_current_player_process.pid).resume()
            except Exception:
                pass
            _current_player_process.terminate()
            _is_paused = False
        return f"Playing previous: {prev}"
    elif _current_song:
        _music_queue.insert(0, _current_song)
        if _current_player_process and _current_player_process.poll() is None:
            try:
                if _is_paused:
                    psutil.Process(_current_player_process.pid).resume()
            except Exception:
                pass
            _current_player_process.terminate()
            _is_paused = False
        return f"Replaying: {_current_song}"
    return "Nothing to replay."

def stop_song():
    """Stops playback and clears the queue."""
    global _music_queue, _current_player_process, _is_paused, _current_song, _current_stream_url, _current_duration, _is_seeking
    _is_seeking = False
    _music_queue.clear()
    _current_song = None
    _current_stream_url = None
    _current_duration = 0
    if _current_player_process and _current_player_process.poll() is None:
        try:
            if _is_paused:
                psutil.Process(_current_player_process.pid).resume()
        except Exception:
            pass
        try:
            _current_player_process.terminate()
            _current_player_process.wait(timeout=1)
        except Exception:
            try:
                _current_player_process.kill()
            except Exception:
                pass
        _current_player_process = None
        _is_paused = False

    # Also clean up any lingering ffplay instances
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and proc.info['name'].lower() == 'ffplay.exe':
                try:
                    proc.kill()
                except Exception:
                    pass
    except Exception:
        pass

    _send_ui_message("MUSIC:STOP")
    return "Playback stopped and queue cleared."

def seek_song(target_seconds: int):
    """Seeks to the given timestamp (in seconds) in the currently playing song."""
    global _current_player_process, _is_paused, _current_stream_url, _current_volume, _current_duration, _is_seeking
    if not _current_stream_url:
        logger.warning("seek_song called but no stream URL is active")
        return "No song is currently playing to seek."

    _is_seeking = True
    try:
        target_seconds = max(0, int(target_seconds))
        if _current_duration > 0:
            target_seconds = min(target_seconds, _current_duration)

        logger.info(f"Seeking current song to {target_seconds}s...")

        # Terminate active ffplay process
        if _current_player_process and _current_player_process.poll() is None:
            try:
                if _is_paused:
                    psutil.Process(_current_player_process.pid).resume()
            except Exception:
                pass
            try:
                _current_player_process.terminate()
                _current_player_process.wait(timeout=0.6)
            except Exception:
                try:
                    _current_player_process.kill()
                except Exception:
                    pass
            _current_player_process = None

        # Clean up any lingering ffplay instances
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == 'ffplay.exe':
                    try:
                        proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass

        creationflags = 0x08000000 if sys.platform == "win32" else 0
        cmd = [
            FFPLAY_PATH,
            "-nodisp",
            "-autoexit",
            "-hide_banner",
            "-loglevel", "error",
            "-volume", str(_current_volume),
            "-ss", str(target_seconds),
            _current_stream_url
        ]
        _current_player_process = subprocess.Popen(
            cmd,
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if _is_paused:
            time.sleep(0.05)
            try:
                p = psutil.Process(_current_player_process.pid)
                p.suspend()
            except Exception:
                pass

        logger.info(f"Playback resumed at {target_seconds}s (PID: {_current_player_process.pid})")
        return f"Seeked to {target_seconds} seconds."
    except Exception as e:
        logger.error(f"Error seeking song: {e}")
        return f"Error seeking song: {e}"
    finally:
        _is_seeking = False

def pause_song():
    """Pauses the currently playing song."""
    global _current_player_process, _is_paused
    if _current_player_process and _current_player_process.poll() is None and not _is_paused:
        try:
            p = psutil.Process(_current_player_process.pid)
            p.suspend()
            _is_paused = True
            return "Song paused."
        except Exception as e:
            return f"Failed to pause: {e}"
    return "Nothing to pause."

def resume_song():
    """Resumes the paused song."""
    global _current_player_process, _is_paused
    if _current_player_process and _current_player_process.poll() is None and _is_paused:
        try:
            p = psutil.Process(_current_player_process.pid)
            p.resume()
            _is_paused = False
            return "Song resumed."
        except Exception as e:
            return f"Failed to resume: {e}"
    return "Nothing to resume."

def set_music_volume(level: int):
    """Sets the volume of the background music player (0-100)."""
    global _current_volume
    try:
        _current_volume = max(0, min(100, int(level)))
    except Exception:
        pass
    try:
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass
        from pycaw.pycaw import AudioUtilities, ISimpleAudioVolume
        sessions = AudioUtilities.GetAllSessions()
        found = False
        for session in sessions:
            if session.Process and session.Process.name().lower() == "ffplay.exe":
                volume = session._ctl.QueryInterface(ISimpleAudioVolume)
                volume.SetMasterVolume(max(0.0, min(1.0, _current_volume / 100.0)), None)
                found = True
        if found:
            return f"Music volume set to {_current_volume}%."
        else:
            return "Could not find an active music player process. Please ensure a song is playing first."
    except Exception as e:
        logger.error(f"Failed to set volume: {e}")
        return f"Error setting volume: {e}"
