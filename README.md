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
- Play songs in **<2s**
- Instantly read Gmail, fill forms, and extract webpage content

### 4. 🖥️ Always-On Desktop Avatar
Casper doesn't hide in a terminal. It features a frameless, transparent PySide6 desktop widget that lives on your screen. The avatar dynamically updates its state (listening, thinking, speaking) so you always know what Casper is doing.

---

## 🚀 Core Features

* **🌐 Advanced Chrome Control:** Full multi-tab management, session control, ad-blocking capabilities, and webpage visual diffing.
* **🎵 Media Mastery:** Complete automation for YouTube (search, play, skip ads) and music platforms (search, play, playlists).
* **📧 Google Workspace Native:** Direct OAuth integration with Google APIs for Gmail, Calendar, and Sheets management.
* **💼 Microsoft Office Native:** Full control over MS Word, Excel, and PowerPoint.
* **🗣️ Voice & Vision (LiveKit):** Talk directly to Casper and share your screen/camera using LiveKit agents and plugins.
* **🧠 Smart Memory (Mem0):** Casper remembers your preferences, past interactions, and context over time.

---

## 🎯 Getting Started (Quick Setup)

### 🔐 0. Repository Decryption (Zero-Trust AES-256-GCM)
Source code in this repository is encrypted with AES-256-GCM on GitHub and in ZIP downloads.
If you have cloned the repository or unzipped it, unlock the files using your master key:
```bash
python casper_crypt.py unlock --key <YOUR_MASTER_KEY>
```
*(If working on your authorized development machine where `.casper_key` is present, files are automatically decrypted.)*

---

### 1. Prerequisites
- Install [Node.js](https://nodejs.org/) (v16+) for the Chrome MCP Server.
- Install Python 3.10+.

### 2. Install Dependencies
```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install Python requirements
pip install -r requirements.txt
```

### 3. Configuration
- Create a `.env` file in the root directory.
- Add your API Keys, LiveKit Secret, and LiveKit URL.
- Run `python generate_token.py` (if available) to authenticate Google Workspace tools.

### 4. Run Casper
```bash
python agent.py
```
*Your Casper desktop avatar will appear and start listening!*

---

## 📚 Documentation & Guides

Comprehensive guides and architectural references are located in the [`docs/`](docs/) directory:
* [Quickstart Guide](docs/QUICKSTART.md) — Fast 5-minute setup
* [Start Here Guide](docs/START_HERE.md) — Feature overview & first steps
* [Chrome MCP Setup](docs/CHROME_MCP_SETUP.md) — Detailed browser automation configuration
* [YouTube Controls](docs/YOUTUBE_COMPLETE_CONTROLS.md) — Complete voice command list for YouTube
* [Implementation Summary](docs/IMPLEMENTATION_SUMMARY.md) — Full technical summary of integrations

---

## 🔒 Security & Encryption Architecture

Casper uses **casper-crypt**, an integrated AES-256-GCM authenticated Git clean/smudge filter system:
* **GitHub Repository:** Every source file (`.py`, `.html`, `.js`, `.css`, etc.) is encrypted ciphertext with an authentication tag.
* **ZIP Downloads:** Anyone downloading the ZIP archive gets encrypted ciphertext that cannot be viewed without the master key.
* **Cloned Repositories:** Standard `git clone` downloads encrypted files until unlocked with `python casper_crypt.py unlock`.
* **Local Workspace:** Seamless transparent decryption for authorized developers with `.casper_key`.
