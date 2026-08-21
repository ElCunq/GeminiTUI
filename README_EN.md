# ⚡ GeminiTUI

🌐 **[English](README_EN.md)** │ **[Türkçe](README.md)**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-green.svg)](https://textual.textualize.io/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%203.7%20Flash-orange.svg)](https://gemini.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**GeminiTUI** is a feature-rich, ultra-fast **Google Gemini Terminal Client** designed for Linux/Hyprland and Wayland/X11 developers with a **naked transparent TUI aesthetic**.

It brings the full power of Google Gemini Web UI directly to your terminal environment.

---

## ✨ Features

- 💎 **Naked Transparent UI:** Zero frame clutter or background color mismatch! Seamlessly matches your terminal emulator's native background transparency.
- ⚡ **0ms Cold-Start & Local Caching:** Instant startup with client-side conversation history caching.
- 🤖 **Default Gemini 3.7 Flash:** Automatically defaults to **3.7 Flash** on launch and new chats (easily switch between 3.1 Pro and 3.5 Flash-Lite with a single keystroke).
- 🖼️ **Imagen 3 Image Generation (2-Way View):**
  - **Inline Render:** Generated images render directly inside the chat log as high-resolution 2x HD ANSI RGB (Half-Block `▀`) Unicode graphics.
  - **Full-HD Preview:** Press `Alt+V` or type `/view` to inspect generated images in full original resolution via an external window (`mpv`).
- 📁 **Client-Side Projects (Chat Organization):** Group conversations into custom project folders like `General`, `Software Project`, or `Notes`, and switch/create projects with `/project <name>`.
- 💻 **Shell Command Execution (`!cmd`):** Execute terminal commands (`! git status`, `! pytest`, etc.) and send their outputs directly to Gemini for instant AI code review or debugging.
- 🔗 **Web Search Grounding Citations:** Web sources used by Gemini are formatted cleanly at the end of responses as clickable links.
- 📋 **Smart Clipboard Copying:**
  - `Alt+C` or `/copy`: Copies the complete last response to system clipboard.
  - `/copycode`: Strips conversational prose and copies **ONLY the code blocks** to clipboard.
- 📥/💾 **Chat Export & Import:** Export chats to Markdown reports (`/export`) and import existing chat files to resume conversations with context (`/import`).
- 📎 **Multimodal Uploads:** Attach images (PNG/JPG/WEBP), PDFs, and source code files using `F3` / `Alt+F` or `/file /path/to/image.png`.
- 💭 **Extended Thinking (F5) & Deep Research (F6):** Toggle thinking process and deep research modes with instant shortcuts.

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

To access your Google Account chat history and unthrottled models, pass your `GEMINI_1PSID` and `GEMINI_1PSIDTS` cookies as environment variables:

```bash
export GEMINI_1PSID="your_1psid_cookie_value"
export GEMINI_1PSIDTS="your_1psidts_cookie_value"

./run.sh
```
*(If no cookies are provided, GeminiTUI launches in **Guest Mode**.)*

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
| **F5** / **Alt+T** | Toggle Extended Thinking mode |
| **F6** / **Alt+R** | Toggle Deep Research mode |
| **F7** / **Alt+H** | Show command help menu |
| **Up Arrow (↑)** | Recall last user prompt into empty message input box |

---

## 💬 Slash & Shell Commands

| Command | Description |
| :--- | :--- |
| **`! <command>`** | Execute terminal shell command and analyze output with Gemini |
| **`/project <name>`** | Create or switch client-side project folder |
| **`/copy`** | Copy complete response to clipboard |
| **`/copycode`** | Copy **ONLY CODE BLOCKS** to clipboard |
| **`/view [path]`** | Open generated image in full-resolution viewer |
| **`/file <path>`** | Attach image (PNG/JPG/WEBP), PDF, or source file |
| **`/export [file]`** | Export chat history as Markdown (.md) |
| **`/import <file>`** | Import saved chat file and resume conversation |
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
