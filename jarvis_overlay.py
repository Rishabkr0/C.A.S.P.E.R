import sys
import os
import threading
import socket

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QObject, Signal, QUrl, QTimer
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtGui import QColor


class CustomWebPage(QWebEnginePage):
    """Intercept UI commands from JavaScript console and route to agent.py via UDP 49153."""
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if message and message.startswith("UI_CMD:"):
            cmd = message[7:].strip()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.sendto(cmd.encode("utf-8"), ("127.0.0.1", 49153))
                sock.close()
            except Exception:
                pass
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


class StateUpdater(QObject):
    update_signal = Signal(str)


def listen_for_commands(updater):
    """Read state commands from stdin (sent by agent.py via subprocess)."""
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            updater.update_signal.emit(line.strip())
        except Exception:
            break


def listen_for_udp_states(updater):
    """Listen for broadcast UI states on UDP port 49152 (e.g., from media_player.py)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 49152))
        while True:
            data, _ = sock.recvfrom(4096)
            if data:
                updater.update_signal.emit(data.decode("utf-8", errors="ignore").strip())
    except Exception:
        pass


class CasperOverlay(QWidget):
    def __init__(self):
        super().__init__()

        # Frameless + always on top + transparent
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        # Position at TOP CENTER (Notch / Dynamic Island style)
        WIN_W, WIN_H = 340, 460
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - WIN_W) // 2
        y = 0
        self.setGeometry(x, y, WIN_W, WIN_H)

        # QWebEngineView fills the window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        self.page = CustomWebPage(self.view)
        self.view.setPage(self.page)
        self.view.setAttribute(Qt.WA_TranslucentBackground)
        self.view.setAttribute(Qt.WA_NoSystemBackground)
        self.page.setBackgroundColor(QColor(Qt.transparent))

        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        html_path = os.path.join(base_dir, 'jarvis_ui_side.html')
        self.view.load(QUrl.fromLocalFile(html_path))
        self.view.loadFinished.connect(self._on_load)

        layout.addWidget(self.view)

        # Stdin & UDP command listeners
        self.updater = StateUpdater()
        self.updater.update_signal.connect(self.set_state)

        threading.Thread(
            target=listen_for_commands,
            args=(self.updater,),
            daemon=True
        ).start()

        threading.Thread(
            target=listen_for_udp_states,
            args=(self.updater,),
            daemon=True
        ).start()

    def _on_load(self, ok):
        """Startup animation when UI finishes loading: stay hidden until Chrome/backend signals ready."""
        if ok:
            self.set_state('hidden')
            # Fallback in case UDP is blocked
            QTimer.singleShot(5000, lambda: self.set_state('listening'))

    def set_state(self, state):
        """
        Map agent state strings to JS setState() calls.
        Handles: idle, listening, speaking, waiting, thinking, tool, custom:<text>, MUSIC:...
        """
        safe = state.replace("'", "\\'").replace('"', '\\"')
        self.view.page().runJavaScript(f"setState('{safe}')")


def main():
    app = QApplication(sys.argv)
    overlay = CasperOverlay()
    overlay.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
