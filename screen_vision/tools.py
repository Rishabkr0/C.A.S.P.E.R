import socket
import logging
import asyncio
from livekit.agents import function_tool, RunContext
from .visual_memory import inspect_focused_image, get_active_focus
from .screen_streamer import get_screen_streamer
from .gesture_detector import get_gesture_detector

def _broadcast_vision_state(state: str, udp_port: int = 49152):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(state.encode("utf-8"), ("127.0.0.1", udp_port))
        sock.close()
    except Exception as e:
        logging.debug(f"[Vision Tools] Error broadcasting state {state}: {e}")

@function_tool()
async def start_screen_vision(
    context: RunContext,
    task_or_query: str = "",
) -> str:
    """
    Activates Casper's screen vision mode ('Specter Vision' / 'Vision Mode').
    Enables real-time display streaming and the glowing neon cursor trail.
    ALWAYS call this tool immediately whenever Boss asks:
    - 'Enable vision mode', 'Start vision mode', 'Turn on vision', 'Specter vision', 'Engage vision mode'
    - 'Start screen share', 'Share my screen', 'Screen share mode', 'Switch to screen share'
    - 'Can you see my screen?', 'Check my screen', 'Take a look at my display'
    - 'Tell me what's on my screen', 'What is on my screen?'
    If an explicit inspection question is included in task_or_query, this tool also
    analyzes the screen and answers directly.
    """
    streamer = get_screen_streamer()
    if streamer and not streamer.is_enabled:
        streamer.enable()

    detector = get_gesture_detector()
    if detector and not detector.is_enabled:
        detector.enable()

    _broadcast_vision_state("VISION:ON")
    logging.info("[Vision Tools] Specter Vision Mode ACTIVATED by user command")

    # Determine if Boss asked an actual question about the screen or is just activating the mode
    query_clean = task_or_query.strip().lower()
    activation_keywords = [
        "engage vision", "enable vision", "start vision", "turn on vision",
        "specter vision", "screen share mode", "vision mode", "start screen share",
        "open vision", "activate vision", "share my screen"
    ]
    query_keywords = [
        "what", "who", "tell", "explain", "describe", "identify", "photo", "image",
        "see", "read", "error", "code", "look", "check", "whose"
    ]

    has_question = any(k in query_clean for k in query_keywords)
    is_pure_activation = not query_clean or (any(k in query_clean for k in activation_keywords) and not has_question)

    if has_question and not is_pure_activation:
        try:
            inspection_result = await asyncio.wait_for(inspect_focused_image(task_or_query), timeout=9.0)
            return (
                f"Full-screen vision engaged, Boss. I am looking at your active display.\n"
                f"Here is what I see on your screen:\n{inspection_result}"
            )
        except Exception as e:
            logging.warning(f"[Vision Tools] Initial inspection timed out or failed: {e}")
            return (
                "Full-screen vision engaged, Boss. I am observing your screen now. "
                "Ask me anything about what is on your display."
            )

    return (
        "Full-screen vision engaged, Boss. I can see your entire active display. "
        "Ask me about any text, code, error, or image you are viewing."
    )

@function_tool()
async def stop_screen_vision(
    context: RunContext,
) -> str:
    """
    Deactivates Casper's screen vision mode ('Vision Mode' / 'Screen Share Mode').
    Turns off real-time screen streaming, dismisses the neon cursor trail, and pauses gesture detection.
    ALWAYS call this tool immediately whenever Boss asks:
    - 'Stop vision mode', 'Exit vision mode', 'Turn off vision', 'Close vision'
    - 'Stop screen share', 'Turn off screen share', 'End screen share'
    - 'Stop looking at my screen', 'Dismiss vision'
    """
    streamer = get_screen_streamer()
    if streamer:
        streamer.disable()

    detector = get_gesture_detector()
    if detector:
        detector.disable()

    _broadcast_vision_state("VISION:OFF")
    logging.info("[Vision Tools] Vision Mode DEACTIVATED by user command")

    return "Full-screen vision disengaged, Boss. Screen feed closed."

@function_tool()
async def inspect_focused_screen_area(
    context: RunContext,
    question: str = "",
) -> str:
    """
    Visually inspects the user's active desktop screen in high resolution.
    Directly answers questions about errors, code, text, photos, diagrams, or UI.
    ALWAYS call this tool immediately whenever Boss asks:
    - 'What is this on screen?' / 'Tell me what's this on screen' / 'What is this?' / 'Look at this'
    - 'Tell me what is on my screen' / 'What do you see on my screen?' / 'Have a look at my screen'
    - 'Look at my screen' / 'Read my screen' / 'Explain this'
    - 'What is wrong with this code?' / 'Fix this error here'
    - 'Identify whose photo this is' / 'Who is this?' / 'Read this text'
    """
    # Ensure vision mode is enabled
    streamer = get_screen_streamer()
    if streamer and not streamer.is_enabled:
        streamer.enable()

    _broadcast_vision_state("VISION:ON")

    try:
        return await asyncio.wait_for(inspect_focused_image(question), timeout=9.0)
    except Exception as e:
        logging.warning(f"[Vision Tools] inspect_focused_screen_area timed out: {e}")
        return "I can see your active screen, Boss, but the visual analysis took slightly too long. Please ask me again."
