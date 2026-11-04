
import os
import sys
import json
import time
import sqlite3
import threading
import urllib.parse
import subprocess
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

# --- Dependency Verification & Automatic Fallbacks ---
try:
    import requests
except ImportError:
    requests = None

try:
    import customtkinter as ctk
    from customtkinter import CTkFont
except ImportError:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    msg = ("CustomTkinter is required for the modern UI.\n\n"
           "Please install it using:\n"
           "pip install customtkinter requests\n\n"
           "Would you like to attempt automatic installation now?")
    if messagebox.askyesno("Missing Dependency", msg):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter", "requests"])
        import customtkinter as ctk
        from customtkinter import CTkFont
        root.destroy()
    else:
        sys.exit(1)

import tkinter as tk
from tkinter import filedialog, messagebox

# Optional: Document Extractors
try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import docx
except ImportError:
    docx = None

# Optional: Speech Tools
try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    from gtts import gTTS
    import pygame
    pygame.mixer.init()
    AUDIO_AVAILABLE = True
except Exception:
    AUDIO_AVAILABLE = False


# ============================================================================
# DATABASE & STORAGE MANAGEMENT
# ============================================================================
class DatabaseManager:
    """Manages SQLite storage for history, favourites, and persistent settings."""

    def __init__(self, db_filename: str = "translator_data.db"):
        self.db_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), db_filename)
        self._lock = threading.Lock()
        self.init_database()

    def _get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def init_database(self):
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_lang TEXT NOT NULL,
                    target_lang TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    is_favourite INTEGER DEFAULT 0,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_history(self, src_lang: str, tgt_lang: str, src_text: str, trans_text: str) -> int:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (source_lang, target_lang, source_text, translated_text)
                VALUES (?, ?, ?, ?)
            """, (src_lang, tgt_lang, src_text, trans_text))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, search_query: str = "") -> List[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            if search_query.strip():
                q = f"%{search_query.strip()}%"
                cursor.execute("""
                    SELECT id, source_lang, target_lang, source_text, translated_text, is_favourite, timestamp
                    FROM history
                    WHERE source_text LIKE ? OR translated_text LIKE ?
                    ORDER BY id DESC LIMIT 200
                """, (q, q))
            else:
                cursor.execute("""
                    SELECT id, source_lang, target_lang, source_text, translated_text, is_favourite, timestamp
                    FROM history
                    ORDER BY id DESC LIMIT 200
                """)
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "src_lang": r[1], "tgt_lang": r[2],
                    "src_text": r[3], "trans_text": r[4], "fav": bool(r[5]),
                    "timestamp": r[6]
                }
                for r in rows
            ]

    def get_favourites(self) -> List[Dict[str, Any]]:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, source_lang, target_lang, source_text, translated_text, is_favourite, timestamp
                FROM history
                WHERE is_favourite = 1
                ORDER BY id DESC
            """)
            rows = cursor.fetchall()
            return [
                {
                    "id": r[0], "src_lang": r[1], "tgt_lang": r[2],
                    "src_text": r[3], "trans_text": r[4], "fav": True,
                    "timestamp": r[6]
                }
                for r in rows
            ]

    def toggle_favourite(self, item_id: int) -> bool:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT is_favourite FROM history WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                new_state = 0 if row[0] == 1 else 1
                cursor.execute("UPDATE history SET is_favourite = ? WHERE id = ?", (new_state, item_id))
                conn.commit()
                return bool(new_state)
            return False

    def delete_history_item(self, item_id: int):
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
            conn.commit()

    def clear_all_history(self):
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history")
            conn.commit()

    def clear_favourites(self):
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE history SET is_favourite = 0")
            conn.commit()

    def get_setting(self, key: str, default: str = "") -> str:
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def set_setting(self, key: str, value: str):
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            conn.commit()


# ============================================================================
# EXTENSIVE LANGUAGE DEFINITION MAP
# ============================================================================
LANGUAGES: Dict[str, str] = {
    "Auto Detect": "auto",
    "Afrikaans": "af",
    "Albanian": "sq",
    "Amharic": "am",
    "Arabic": "ar",
    "Armenian": "hy",
    "Azerbaijani": "az",
    "Basque": "eu",
    "Belarusian": "be",
    "Bengali": "bn",
    "Bosnian": "bs",
    "Bulgarian": "bg",
    "Burmese (Myanmar)": "my",
    "Catalan": "ca",
    "Cebuano": "ceb",
    "Chichewa": "ny",
    "Chinese (Simplified)": "zh-CN",
    "Chinese (Traditional)": "zh-TW",
    "Corsican": "co",
    "Croatian": "hr",
    "Czech": "cs",
    "Danish": "da",
    "Dutch": "nl",
    "English": "en",
    "Esperanto": "eo",
    "Estonian": "et",
    "Filipino (Tagalog)": "tl",
    "Finnish": "fi",
    "French": "fr",
    "Frisian": "fy",
    "Galician": "gl",
    "Georgian": "ka",
    "German": "de",
    "Greek": "el",
    "Gujarati": "gu",
    "Haitian Creole": "ht",
    "Hausa": "ha",
    "Hawaiian": "haw",
    "Hebrew": "he",
    "Hindi": "hi",
    "Hmong": "hmn",
    "Hungarian": "hu",
    "Icelandic": "is",
    "Igbo": "ig",
    "Indonesian": "id",
    "Irish": "ga",
    "Italian": "it",
    "Japanese": "ja",
    "Javanese": "jv",
    "Kannada": "kn",
    "Kazakh": "kk",
    "Khmer": "km",
    "Kinyarwanda": "rw",
    "Korean": "ko",
    "Kurdish": "ku",
    "Kyrgyz": "ky",
    "Lao": "lo",
    "Latin": "la",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Luxembourgish": "lb",
    "Macedonian": "mk",
    "Malagasy": "mg",
    "Malay": "ms",
    "Malayalam": "ml",
    "Maltese": "mt",
    "Maori": "mi",
    "Marathi": "mr",
    "Mongolian": "mn",
    "Nepali": "ne",
    "Norwegian": "no",
    "Odia (Oriya)": "or",
    "Pashto": "ps",
    "Persian": "fa",
    "Polish": "pl",
    "Portuguese": "pt",
    "Punjabi": "pa",
    "Romanian": "ro",
    "Russian": "ru",
    "Samoan": "sm",
    "Scots Gaelic": "gd",
    "Serbian": "sr",
    "Sesotho": "st",
    "Shona": "sn",
    "Sindhi": "sd",
    "Sinhala": "si",
    "Slovak": "sk",
    "Slovenian": "sl",
    "Somali": "so",
    "Spanish": "es",
    "Sundanese": "su",
    "Swahili": "sw",
    "Swedish": "sv",
    "Tajik": "tg",
    "Tamil": "ta",
    "Tatar": "tt",
    "Telugu": "te",
    "Thai": "th",
    "Turkish": "tr",
    "Turkmen": "tk",
    "Ukrainian": "uk",
    "Urdu": "ur",
    "Uyghur": "ug",
    "Uzbek": "uz",
    "Vietnamese": "vi",
    "Welsh": "cy",
    "Xhosa": "xh",
    "Yiddish": "yi",
    "Yoruba": "yo",
    "Zulu": "zu"
}

CODE_TO_NAME: Dict[str, str] = {code: name for name, code in LANGUAGES.items()}
CODE_TO_NAME["zh"] = "Chinese (Simplified)"
CODE_TO_NAME["zh-cn"] = "Chinese (Simplified)"
CODE_TO_NAME["zh-tw"] = "Chinese (Traditional)"
CODE_TO_NAME["iw"] = "Hebrew"
CODE_TO_NAME["jw"] = "Javanese"


# ============================================================================
# MULTI-PROVIDER TRANSLATION & SPEECH ENGINE
# ============================================================================
class TranslationEngine:
    """Handles neural translation requests, auto-detection, and dictionary entries."""

    HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36")
    }

    @classmethod
    def translate(cls, text: str, src_lang: str = "auto", tgt_lang: str = "en", timeout: int = 15) -> Dict[str, Any]:
        if not text or not text.strip():
            return {
                "translated_text": "",
                "detected_lang": src_lang,
                "alternatives": [],
                "definitions": []
            }

        text = text.strip()
        if requests is not None:
            return cls._translate_requests(text, src_lang, tgt_lang, timeout)
        else:
            return cls._translate_urllib(text, src_lang, tgt_lang, timeout)

    @classmethod
    def _translate_requests(cls, text: str, src_lang: str, tgt_lang: str, timeout: int) -> Dict[str, Any]:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": src_lang,
            "tl": tgt_lang,
            "dt": ["t", "at", "bd", "rm"],
            "q": text
        }
        resp = requests.post(url, data=params, headers=cls.HEADERS, timeout=timeout)
        if resp.status_code != 200:
            resp = requests.get(url, params=params, headers=cls.HEADERS, timeout=timeout)
            resp.raise_for_status()

        data = resp.json()
        return cls._parse_response(data, src_lang)

    @classmethod
    def _translate_urllib(cls, text: str, src_lang: str, tgt_lang: str, timeout: int) -> Dict[str, Any]:
        import urllib.request
        base_url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl={}&tl={}&dt=t&dt=at&dt=bd&dt=rm&q={}"
        encoded_q = urllib.parse.quote(text)
        req_url = base_url.format(src_lang, tgt_lang, encoded_q)
        req = urllib.request.Request(req_url, headers=cls.HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read().decode("utf-8")
            data = json.loads(content)
            return cls._parse_response(data, src_lang)

    @classmethod
    def _parse_response(cls, data: Any, requested_src: str) -> Dict[str, Any]:
        translated_segments = []
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            for part in data[0]:
                if part and len(part) > 0 and part[0]:
                    translated_segments.append(str(part[0]))

        full_translation = "".join(translated_segments)

        detected_lang = requested_src
        try:
            if len(data) > 2 and isinstance(data[2], str):
                detected_lang = data[2]
            elif len(data) > 8 and isinstance(data[8], list) and len(data[8]) > 0:
                detected_lang = data[8][0][0]
        except Exception:
            pass

        alternatives = []
        definitions = []

        try:
            if len(data) > 1 and isinstance(data[1], list):
                for category in data[1]:
                    pos = category[0] if len(category) > 0 else "general"
                    words = category[1] if len(category) > 1 else []
                    definitions.append(f"[{pos}]: {', '.join(words[:5])}")

            if len(data) > 5 and isinstance(data[5], list):
                for alt_group in data[5]:
                    if len(alt_group) > 2 and isinstance(alt_group[2], list):
                        for alt in alt_group[2]:
                            if isinstance(alt, list) and len(alt) > 0 and alt[0]:
                                if alt[0] not in alternatives and alt[0] != full_translation:
                                    alternatives.append(alt[0])
        except Exception:
            pass

        return {
            "translated_text": full_translation,
            "detected_lang": detected_lang,
            "alternatives": alternatives[:6],
            "definitions": definitions
        }


# ============================================================================
# DOCUMENT PROCESSING UTILITIES (TXT, DOCX, PDF)
# ============================================================================
class DocumentProcessor:
    """Extracts raw text from TXT, DOCX, and PDF formats."""

    @staticmethod
    def extract_text(file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError("The selected file was not found.")

        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".txt":
            for enc in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            raise ValueError("Unable to decode text file. Ensure it is encoded in UTF-8 or ANSI.")

        elif ext == ".pdf":
            if pypdf is None:
                raise ImportError("pypdf is not installed. Please run: pip install pypdf")
            reader = pypdf.PdfReader(file_path)
            extracted = []
            for i, page in enumerate(reader.pages):
                txt = page.extract_text()
                if txt:
                    extracted.append(txt)
            if not extracted:
                raise ValueError("No readable text found in this PDF (it might be a scanned image).")
            return "\n\n".join(extracted)

        elif ext == ".docx":
            if docx is not None:
                doc = docx.Document(file_path)
                return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            else:
                import zipfile
                import xml.etree.ElementTree as ET
                with zipfile.ZipFile(file_path, "r") as z:
                    xml_content = z.read("word/document.xml")
                    tree = ET.fromstring(xml_content)
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    paragraphs = []
                    for p in tree.iter(f"{{{ns['w']}}}p"):
                        texts = [node.text for node in p.iter(f"{{{ns['w']}}}t") if node.text]
                        if texts:
                            paragraphs.append("".join(texts))
                    return "\n".join(paragraphs)

        else:
            raise ValueError(f"Unsupported file format: {ext}. Only .txt, .pdf, and .docx are supported.")


# ============================================================================
# AUDIO / VOICE CONTROLLER (TTS & STT)
# ============================================================================
class VoiceController:
    """Handles Text-to-Speech and Speech-to-Text."""

    @staticmethod
    def speak(text: str, lang_code: str):
        def _run():
            if not text.strip():
                return
            clean_lang = lang_code.split("-")[0].lower() if lang_code != "auto" else "en"

            # 1. gTTS + pygame
            if AUDIO_AVAILABLE:
                try:
                    import tempfile
                    tts = gTTS(text=text[:1000], lang=clean_lang, slow=False)
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                        temp_filename = fp.name
                    tts.save(temp_filename)
                    pygame.mixer.music.load(temp_filename)
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                    pygame.mixer.music.unload()
                    try:
                        os.remove(temp_filename)
                    except Exception:
                        pass
                    return
                except Exception:
                    pass

            # 2. Windows SAPI fallback
            if sys.platform.startswith("win"):
                try:
                    escaped_text = text[:500].replace('"', '""').replace("'", "''")
                    ps_cmd = (
                        f"Add-Type -AssemblyName System.Speech; "
                        f"$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$synth.Speak('{escaped_text}');"
                    )
                    subprocess.run(["powershell", "-Command", ps_cmd], creationflags=0x08000000)
                    return
                except Exception:
                    pass

            # 3. macOS say fallback
            if sys.platform == "darwin":
                try:
                    subprocess.run(["say", text[:500]])
                    return
                except Exception:
                    pass

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def listen_and_recognize(lang_code: str = "en") -> str:
        if sr is None:
            raise ImportError("SpeechRecognition is not installed.\nInstall using: pip install SpeechRecognition")

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True

        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.6)
            audio = recognizer.listen(source, timeout=6, phrase_time_limit=15)

        return recognizer.recognize_google(audio, language=lang_code)


# ============================================================================
# SEARCHABLE LANGUAGE SELECTION DIALOG
# ============================================================================
class SearchableLanguageDialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, current_lang: str, on_select_callback, allow_auto: bool = True):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x520")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_select_callback = on_select_callback
        self.allow_auto = allow_auto
        self.current_lang = current_lang

        self.full_list = sorted([k for k in LANGUAGES.keys() if k != "Auto Detect"])
        if self.allow_auto:
            self.full_list = ["Auto Detect"] + self.full_list

        self._build_ui()
        self.search_entry.focus_set()

    def _build_ui(self):
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=16, pady=(16, 8))

        lbl = ctk.CTkLabel(top_frame, text="Select Language", font=CTkFont(size=16, weight="bold"))
        lbl.pack(anchor="w", pady=(0, 6))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)

        self.search_entry = ctk.CTkEntry(
            top_frame,
            textvariable=self.search_var,
            placeholder_text="🔍 Type to filter languages...",
            height=36,
            corner_radius=8
        )
        self.search_entry.pack(fill="x")

        self.scroll_frame = ctk.CTkScrollableFrame(self, corner_radius=8)
        self.scroll_frame.pack(fill="both", expand=True, padx=16, pady=8)

        self._populate_list(self.full_list)

    def _populate_list(self, items: List[str]):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        if not items:
            lbl = ctk.CTkLabel(self.scroll_frame, text="No matching language found", text_color="gray")
            lbl.pack(pady=20)
            return

        for name in items:
            is_active = (name == self.current_lang)
            btn = ctk.CTkButton(
                self.scroll_frame,
                text=name,
                anchor="w",
                height=34,
                fg_color="#2b5c8f" if is_active else "transparent",
                hover_color="#1f4b7a" if is_active else ("#e1e5eb", "#2a2d32"),
                text_color=None,
                font=CTkFont(size=13, weight="bold" if is_active else "normal"),
                command=lambda n=name: self._choose(n)
            )
            btn.pack(fill="x", pady=1)

    def _on_search_change(self, *args):
        query = self.search_var.get().strip().lower()
        if not query:
            self._populate_list(self.full_list)
        else:
            filtered = [name for name in self.full_list if query in name.lower()]
            self._populate_list(filtered)

    def _choose(self, name: str):
        self.on_select_callback(name)
        self.destroy()


# ============================================================================
# MAIN APPLICATION CONTROLLER & INTERFACE
# ============================================================================
class TranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Translator")
        self.geometry("1100x720")
        self.minsize(960, 640)

        # Database
        self.db = DatabaseManager()

        # Settings
        saved_theme = self.db.get_setting("theme", "Dark")
        ctk.set_appearance_mode(saved_theme)
        ctk.set_default_color_theme("blue")

        self.default_src_lang = self.db.get_setting("default_src_lang", "Auto Detect")
        self.default_tgt_lang = self.db.get_setting("default_tgt_lang", "English")

        self.source_lang_name = self.default_src_lang
        self.target_lang_name = self.default_tgt_lang

        self.is_translating = False
        self.current_history_id: Optional[int] = None

        self._setup_layout()
        self._setup_keyboard_shortcuts()
        self.select_nav_view("translator")

    def _setup_layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Left Sidebar Navigation
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(7, weight=1)

        # App Brand Header
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="⚡ TRANSLATOR",
            font=CTkFont(size=18, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(24, 20), sticky="w")

        self.nav_buttons = {}
        views = [
            ("translator", "🌐  Translator"),
            ("history", "🕒  History"),
            ("favourites", "⭐  Favourites"),
            ("documents", "📄  Documents"),
            ("settings", "⚙️  Settings"),
            ("about", "ℹ️  About")
        ]

        for idx, (view_id, label_text) in enumerate(views, start=1):
            btn = ctk.CTkButton(
                self.sidebar_frame,
                text=label_text,
                anchor="w",
                height=40,
                font=CTkFont(size=14, weight="normal"),
                fg_color="transparent",
                hover_color=("gray85", "#2a2d32"),
                command=lambda v=view_id: self.select_nav_view(v)
            )
            btn.grid(row=idx, column=0, padx=12, pady=4, sticky="ew")
            self.nav_buttons[view_id] = btn

        # Theme Switcher
        self.theme_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", font=CTkFont(size=12))
        self.theme_label.grid(row=8, column=0, padx=20, pady=(10, 0), sticky="w")

        self.theme_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Dark", "Light", "System"],
            command=self._change_theme,
            height=30
        )
        self.theme_menu.set(ctk.get_appearance_mode())
        self.theme_menu.grid(row=9, column=0, padx=16, pady=(4, 20), sticky="ew")

        # Right Main Workspace
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.views = {
            "translator": self._build_translator_view(),
            "history": self._build_history_view(),
            "favourites": self._build_favourites_view(),
            "documents": self._build_documents_view(),
            "settings": self._build_settings_view(),
            "about": self._build_about_view()
        }

    def select_nav_view(self, view_name: str):
        for name, btn in self.nav_buttons.items():
            if name == view_name:
                btn.configure(fg_color="#1f538d", text_color="white", font=CTkFont(size=14, weight="bold"))
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"), font=CTkFont(size=14, weight="normal"))

        for frame in self.views.values():
            frame.grid_forget()

        self.views[view_name].grid(row=0, column=0, sticky="nsew")

        if view_name == "history":
            self._reload_history_list()
        elif view_name == "favourites":
            self._reload_favourites_list()

    def _change_theme(self, new_theme: str):
        ctk.set_appearance_mode(new_theme)
        self.db.set_setting("theme", new_theme)

    def _setup_keyboard_shortcuts(self):
        self.bind("<Control-Return>", lambda e: self.perform_translation())
        self.bind("<Control-Shift-L>", lambda e: self._clear_text_boxes())

    # ------------------------------------------------------------------------
    # VIEW: TRANSLATOR
    # ------------------------------------------------------------------------
    def _build_translator_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_rowconfigure(2, weight=0)
        view.grid_columnconfigure(0, weight=1)
        view.grid_columnconfigure(1, weight=1)

        # Top Selectors
        controls_frame = ctk.CTkFrame(view, corner_radius=10)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        controls_frame.grid_columnconfigure(0, weight=1)
        controls_frame.grid_columnconfigure(2, weight=1)

        self.src_lang_btn = ctk.CTkButton(
            controls_frame,
            text=f"From: {self.source_lang_name}",
            font=CTkFont(size=14, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=("gray80", "#2a2d32"),
            hover_color=("gray70", "#3a3d44"),
            text_color=("black", "white"),
            command=self._open_source_lang_picker
        )
        self.src_lang_btn.grid(row=0, column=0, padx=12, pady=10, sticky="ew")

        self.swap_btn = ctk.CTkButton(
            controls_frame,
            text="⇄",
            width=46,
            height=38,
            font=CTkFont(size=20, weight="bold"),
            corner_radius=8,
            command=self._swap_languages
        )
        self.swap_btn.grid(row=0, column=1, padx=6, pady=10)

        self.tgt_lang_btn = ctk.CTkButton(
            controls_frame,
            text=f"To: {self.target_lang_name}",
            font=CTkFont(size=14, weight="bold"),
            height=38,
            corner_radius=8,
            fg_color=("gray80", "#2a2d32"),
            hover_color=("gray70", "#3a3d44"),
            text_color=("black", "white"),
            command=self._open_target_lang_picker
        )
        self.tgt_lang_btn.grid(row=0, column=2, padx=12, pady=10, sticky="ew")

        # Input Card
        self.input_card = ctk.CTkFrame(view, corner_radius=10)
        self.input_card.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.input_card.grid_rowconfigure(1, weight=1)
        self.input_card.grid_columnconfigure(0, weight=1)

        in_header = ctk.CTkFrame(self.input_card, fg_color="transparent")
        in_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.detected_label = ctk.CTkLabel(in_header, text="Original Text", font=CTkFont(size=13, weight="bold"))
        self.detected_label.pack(side="left")

        self.char_count_label = ctk.CTkLabel(in_header, text="0 chars", font=CTkFont(size=12), text_color="gray")
        self.char_count_label.pack(side="right")

        self.input_text = ctk.CTkTextbox(self.input_card, font=CTkFont(size=15), wrap="word", corner_radius=8)
        self.input_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        self.input_text.bind("<KeyRelease>", self._on_input_text_change)

        in_toolbar = ctk.CTkFrame(self.input_card, fg_color="transparent")
        in_toolbar.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))

        self.mic_btn = ctk.CTkButton(
            in_toolbar,
            text="🎙️ Listen",
            width=90,
            height=32,
            corner_radius=6,
            command=self._listen_microphone
        )
        self.mic_btn.pack(side="left", padx=(0, 6))

        self.in_speak_btn = ctk.CTkButton(
            in_toolbar,
            text="🔊 Read",
            width=80,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#3a3d42"),
            text_color=("black", "white"),
            command=lambda: self._speak_text(self.input_text.get("1.0", "end-1c"), self.source_lang_name)
        )
        self.in_speak_btn.pack(side="left", padx=4)

        self.clear_btn = ctk.CTkButton(
            in_toolbar,
            text="🗑️ Clear",
            width=76,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#3a3d42"),
            text_color=("black", "white"),
            command=self._clear_text_boxes
        )
        self.clear_btn.pack(side="right")

        self.in_copy_btn = ctk.CTkButton(
            in_toolbar,
            text="📋 Copy",
            width=76,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#3a3d42"),
            text_color=("black", "white"),
            command=lambda: self._copy_to_clipboard(self.input_text.get("1.0", "end-1c"), "Original text copied!")
        )
        self.in_copy_btn.pack(side="right", padx=6)

        # Output Card
        self.output_card = ctk.CTkFrame(view, corner_radius=10)
        self.output_card.grid(row=1, column=1, sticky="nsew", padx=(6, 0))
        self.output_card.grid_rowconfigure(1, weight=1)
        self.output_card.grid_columnconfigure(0, weight=1)

        out_header = ctk.CTkFrame(self.output_card, fg_color="transparent")
        out_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        self.out_title_label = ctk.CTkLabel(out_header, text="Translation Result", font=CTkFont(size=13, weight="bold"))
        self.out_title_label.pack(side="left")

        self.status_label = ctk.CTkLabel(out_header, text="Ready", font=CTkFont(size=12), text_color="#1f8b4c")
        self.status_label.pack(side="right")

        self.output_text = ctk.CTkTextbox(self.output_card, font=CTkFont(size=15), wrap="word", corner_radius=8)
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        out_toolbar = ctk.CTkFrame(self.output_card, fg_color="transparent")
        out_toolbar.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))

        self.out_speak_btn = ctk.CTkButton(
            out_toolbar,
            text="🔊 Read Aloud",
            width=100,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#3a3d42"),
            text_color=("black", "white"),
            command=lambda: self._speak_text(self.output_text.get("1.0", "end-1c"), self.target_lang_name)
        )
        self.out_speak_btn.pack(side="left", padx=(0, 6))

        self.fav_btn = ctk.CTkButton(
            out_toolbar,
            text="⭐ Save Favourite",
            width=120,
            height=32,
            corner_radius=6,
            fg_color=("gray75", "#3a3d42"),
            text_color=("black", "white"),
            command=self._favourite_current_translation
        )
        self.fav_btn.pack(side="left", padx=4)

        self.out_copy_btn = ctk.CTkButton(
            out_toolbar,
            text="📋 Copy Result",
            width=100,
            height=32,
            corner_radius=6,
            fg_color="#1f538d",
            hover_color="#184271",
            command=lambda: self._copy_to_clipboard(self.output_text.get("1.0", "end-1c"), "Translation copied!")
        )
        self.out_copy_btn.pack(side="right")

        # Translate Action Bar
        bottom_bar = ctk.CTkFrame(view, corner_radius=10)
        bottom_bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        self.translate_btn = ctk.CTkButton(
            bottom_bar,
            text="⚡ TRANSLATE NOW  (Ctrl + Enter)",
            height=46,
            font=CTkFont(size=15, weight="bold"),
            corner_radius=8,
            fg_color="#1f538d",
            hover_color="#164373",
            command=self.perform_translation
        )
        self.translate_btn.pack(fill="x", padx=12, pady=10)

        # Dictionary & Alternatives Accordion
        self.alternatives_box = ctk.CTkFrame(view, corner_radius=8, fg_color=("gray90", "#23262a"))
        self.alternatives_box.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.alternatives_label = ctk.CTkLabel(
            self.alternatives_box,
            text="Alternative translations & dictionary entries will appear here.",
            font=CTkFont(size=12),
            text_color="gray",
            anchor="w",
            justify="left"
        )
        self.alternatives_label.pack(fill="x", padx=12, pady=8)

        return view

    def _open_source_lang_picker(self):
        SearchableLanguageDialog(
            parent=self,
            title="Choose Source Language",
            current_lang=self.source_lang_name,
            on_select_callback=self._set_source_language,
            allow_auto=True
        )

    def _open_target_lang_picker(self):
        SearchableLanguageDialog(
            parent=self,
            title="Choose Target Language",
            current_lang=self.target_lang_name,
            on_select_callback=self._set_target_language,
            allow_auto=False
        )

    def _set_source_language(self, name: str):
        self.source_lang_name = name
        self.src_lang_btn.configure(text=f"From: {name}")

    def _set_target_language(self, name: str):
        self.target_lang_name = name
        self.tgt_lang_btn.configure(text=f"To: {name}")

    def _swap_languages(self):
        if self.source_lang_name == "Auto Detect":
            detected = self.detected_label.cget("text").replace("Original Text (Detected: ", "").replace(")", "")
            if detected in LANGUAGES and detected != "Original Text":
                self.source_lang_name = self.target_lang_name
                self.target_lang_name = detected
            else:
                messagebox.showinfo("Swap Notice", "Cannot swap when source language is still set to Auto Detect without detection.")
                return
        else:
            self.source_lang_name, self.target_lang_name = self.target_lang_name, self.source_lang_name

        self.src_lang_btn.configure(text=f"From: {self.source_lang_name}")
        self.tgt_lang_btn.configure(text=f"To: {self.target_lang_name}")

        curr_in = self.input_text.get("1.0", "end-1c")
        curr_out = self.output_text.get("1.0", "end-1c")
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", curr_out)
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", curr_in)
        self._on_input_text_change()

    def _on_input_text_change(self, event=None):
        text = self.input_text.get("1.0", "end-1c")
        self.char_count_label.configure(text=f"{len(text)} chars")

    def _clear_text_boxes(self):
        self.input_text.delete("1.0", "end")
        self.output_text.delete("1.0", "end")
        self.char_count_label.configure(text="0 chars")
        self.status_label.configure(text="Cleared", text_color="gray")
        self.detected_label.configure(text="Original Text")
        self.alternatives_label.configure(text="Alternative translations & dictionary entries will appear here.")
        self.current_history_id = None

    def perform_translation(self):
        if self.is_translating:
            return

        text = self.input_text.get("1.0", "end-1c").strip()
        if not text:
            self.status_label.configure(text="Empty input", text_color="#d97706")
            return

        src_code = LANGUAGES.get(self.source_lang_name, "auto")
        tgt_code = LANGUAGES.get(self.target_lang_name, "en")

        if src_code == tgt_code and src_code != "auto":
            messagebox.showinfo("Identical Languages", "Source and target languages are identical.")
            return

        self.is_translating = True
        self.translate_btn.configure(text="⏳ Translating... please wait", state="disabled")
        self.status_label.configure(text="Translating...", text_color="#2563eb")

        def _worker():
            try:
                res = TranslationEngine.translate(text, src_lang=src_code, tgt_lang=tgt_code)
                self.after(0, lambda: self._handle_translation_success(res, text, src_code, tgt_code))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._handle_translation_error(err_msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_translation_success(self, res: Dict[str, Any], raw_text: str, src_code: str, tgt_code: str):
        self.is_translating = False
        self.translate_btn.configure(text="⚡ TRANSLATE NOW  (Ctrl + Enter)", state="normal")
        self.status_label.configure(text="✓ Done", text_color="#1f8b4c")

        trans_text = res.get("translated_text", "")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", trans_text)

        detected_code = res.get("detected_lang", src_code)
        detected_full = CODE_TO_NAME.get(detected_code.lower(), detected_code.upper())
        if self.source_lang_name == "Auto Detect":
            self.detected_label.configure(text=f"Original Text (Detected: {detected_full})")

        self.current_history_id = self.db.add_history(
            src_lang=detected_full if self.source_lang_name == "Auto Detect" else self.source_lang_name,
            tgt_lang=self.target_lang_name,
            src_text=raw_text,
            trans_text=trans_text
        )

        alts = res.get("alternatives", [])
        defs = res.get("definitions", [])
        info_lines = []
        if alts:
            info_lines.append(f"Alternatives: {', '.join(alts)}")
        if defs:
            info_lines.append(f"Meanings: {' | '.join(defs)}")

        if info_lines:
            self.alternatives_label.configure(text="\n".join(info_lines))
        else:
            self.alternatives_label.configure(text="No additional synonyms or definitions for this query.")

    def _handle_translation_error(self, error_message: str):
        self.is_translating = False
        self.translate_btn.configure(text="⚡ TRANSLATE NOW  (Ctrl + Enter)", state="normal")
        self.status_label.configure(text="Failed", text_color="#dc2626")

        friendly_msg = "Could not complete translation."
        if "Failed to establish a new connection" in error_message or "timed out" in error_message:
            friendly_msg = "Network connection timeout. Please check your internet connection."
        messagebox.showerror("Translation Error", f"{friendly_msg}\n\nTechnical details:\n{error_message}")

    def _speak_text(self, text: str, lang_name: str):
        if not text.strip():
            return
        code = LANGUAGES.get(lang_name, "en")
        VoiceController.speak(text, code)

    def _listen_microphone(self):
        if sr is None:
            messagebox.showwarning(
                "Speech Recognition Not Installed",
                "Speech recognition library is missing.\nPlease install it with:\npip install SpeechRecognition"
            )
            return

        self.mic_btn.configure(text="🔴 Listening...", fg_color="#b91c1c")
        src_code = LANGUAGES.get(self.source_lang_name, "en")
        if src_code == "auto":
            src_code = "en"

        def _mic_worker():
            try:
                spoken_text = VoiceController.listen_and_recognize(lang_code=src_code)
                self.after(0, lambda: self._on_mic_success(spoken_text))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_mic_error(err))

        threading.Thread(target=_mic_worker, daemon=True).start()

    def _on_mic_success(self, text: str):
        self.mic_btn.configure(text="🎙️ Listen", fg_color="#1f538d")
        if text:
            curr = self.input_text.get("1.0", "end-1c").strip()
            new_val = f"{curr} {text}".strip() if curr else text
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", new_val)
            self._on_input_text_change()
            self.perform_translation()

    def _on_mic_error(self, err: str):
        self.mic_btn.configure(text="🎙️ Listen", fg_color="#1f538d")
        messagebox.showerror("Microphone Notice", f"Speech recognition error:\n{err}\n(Check microphone input settings).")

    def _copy_to_clipboard(self, text: str, feedback: str):
        if not text.strip():
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_label.configure(text=f"✓ {feedback}", text_color="#1f8b4c")

    def _favourite_current_translation(self):
        if self.current_history_id:
            is_fav = self.db.toggle_favourite(self.current_history_id)
            if is_fav:
                self.fav_btn.configure(text="★ Favourited", fg_color="#d97706")
                self.status_label.configure(text="Added to Favourites", text_color="#d97706")
            else:
                self.fav_btn.configure(text="⭐ Save Favourite", fg_color=("gray75", "#3a3d42"))
        else:
            text = self.input_text.get("1.0", "end-1c").strip()
            trans = self.output_text.get("1.0", "end-1c").strip()
            if text and trans:
                hid = self.db.add_history(self.source_lang_name, self.target_lang_name, text, trans)
                self.db.toggle_favourite(hid)
                self.current_history_id = hid
                self.fav_btn.configure(text="★ Favourited", fg_color="#d97706")

    # ------------------------------------------------------------------------
    # VIEW: HISTORY
    # ------------------------------------------------------------------------
    def _build_history_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(view, corner_radius=10)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        lbl = ctk.CTkLabel(top_bar, text="Translation History", font=CTkFont(size=18, weight="bold"))
        lbl.pack(side="left", padx=16, pady=12)

        self.hist_search_var = tk.StringVar()
        self.hist_search_var.trace_add("write", lambda *a: self._reload_history_list())
        search_box = ctk.CTkEntry(
            top_bar,
            textvariable=self.hist_search_var,
            placeholder_text="🔍 Filter history...",
            width=240,
            height=32
        )
        search_box.pack(side="left", padx=10)

        clear_btn = ctk.CTkButton(
            top_bar,
            text="Clear All History",
            fg_color="#b91c1c",
            hover_color="#991b1b",
            height=32,
            command=self._clear_all_history
        )
        clear_btn.pack(side="right", padx=16)

        self.hist_scroll = ctk.CTkScrollableFrame(view, corner_radius=10)
        self.hist_scroll.grid(row=1, column=0, sticky="nsew")

        return view

    def _reload_history_list(self):
        for w in self.hist_scroll.winfo_children():
            w.destroy()

        query = self.hist_search_var.get()
        items = self.db.get_history(query)

        if not items:
            lbl = ctk.CTkLabel(self.hist_scroll, text="No translation records found.", text_color="gray")
            lbl.pack(pady=40)
            return

        for item in items:
            self._render_record_card(self.hist_scroll, item, is_favourite_tab=False)

    def _render_record_card(self, parent, item: Dict[str, Any], is_favourite_tab: bool):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color=("gray90", "#24272c"))
        card.pack(fill="x", pady=5, padx=6)
        card.grid_columnconfigure(1, weight=1)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(8, 2))

        lang_badge = ctk.CTkLabel(
            header,
            text=f"{item['src_lang']} → {item['tgt_lang']}",
            font=CTkFont(size=12, weight="bold"),
            text_color="#3b82f6"
        )
        lang_badge.pack(side="left")

        ts_label = ctk.CTkLabel(header, text=str(item['timestamp']), font=CTkFont(size=11), text_color="gray")
        ts_label.pack(side="right")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=12, pady=4)

        src_lbl = ctk.CTkLabel(body, text=f"“{item['src_text']}”", anchor="w", justify="left", wraplength=700)
        src_lbl.pack(fill="x")

        trans_lbl = ctk.CTkLabel(
            body,
            text=f"➔ {item['trans_text']}",
            anchor="w",
            justify="left",
            wraplength=700,
            font=CTkFont(size=13, weight="bold")
        )
        trans_lbl.pack(fill="x", pady=(2, 0))

        footer = ctk.CTkFrame(card, fg_color="transparent")
        footer.pack(fill="x", padx=12, pady=(4, 8))

        fav_symbol = "★ Favourited" if item['fav'] else "☆ Favourite"
        fav_col = "#d97706" if item['fav'] else ("gray75", "#3a3d42")

        fav_b = ctk.CTkButton(
            footer,
            text=fav_symbol,
            width=90,
            height=26,
            font=CTkFont(size=11),
            fg_color=fav_col,
            command=lambda i=item['id']: self._toggle_item_fav(i, is_favourite_tab)
        )
        fav_b.pack(side="left", padx=(0, 6))

        load_b = ctk.CTkButton(
            footer,
            text="Load to Translator",
            width=120,
            height=26,
            font=CTkFont(size=11),
            command=lambda it=item: self._load_record_to_translator(it)
        )
        load_b.pack(side="left", padx=4)

        del_b = ctk.CTkButton(
            footer,
            text="Delete",
            width=70,
            height=26,
            font=CTkFont(size=11),
            fg_color="#b91c1c",
            hover_color="#991b1b",
            command=lambda i=item['id']: self._delete_history_item(i, is_favourite_tab)
        )
        del_b.pack(side="right")

    def _toggle_item_fav(self, item_id: int, is_favourite_tab: bool):
        self.db.toggle_favourite(item_id)
        if is_favourite_tab:
            self._reload_favourites_list()
        else:
            self._reload_history_list()

    def _load_record_to_translator(self, item: Dict[str, Any]):
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", item['src_text'])

        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", item['trans_text'])

        if item['src_lang'] in LANGUAGES:
            self._set_source_language(item['src_lang'])
        if item['tgt_lang'] in LANGUAGES:
            self._set_target_language(item['tgt_lang'])

        self._on_input_text_change()
        self.select_nav_view("translator")

    def _delete_history_item(self, item_id: int, is_favourite_tab: bool):
        self.db.delete_history_item(item_id)
        if is_favourite_tab:
            self._reload_favourites_list()
        else:
            self._reload_history_list()

    def _clear_all_history(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to delete the complete translation history?"):
            self.db.clear_all_history()
            self._reload_history_list()

    # ------------------------------------------------------------------------
    # VIEW: FAVOURITES
    # ------------------------------------------------------------------------
    def _build_favourites_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(1, weight=1)
        view.grid_columnconfigure(0, weight=1)

        top_bar = ctk.CTkFrame(view, corner_radius=10)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        lbl = ctk.CTkLabel(top_bar, text="Saved Favourites", font=CTkFont(size=18, weight="bold"))
        lbl.pack(side="left", padx=16, pady=12)

        clear_favs = ctk.CTkButton(
            top_bar,
            text="Clear All Favourites",
            fg_color="#b91c1c",
            hover_color="#991b1b",
            height=32,
            command=self._clear_all_favourites
        )
        clear_favs.pack(side="right", padx=16)

        self.favs_scroll = ctk.CTkScrollableFrame(view, corner_radius=10)
        self.favs_scroll.grid(row=1, column=0, sticky="nsew")

        return view

    def _reload_favourites_list(self):
        for w in self.favs_scroll.winfo_children():
            w.destroy()

        items = self.db.get_favourites()
        if not items:
            lbl = ctk.CTkLabel(self.favs_scroll, text="No favourited translations yet. Click ⭐ to save translations here.", text_color="gray")
            lbl.pack(pady=40)
            return

        for item in items:
            self._render_record_card(self.favs_scroll, item, is_favourite_tab=True)

    def _clear_all_favourites(self):
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to remove all translations from favourites?"):
            self.db.clear_favourites()
            self._reload_favourites_list()

    # ------------------------------------------------------------------------
    # VIEW: DOCUMENTS
    # ------------------------------------------------------------------------
    def _build_documents_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_rowconfigure(2, weight=1)
        view.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(view, corner_radius=10)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        lbl = ctk.CTkLabel(header, text="Document Translation", font=CTkFont(size=18, weight="bold"))
        lbl.pack(side="left", padx=16, pady=12)

        sub = ctk.CTkLabel(header, text="Extract and translate files (.txt, .docx, .pdf)", text_color="gray")
        sub.pack(side="left", padx=6)

        picker_card = ctk.CTkFrame(view, corner_radius=10)
        picker_card.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        self.selected_file_label = ctk.CTkLabel(picker_card, text="No document chosen yet", font=CTkFont(size=13))
        self.selected_file_label.pack(side="left", padx=16, pady=12)

        browse_btn = ctk.CTkButton(
            picker_card,
            text="📁 Browse File",
            height=34,
            command=self._browse_document
        )
        browse_btn.pack(side="right", padx=12, pady=12)

        preview_card = ctk.CTkFrame(view, corner_radius=10)
        preview_card.grid(row=2, column=0, sticky="nsew")
        preview_card.grid_rowconfigure(1, weight=1)
        preview_card.grid_columnconfigure(0, weight=1)

        p_top = ctk.CTkFrame(preview_card, fg_color="transparent")
        p_top.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        p_lbl = ctk.CTkLabel(p_top, text="Extracted & Translated Preview", font=CTkFont(size=13, weight="bold"))
        p_lbl.pack(side="left")

        self.doc_status_lbl = ctk.CTkLabel(p_top, text="Ready", text_color="gray")
        self.doc_status_lbl.pack(side="right")

        self.doc_textbox = ctk.CTkTextbox(preview_card, font=CTkFont(size=14), wrap="word")
        self.doc_textbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)

        p_bot = ctk.CTkFrame(preview_card, fg_color="transparent")
        p_bot.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 10))

        self.doc_translate_btn = ctk.CTkButton(
            p_bot,
            text="⚡ Translate Extracted Document",
            height=36,
            fg_color="#1f538d",
            command=self._translate_document_text
        )
        self.doc_translate_btn.pack(side="left")

        save_btn = ctk.CTkButton(
            p_bot,
            text="💾 Save Translated Document (.txt)",
            height=36,
            command=self._save_translated_document
        )
        save_btn.pack(side="right")

        return view

    def _browse_document(self):
        f = filedialog.askopenfilename(
            title="Select a Document to Translate",
            filetypes=[
                ("All Supported Files", "*.txt;*.docx;*.pdf"),
                ("Text Files (*.txt)", "*.txt"),
                ("Word Documents (*.docx)", "*.docx"),
                ("PDF Documents (*.pdf)", "*.pdf")
            ]
        )
        if not f:
            return

        self.selected_file_label.configure(text=os.path.basename(f))
        self.doc_status_lbl.configure(text="Extracting text...", text_color="#2563eb")

        def _worker():
            try:
                extracted = DocumentProcessor.extract_text(f)
                self.after(0, lambda: self._on_doc_extract_success(extracted))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_doc_extract_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_doc_extract_success(self, text: str):
        self.doc_status_lbl.configure(text="Extracted successfully", text_color="#1f8b4c")
        self.doc_textbox.delete("1.0", "end")
        self.doc_textbox.insert("1.0", text)

    def _on_doc_extract_error(self, err: str):
        self.doc_status_lbl.configure(text="Extraction failed", text_color="#dc2626")
        messagebox.showerror("Document Read Error", f"Unable to extract text:\n{err}")

    def _translate_document_text(self):
        text = self.doc_textbox.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Empty Content", "Please load a document with text first.")
            return

        self.doc_status_lbl.configure(text="Translating document...", text_color="#2563eb")
        self.doc_translate_btn.configure(state="disabled")

        tgt_code = LANGUAGES.get(self.target_lang_name, "en")

        def _worker():
            try:
                paragraphs = text.split("\n")
                translated_paragraphs = []
                chunk = []
                chunk_len = 0

                for p in paragraphs:
                    chunk.append(p)
                    chunk_len += len(p)
                    if chunk_len > 1200:
                        batch = "\n".join(chunk)
                        res = TranslationEngine.translate(batch, src_lang="auto", tgt_lang=tgt_code)
                        translated_paragraphs.append(res.get("translated_text", ""))
                        chunk = []
                        chunk_len = 0
                        time.sleep(0.1)

                if chunk:
                    batch = "\n".join(chunk)
                    res = TranslationEngine.translate(batch, src_lang="auto", tgt_lang=tgt_code)
                    translated_paragraphs.append(res.get("translated_text", ""))

                final_text = "\n".join(translated_paragraphs)
                self.after(0, lambda: self._on_doc_trans_success(final_text))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._on_doc_trans_error(err))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_doc_trans_success(self, result: str):
        self.doc_translate_btn.configure(state="normal")
        self.doc_status_lbl.configure(text="Translation finished", text_color="#1f8b4c")
        self.doc_textbox.delete("1.0", "end")
        self.doc_textbox.insert("1.0", result)

    def _on_doc_trans_error(self, err: str):
        self.doc_translate_btn.configure(state="normal")
        self.doc_status_lbl.configure(text="Translation failed", text_color="#dc2626")
        messagebox.showerror("Document Translation Error", f"Could not translate document:\n{err}")

    def _save_translated_document(self):
        text = self.doc_textbox.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("Save Notice", "No text to save.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("All Files", "*.*")],
            title="Save Translated Document"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            messagebox.showinfo("Saved", f"Document saved successfully to:\n{path}")

    # ------------------------------------------------------------------------
    # VIEW: SETTINGS
    # ------------------------------------------------------------------------
    def _build_settings_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")
        view.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(view, corner_radius=10)
        card.pack(fill="both", expand=True)

        lbl = ctk.CTkLabel(card, text="Application Settings", font=CTkFont(size=18, weight="bold"))
        lbl.pack(anchor="w", padx=20, pady=(20, 16))

        # Default Source
        f1 = ctk.CTkFrame(card, fg_color="transparent")
        f1.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(f1, text="Default Source Language:", font=CTkFont(size=14)).pack(side="left")
        self.def_src_var = tk.StringVar(value=self.default_src_lang)
        src_opt = ctk.CTkOptionMenu(
            f1,
            values=["Auto Detect"] + sorted([k for k in LANGUAGES.keys() if k != "Auto Detect"]),
            variable=self.def_src_var,
            command=self._save_default_src
        )
        src_opt.pack(side="right")

        # Default Target
        f2 = ctk.CTkFrame(card, fg_color="transparent")
        f2.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(f2, text="Default Target Language:", font=CTkFont(size=14)).pack(side="left")
        self.def_tgt_var = tk.StringVar(value=self.default_tgt_lang)
        tgt_opt = ctk.CTkOptionMenu(
            f2,
            values=sorted([k for k in LANGUAGES.keys() if k != "Auto Detect"]),
            variable=self.def_tgt_var,
            command=self._save_default_tgt
        )
        tgt_opt.pack(side="right")

        # Database management
        ctk.CTkLabel(card, text="Data Management", font=CTkFont(size=15, weight="bold")).pack(anchor="w", padx=20, pady=(24, 8))

        f3 = ctk.CTkFrame(card, fg_color="transparent")
        f3.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(f3, text="Delete local translation history:").pack(side="left")
        ctk.CTkButton(f3, text="Clear History", fg_color="#b91c1c", hover_color="#991b1b", command=self._clear_all_history).pack(side="right")

        f4 = ctk.CTkFrame(card, fg_color="transparent")
        f4.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(f4, text="Clear all saved favourites:").pack(side="left")
        ctk.CTkButton(f4, text="Clear Favourites", fg_color="#b91c1c", hover_color="#991b1b", command=self._clear_all_favourites).pack(side="right")

        return view

    def _save_default_src(self, val: str):
        self.default_src_lang = val
        self.db.set_setting("default_src_lang", val)

    def _save_default_tgt(self, val: str):
        self.default_tgt_lang = val
        self.db.set_setting("default_tgt_lang", val)

    # ------------------------------------------------------------------------
    # VIEW: ABOUT
    # ------------------------------------------------------------------------
    def _build_about_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.main_container, fg_color="transparent")

        card = ctk.CTkFrame(view, corner_radius=10)
        card.pack(fill="both", expand=True, padx=4, pady=4)

        title = ctk.CTkLabel(card, text="Translator", font=CTkFont(size=22, weight="bold"))
        title.pack(anchor="w", padx=24, pady=(24, 6))

        ver = ctk.CTkLabel(card, text="Version 2.0.0", text_color="#3b82f6", font=CTkFont(size=13, weight="bold"))
        ver.pack(anchor="w", padx=24, pady=(0, 16))

        desc = (
            "A fast desktop translation workstation supporting over 100 languages with\n"
            "automatic detection, voice features, and document translation."
        )
        ctk.CTkLabel(card, text=desc, justify="left", font=CTkFont(size=14)).pack(anchor="w", padx=24, pady=(0, 20))

        ctk.CTkLabel(card, text="Privacy & Storage", font=CTkFont(size=15, weight="bold")).pack(anchor="w", padx=24, pady=(10, 6))
        privacy = (
            "• All history, favourites, and settings are stored locally on your device.\n"
            "• Translations are performed over secure HTTPS.\n"
            "• No telemetry, accounts, or personal data are stored or shared."
        )
        ctk.CTkLabel(card, text=privacy, justify="left", font=CTkFont(size=13)).pack(anchor="w", padx=24, pady=(0, 20))

        ctk.CTkLabel(card, text="Shortcuts", font=CTkFont(size=15, weight="bold")).pack(anchor="w", padx=24, pady=(10, 6))
        shortcuts = (
            "• Ctrl + Enter : Instant translation\n"
            "• Ctrl + Shift + L : Clear text"
        )
        ctk.CTkLabel(card, text=shortcuts, justify="left", font=CTkFont(size=13), text_color="gray").pack(anchor="w", padx=24)

        return view


def main():
    app = TranslatorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
