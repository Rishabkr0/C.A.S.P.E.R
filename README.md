# 👻 Casper - The Next-Generation Hybrid AI Assistant

**Casper** is a powerful, desktop-native AI assistant designed to live alongside your workflow. Unlike traditional AI agents that rely solely on slow vision models or basic web scraping, Casper introduces a **Hybrid Automation Architecture** that dynamically routes tasks between lightning-fast browser protocols and native desktop automation.

With an always-on, transparent desktop avatar, Casper is always ready to help—whether it's skipping a YouTube ad in milliseconds, managing your emails, or stealthily generating Microsoft Office documents in the background.

---

## ✨ Why Casper is Different

### 1. 🧠 Hybrid Automation Routing
Most agents use a one-size-fits-all approach. Casper is smarter. It analyzes your request and routes it to the most efficient automation engine:
- **Browser Tasks?** Routed through a direct Chrome DevTools Protocol (CDP) via MCP. This means 10x faster execution and 99% reliability because Casper talks directly to the browser's DOM.
- **Desktop Tasks?** Routed through native Windows COM and UI Automation (UIA) as a fallback.

### 2. 🥷 Stealth Office Automation
Need a report generated in Excel or Word? Casper uses zero-setup local COM automation (`pywin32`) to control Microsoft Office apps *invisibly*. It won't steal your screen focus or interrupt your workflow while it works, only revealing the document when it's perfectly finished.

### 3. ⚡ Lightning-Fast Web Execution
Because Casper uses direct Chrome DevTools integration instead of slow vision models to navigate the web, it achieves incredible speeds:
- Skip YouTube Ads in **<500ms**
- Play Spotify songs in **<2s**
- Instantly read Gmail, fill forms, and extract webpage content

### 4. 🖥️ Always-On Desktop Avatar
Casper doesn't hide in a terminal. It features a frameless, transparent PySide6 desktop widget that lives on your screen. The avatar dynamically updates its state (listening, thinking, speaking) so you always know what Casper is doing.

---

## 🚀 Core Features

* **🌐 Advanced Chrome Control:** Full multi-tab management, session control, ad-blocking capabilities, and webpage visual diffing.
* **🎵 Media Mastery:** Complete automation for YouTube (search, play, skip ads) and Spotify (search, play, playlists, likes).
* **📧 Google Workspace Native:** Direct OAuth integration with Google APIs for Gmail, Calendar, and Sheets management.
* **💼 Microsoft Office Native:** Full control over MS Word, Excel, and PowerPoint.
* **🗣️ Voice & Vision (LiveKit):** Talk directly to Casper and share your screen/camera using LiveKit agents and plugins.
* **🧠 Smart Memory (Mem0):** Casper remembers your preferences, past interactions, and context over time.

---

## 🎯 Getting Started (Quick Setup)

1. **Prerequisites:** 
   - Install [Node.js](https://nodejs.org/) (v16+) for the Chrome MCP Server.
   - Install Python 3.10+.
2. **Install Dependencies:**
   ```bash
   # Create and activate a virtual environment
   python -m venv .venv
   .venv\Scripts\activate
   
   # Install Python requirements
   pip install -r requirements.txt
   ```
3. **Configuration:**
   - Create a `.env` file in the root directory.
   - Add your API Keys, LiveKit Secret, and LiveKit URL.
   - Run `python generate_token.py` (if available) to authenticate Google Workspace tools.
4. **Run Casper:**
   ```bash
   python agent.py
   ```
   *Your Casper desktop avatar will appear and start listening!*

---

## 🧪 Testing

To verify that Casper's advanced Chrome integration and Node.js environment are set up correctly, run the test suite:
```bash
python test_chrome_integration.py
```

---

## 📜 Licensing

- **Casper Source Code:** Proprietary & Confidential. All Rights Reserved.
- **Third-Party Libraries:** Casper uses several open-source libraries (MIT, Apache 2.0, LGPL, etc.). Please see `thirdparty_licenses/third_party_notices.md` for full attribution and details.
