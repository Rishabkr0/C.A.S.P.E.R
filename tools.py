import logging
from livekit.agents import function_tool, RunContext
import requests
import os
import smtplib
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText
from typing import Optional
import media_player

@function_tool()
async def get_weather(
    context: RunContext,  # type: ignore
    city: str) -> str:
    """
    Get the current weather for a given city.
    """
    try:
        response = requests.get(
            f"https://wttr.in/{city}?format=3")
        if response.status_code == 200:
            logging.info(f"Weather for {city}: {response.text.strip()}")
            return response.text.strip()   
        else:
            logging.error(f"Failed to get weather for {city}: {response.status_code}")
            return f"Could not retrieve weather for {city}."
    except Exception as e:
        logging.error(f"Error retrieving weather for {city}: {e}")
        return f"An error occurred while retrieving weather for {city}." 

@function_tool()
async def search_web(
    context: RunContext,  # type: ignore
    query: str) -> str:
    """
    Search the web using DuckDuckGo and show results.
    Uses ddgs (new package) with fallback to duckduckgo_search and langchain.
    """
    # Try direct ddgs first (most reliable, avoids langchain wrapper issues)
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=8))
            if results:
                formatted = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    body = r.get("body", "")[:220]
                    href = r.get("href", "")
                    formatted.append(f"{i}. {title}\n   {body}\n   {href}")
                text = "\n\n".join(formatted)
                logging.info(f"search_web ddgs results for '{query}': {text[:500]}")
                return text
    except Exception as e:
        logging.warning(f"ddgs direct search failed ({e}), trying fallback")

    # Fallback 2: duckduckgo_search legacy
    try:
        from duckduckgo_search import DDGS as LegacyDDGS
        with LegacyDDGS() as ddgs:
            results = list(ddgs.text(query, max_results=8))
            if results:
                formatted = []
                for i, r in enumerate(results, 1):
                    title = r.get("title", "No title")
                    body = r.get("body", "")[:220]
                    href = r.get("href", "")
                    formatted.append(f"{i}. {title}\n   {body}\n   {href}")
                text = "\n\n".join(formatted)
                logging.info(f"search_web legacy DDGS for '{query}': {text[:500]}")
                return text
    except Exception as e:
        logging.warning(f"legacy DDGS failed ({e}), trying langchain")

    # Fallback 3: langchain wrapper
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        results = DuckDuckGoSearchRun().run(tool_input=query)
        logging.info(f"Search results for '{query}': {results}")
        return results
    except Exception as e:
        logging.error(f"Error searching the web for '{query}': {e}")
        return f"An error occurred while searching the web for '{query}': {e}. Try using control_computer to search via Chrome."    

@function_tool()    
async def send_email(
    context: RunContext,  # type: ignore
    to_email: str,
    subject: str,
    message: str,
    cc_email: Optional[str] = None
) -> str:
    """
    Send an email through Gmail.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        message: Email body content
        cc_email: Optional CC email address
    """
    try:
        # Gmail SMTP configuration
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        
        # Get credentials from environment variables
        gmail_user = os.getenv("GMAIL_USER")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")  # Use App Password, not regular password
        
        if not gmail_user or not gmail_password:
            logging.error("Gmail credentials not found in environment variables")
            return "Email sending failed: Gmail credentials not configured."
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = gmail_user
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add CC if provided
        recipients = [to_email]
        if cc_email:
            msg['Cc'] = cc_email
            recipients.append(cc_email)
        
        # Attach message body
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to Gmail SMTP server
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Enable TLS encryption
        server.login(gmail_user, gmail_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(gmail_user, recipients, text)
        server.quit()
        
        logging.info(f"Email sent successfully to {to_email}")
        return f"Email sent successfully to {to_email}"
        
    except smtplib.SMTPAuthenticationError:
        logging.error("Gmail authentication failed")
        return "Email sending failed: Authentication error. Please check your Gmail credentials."
    except smtplib.SMTPException as e:
        logging.error(f"SMTP error occurred: {e}")
        return f"Email sending failed: SMTP error - {str(e)}"
    except Exception as e:
        logging.error(f"Error sending email: {e}")
        return f"An error occurred while sending email: {str(e)}"

@function_tool()
async def play_music(
    context: RunContext,  # type: ignore
    song_name: str) -> str:
    """
    Search and play a song in the background.
    """
    logging.info(f"play_music called for '{song_name}'")
    return media_player.play_song(song_name)

@function_tool()
async def stop_music(
    context: RunContext  # type: ignore
) -> str:
    """
    Stop the currently playing background music.
    """
    logging.info("stop_music called")
    return media_player.stop_song()

@function_tool()
async def add_to_queue(
    context: RunContext,  # type: ignore
    song_name: str) -> str:
    """
    Add a song to the music playback queue.
    """
    return media_player.add_to_queue(song_name)

@function_tool()
async def skip_song(
    context: RunContext  # type: ignore
) -> str:
    """
    Skip the currently playing song to play the next one in the queue.
    """
    return media_player.skip_song()

@function_tool()
async def get_queue(
    context: RunContext  # type: ignore
) -> str:
    """
    Get the current music playback queue.
    """
    return media_player.get_queue()

@function_tool()
async def set_music_volume(
    context: RunContext,  # type: ignore
    level: int) -> str:
    """
    Set the volume of the background music player (0 to 100).
    """
    return media_player.set_music_volume(level)

@function_tool()
async def play_obsidian_playlist(
    context: RunContext,  # type: ignore
    note_name: str) -> str:
    """
    Read a playlist from an Obsidian note and add all songs in it to the music queue.
    """
    import os
    from obsidian_tools import _get_note_path
    
    file_path = _get_note_path(note_name)
    if not os.path.exists(file_path):
        return f"Error: Playlist note '{note_name}' does not exist in the vault."
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        songs_added = 0
        for line in lines:
            song = line.strip().lstrip("-").strip()
            if song and not song.startswith("#"):
                media_player.add_to_queue(song)
                songs_added += 1
                
        return f"Successfully read playlist '{note_name}'. Added {songs_added} songs to the queue."
    except Exception as e:
        return f"Failed to read playlist '{note_name}': {str(e)}"