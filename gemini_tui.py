import os
import re
import json
import time
import asyncio
import pathlib
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Union

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import ListView, ListItem, Label, Input, RichLog
from textual.binding import Binding
from textual.events import Key
from textual import work

from rich.markdown import Markdown
from rich.text import Text

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

from gemini_webapi import GeminiClient
from gemini_webapi.types.availablemodel import AvailableModel
from gemini_webapi.utils import set_log_level, logger

# Loguru ve internal log seviyesini ERROR yaparak terminal kirliliğini önlüyoruz
set_log_level("ERROR")
try:
    logger.remove()
except Exception:
    pass

# Lokal cache dizinleri
CACHE_DIR = pathlib.Path.home() / ".cache" / "gemini_tui"
CACHE_FILE = CACHE_DIR / "chats_cache.json"
PROJECTS_FILE = CACHE_DIR / "projects_cache.json"
IMAGES_DIR = CACHE_DIR / "images"

# Kullanılabilir Slash Komutları
COMMANDS_LIST = [
    ("/help", "Kullanım yardımını ve komut listesini gösterir"),
    ("/new", "Yeni temiz bir sohbet başlatır"),
    ("/project <isim>", "Yeni proje oluşturur veya var olana geçiş yapar"),
    ("/model", "AI modelleri arasında geçiş yapar (3.7 Flash, 3.1 Pro, 3.5 Flash-Lite)"),
    ("! <komut>", "Terminal shell komutunu çalıştırır ve çıktısını Gemini'a analiz ettirir"),
    ("/view [dosya]", "Son üretilen görseli veya belirtilen resmi mpv/full-hd penceresinde açar"),
    ("/copy", "En son verilen yanıtın tamamını panoya kopyalar (Alt+C)"),
    ("/copycode", "En son verilen yanıt içindeki SADECE KOD bloklarını kopyalar"),
    ("/export <dosya>", "Aktif sohbeti Markdown (.md) dosyası olarak kaydeder"),
    ("/import <dosya>", "Kaydedilmiş sohbet dosyasını geri yükler ve devam ettirir"),
    ("/file <yol>", "Görsel (PNG/JPG/WEBP), PDF veya metin/kod dosyası ekler (F3/Alt+F)"),
    ("/retry", "En son gönderilen mesajı yeniden yanıtlatır"),
    ("/rename <başlık>", "Aktif sohbetin başlığını değiştirir"),
    ("/pin", "Sohbeti sol panele iğneler veya iğneyi kaldırır (📌)"),
    ("/delete", "Aktif sohbeti Google hesabınızdan siler"),
    ("/thinking", "Derin Düşünme (Extended Thinking) modunu açar/kapatır"),
    ("/research", "Derin Araştırma (Deep Research) modunu açar/kapatır"),
    ("/clear", "Eklenmiş dosyaları temizler"),
    ("/exit", "Uygulamadan çıkış yapar"),
]

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
        Binding("f5", "action_toggle_thinking", "Düşünme Modu", priority=True),
        Binding("alt+t", "action_toggle_thinking", "Düşünme Modu", priority=True),
        Binding("f6", "action_toggle_research", "Araştırma Modu", priority=True),
        Binding("alt+r", "action_toggle_research", "Araştırma Modu", priority=True),
        Binding("f7", "action_show_help", "Yardım", priority=True),
        Binding("alt+h", "action_show_help", "Yardım", priority=True),
        Binding("alt+v", "action_open_last_generated_image", "Görseli Aç", priority=True),
    ]

    CSS = """
    * { 
        background: transparent; 
        border: none; 
    }
    Screen { 
        layout: vertical; 
    }
    #header-bar { 
        height: 1; 
        border-bottom: solid #444444; 
        padding: 0 1; 
        color: #ffffff;
    }
    #body-container { 
        height: 1fr; 
        layout: horizontal; 
    }
    #sidebar { 
        width: 32; 
        height: 100%; 
        border-right: solid #555555; 
        padding: 0 1; 
    }
    #sidebar-header-proj {
        color: #aaaaaa;
        text-style: bold;
    }
    #sidebar-header-chat {
        color: #aaaaaa;
        text-style: bold;
        margin-top: 1;
    }
    #project-list {
        height: 6;
        border-bottom: solid #333333;
        margin-bottom: 1;
    }
    #search-input {
        height: 1;
        margin-bottom: 1;
        border-bottom: solid #333333;
    }
    #chat-list {
        height: 1fr;
        scrollbar-size: 1 1;
    }
    #main-area { 
        width: 1fr; 
        height: 100%; 
        padding: 0 1; 
    }
    #chat-log { 
        height: 1fr; 
        scrollbar-size: 1 1; 
    }
    #command-suggestions {
        height: 7;
        border: solid #00ffcc;
        background: #111111;
        display: none;
        margin-bottom: 1;
    }
    #chat-info-bar { 
        height: 3; 
        border-top: solid #00ffcc; 
        border-bottom: solid #00ffcc; 
        padding: 0 1; 
        color: #ffffff;
        text-style: bold;
    }
    #attachments-bar { 
        height: 1; 
        color: #77aaff; 
        padding: 0 1;
        display: none;
    }
    #message-input { 
        dock: bottom; 
        padding: 0; 
        margin: 0; 
    }
    #footer-bar {
        height: 1;
        border-top: solid #333333;
        color: #888888;
        padding: 0 1;
    }
    ListItem { 
        padding-bottom: 1; 
    }
    ListItem:hover, ListItem.--highlight { 
        background: transparent; 
        text-style: bold; 
        color: #00ffcc;
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
        self.extended_thinking: bool = False
        self.deep_research: bool = False
        self.all_chats_cache: List[Dict[str, Any]] = []
        
        self.projects_list: List[str] = ["Genel", "Yazılım Projesi", "Kişisel / Notlar"]
        self.active_project_name: str = "Genel"
        
        self.last_user_prompt: str = ""
        self.last_gemini_response: str = ""
        self.last_generated_image_path: Optional[str] = None
        self._search_task: Optional[asyncio.Task] = None

        self.load_local_cache()
        self.load_projects_cache()

    def compose(self) -> ComposeResult:
        yield Label("⚡ Gemini TUI │ Yükleniyor...", id="header-bar")
        
        with Horizontal(id="body-container"):
            with Vertical(id="sidebar"):
                yield Label("📁 PROJELER\n", id="sidebar-header-proj")
                yield ListView(id="project-list")
                yield Label("💬 GEÇMİŞ SOHBETLER\n", id="sidebar-header-chat")
                yield Input(placeholder="🔍 Sohbet ara...", id="search-input")
                yield ListView(id="chat-list")
            
            with Vertical(id="main-area"):
                yield RichLog(id="chat-log", wrap=True)
                yield ListView(id="command-suggestions")
                yield Label("💬 Sohbet: Yeni Sohbet  │  ⚡ Model: 3.7 Flash", id="chat-info-bar")
                yield Label("", id="attachments-bar")
                yield Input(placeholder="Mesajınız, komut (/), dosya ekle (/file) veya terminal komutu (!ls)...", id="message-input")
                
        yield Label("F1: Yeni │ F2: Model │ F3: Dosya │ F4: Sil │ Alt+C: Kopyala │ Alt+V: Görseli Aç │ F5: Düşünme │ F6: Araştırma │ F7: Yardım", id="footer-bar")

    def on_mount(self) -> None:
        self.render_project_list()
        
        if self.all_chats_cache:
            asyncio.create_task(self.render_chat_list(self.all_chats_cache))
            
        self.update_header_status()
        self.update_chat_info_bar()
        self.connect_to_gemini()

    # --- SOHBET İÇİ YARIM-BLOK (HALF-BLOCK ▀) RENDER EDİCİ ---
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

    # --- İSTEĞE BAĞLI OTO/KULLANICI TETİKLEMELİ POPUP GÖRÜNTÜLEYİCİ ---
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
            chat_log.write(Markdown(f"🔍 **Görsel FullHD pencerede açıldı:** `{Path(target_path).name}`"))
            chat_log.write("\n")
        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **Görsel açma hatası:** `{str(e)}`"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- YUKARI OK İLE SON MESAJI GERİ ÇAĞIRMA ---
    def on_key(self, event: Key) -> None:
        if event.key == "up":
            try:
                msg_input = self.query_one("#message-input", Input)
                if msg_input.is_focused and not msg_input.value.strip() and self.last_user_prompt:
                    msg_input.value = self.last_user_prompt
                    msg_input.cursor_position = len(msg_input.value)
                    event.prevent_default()
                    event.stop()
            except Exception:
                pass

    # --- CLIENT-SIDE PROJELER LİSTESİNİ ÇİZDİRME ---
    def render_project_list(self) -> None:
        if not self.is_mounted:
            return
        try:
            p_list = self.query_one("#project-list", ListView)
        except Exception:
            return
            
        p_list.clear()
        items = []
        for name in self.projects_list:
            prefix = "[bold green]▶ [/bold green]" if name == self.active_project_name else "  "
            item = ListItem(Label(f"{prefix}📁 {name}"))
            item.project_name = name
            items.append(item)
            
        if items and p_list.is_mounted:
            p_list.mount(*items)

    def load_projects_cache(self) -> None:
        try:
            if PROJECTS_FILE.exists():
                with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.projects_list = data.get("projects", self.projects_list)
                    self.active_project_name = data.get("active_project", self.active_project_name)
        except Exception:
            pass

    def save_projects_cache(self) -> None:
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "projects": self.projects_list,
                    "active_project": self.active_project_name
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --- VARSAYILAN MODELİ 3.7 FLASH YAPAN YARDIMCI METOT ---
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
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(chats_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # --- GİRDİ KUTUSU ÜSTÜNDEKİ SABİT ÇERÇEVELİ SOHBET VE MODEL BARI ---
    def update_chat_info_bar(self) -> None:
        bar = self.query_one("#chat-info-bar", Label)
        
        chat_title = self.active_chat_title or "Yeni Sohbet"
        if len(chat_title) > 35:
            chat_title = chat_title[:32] + "..."

        model_name = self.get_current_model_display_name()
        proj_str = f"  │  📁 Proje: [bold yellow]{self.active_project_name}[/bold yellow]"

        bar.update(f"💬 Sohbet: [bold white]{chat_title}[/bold white]  │  ⚡ Model: [bold green]{model_name}[/bold green]{proj_str}")

    def update_header_status(self) -> None:
        header = self.query_one("#header-bar", Label)
        
        model_display = self.get_current_model_display_name()
            
        thinking_str = "[bold green]AÇIK[/bold green]" if self.extended_thinking else "[dim]KAPALI[/dim]"
        research_str = "[bold magenta]AÇIK[/bold magenta]" if self.deep_research else "[dim]KAPALI[/dim]"
        
        session_status = "[bold green]🟢 Aktif[/bold green]"
        if self.client:
            cookie_source = getattr(self.client, "_cookie_source", "")
            if cookie_source == "Guest":
                session_status = "[bold yellow]🟡 Misafir (Guest)[/bold yellow]"
        else:
            session_status = "[bold red]🔴 Bağlanıyor...[/bold red]"

        status_text = (
            f"⚡ [bold cyan]MODEL:[/bold cyan] [bold white underline]{model_display}[/bold white underline]  │  "
            f"💭 [cyan]Düşünme:[/cyan] {thinking_str}  │  "
            f"🔍 [magenta]Araştırma:[/magenta] {research_str}  │  "
            f"Oturum: {session_status}"
        )
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

    # --- GEMINI CLIENT VE ARKA PLAN BAĞLANTISI ---
    @work(exclusive=True)
    async def connect_to_gemini(self) -> None:
        try:
            psid = os.getenv("GEMINI_1PSID", None)
            psidts = os.getenv("GEMINI_1PSIDTS", None)
            
            self.client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts)
            await self.client.init(timeout=45, auto_close=False, auto_refresh=True)
            
            models = self.client.list_models()
            if models:
                real_avail = [m for m in models if getattr(m, "is_available", True)]
                if real_avail:
                    self.available_models = real_avail
            
            self.select_default_model_flash_37()
            
            selected_model = self.available_models[self.active_model_idx] if self.available_models else None
            self.active_chat = self.client.start_chat(model=selected_model)
            
            self.update_header_status()
            self.update_chat_info_bar()
            self.sync_chats_from_server_bg()
        except Exception:
            self.update_header_status()
            self.update_chat_info_bar()

    @work(exclusive=True, group="sync_bg")
    async def sync_chats_from_server_bg(self) -> None:
        if not self.client:
            return
        
        cookie_source = getattr(self.client, "_cookie_source", "")
        if cookie_source == "Guest":
            self.all_chats_cache = []
            self.save_local_cache([])
            await self.render_chat_list([])
            return

        await self.client._fetch_recent_chats(recent=500)
        chats = self.client.list_chats() or []
        
        cache_data = []
        for c in chats:
            local_pin = False
            local_title = c.title
            local_project = "Genel"
            for old in self.all_chats_cache:
                if old.get("cid") == c.cid:
                    if "is_pinned" in old:
                        local_pin = old["is_pinned"]
                    if old.get("title_renamed"):
                        local_title = old["title"]
                    if old.get("project"):
                        local_project = old["project"]
                    break

            cache_data.append({
                "cid": c.cid,
                "title": local_title,
                "is_pinned": getattr(c, "is_pinned", False) or local_pin,
                "project": local_project,
                "timestamp": getattr(c, "timestamp", 0.0)
            })
            
        self.all_chats_cache = cache_data
        self.save_local_cache(cache_data)

        if self.active_chat and self.active_chat.cid:
            for c in cache_data:
                if c["cid"] == self.active_chat.cid and c["title"]:
                    self.active_chat_title = c["title"]
                    self.update_chat_info_bar()
                    break

        search_val = self.query_one("#search-input", Input).value
        await self.render_chat_list(cache_data, filter_query=search_val)

    # ⚡ CLIENT-SIDE PROJE FİLTRELEMELİ ÇİZDİRME
    async def render_chat_list(self, chats: List[Dict[str, Any]], filter_query: str = "") -> None:
        if not self.is_mounted:
            return
            
        try:
            chat_list = self.query_one("#chat-list", ListView)
        except Exception:
            return

        if not getattr(chat_list, "is_mounted", False):
            return

        try:
            await chat_list.clear()

            project_filtered = [
                c for c in chats 
                if c.get("project", "Genel") == self.active_project_name
            ]

            try:
                sidebar_header = self.query_one("#sidebar-header-chat", Label)
                sidebar_header.update(f"💬 GEÇMİŞ SOHBETLER ({len(project_filtered)})\n")
            except Exception:
                pass

            cookie_source = getattr(self.client, "_cookie_source", "") if self.client else ""
            if cookie_source == "Guest":
                item = ListItem(Label("> (Giriş Yapılmadı)"))
                item.chat_id = None
                await chat_list.mount(item)
                return

            if not project_filtered:
                item = ListItem(Label("> (Bu Projede Sohbet Yok)"))
                item.chat_id = None
                await chat_list.mount(item)
                return

            filter_lower = filter_query.lower().strip()
            
            pinned = [c for c in project_filtered if c.get("is_pinned", False)]
            others = [c for c in project_filtered if not c.get("is_pinned", False)]
            ordered = pinned + others

            items = []
            for chat in ordered:
                title = chat.get("title") or f"Sohbet ({chat.get('cid', '')[:8]})"
                if filter_lower and filter_lower not in title.lower():
                    continue
                    
                pin_prefix = "📌 " if chat.get("is_pinned", False) else "> "
                item = ListItem(Label(f"{pin_prefix}{title}"))
                item.chat_id = chat.get("cid")
                item.title_text = title
                items.append(item)

            if items:
                await chat_list.mount(*items)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            if self._search_task and not self._search_task.done():
                self._search_task.cancel()
            filter_query = event.value
            self._search_task = asyncio.create_task(self._debounced_search(filter_query))
            return

        if event.input.id == "message-input":
            val = event.value.strip()
            popup = self.query_one("#command-suggestions", ListView)
            
            if val.startswith("/") or val.startswith("!"):
                query = val.lower()
                asyncio.create_task(self.render_command_popup(query))
            else:
                popup.display = False

    async def _debounced_search(self, query: str) -> None:
        await asyncio.sleep(0.04)
        await self.render_chat_list(self.all_chats_cache, filter_query=query)

    async def render_command_popup(self, query: str) -> None:
        popup = self.query_one("#command-suggestions", ListView)
        await popup.clear()

        matching = [
            (cmd, desc) for cmd, desc in COMMANDS_LIST 
            if query in ["/", "!"] or cmd.lower().startswith(query)
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
        if event.list_view.id == "project-list":
            p_name = getattr(event.item, "project_name", None)
            if p_name:
                self.active_project_name = p_name
                self.render_project_list()
                self.save_projects_cache()
                self.update_chat_info_bar()
                search_val = self.query_one("#search-input", Input).value
                asyncio.create_task(self.render_chat_list(self.all_chats_cache, filter_query=search_val))
                self.query_one("#message-input", Input).focus()
            return

        if event.list_view.id == "command-suggestions":
            cmd = getattr(event.item, "command_str", None)
            if cmd:
                msg_input = self.query_one("#message-input", Input)
                if cmd in ["/file <yol>", "/upload <yol>"]:
                    msg_input.value = "/file "
                elif cmd == "/rename <başlık>":
                    msg_input.value = "/rename "
                elif cmd == "/project <isim>":
                    msg_input.value = "/project "
                elif cmd in ["/import <dosya>", "/export <dosya>"]:
                    msg_input.value = cmd.split()[0] + " "
                elif cmd == "/view [dosya]":
                    msg_input.value = "/view "
                elif cmd == "! <komut>":
                    msg_input.value = "! "
                else:
                    msg_input.value = cmd
                msg_input.focus()
                self.query_one("#command-suggestions", ListView).display = False
            return

        if event.list_view.id == "chat-list":
            chat_id = getattr(event.item, "chat_id", None)
            if chat_id:
                title = getattr(event.item, "title_text", "Sohbet")
                self.load_historical_chat(chat_id, title)
                self.query_one("#message-input", Input).focus()

    # --- SHELL KOMUT ÇALIŞTIRMA (!komut / /sh) ---
    def action_execute_shell(self, shell_command: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Markdown(f"💻 **Shell Komutu Çalıştırılıyor:** `{shell_command}`"))
        chat_log.write("\n")
        chat_log.scroll_end(animate=False)
        
        asyncio.create_task(self._do_execute_shell(shell_command))

    async def _do_execute_shell(self, shell_command: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        try:
            res = await asyncio.to_thread(
                subprocess.run,
                shell_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = (res.stdout + res.stderr).strip()
            if not output:
                output = "(Komut başarılı şekilde çalıştırıldı, çıktı vermedi.)"
                
            code_block = f"```text\n{output}\n```"
            chat_log.write(Markdown(code_block))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            
            prompt_payload = (
                f"Aşağıdaki terminal komutunu ve çıktısını analiz et, gerekiyorsa açıkla veya tavsiyede bulun:\n\n"
                f"**Komut:** `{shell_command}`\n\n"
                f"**Çıktı:**\n{code_block}"
            )
            
            if self.active_chat:
                self.send_message_to_gemini(prompt_payload)
        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **Komut çalıştırma hatası:** `{str(e)}`"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)

    # --- CLIENT-SIDE PROJE OLUŞTURMA & GEÇİŞ (`/project <isim>`) ---
    def action_switch_or_create_project(self, proj_name: str) -> None:
        if not proj_name:
            return
        clean_name = proj_name.strip()
        if clean_name not in self.projects_list:
            self.projects_list.append(clean_name)
            
        self.active_project_name = clean_name
        self.render_project_list()
        self.save_projects_cache()
        self.update_chat_info_bar()
        
        search_val = self.query_one("#search-input", Input).value
        asyncio.create_task(self.render_chat_list(self.all_chats_cache, filter_query=search_val))
        
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Markdown(f"📁 **Aktif Proje Değiştirildi:** `{clean_name}`"))
        chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- SOHBET DOSYASI İÇE AKTARMA (/import) ---
    def action_import_chat(self, filepath_str: str) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not filepath_str:
            chat_log.write(Markdown("⚠️ **Lütfen bir dosya yolu belirtin:** `/import sohbet_dosyasi.md`"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        import_path = Path(filepath_str).expanduser()
        if not import_path.exists():
            chat_log.write(Markdown(f"⚠️ **Dosya bulunamadı:** `{filepath_str}`"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        asyncio.create_task(self._do_import_file(import_path))

    async def _do_import_file(self, import_path: Path) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        try:
            with open(import_path, "r", encoding="utf-8") as f:
                content = f.read()

            sections = re.split(r'### (👤 Sen|🤖 Gemini)\n\n', content)
            imported_turns = []
            for i in range(1, len(sections), 2):
                role_raw = sections[i]
                text = sections[i+1].split('\n\n---\n\n')[0].strip()
                role = "user" if "Sen" in role_raw else "model"
                imported_turns.append((role, text))

            if not imported_turns:
                chat_log.write(Markdown("⚠️ **Dosya içerisinde geçerli sohbet turu bulunamadı.**"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
                return

            selected_model = self.available_models[self.active_model_idx] if self.available_models else None
            self.active_chat = self.client.start_chat(model=selected_model) if self.client else None
            self.active_chat_title = f"İçeri Aktarıldı: {import_path.stem}"
            self.update_chat_info_bar()

            chat_log.clear()
            chat_log.write(Markdown(f"📥 **Sohbet dosyası içeri aktarıldı:** `{import_path.name}` ({len(imported_turns)} mesaj)"))
            chat_log.write("\n---\n")

            history_summary = []
            for role, text in imported_turns:
                if role == "user":
                    chat_log.write(Markdown(f"**Sen:** {text}"))
                    chat_log.write("\n")
                    history_summary.append(f"User: {text}")
                else:
                    self.last_gemini_response = text
                    chat_log.write(Text("Gemini:", style="bold green"))
                    chat_log.write(Markdown(text))
                    chat_log.write("\n---\n")
                    history_summary.append(f"Gemini: {text}")

            chat_log.scroll_end(animate=False)

            if self.active_chat:
                context_prompt = (
                    f"[Sohbet Geçmişi İçe Aktarıldı - Lütfen aşağıdaki sohbet geçmişini dikkate alarak devam et]:\n\n"
                    + "\n\n".join(history_summary[-6:])
                )
                asyncio.create_task(self.active_chat.send_message(context_prompt))

        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **İçeri aktarma hatası:** `{str(e)}`"))
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

    # --- SADECE KOD BLOKLARINI KOPYALAMA (/copycode) ---
    def action_copy_code_blocks(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not self.last_gemini_response:
            chat_log.write(Markdown("⚠️ **Kopyalanacak yanıt bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        code_blocks = re.findall(r"```(?:\w+)?\n(.*?)```", self.last_gemini_response, re.DOTALL)
        if not code_blocks:
            chat_log.write(Markdown("⚠️ **Yanıt içerisinde kod bloğu bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        code_text = "\n\n".join(cb.strip() for cb in code_blocks)
        success = False
        if shutil.which("wl-copy"):
            try:
                p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                p.communicate(input=code_text.encode("utf-8"))
                success = True
            except Exception:
                pass
        elif shutil.which("xclip"):
            try:
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                p.communicate(input=code_text.encode("utf-8"))
                success = True
            except Exception:
                pass

        if success:
            chat_log.write(Markdown(f"📋 **{len(code_blocks)} adet kod bloğu panoya kopyalandı!**"))
            chat_log.write("\n")
        else:
            chat_log.write(Markdown("⚠️ **Panoya kopyalama başarısız (wl-copy / xclip bulunamadı).**"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- SOHBETİ DISA AKTARMA (/export) ---
    def action_export_chat(self, filename: str = "") -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        if not self.active_chat or not self.active_chat.cid:
            chat_log.write(Markdown("⚠️ **Dışa aktarılacak kayıtlı sohbet bulunamadı.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        if not filename:
            now_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            clean_title = "".join(c if c.isalnum() else "_" for c in self.active_chat_title)[:25]
            filename = f"Gemini_Sohbet_{clean_title}_{now_str}.md"

        export_path = Path.cwd() / filename
        asyncio.create_task(self._do_export_file(export_path))

    async def _do_export_file(self, export_path: Path) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        try:
            cid = self.active_chat.cid
            history = await self.client.read_chat(cid, limit=150) if self.client else None
            
            content = f"# 🤖 Gemini TUI Sohbet Raporu\n"
            content += f"- **Başlık:** {self.active_chat_title}\n"
            content += f"- **Model:** {self.get_current_model_display_name()}\n"
            content += f"- **Proje:** {self.active_project_name}\n"
            content += f"- **Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            content += f"- **Sohbet ID:** `{cid}`\n\n"
            content += "---\n\n"
            
            if history and history.turns:
                for turn in reversed(history.turns):
                    role_name = "👤 Sen" if turn.role == "user" else "🤖 Gemini"
                    content += f"### {role_name}\n\n{turn.text}\n\n---\n\n"
                    
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            chat_log.write(Markdown(f"💾 **Sohbet dışa aktarıldı:** `{export_path.name}`"))
            chat_log.write("\n")
        except Exception as e:
            chat_log.write(Markdown(f"⚠️ **Dışa aktarma hatası:** `{str(e)}`"))
            chat_log.write("\n")
        chat_log.scroll_end(animate=False)

    # --- SOHBETİ YENİDEN ADLANDIRMA VE SABİTLEME ---
    def action_pin_chat(self) -> None:
        if not self.active_chat or not self.active_chat.cid:
            return
        
        cid = self.active_chat.cid
        chat_log = self.query_one("#chat-log", RichLog)
        
        for c in self.all_chats_cache:
            if c.get("cid") == cid:
                c["is_pinned"] = not c.get("is_pinned", False)
                state_str = "iğnelendi (📌)" if c["is_pinned"] else "iğnesi kaldırıldı"
                chat_log.write(Markdown(f"📌 **Sohbet {state_str}.**"))
                chat_log.write("\n")
                break
                
        self.save_local_cache(self.all_chats_cache)
        search_val = self.query_one("#search-input", Input).value
        asyncio.create_task(self.render_chat_list(self.all_chats_cache, filter_query=search_val))
        chat_log.scroll_end(animate=False)

    def action_rename_chat(self, new_title: str) -> None:
        if not self.active_chat or not self.active_chat.cid or not new_title:
            return
            
        cid = self.active_chat.cid
        self.active_chat_title = new_title
        self.update_chat_info_bar()
        
        for c in self.all_chats_cache:
            if c.get("cid") == cid:
                c["title"] = new_title
                c["title_renamed"] = True
                break
                
        self.save_local_cache(self.all_chats_cache)
        search_val = self.query_one("#search-input", Input).value
        asyncio.create_task(self.render_chat_list(self.all_chats_cache, filter_query=search_val))
        
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(Markdown(f"✏️ **Sohbet yeniden adlandırıldı:** `{new_title}`"))
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
        msg_input = self.query_one("#message-input", Input)
        msg_input.value = "/file "
        msg_input.focus()

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

    def action_toggle_thinking(self) -> None:
        self.extended_thinking = not self.extended_thinking
        self.update_header_status()

    def action_toggle_research(self) -> None:
        self.deep_research = not self.deep_research
        self.update_header_status()

    def action_show_help(self) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        help_md = (
            "### 💡 KULLANIM VE KOMUT YARDIMI\n\n"
            "- **F1** veya **Alt+N** veya `/new` : Yeni sohbet başlatır.\n"
            "- **F2** veya **Alt+M** veya `/model` : AI Modelleri arasında geçiş yapar.\n"
            "- **F3** veya **Alt+F** veya `/file <yol>` : Görsel (PNG/JPG/WEBP), PDF veya metin dosyası ekler.\n"
            "- **! <komut>** veya `/sh <komut>` : Terminal komutunu çalıştırır ve Gemini'a analiz ettirir.\n"
            "- `/project <isim>` : Yeni proje oluşturur veya var olan projeye geçiş yapar.\n"
            "- **Alt+V** veya `/view [dosya]` : Üretilen görseli mpv ile tam çözünürlükte açar.\n"
            "- **F4** veya **Alt+D** veya `/delete` : Aktif sohbeti hesabınızdan siler.\n"
            "- **Alt+C** veya `/copy` : En son verilen yanıtı panoya kopyalar.\n"
            "- `/copycode` : Yanıt içindeki sadece KOD bloklarını panoya kopyalar.\n"
            "- **F5** veya **Alt+T** veya `/thinking` : Derin Düşünme modunu açar/kapatır.\n"
            "- **F6** veya **Alt+R** veya `/research` : Derin Araştırma modunu açar/kapatır.\n"
            "- **F7** veya **Alt+H** veya `/help` : Yardım menüsünü gösterir.\n"
            "- `/export <dosya>` : Sohbeti Markdown (.md) olarak kaydeder.\n"
            "- `/import <dosya>` : Kaydedilmiş sohbet dosyasını yükler ve bağlamla devam eder.\n"
            "- `/retry` : Son mesajı yeniden yanıtlatır (Yukarı Ok ile çağırabilirsiniz).\n"
            "- `/pin` : Sohbeti iğneler/iğneyi kaldırır (📌).\n"
            "- `/rename <başlık>` : Sohbetin adını değiştirir.\n"
            "- `/clear` : Eklenmiş dosyaları temizler.\n"
            "- `/exit` : Uygulamadan çıkar.\n\n"
            "---\n"
        )
        chat_log.write(Markdown(help_md))
        chat_log.scroll_end(animate=False)

    # --- INPUT VE MESAJ GÖNDERİMİ ---
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "message-input":
            return
            
        text = event.value.strip()
        if not text:
            return

        self.query_one("#message-input", Input).value = ""
        self.query_one("#command-suggestions", ListView).display = False

        if text.startswith("!"):
            sh_cmd = text[1:].strip()
            if sh_cmd:
                self.action_execute_shell(sh_cmd)
                return

        if text.startswith("/sh "):
            sh_cmd = text.split(" ", 1)[1].strip()
            if sh_cmd:
                self.action_execute_shell(sh_cmd)
                return

        if text.startswith("/project "):
            pname = text.split(" ", 1)[1].strip()
            self.action_switch_or_create_project(pname)
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

        if text.startswith("/import "):
            fpath = text.split(" ", 1)[1].strip()
            self.action_import_chat(fpath)
            return

        if text == "/copy":
            self.action_copy_last_response()
            return

        if text == "/copycode":
            self.action_copy_code_blocks()
            return

        if text.startswith("/export") or text.startswith("/save"):
            parts = text.split(" ", 1)
            fname = parts[1].strip() if len(parts) > 1 else ""
            self.action_export_chat(fname)
            return

        if text == "/retry":
            if self.last_user_prompt:
                text = self.last_user_prompt
            else:
                chat_log = self.query_one("#chat-log", RichLog)
                chat_log.write(Markdown("⚠️ **Yeniden gönderilecek mesaj bulunamadı.**"))
                chat_log.write("\n")
                chat_log.scroll_end(animate=False)
                return

        if text == "/pin":
            self.action_pin_chat()
            return

        if text.startswith("/rename "):
            new_t = text.split(" ", 1)[1].strip()
            self.action_rename_chat(new_t)
            return

        if text == "/clear":
            self.attached_files.clear()
            self.update_attachments_bar()
            chat_log = self.query_one("#chat-log", RichLog)
            chat_log.write(Markdown("📎 **Ekli dosyalar temizlendi.**"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)
            return

        if text == "/new":
            self.action_new_chat()
            return

        if text in ["/model", "/models"]:
            if self.available_models:
                self.action_cycle_model()
            return

        if text.startswith("/model "):
            val = text.split(" ", 1)[1].strip()
            if val.isdigit() and 1 <= int(val) <= len(self.available_models):
                self.active_model_idx = int(val) - 1
                new_m = self.available_models[self.active_model_idx]
                if self.active_chat:
                    self.active_chat.model = new_m
                self.update_header_status()
                self.update_chat_info_bar()
                return

        if text == "/delete":
            self.action_delete_chat()
            return

        if text == "/thinking":
            self.action_toggle_thinking()
            return

        if text == "/research":
            self.action_toggle_research()
            return

        if text in ["/help", "/yardim"]:
            self.action_show_help()
            return

        if text in ["/exit", "/quit"]:
            self.exit()
            return

        if not self.active_chat:
            return

        # Normal Mesaj Gönderimi
        self.last_user_prompt = text
        chat_log = self.query_one("#chat-log", RichLog)
        
        file_names_str = ""
        if self.attached_files:
            names = ", ".join(Path(f).name for f in self.attached_files)
            file_names_str = f" `[📎 {names}]`"

        chat_log.write(Markdown(f"**Sen:** {text}{file_names_str}"))
        chat_log.write("\n")
        chat_log.scroll_end(animate=False)

        files_to_send = list(self.attached_files) if self.attached_files else None
        self.attached_files.clear()
        self.update_attachments_bar()

        if self.active_chat and self.active_chat.cid:
            for c in self.all_chats_cache:
                if c.get("cid") == self.active_chat.cid:
                    c["project"] = self.active_project_name
                    break
            self.save_local_cache(self.all_chats_cache)
        
        self.send_message_to_gemini(text, files=files_to_send)

    # ⚡ İMAGEN 3 İKİ YÖNLÜ (SOHBET İÇİ RENDER + İSTEĞE BAĞLI /view VEYA Alt+V KISAYOLU)
    @work(exclusive=True)
    async def send_message_to_gemini(self, message: str, files: Optional[List[str]] = None) -> None:
        chat_log = self.query_one("#chat-log", RichLog)
        
        try:
            response_text = ""
            base_lines = len(chat_log.lines)
            last_chunk_obj = None
            
            async for chunk in self.active_chat.send_message_stream(
                prompt=message,
                files=files,
                extended_thinking=self.extended_thinking,
                deep_research=self.deep_research,
            ):
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

                # ⚡ İKİ YÖNLÜ (SOHBET İÇİ ANSI RENDER + İSTEĞE BAĞLI İKİNCİ YOL KISAYOLU)
                if last_chunk_obj and hasattr(last_chunk_obj, "images") and last_chunk_obj.images:
                    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
                    for img in last_chunk_obj.images:
                        try:
                            saved_file = await img.save(path=str(IMAGES_DIR))
                            self.last_generated_image_path = saved_file
                            
                            # 1. YOL: Sohbet İçerisinde Otomatik Göster (Otomatik Pencere Açılmaz!)
                            chat_log.write(Markdown(f"🖼️ **Görsel Üretildi:** `{saved_file}`  *(🔍 Tam çözünürlük için: **Alt+V** veya `/view`)*"))
                            
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
                        c["project"] = self.active_project_name
                        is_new_chat = False
                        break
                        
            self.save_local_cache(self.all_chats_cache)
            if is_new_chat:
                self.sync_chats_from_server_bg()
            
        except Exception as e:
            chat_log.write(Markdown(f"**[Hata]:** `{str(e)}`"))
            chat_log.write("\n")
            chat_log.scroll_end(animate=False)

if __name__ == "__main__":
    app = NakedGeminiTUI()
    app.run()
