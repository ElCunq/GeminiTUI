# ⚡ GeminiTUI

🌐 **[English](README_EN.md)** │ **[Türkçe](README.md)**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-green.svg)](https://textual.textualize.io/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%203.7%20Flash-orange.svg)](https://gemini.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**GeminiTUI** is a lightweight, ultra-fast **Google Gemini Terminal Client** designed for Linux/Hyprland and Wayland/X11 developers with a **naked transparent TUI aesthetic**.

It brings the pure experience of the official Google Gemini Web UI directly to your terminal.

---

## ✨ Features

- 💎 **Naked Transparent UI:** Zero frame clutter or background color mismatch! Seamlessly matches your terminal emulator's native background transparency.
- ⚡ **0ms Cold-Start & Local Caching:** Instant startup with client-side conversation history caching.
- 🤖 **Default Gemini 3.7 Flash:** Automatically defaults to **3.7 Flash** on launch and new chats (easily switch between 3.1 Pro and 3.5 Flash-Lite with a single keystroke).
- 🖼️ **Imagen 3 Image Generation (2-Way View):**
  - **Inline Render:** Generated images render directly inside the chat log as high-resolution 2x HD ANSI RGB (Half-Block `▀`) Unicode graphics.
  - **Full-HD Preview:** Press `Alt+V` or type `/view` to inspect generated images in full original resolution via an external window (`mpv`).
- 🔗 **Web Search Grounding Citations:** Web sources used by Gemini are formatted cleanly at the end of responses as clickable links.
- 📋 **Smart Clipboard Copying:** Press `Alt+C` or type `/copy` to copy the complete last response to system clipboard.
- 🔑 **Easy In-TUI Login:** Easily authenticate inside the TUI with `/login <1PSID> <1PSIDTS>`.
- 📎 **Multimodal Uploads:** Attach images (PNG/JPG/WEBP), PDFs, and source code files using `F3` / `Alt+F` or `/file /path/to/image.png`.

---

## 🚀 Quick Start

### Prerequisites
- Linux (Arch, Fedora, Ubuntu, Debian, etc.)
- Python 3.10+
- `wl-clipboard` (for Wayland) or `xclip` (for X11)
- `mpv` *(optional, for opening full-resolution images)*

### Installation
```bash
# Clone repository
git clone https://github.com/ElCunq/GeminiTUI.git
cd GeminiTUI

# Grant execution permissions and run (Virtualenv is set up automatically)
chmod +x run.sh
./run.sh
```

---

## 🔑 Authentication (Cookie Setup)

To access your Google Account chat history and unthrottled models:

### Method A (Inside TUI):
Type in the message box:
```text
/login <YOUR_GEMINI_1PSID> <YOUR_GEMINI_1PSIDTS>
```

### Method B (Environment Variables):
```bash
export GEMINI_1PSID="your_1psid_cookie_value"
export GEMINI_1PSIDTS="your_1psidts_cookie_value"

./run.sh
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Description |
| :--- | :--- |
| **F1** / **Alt+N** | Start a new chat |
| **F2** / **Alt+M** | Cycle AI Models (3.7 Flash, 3.1 Pro, 3.5 Flash-Lite) |
| **F3** / **Alt+F** | Attach file or image (`/file`) |
| **F4** / **Alt+D** | Delete active chat from Google account |
| **Alt+C** | Copy entire last response to clipboard |
| **Alt+V** | Open last generated image in full-resolution `mpv` window |
| **F7** / **Alt+H** | Show command help menu |
| **Up Arrow (↑)** | Recall last user prompt into empty message input box |

---

## 💬 Slash Commands

| Command | Description |
| :--- | :--- |
| **`/login <1PSID> <1PSIDTS>`** | Save cookies and connect to Google account |
| **`/copy`** | Copy complete response to clipboard |
| **`/view`** | Open generated image in full-resolution viewer |
| **`/file <path>`** | Attach image (PNG/JPG/WEBP), PDF, or source file |
| **`/rename <title>`** | Rename current chat title |
| **`/pin`** | Pin/unpin chat in sidebar (📌) |
| **`/new`** | Start new chat |
| **`/model`** | Cycle model |
| **`/clear`** | Clear attached files |
| **`/exit`** | Exit application |

---

## 🙏 Credits & Acknowledgements

The core Google Gemini Web API integration of this project is powered by **[`Gemini-API`](https://github.com/HanaokaYuzu/Gemini-API)**.

Special thanks to **[HanaokaYuzu](https://github.com/HanaokaYuzu)** and all open-source contributors of `Gemini-API` for creating and maintaining the core API wrapper!

Also thanks to the **[Textualize (Textual & Rich)](https://github.com/Textualize/textual)** team for building the magnificent Python TUI framework.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
