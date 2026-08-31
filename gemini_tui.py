import os
import re
import json
import time
import asyncio
import pathlib
import sqlite3
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import ListView, ListItem, Label, Input, RichLog, Button, TextArea
from textual.binding import Binding
from textual.events import Key, Click
from textual import work

from rich.markdown import Markdown
from rich.text import Text

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

try:
    import secretstorage
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    HAS_NATIVE_DECRYPT = True
except ImportError:
    HAS_NATIVE_DECRYPT = False

from gemini_webapi import GeminiClient
from gemini_webapi.types.availablemodel import AvailableModel
from gemini_webapi.utils import set_log_level, logger, rotate_1psidts, clear_cookies_cache

# Terminal log kirliliğini tamamen kapatıyoruz
set_log_level("ERROR")
try:
    logger.remove()
except Exception:
    pass

CACHE_DIR = Path.home() / ".cache" / "gemini_tui"
CACHE_FILE = CACHE_DIR / "chats_cache.json"
IMAGES_DIR = CACHE_DIR / "images"

CONFIG_DIR = Path.home() / ".config" / "gemini_tui"
CONFIG_FILE = CONFIG_DIR / "config.json"

COMMANDS_LIST = [
    ("/help", "Kullanım yardımını ve komut listesini gösterir"),
    ("/new", "Yeni temiz bir sohbet başlatır"),
    ("/model", "AI modelleri arasında geçiş yapar (3.7 Flash, 3.1 Pro, 3.5 Flash-Lite)"),
    ("/login", "Çerezleri otomatik tarar ve hesaba doğrudan bağlanır"),
    ("/export <dosya>", "Aktif sohbeti Markdown (.md) dosyası olarak kaydeder"),
    ("/import <dosya>", "Kaydedilmiş sohbet dosyasını yükler ve bağlamı canlı oturuma aktarır"),
    ("/file <yol>", "Görsel (PNG/JPG/WEBP), PDF veya metin dosyası ekler (F3/Alt+F)"),
    ("/view", "Son üretilen görseli mpv ile tam çözünürlükte açar (Alt+V)"),
    ("/copy", "En son verilen yanıtı panoya kopyalar (Alt+C)"),
    ("/rename <başlık>", "Aktif sohbetin başlığını değiştirir"),
    ("/pin", "Sohbeti sol panele iğneler veya iğneyi kaldırır (📌)"),
    ("/delete", "Aktif sohbeti hesabınızdan siler (F4/Alt+D)"),
    ("/clear", "Eklenmiş dosyaları temizler"),
    ("/exit", "Uygulamadan çıkış yapar"),
]

def get_linux_dbus_secret(label: str) -> Optional[bytes]:
    if not HAS_NATIVE_DECRYPT:
        return None
    try:
        bus = secretstorage.dbus_init()
        collection = secretstorage.get_default_collection(bus)
        for item in collection.get_all_items():
            if item.get_label() == label:
                return item.get_secret()
    except Exception:
        pass
    return None

def decrypt_chrome_cookie_linux(encrypted_val: bytes, key_secret: bytes) -> str:
    if not encrypted_val or not key_secret:
        return ""
    try:
        if encrypted_val[:3] in [b'v10', b'v11']:
            encrypted_val = encrypted_val[3:]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA1(),
            length=16,
            salt=b'saltysalt',
            iterations=1,
        )
        key = kdf.derive(key_secret)
        iv = b' ' * 16
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_val) + decryptor.finalize()
        
        if len(decrypted) > 32:
            val = decrypted[32:].decode('utf-8', errors='ignore')
            val = re.sub(r'[\x00-\x1f\x7f-\xff]+.*$', '', val)
            return val
    except Exception:
        pass
    return ""

def auto_extract_native_linux_cookies() -> Dict[str, str]:
    extracted = {}
    
    candidate_paths = [
        ("Brave Safe Storage", Path.home() / ".config/BraveSoftware/Brave-Origin/Default/Cookies"),
        ("Brave Safe Storage", Path.home() / ".config/BraveSoftware/Brave-Browser/Default/Cookies"),
        ("Chrome Safe Storage", Path.home() / ".config/google-chrome/Default/Cookies"),
        ("Chromium Safe Storage", Path.home() / ".config/chromium/Default/Cookies"),
    ]
    
    for label, cookie_path in candidate_paths:
        if not cookie_path.exists():
            continue
        secret = get_linux_dbus_secret(label)
        if not secret:
            continue
            
        try:
            tmp_copy = Path("/tmp/tui_cookie_scan.db")
            shutil.copy2(cookie_path, tmp_copy)
            conn = sqlite3.connect(tmp_copy)
            c = conn.cursor()
            c.execute("SELECT name, encrypted_value, host_key FROM cookies WHERE host_key LIKE '%google.com%'")
            for name, enc_val, host in c.fetchall():
                if '1PSID' in name and host in ['.google.com', 'google.com']:
                    dec = decrypt_chrome_cookie_linux(enc_val, secret)
                    if dec and len(dec) > 10:
                        extracted[name] = dec
            conn.close()
            try:
                tmp_copy.unlink()
            except Exception:
                pass
                
            if extracted.get("__Secure-1PSID"):
                break
        except Exception:
            pass
            
    return extracted

def load_cookie_credentials():
    psid = os.getenv("GEMINI_1PSID", None)
    psidts = os.getenv("GEMINI_1PSIDTS", None)
    psidcc = os.getenv("GEMINI_1PSIDCC", None)
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not psid:
                    psid = data.get("GEMINI_1PSID") or data.get("1PSID")
                if not psidts:
                    psidts = data.get("GEMINI_1PSIDTS") or data.get("1PSIDTS")
                if not psidcc:
                    psidcc = data.get("GEMINI_1PSIDCC") or data.get("1PSIDCC")
        except Exception:
            pass

    if not psid:
        native_cookies = auto_extract_native_linux_cookies()
        if native_cookies.get("__Secure-1PSID"):
            psid = native_cookies.get("__Secure-1PSID")
            psidts = native_cookies.get("__Secure-1PSIDTS")
            psidcc = native_cookies.get("__Secure-1PSIDCC")
            save_cookie_credentials(psid, psidts, psidcc)
            
    return psid, psidts, psidcc

def save_cookie_credentials(psid: str, psidts: Optional[str] = None, psidcc: Optional[str] = None):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        if psid:
            data["GEMINI_1PSID"] = psid.strip()
        if psidts:
            data["GEMINI_1PSIDTS"] = psidts.strip()
        if psidcc:
            data["GEMINI_1PSIDCC"] = psidcc.strip()
            
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def parse_cookie_input(raw_text: str):
    psid_m = re.search(r'__Secure-1PSID=([^;\s]+)', raw_text)
    psidts_m = re.search(r'__Secure-1PSIDTS=([^;\s]+)', raw_text)
    psidcc_m = re.search(r'__Secure-1PSIDCC=([^;\s]+)', raw_text)
    
    psid = psid_m.group(1) if psid_m else None
    psidts = psidts_m.group(1) if psidts_m else None
    psidcc = psidcc_m.group(1) if psidcc_m else None
    
    if not psid:
        clean = raw_text.replace("/login", "").strip()
        parts = clean.split()
        if len(parts) >= 1:
            psid = parts[0]
        if len(parts) >= 2:
            psidts = parts[1]
        if len(parts) >= 3:
            psidcc = parts[2]
            
    return psid, psidts, psidcc

# --- ÇOK SATIRLI ÇOKLU GİRDİ VE BELİRGİN İMLEÇ (TEXTAREA) ---
class PromptTextArea(TextArea):
    def on_mount(self) -> None:
        self.cursor_blink = True

    async def _on_key(self, event: Key) -> None:
        key = event.key.lower()
        
        # Çok satırlı yeni satır tuş kombinasyonları: Shift+Enter, Alt+Enter, Ctrl+Enter, Escape+Enter, Ctrl+J
        if key in ["shift+enter", "alt+enter", "ctrl+enter", "escape+enter", "ctrl+j"]:
            self.insert("\n")
            event.prevent_default()
            event.stop()
        elif key == "enter":
            current_text = self.text
            if current_text.endswith("\\"):
                self.text = current_text[:-1] + "\n"
                event.prevent_default()
                event.stop()
            else:
                event.prevent_default()
                event.stop()
                self.app.handle_prompt_submit()
        else:
            await super()._on_key(event)

class NakedGeminiTUI(App):
    BINDINGS = [
        Binding("ctrl+c", "quit", "Çıkış", priority=True),
        Binding("f1", "action_new_chat", "Yeni Sohbet", priority=True),
        Binding("alt+n", "action_new_chat", "Yeni Sohbet", priority=True),
        Binding("f2", "action_cycle_model", "Model Seç", priority=True),
        Binding("alt+m", "action_cycle_model", "Model Seç", priority=True),
        Binding("f3", "action_prompt_file", "Dosya Ekle", priority=True),
        Binding("alt+f", "action_prompt_file", "Dosya Ekle", priority=True),
        Binding("f4", "action_delete_chat", "Sohbeti Sil", priority=True),
        Binding("alt+d", "action_delete_chat", "Sohbeti Sil", priority=True),
        Binding("alt+c", "action_copy_last_response", "Yanıtı Kopyala", priority=True),
        Binding("alt+v", "action_open_last_generated_image", "Görseli Aç", priority=True),
        Binding("f7", "action_show_help", "Yardım", priority=True),
        Binding("alt+h", "action_show_help", "Yardım", priority=True),
    ]

    CSS = """
    * { 
        background: transparent; 
        border: none; 
    }
    Screen { 
        layout: vertical; 
        height: 100%;
        overflow: hidden;
    }
    
    /* ÜST BAŞLIK BARI (HEADER) */
    #header-container {
        height: 1;
        layout: horizontal;
        border-bottom: solid #444444;
        padding: 0 1;
        margin-bottom: 1;
    }
    #toggle-sidebar-btn {
        width: 5;
        height: 1;
        color: #00ffcc;
        text-style: bold;
    }
    #header-title-label {
        width: 1fr;
        height: 1;
        color: #ffffff;
        text-style: bold;
    }
    #incognito-btn {
        width: 15;
        height: 1;
        color: #ffaa00;
        text-style: bold;
    }
    #top-menu-btn {
        width: 7;
        height: 1;
        color: #00ffcc;
        text-style: bold;
    }

    /* ANA BÖLGE (BODY) */
    #body-container { 
        height: 1fr; 
        layout: horizontal; 
        overflow: hidden;
    }
    
    /* SOL KENAR ÇUBUĞU (SIDEBAR) */
    #sidebar { 
        width: 34; 
        height: 100%; 
        border-right: solid #555555; 
        padding: 0 1; 
    }
    #new-chat-btn {
        height: 1;
        margin-bottom: 1;
        color: #00ffcc;
        text-style: bold;
        border-bottom: solid #333333;
    }
    #search-input {
        height: 1;
        margin-bottom: 1;
        border-bottom: solid #333333;
    }
    #pinned-header {
        color: #ffaa00;
        text-style: bold;
        margin-top: 1;
    }
    #pinned-list {
        max-height: 7;
        margin-bottom: 1;
    }
    #recent-header {
        color: #aaaaaa;
        text-style: bold;
    }
    #recent-list {
        height: 1fr;
        scrollbar-size: 1 1;
    }

    /* SAĞ ANA ALAN (MAIN VIEWPORT) */
    #main-area { 
        width: 1fr; 
        height: 100%; 
        layout: vertical;
        padding: 0 1; 
        overflow: hidden;
    }
    #chat-log { 
        height: 1fr; 
        margin-bottom: 1;
        scrollbar-size: 1 1; 
    }
    
    /* AÇILIR POPUP MENÜLER (YÜZEN KATMAN OVERLAY - HİÇBİR ŞEYİ KAYDIRMAZ) */
    #top-dropdown-menu {
        height: 5;
        width: 32;
        dock: right;
        border: solid #00ffcc;
        background: #111111;
        display: none;
        margin-top: 1;
    }

    #model-dropdown-menu {
        dock: bottom;
        width: 34;
        height: 5;
        margin-bottom: 5;
        margin-right: 15;
        border: double #00ffcc;
        background: #111111;
        display: none;
    }
    #model-dropdown-menu ListItem {
        padding: 0;
        margin: 0;
        height: 1;
    }

    #command-suggestions {
        height: 7;
        border: solid #00ffcc;
        background: #111111;
        display: none;
        margin-bottom: 1;
    }

    /* KART MENÜLERİ VE AKSİYON BUTONLARI */
    #chat-action-buttons {
        height: 1;
        layout: horizontal;
        margin-bottom: 1;
        padding: 0 1;
    }
    .action-btn {
        width: 18;
        height: 1;
        color: #00ffcc;
        margin-right: 2;
    }

    #chat-info-bar { 
        height: 1; 
        border-top: solid #333333; 
        padding: 0 1; 
        color: #ffffff;
        text-style: bold;
        margin-bottom: 1;
    }
    #attachments-bar { 
        height: 1; 
        color: #77aaff; 
        padding: 0 1;
        display: none;
        margin-bottom: 1;
    }

    /* ALT GİRDİ ÇUBUĞU (INPUT BAR) */
    #input-container {
        height: 4;
        layout: horizontal;
        border: solid #00ffcc;
        margin-bottom: 1;
        padding: 0;
    }
    #add-file-btn, #model-select-btn, #send-stop-btn {
        height: 100%;
        content-align: center middle;
    }
    #add-file-btn {
        width: 5;
        color: #00ffcc;
        text-style: bold;
    }
    #prompt-text-area { 
        width: 1fr;
        height: 100%;
        padding: 0 1; 
        margin: 0; 
        border: none;
        background: #111111;
        color: #ffffff;
    }
    PromptTextArea {
        background: #111111;
        color: #ffffff;
    }
    PromptTextArea .text-area--cursor {
        background: #00ffcc;
        color: #000000;
        text-style: bold;
    }
    #model-select-btn {
        width: 14;
        color: #00ffcc;
        text-style: bold;
    }
    #send-stop-btn {
        width: 14;
        color: #00ffcc;
        text-style: bold;
    }

    #footer-bar {
        height: 1;
        color: #888888;
        padding: 0 1;
        margin-bottom: 1;
    }

    ListItem { 
        padding-bottom: 1; 
    }
    ListItem:hover, ListItem.--highlight { 
        background: transparent; 
        text-style: bold; 
        color: #00ffcc;
    }
    Button:hover {
        text-style: bold;
        color: #ffffff;
    }
    Input:focus { 
        border: none; 
    }
    """

    def __init__(self):
        super().__init__()
        self.client: Optional[GeminiClient] = None
        self.active_chat = None
        self.active_chat_title: str = "Yeni Sohbet"
        
        self.fallback_models = ["3.7 Flash", "3.1 Pro", "3.5 Flash-Lite"]
        self.available_models: List[Any] = list(self.fallback_models)
        self.active_model_idx: int = 0
        
        self.attached_files: List[str] = []
        self.all_chats_cache: List[Dict[str, Any]] = []
        self.is_authenticated_user: bool = False
        self.is_incognito_mode: bool = False
        self.is_generating_stream: bool = False
        
        self.last_user_prompt: str = ""
        self.last_gemini_response: str = ""
        self.last_generated_image_path: Optional[str] = None
        self._search_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        self.load_local_cache()

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-container"):
            yield Button("[≡]", id="toggle-sidebar-btn")
            yield Label("✨ Gemini TUI │ Oturum kontrol ediliyor...", id="header-title-label")
            yield Button("[🕶️ Incognito]", id="incognito-btn")
            yield Button("[⋮] Menü", id="top-menu-btn")

        with Horizontal(id="body-container"):
            with Vertical(id="sidebar"):
                yield Button("[✏️ Yeni Sohbet]", id="new-chat-btn")
                yield Input(placeholder="🔍 Sohbetlerde ara...", id="search-input")
                yield Label("📌 SABİTLENENLER", id="pinned-header")
                yield ListView(id="pinned-list")
                yield Label("🕒 SON KULLANILANLAR", id="recent-header")
                yield ListView(id="recent-list")
            
            with Vertical(id="main-area"):
                yield RichLog(id="chat-log", wrap=True)
                
                with Horizontal(id="chat-action-buttons"):
                    yield Button("[📋 Kopyala]", id="act-copy-btn", classes="action-btn")
                    yield Button("[🔍 Metni İncele]", id="act-inspect-btn", classes="action-btn")
                    yield Button("[🔄 Yeniden Oluştur]", id="act-retry-btn", classes="action-btn")
                    yield Button("[✏️ Düzenle]", id="act-edit-btn", classes="action-btn")

                yield ListView(id="top-dropdown-menu")
                yield ListView(id="model-dropdown-menu")
                yield ListView(id="command-suggestions")
                
                yield Label("💬 Sohbet: Yeni Sohbet  │  ⚡ Model: 3.7 Flash", id="chat-info-bar")
                yield Label("", id="attachments-bar")
                
                with Horizontal(id="input-container"):
                    yield Button("[+]", id="add-file-btn")
                    ta = PromptTextArea(id="prompt-text-area")
                    ta.cursor_blink = True
                    yield ta
                    yield Button("[Flash ▾]", id="model-select-btn")
                    yield Button("[ Gönder ⏎ ]", id="send-stop-btn")

                yield Label("💡 İpucu: Alt satıra geçmek için: Shift+Enter / Alt+Enter / ' \\ ' + Enter │ Metin Seçme: Shift + Sol Tık Sürükle", id="footer-bar")

    def on_mount(self) -> None:
        if self.all_chats_cache:
            asyncio.create_task(self.render_chat_list(self.all_chats_cache))
            
        self.update_header_status()
        self.update_chat_info_bar()
        self.connect_to_gemini()
        
        # YÖNTEM A: Saf HTTP Heartbeat Motoru
        self._heartbeat_task = asyncio.create_task(self.start_http_heartbeat_loop())

        # Girdi alanını doğrudan odakla
        try:
            self.query_one("#prompt-text-area", PromptTextArea).focus()
        except Exception:
            pass

    # --- PROMPT SUBMIT HANDLER (ENTER VEYA GÖNDER BUTTON) ---
    def handle_prompt_submit(self) -> None:
        ta = self.query_one("#prompt-text-area", PromptTextArea)
        text = ta.text.strip()
        if not text:
            return

        ta.text = ""
        self.query_one("#command-suggestions", ListView).display = False

        if text == "/login":
            self.trigger_auto_browser_login()
            return

        if text.startswith("/login "):
            raw_input = text.split(" ", 1)[1].strip()
            chat_log = self.query_one("#chat-log", RichLog)
            
            psid, psidts, psidcc = parse_cookie_input(raw_input)
            if psid:
                save_cookie_credentials(psid, psidts, psidcc)
                chat_log.write(Markdown("🔑 **Çerezler otomatik ayıklandı ve kaydedildi! Hesaba yeniden bağlanılıyor...**"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
                self.connect_to_gemini()
            else:
                self.trigger_auto_browser_login()
            return

        if text.startswith("/import "):
            fpath = text.split(" ", 1)[1].strip()
            self.action_import_chat(fpath)
            return

        if text.startswith("/export") or text.startswith("/save"):
            parts = text.split(" ", 1)
            fname = parts[1].strip() if len(parts) > 1 else ""
            self.action_export_chat(fname)
            return

        if text.startswith("/view"):
            parts = text.split(" ", 1)
            target = parts[1].strip() if len(parts) > 1 else None
            self.action_open_last_generated_image(target)
            return

        if text.startswith("/file ") or text.startswith("/upload "):
            filepath_str = text.split(" ", 1)[1].strip()
            clean_path = Path(filepath_str.strip("'\"")).expanduser()
            if clean_path.exists():
                self.attached_files.append(str(clean_path))
                self.update_attachments_bar()
                chat_log = self.query_one("#chat-log", RichLog)
                chat_log.write(Markdown(f"📎 **Dosya eklendi:** `{clean_path.name}` (`{clean_path}`)"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
            else:
                chat_log = self.query_one("#chat-log", RichLog)
                chat_log.write(Markdown(f"⚠️ **Dosya bulunamadı:** `{filepath_str}`"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
            return

        if text == "/copy":
            self.action_copy_last_response()
            return

        if text == "/new":
            self.action_new_chat()
            return

        if text in ["/model", "/models"]:
            if self.available_models:
                self.action_cycle_model()
            return

        if text == "/delete":
            self.action_delete_chat()
            return

        if text in ["/help", "/yardim"]:
            self.action_show_help()
            return

        if text in ["/exit", "/quit"]:
            self.exit()
            return

        if not self.active_chat:
            return

        # AGY STYLE COMPACT PASTE DISPLAY ([📋 Yapıştırılan Metin: +X Satır])
        self.last_user_prompt = text
        chat_log = self.query_one("#chat-log", RichLog)
        
        lines = text.split("\n")
        file_names_str = ""
        if self.attached_files:
            names = ", ".join(Path(f).name for f in self.attached_files)
            file_names_str = f" `[📎 {names}]`"

        if len(lines) > 3 or len(text) > 250:
            preview = "\n".join(lines[:2])
            chat_log.write(Markdown(f"**Sen:** `[📋 Yapıştırılan Metin (+{len(lines)} Satır)]`{file_names_str}\n\n> {preview}\n\n*... (Toplam {len(text)} karakter)*"))
        else:
            chat_log.write(Markdown(f"**Sen:** {text}{file_names_str}"))

        chat_log.write("\n")
        chat_log.scroll_end(animate=False)

        files_to_send = list(self.attached_files) if self.attached_files else None
        self.attached_files.clear()
        self.update_attachments_bar()

        self.send_message_to_gemini(text, files=files_to_send)

    # --- HTTP HEARTBEAT MOTORU (0 MB RAM / 0 MB DISK / %0 CPU) ---
    async def start_http_heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(120)
            if self.client and self.is_authenticated_user and not self.is_incognito_mode:
                try:
                    if hasattr(self.client, "client") and self.client.client:
                        await rotate_1psidts(self.client.client, verbose=False)
                    await self.client._fetch_user_status()
                except Exception:
                    pass

    # --- BUTTON VE CLICKGUI TIKLAMA OLAYLARI ---
    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        if btn_id == "toggle-sidebar-btn":
            sidebar = self.query_one("#sidebar", Vertical)
            sidebar.display = not sidebar.display

        elif btn_id == "incognito-btn":
            self.is_incognito_mode = not self.is_incognito_mode
            incog_btn = self.query_one("#incognito-btn", Button)
            if self.is_incognito_mode:
                incog_btn.label = "[🕶️ GİZLİ SOHBET]"
                incog_btn.styles.color = "#ff3366"
            else:
                incog_btn.label = "[🕶️ Incognito]"
                incog_btn.styles.color = "#ffaa00"
            self.update_header_status()

        elif btn_id == "top-menu-btn":
            self.toggle_top_menu()

        elif btn_id == "new-chat-btn":
            self.action_new_chat()

        elif btn_id == "act-copy-btn":
            self.action_copy_last_response()

        elif btn_id == "act-inspect-btn":
            self.action_inspect_last_response()

        elif btn_id == "act-retry-btn":
            if self.last_user_prompt and self.active_chat:
                self.send_message_to_gemini(self.last_user_prompt)

        elif btn_id == "act-edit-btn":
            if self.last_user_prompt:
                ta = self.query_one("#prompt-text-area", PromptTextArea)
                ta.text = self.last_user_prompt
                ta.focus()

        elif btn_id == "add-file-btn":
            self.action_prompt_file()

        elif btn_id == "model-select-btn":
            self.toggle_model_menu()

        elif btn_id == "send-stop-btn":
            if self.is_generating_stream:
                self.stop_generating_stream()
            else:
                self.handle_prompt_submit()

    def action_inspect_last_response(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not self.last_gemini_response:
            chat_log.write(Markdown("⚠️ **İncelenecek yanıt bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        chat_log.write(Markdown(f"🔍 **Seçilebilir Tam Yanıt Görünümü:**\n\n```markdown\n{self.last_gemini_response}\n```"))
        chat_log.write("\n---\n")
        chat_log.scroll_end(animate=False)

    def stop_generating_stream(self) -> None:
        self.is_generating_stream = False
        btn = self.query_one("#send-stop-btn", Button)
        btn.label = "[ Gönder ⏎ ]"
        btn.styles.color = "#00ffcc"

    def toggle_top_menu(self) -> None:
        top_menu = self.query_one("#top-dropdown-menu", ListView)
        if top_menu.display:
            top_menu.display = False
        else:
            asyncio.create_task(self._render_top_menu_items())

    async def _render_top_menu_items(self) -> None:
        top_menu = self.query_one("#top-dropdown-menu", ListView)
        await top_menu.clear()
        
        items = [
            ListItem(Label("🧹 Geçmişi Temizle"), id="menu-clear-history"),
            ListItem(Label("💾 Markdown Olarak Kaydet"), id="menu-export-md"),
            ListItem(Label("📊 Token / Kullanım Bilgisi"), id="menu-token-info"),
        ]
        await top_menu.mount(*items)
        top_menu.display = True

    def toggle_model_menu(self) -> None:
        model_menu = self.query_one("#model-dropdown-menu", ListView)
        if model_menu.display:
            model_menu.display = False
        else:
            asyncio.create_task(self._render_model_menu_items())

    async def _render_model_menu_items(self) -> None:
        model_menu = self.query_one("#model-dropdown-menu", ListView)
        await model_menu.clear()
        
        items = []
        for idx, m in enumerate(self.available_models):
            display = m.display_name if hasattr(m, "display_name") else str(m)
            prefix = "● " if idx == self.active_model_idx else "○ "
            item = ListItem(Label(f"{prefix}{display}"))
            item.model_index = idx
            items.append(item)
            
        await model_menu.mount(*items)
        model_menu.display = True

    # --- 2 KAT YÜKSEK ÇÖZÜNÜRLÜKLÜ SOHBET İÇİ YARIM-BLOK (HALF-BLOCK ▀) RENDER EDİCİ ---
    def render_image_in_chat(self, img_path_str: str, max_width: int = 85) -> Optional[Text]:
        if not PILImage:
            return None
        try:
            p = Path(img_path_str)
            if not p.exists():
                return None
            img = PILImage.open(p)
            aspect_ratio = img.height / img.width
            height = int(max_width * aspect_ratio)
            if height % 2 != 0:
                height += 1
                
            img = img.resize((max_width, height), PILImage.Resampling.LANCZOS).convert("RGB")
            
            t = Text()
            for y in range(0, height, 2):
                for x in range(max_width):
                    r1, g1, b1 = img.getpixel((x, y))
                    r2, g2, b2 = img.getpixel((x, y + 1)) if y + 1 < height else (0, 0, 0)
                    t.append("▀", style=f"rgb({r1},{g1},{b1}) on rgb({r2},{g2},{b2})")
                t.append("\n")
            return t
        except Exception:
            return None

    def action_open_last_generated_image(self, custom_path: Optional[str] = None) -> None:
        target_path = custom_path or self.last_generated_image_path
        chat_log = self.query_one("#chat-log", RichLog)

        if not target_path or not Path(target_path).exists():
            chat_log.write(Markdown("⚠️ **Açılacak görsel bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        try:
            if shutil.which("mpv"):
                subprocess.Popen(["mpv", "--title=Gemini Üretilen Görsel (FullHD)", str(target_path)])
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", str(target_path)])
            chat_log.write(Markdown(f"🔍 **Görsel pencerede açıldı:** `{Path(target_path).name}`"))
            chat_log.write("\n")
        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **Görsel açma hatası:** `{str(e)}`"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    def select_default_model_flash_37(self) -> None:
        if not self.available_models:
            return
        
        for idx, m in enumerate(self.available_models):
            display = m.display_name.lower() if hasattr(m, "display_name") else str(m).lower()
            name = m.model_name.lower() if hasattr(m, "model_name") else str(m).lower()
            if "3.7" in display or (name == "gemini-flash" and "lite" not in display):
                self.active_model_idx = idx
                return
                
        for idx, m in enumerate(self.available_models):
            display = m.display_name.lower() if hasattr(m, "display_name") else str(m).lower()
            if "flash" in display and "lite" not in display:
                self.active_model_idx = idx
                return

    def get_current_model_display_name(self) -> str:
        if self.available_models and 0 <= self.active_model_idx < len(self.available_models):
            m = self.available_models[self.active_model_idx]
            if hasattr(m, "display_name"):
                return m.display_name
            return str(m)
        return "3.7 Flash"

    # --- LOKAL CACHE İŞLEMLERİ ---
    def load_local_cache(self) -> None:
        try:
            if CACHE_FILE.exists():
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    self.all_chats_cache = json.load(f)
        except Exception:
            self.all_chats_cache = []

    def save_local_cache(self, chats_data: List[Dict[str, Any]]) -> None:
        if self.is_incognito_mode:
            return
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(chats_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def update_chat_info_bar(self) -> None:
        bar = self.query_one("#chat-info-bar", Label)
        
        chat_title = self.active_chat_title or "Yeni Sohbet"
        if len(chat_title) > 35:
            chat_title = chat_title[:32] + "..."

        model_name = self.get_current_model_display_name()
        bar.update(f"💬 Sohbet: [bold white]{chat_title}[/bold white]  │  ⚡ Model: [bold green]{model_name}[/bold green]")

    def update_header_status(self) -> None:
        header = self.query_one("#header-title-label", Label)
        model_display = self.get_current_model_display_name()
        
        if self.is_incognito_mode:
            session_status = "[bold red]🕶️ GİZLİ SOHBET (Bellekte)[/bold red]"
        elif self.is_authenticated_user and self.all_chats_cache:
            session_status = "[bold green]🟢 Hesaba Bağlı (Google Account)[/bold green]"
        elif self.client and getattr(self.client, "_cookie_source", "") != "Guest":
            session_status = f"[bold green]🟢 Bağlandı ({getattr(self.client, '_cookie_source', '')})[/bold green]"
        else:
            session_status = "[bold yellow]🟡 Misafir Modu (Giriş Yapılmadı)[/bold yellow]"

        status_text = f"✨ [bold cyan]Gemini TUI[/bold cyan]  │  ⚡ [bold cyan]MODEL:[/bold cyan] [bold white underline]{model_display}[/bold white underline]  │  Oturum: {session_status}"
        header.update(status_text)

    def update_attachments_bar(self) -> None:
        bar = self.query_one("#attachments-bar", Label)
        if self.attached_files:
            filenames = ", ".join(Path(f).name for f in self.attached_files)
            bar.update(f"📎 Ekli Dosyalar ({len(self.attached_files)}): {filenames} (Temizlemek için: /clear)")
            bar.display = True
        else:
            bar.update("")
            bar.display = False

    def trigger_auto_browser_login(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        
        native_cookies = auto_extract_native_linux_cookies()
        if native_cookies.get("__Secure-1PSID"):
            psid = native_cookies.get("__Secure-1PSID")
            psidts = native_cookies.get("__Secure-1PSIDTS")
            psidcc = native_cookies.get("__Secure-1PSIDCC")
            save_cookie_credentials(psid, psidts, psidcc)
            chat_log.write(Markdown("🎉 **Sistemdeki tarayıcınızdan (Brave/Chrome) Google oturum çerezleri 0-tık ile otomatik olarak algılandı ve bağlandı!**"))
            chat_log.write("\n---\n")
            chat_log.scroll_end(animate=False)
            self.connect_to_gemini()
            return

        chat_log.write(Markdown("🌐 **Varsayılan tarayıcınızda `gemini.google.com` adresi açılıyor...**"))
        chat_log.write(Markdown("⌛ *Google hesabınız arka planda taranıyor (30 saniye)...*"))
        chat_log.write("\n")
        chat_log.scroll_end(animate=False)
        
        try:
            webbrowser.open("https://gemini.google.com")
        except Exception:
            pass

        asyncio.create_task(self._poll_auto_login())

    async def _poll_auto_login(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        start_t = time.time()
        
        while time.time() - start_t < 30:
            await asyncio.sleep(2.5)
            try:
                native_cookies = auto_extract_native_linux_cookies()
                if native_cookies.get("__Secure-1PSID"):
                    psid = native_cookies.get("__Secure-1PSID")
                    psidts = native_cookies.get("__Secure-1PSIDTS")
                    psidcc = native_cookies.get("__Secure-1PSIDCC")
                    save_cookie_credentials(psid, psidts, psidcc)
                    chat_log.write(Markdown("🎉 **Tebrikler! Google hesabınız otomatik olarak algılandı ve bağlandı!**"))
                    chat_log.write("\n---\n")
                    chat_log.scroll_end(animate=False)
                    self.connect_to_gemini()
                    return
            except Exception:
                pass

    def show_login_instructions(self) -> None:
        self.trigger_auto_browser_login()

    # --- GEMINI CLIENT VE CANLI WEB BAGLANTISI ---
    @work(exclusive=True)
    async def connect_to_gemini(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        try:
            psid, psidts, psidcc = load_cookie_credentials()
            
            kwargs = {}
            if psidcc:
                kwargs["secure_1psidcc"] = psidcc
                
            self.client = GeminiClient(
                secure_1psid=psid,
                secure_1psidts=psidts,
                auto_cookies=True if not psid else False,
                **kwargs
            )
            
            await self.client.init(timeout=45, auto_close=False, auto_refresh=True)
            
            models = self.client.list_models()
            if models:
                real_avail = [m for m in models if getattr(m, "is_available", True)]
                if real_avail:
                    self.available_models = real_avail
            
            self.select_default_model_flash_37()
            selected_model = self.available_models[self.active_model_idx] if self.available_models else None
            self.active_chat = self.client.start_chat(model=selected_model)
            
            try:
                await self.client._fetch_recent_chats(recent=100)
                chats = self.client.list_chats() or []
                if chats:
                    self.is_authenticated_user = True
            except Exception:
                self.is_authenticated_user = False

            self.update_header_status()
            self.update_chat_info_bar()
            
            cookie_source = getattr(self.client, "_cookie_source", "")
            if cookie_source == "Guest" or not self.is_authenticated_user:
                self.trigger_auto_browser_login()
            else:
                self.sync_chats_from_server_bg()
        except Exception as e:
            self.update_header_status()
            self.update_chat_info_bar()
            chat_log.write(Markdown(f"⚠️ **Bağlantı Kurulamadı:** `{str(e)}`"))
            chat_log.write("\n")

    @work(exclusive=True, group="sync_bg")
    async def sync_chats_from_server_bg(self) -> None:
        if not self.client or self.is_incognito_mode:
            return

        try:
            await self.client._fetch_recent_chats(recent=500)
            chats = self.client.list_chats() or []
            
            if not chats:
                self.is_authenticated_user = False
                self.update_header_status()
                await self.render_chat_list([])
                return

            self.is_authenticated_user = True
            self.update_header_status()

            cache_data = []
            for c in chats:
                local_pin = False
                local_title = c.title
                for old in self.all_chats_cache:
                    if old.get("cid") == c.cid:
                        if "is_pinned" in old:
                            local_pin = old["is_pinned"]
                        if old.get("title_renamed"):
                            local_title = old["title"]
                        break

                cache_data.append({
                    "cid": c.cid,
                    "title": local_title,
                    "is_pinned": getattr(c, "is_pinned", False) or local_pin,
                    "timestamp": getattr(c, "timestamp", 0.0)
                })
                
            self.all_chats_cache = cache_data
            self.save_local_cache(cache_data)

            search_val = self.query_one("#search-input", Input).value
            await self.render_chat_list(cache_data, filter_query=search_val)
        except Exception:
            pass

    async def render_chat_list(self, chats: List[Dict[str, Any]], filter_query: str = "") -> None:
        if not self.is_mounted or self.is_incognito_mode:
            return
            
        try:
            pinned_list = self.query_one("#pinned-list", ListView)
            recent_list = self.query_one("#recent-list", ListView)
            await pinned_list.clear()
            await recent_list.clear()
        except Exception:
            return

        filter_lower = filter_query.lower().strip()
        
        pinned_chats = [c for c in chats if c.get("is_pinned", False)]
        recent_chats = [c for c in chats if not c.get("is_pinned", False)]

        # Pinned mount
        pinned_items = []
        for chat in pinned_chats:
            title = chat.get("title") or "Sohbet"
            if filter_lower and filter_lower not in title.lower():
                continue
            item = ListItem(Label(f"📌 {title}"))
            item.chat_id = chat.get("cid")
            item.title_text = title
            pinned_items.append(item)
        if pinned_items:
            await pinned_list.mount(*pinned_items)

        # Recent mount
        recent_items = []
        for chat in recent_chats:
            title = chat.get("title") or "Sohbet"
            if filter_lower and filter_lower not in title.lower():
                continue
            item = ListItem(Label(f"• {title}"))
            item.chat_id = chat.get("cid")
            item.title_text = title
            recent_items.append(item)
        if recent_items:
            await recent_list.mount(*recent_items)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            if self._search_task and not self._search_task.done():
                self._search_task.cancel()
            filter_query = event.value
            self._search_task = asyncio.create_task(self._debounced_search(filter_query))
            return

    async def _debounced_search(self, query: str) -> None:
        await asyncio.sleep(0.04)
        await self.render_chat_list(self.all_chats_cache, filter_query=query)

    async def render_command_popup(self, query: str) -> None:
        popup = self.query_one("#command-suggestions", ListView)
        await popup.clear()

        matching = [
            (cmd, desc) for cmd, desc in COMMANDS_LIST 
            if query == "/" or cmd.lower().startswith(query)
        ]

        if matching:
            items = []
            for cmd, desc in matching:
                item = ListItem(Label(f"[bold green]{cmd}[/bold green] ── [dim]{desc}[/dim]"))
                item.command_str = cmd
                items.append(item)
            await popup.mount(*items)
            popup.display = True
        else:
            popup.display = False

    # --- GEÇMİŞ SOHBETİ YÜKLEME ---
    @work(exclusive=True)
    async def load_historical_chat(self, chat_id: str, title: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        
        self.active_chat_title = title
        self.update_chat_info_bar()
        
        selected_model = self.available_models[self.active_model_idx] if self.available_models else None
        
        if self.client:
            history = await self.client.read_chat(chat_id, limit=100)
            rid = ""
            rcid = ""
            
            if history and history.turns:
                for turn in history.turns:
                    if turn.role == "model" and turn.model_output:
                        mo = turn.model_output
                        if len(mo.metadata) >= 2 and mo.metadata[1]:
                            rid = mo.metadata[1]
                        if mo.rcid:
                            rcid = mo.rcid
                        break
                
                self.active_chat = self.client.start_chat(
                    cid=chat_id,
                    rid=rid,
                    rcid=rcid,
                    model=selected_model
                )

                for turn in reversed(history.turns):
                    if turn.role == "user":
                        chat_log.write(Markdown(f"**Sen:** {turn.text}"))
                        chat_log.write("\n")
                    else:
                        self.last_gemini_response = turn.text
                        chat_log.write(Text("Gemini:", style="bold green"))
                        chat_log.write(Markdown(turn.text))
                        
                        if hasattr(turn, "citations") and turn.citations:
                            sources_md = "\n🔗 **Web Kaynakları:**\n"
                            for c in turn.citations:
                                t_str = getattr(c, "title", None) or getattr(c, "url", "Kaynak")
                                u_str = getattr(c, "url", "#")
                                sources_md += f"- [{t_str}]({u_str})\n"
                            chat_log.write(Markdown(sources_md))
                            
                        chat_log.write("\n---\n")
                
                chat_log.scroll_end(animate=False)
            else:
                self.active_chat = self.client.start_chat(cid=chat_id, model=selected_model)
        else:
            self.active_chat = self.client.start_chat(cid=chat_id, model=selected_model) if self.client else None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_id = event.list_view.id

        if list_id == "top-dropdown-menu":
            item_id = event.item.id
            self.query_one("#top-dropdown-menu", ListView).display = False
            
            if item_id == "menu-clear-history":
                self.query_one("#chat-log", RichLog).clear()
            elif item_id == "menu-export-md":
                self.action_export_chat()
            elif item_id == "menu-token-info":
                chat_log = self.query_one("#chat-log", RichLog)
                chat_log.write(Markdown("📊 **Token ve Kullanım Bilgisi:** Sınırsız Web İstemci Modu (Compute Limit: Aktif)"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
            return

        if list_id == "model-dropdown-menu":
            idx = getattr(event.item, "model_index", 0)
            self.active_model_idx = idx
            self.query_one("#model-dropdown-menu", ListView).display = False
            
            new_m = self.available_models[self.active_model_idx]
            if self.active_chat:
                self.active_chat.model = new_m
            self.update_header_status()
            self.update_chat_info_bar()
            return

        if list_id == "command-suggestions":
            cmd = getattr(event.item, "command_str", None)
            if cmd:
                ta = self.query_one("#prompt-text-area", PromptTextArea)
                if cmd in ["/file <yol>", "/upload <yol>"]:
                    ta.text = "/file "
                elif cmd == "/rename <başlık>":
                    ta.text = "/rename "
                elif cmd == "/login [Çerez]":
                    ta.text = "/login "
                elif cmd in ["/import <dosya>", "/export <dosya>"]:
                    ta.text = cmd.split()[0] + " "
                elif cmd == "/view":
                    ta.text = "/view"
                else:
                    ta.text = cmd
                ta.focus()
                self.query_one("#command-suggestions", ListView).display = False
            return

        if list_id in ["pinned-list", "recent-list"]:
            chat_id = getattr(event.item, "chat_id", None)
            if chat_id:
                title = getattr(event.item, "title_text", "Sohbet")
                self.load_historical_chat(chat_id, title)
                self.query_one("#prompt-text-area", PromptTextArea).focus()

    # --- SOHBETİ DISA AKTARMA (/export) ---
    def action_export_chat(self, filename: str = "") -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not filename:
            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            clean_title = "".join(c if c.isalnum() else "_" for c in self.active_chat_title)[:25]
            filename = f"Gemini_Sohbet_{clean_title}_{now_str}.md"

        export_path = Path.cwd() / filename
        asyncio.create_task(self._do_export_file(export_path))

    async def _do_export_file(self, export_path: Path) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        try:
            cid = self.active_chat.cid if self.active_chat else ""
            history = await self.client.read_chat(cid, limit=150) if (self.client and cid) else None
            
            content = f"# 🤖 GeminiTUI Sohbet Raporu\n"
            content += f"- **Başlık:** {self.active_chat_title}\n"
            content += f"- **Model:** {self.get_current_model_display_name()}\n"
            content += f"- **Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"- **Sohbet ID:** `{cid}`\n\n"
            content += "---\n\n"
            
            if history and history.turns:
                for turn in reversed(history.turns):
                    role_name = "👤 Sen" if turn.role == "user" else "🤖 Gemini"
                    content += f"### {role_name}\n\n{turn.text}\n\n---\n\n"
            elif self.last_gemini_response:
                content += f"### 👤 Sen\n\n{self.last_user_prompt}\n\n---\n\n"
                content += f"### 🤖 Gemini\n\n{self.last_gemini_response}\n\n---\n\n"
                
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            chat_log.write(Markdown(f"💾 **Sohbet dışa aktarıldı:** `{export_path.name}` (`{export_path}`)"))
            chat_log.write("\n")
        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **Dışa aktarma hatası:** `{str(e)}`"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- PANOYA KOPYALAMA (Alt+C / /copy) ---
    def action_copy_last_response(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not self.last_gemini_response:
            chat_log.write(Markdown("⚠️ **Kopyalanacak yanıt bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return
            
        success = False
        text_to_copy = self.last_gemini_response
        
        if shutil.which("wl-copy"):
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(input=text_to_copy.encode("utf-8"))
                success = True
            except Exception:
                pass
        elif shutil.which("xclip"):
            try:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                p.communicate(input=text_to_copy.encode("utf-8"))
                success = True
            except Exception:
                pass

        if success:
            chat_log.write(Markdown("📋 **En son yanıt panoya kopyalandı!**"))
            chat_log.write("\n")
        else:
            chat_log.write(Markdown("⚠️ **Panoya kopyalama başarısız (wl-copy / xclip bulunamadı).**"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- AKSİYON KISAYOLLARI ---
    def action_new_chat(self) -> None:
        if not self.client:
            return
        selected_model = self.available_models[self.active_model_idx] if self.available_models else None
        self.active_chat = self.client.start_chat(model=selected_model)
        
        self.active_chat_title = "Yeni Sohbet"
        self.update_chat_info_bar()
        
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()

    def action_cycle_model(self) -> None:
        if not self.available_models:
            return
        self.active_model_idx = (self.active_model_idx + 1) % len(self.available_models)
        new_model = self.available_models[self.active_model_idx]
        
        if self.active_chat:
            self.active_chat.model = new_model
            
        self.update_header_status()
        self.update_chat_info_bar()
        
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Markdown(f"⚡ **Aktif AI Modeli Değiştirildi:** `{self.get_current_model_display_name()}`"))
        chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    def action_prompt_file(self) -> None:
        ta = self.query_one("#prompt-text-area", PromptTextArea)
        ta.text = "/file "
        ta.focus()

    @work(exclusive=True)
    async def action_delete_chat(self) -> None:
        if not self.client or not self.active_chat or not self.active_chat.cid:
            return
            
        cid = self.active_chat.cid
        try:
            self.client.delete_chat(cid)
            self.action_new_chat()
            self.sync_chats_from_server_bg()
        except Exception:
            pass

    def action_show_help(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        help_md = (
            "### 💡 KULLANIM VE KOMUT YARDIMI\n\n"
            "- **Enter** : Mesajı gönderir.\n"
            "- **Shift+Enter** veya **Alt+Enter** veya **'\\'+Enter** : Girdi alanında alt satıra geçer.\n"
            "- **Shift + Sol Tık Sürükle** : Terminal içinden doğrudan metin seçip kopyalar.\n"
            "- **F1** veya **Alt+N** veya `/new` : Yeni sohbet başlatır.\n"
            "- **F2** veya **Alt+M** veya `/model` : AI Modelleri arasında geçiş yapar.\n"
            "- **F3** veya **Alt+F** veya `/file <yol>` : Görsel (PNG/JPG/WEBP), PDF veya metin dosyası ekler.\n"
            "- `/login` : Tarayıcı çerezlerinizi otomatik algılar ve bağlanır.\n"
            "- `/export <dosya>` : Aktif sohbeti Markdown (.md) dosyası olarak kaydeder.\n"
            "- `/import <dosya>` : Kaydedilmiş sohbet dosyasını yükler ve canlı oturum bağlamına aktarır.\n"
            "- **F4** veya **Alt+D** veya `/delete` : Aktif sohbeti hesabınızdan siler.\n"
            "- **Alt+C** veya `/copy` : En son verilen yanıtı panoya kopyalar.\n"
            "- **Alt+V** veya `/view` : Üretilen görseli mpv ile tam çözünürlükte açar.\n"
            "- **F7** veya **Alt+H** veya `/help` : Yardım menüsünü gösterir.\n"
            "- `/pin` : Sohbeti iğneler/iğneyi kaldırır (📌).\n"
            "- `/rename <başlık>` : Sohbetin adını değiştirir.\n"
            "- `/clear` : Eklenmiş dosyaları temizler.\n"
            "- `/exit` : Uygulamadan çıkar.\n\n"
            "---\n"
        )
        chat_log.write(Markdown(help_md))
        chat_log.scroll_end(animate=False)

    # ⚡ TEMİZ AKICI MESAJLAŞMA MOTORU
    @work(exclusive=True)
    async def send_message_to_gemini(self, message: str, files: Optional[List[str]] = None) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        send_btn = self.query_one("#send-stop-btn", Button)
        
        try:
            self.is_generating_stream = True
            send_btn.label = "[ 🛑 Durdur ]"
            send_btn.styles.color = "#ff3366"

            response_text = ""
            base_lines = len(chat_log.lines)
            last_chunk_obj = None
            
            async for chunk in self.active_chat.send_message_stream(
                prompt=message,
                files=files
            ):
                if not self.is_generating_stream:
                    break

                if chunk:
                    last_chunk_obj = chunk
                    if chunk.text_delta:
                        response_text += chunk.text_delta
                        chat_log.lines = chat_log.lines[:base_lines]
                        chat_log.write(Text("Gemini:", style="bold green"))
                        chat_log.write(response_text)
                        chat_log.scroll_end(animate=False)

            if response_text.strip():
                self.last_gemini_response = response_text
                chat_log.lines = chat_log.lines[:base_lines]
                chat_log.write(Text("Gemini:", style="bold green"))
                chat_log.write(Markdown(response_text))
                
                if last_chunk_obj and hasattr(last_chunk_obj, "citations") and last_chunk_obj.citations:
                    sources_md = "\n🔗 **Web Kaynakları:**\n"
                    for c in last_chunk_obj.citations:
                        t_str = getattr(c, "title", None) or getattr(c, "url", "Kaynak")
                        u_str = getattr(c, "url", "#")
                        sources_md += f"- [{t_str}]({u_str})\n"
                    chat_log.write(Markdown(sources_md))

                if last_chunk_obj and hasattr(last_chunk_obj, "images") and last_chunk_obj.images:
                    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                    for img in last_chunk_obj.images:
                        try:
                            saved_file = await img.save(path=str(IMAGES_DIR))
                            self.last_generated_image_path = saved_file
                            
                            chat_log.write(Markdown(f"🖼️ **Görsel Üretildi:** `{saved_file}`  *(🔍 Tam çözünürlük: **Alt+V** / `/view`)*"))
                            
                            ansi_img_text = self.render_image_in_chat(saved_file, max_width=85)
                            if ansi_img_text:
                                chat_log.write(ansi_img_text)
                        except Exception:
                            pass

                chat_log.write("\n---\n")
                chat_log.scroll_end(animate=False)

            is_new_chat = True
            if self.active_chat and self.active_chat.cid:
                for c in self.all_chats_cache:
                    if c.get("cid") == self.active_chat.cid:
                        is_new_chat = False
                        break
                        
            if is_new_chat and not self.is_incognito_mode:
                self.sync_chats_from_server_bg()
            
        except Exception as e:
            chat_log.write(Markdown(f"**[Hata]:** `{str(e)}`"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
        finally:
            self.is_generating_stream = False
            send_btn.label = "[ Gönder ⏎ ]"
            send_btn.styles.color = "#00ffcc"

if __name__ == "__main__":
    app = NakedGeminiTUI()
    app.run()
