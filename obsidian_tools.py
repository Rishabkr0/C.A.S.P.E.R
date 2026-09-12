import os
import glob
import logging
import time
import subprocess
import threading
import urllib.parse
from livekit.agents import function_tool, RunContext

logger = logging.getLogger("obsidian-tools")

def _show_on_screen_and_close(note_name: str, file_path: str):
    """Visually pops up the note on the screen for 8 seconds, then closes it."""
    def _task():
        try:
            # Attempt to open with Obsidian URI scheme
            encoded_name = urllib.parse.quote(note_name.replace('.md', ''))
            # vault parameter is optional, Obsidian usually opens the default or active vault
            subprocess.run(['start', f'obsidian://open?file={encoded_name}'], shell=True)
        except Exception:
            # Fallback to default system handler or notepad
            subprocess.Popen(['notepad.exe', file_path])
            
        time.sleep(8)
        
        # Close the app
        subprocess.run(['taskkill', '/IM', 'Obsidian.exe', '/F'], capture_output=True, shell=True)
        subprocess.run(['taskkill', '/IM', 'notepad.exe', '/F'], capture_output=True, shell=True)
        
    threading.Thread(target=_task, daemon=True).start()

# Dynamically resolve the current user's Documents folder so it works on any PC!
OBSIDIAN_VAULT_PATH = os.path.join(os.path.expanduser("~"), "Documents", "MyVault", "CASPER")

def _ensure_vault_exists():
    if not os.path.exists(OBSIDIAN_VAULT_PATH):
        os.makedirs(OBSIDIAN_VAULT_PATH, exist_ok=True)
        logger.info(f"Created Obsidian vault directory at {OBSIDIAN_VAULT_PATH}")

def _get_note_path(note_name: str) -> str:
    _ensure_vault_exists()
    if not note_name.endswith(".md"):
        note_name += ".md"
    return os.path.join(OBSIDIAN_VAULT_PATH, note_name)

@function_tool()
async def obsidian_search_notes(context: RunContext, query: str) -> str:
    """Searches all notes in the Obsidian vault for a specific keyword or phrase."""
    _ensure_vault_exists()
    results = []
    
    # Search all .md files in the vault
    search_pattern = os.path.join(OBSIDIAN_VAULT_PATH, "**", "*.md")
    for file_path in glob.glob(search_pattern, recursive=True):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if query.lower() in content.lower():
                    # Extract snippets
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if query.lower() in line.lower():
                            note_name = os.path.relpath(file_path, OBSIDIAN_VAULT_PATH)
                            results.append(f"[{note_name}]: {line.strip()}")
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            
    if not results:
        return f"No results found for '{query}' in the Obsidian vault."
    
    return "Search Results:\n" + "\n".join(results)

@function_tool()
async def obsidian_read_note(context: RunContext, note_name: str) -> str:
    """Reads the full contents of a specific note from the Obsidian vault."""
    file_path = _get_note_path(note_name)
    if not os.path.exists(file_path):
        return f"Error: Note '{note_name}' does not exist in the vault."
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return f"--- Content of {note_name} ---\n{content}"
    except Exception as e:
        return f"Failed to read note '{note_name}': {str(e)}"

@function_tool()
async def obsidian_append_note(context: RunContext, note_name: str, content: str) -> str:
    """Appends new text to the bottom of an existing note."""
    file_path = _get_note_path(note_name)
    if not os.path.exists(file_path):
        return f"Error: Note '{note_name}' does not exist. Use obsidian_create_note first."
        
    try:
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write("\n" + content)
        
        # Show the updated note on screen briefly
        _show_on_screen_and_close(note_name, file_path)
        
        return f"Successfully appended content to '{note_name}'."
    except Exception as e:
        return f"Failed to append to note '{note_name}': {str(e)}"

@function_tool()
async def obsidian_create_note(context: RunContext, note_name: str, content: str) -> str:
    """Creates a brand new note in the Obsidian vault with the given content."""
    file_path = _get_note_path(note_name)
    if os.path.exists(file_path):
        return f"Error: Note '{note_name}' already exists. Use obsidian_append_note instead."
        
    try:
        # Ensure subdirectories exist if the note_name includes folders like "Projects/NewApp"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        # Show the newly created note on screen briefly
        _show_on_screen_and_close(note_name, file_path)
        
        return f"Successfully created new note '{note_name}'."
    except Exception as e:
        return f"Failed to create note '{note_name}': {str(e)}"

OBSIDIAN_TOOLS = [
    obsidian_search_notes,
    obsidian_read_note,
    obsidian_append_note,
    obsidian_create_note
]
