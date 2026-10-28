"""
Stopwatch Desktop Application
=============================
A professional, distraction-free desktop stopwatch and timing utility built
exclusively with Python's standard library (Tkinter/ttk).

Key Features:
- Monotonic, drift-free timing engine (time.perf_counter).
- Multi-day timing without 24-hour wrap-around.
- Full lap/split tracking with delta calculation and fastest/slowest highlighting.
- In-place editing of lap labels and notes.
- Summary statistics (Fastest, Slowest, Average, Median, Std Dev).
- Dark and Light themes with persistent configuration.
- Local session storage with Session Manager and side-by-side comparison.
- Full CSV / JSON export and JSON session import.
- Integrated Countdown and Interval timing tools.
- Non-blocking sound notifications using Windows audio (winsound) with fallback.
- Context menus, keyboard shortcuts, and clean lifecycle management.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field
import datetime
import json
import math
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

# Attempt Windows audio support; fallback safely if unavailable
try:
    import winsound
except ImportError:
    winsound = None  # type: ignore


# ============================================================================
# CONSTANTS & THEMING
# ============================================================================

APP_NAME = "Stopwatch"
APP_VERSION = "2.1.0"
CONFIG_FILE_NAME = "stopwatch_config.json"
SESSIONS_FILE_NAME = "stopwatch_sessions.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "light",
    "precision": 3,              # 1=tenths, 2=hundredths, 3=milliseconds, 0=whole seconds
    "font_size": 42,
    "always_on_top": False,
    "sound_enabled": True,
    "confirm_reset": True,
    "compact_mode": False,
    "window_geometry": "640x700",
}

THEMES = {
    "light": {
        "bg_main": "#F8FAFC",
        "bg_card": "#FFFFFF",
        "bg_subtle": "#EDF2F7",
        "fg_primary": "#0F172A",
        "fg_secondary": "#475569",
        "fg_muted": "#94A3B8",
        "border": "#CBD5E1",
        "accent": "#0284C7",
        "accent_hover": "#0369A1",
        "btn_bg": "#E2E8F0",
        "btn_fg": "#0F172A",
        "fastest_bg": "#DCFCE7",
        "fastest_fg": "#166534",
        "slowest_bg": "#FEE2E2",
        "slowest_fg": "#991B1B",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#0F172A",
        "tree_select": "#E0F2FE",
    },
    "dark": {
        "bg_main": "#0F172A",
        "bg_card": "#1E293B",
        "bg_subtle": "#172033",
        "fg_primary": "#F8FAFC",
        "fg_secondary": "#94A3B8",
        "fg_muted": "#64748B",
        "border": "#334155",
        "accent": "#38BDF8",
        "accent_hover": "#0EA5E9",
        "btn_bg": "#334155",
        "btn_fg": "#F8FAFC",
        "fastest_bg": "#14532D",
        "fastest_fg": "#BBF7D0",
        "slowest_bg": "#7F1D1D",
        "slowest_fg": "#FECACA",
        "entry_bg": "#0F172A",
        "entry_fg": "#F8FAFC",
        "tree_select": "#0369A1",
    },
}

MONO_FONT = ("Consolas", "Courier New", "monospace")
UI_FONT = ("Segoe UI", "Tahoma", "sans-serif")


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class LapRecord:
    lap_num: int
    lap_time: float
    split_time: float
    delta: float = 0.0
    label: str = ""
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> LapRecord:
        return cls(
            lap_num=int(data.get("lap_num", 0)),
            lap_time=float(data.get("lap_time", 0.0)),
            split_time=float(data.get("split_time", 0.0)),
            delta=float(data.get("delta", 0.0)),
            label=str(data.get("label", "")),
            note=str(data.get("note", "")),
        )


@dataclass
class TimingSession:
    id: str
    name: str
    created_at: str
    total_elapsed: float
    laps: List[LapRecord] = field(default_factory=list)
    mode: str = "stopwatch"
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "total_elapsed": self.total_elapsed,
            "mode": self.mode,
            "notes": self.notes,
            "laps": [lap.to_dict() for lap in self.laps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TimingSession:
        raw_laps = data.get("laps", [])
        laps = [LapRecord.from_dict(item) for item in raw_laps]
        return cls(
            id=str(data.get("id", str(time.time()))),
            name=str(data.get("name", "Untitled Session")),
            created_at=str(data.get("created_at", datetime.datetime.now().isoformat())),
            total_elapsed=float(data.get("total_elapsed", 0.0)),
            laps=laps,
            mode=str(data.get("mode", "stopwatch")),
            notes=str(data.get("notes", "")),
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def format_time(seconds: float, precision: int = 3) -> str:
    """Format seconds into HH:MM:SS.mmm with proper mathematical rounding."""
    if seconds < 0:
        sign = "-"
        seconds = abs(seconds)
    else:
        sign = ""

    if precision == 3:
        total_ms = int(round(seconds * 1000))
        ms = total_ms % 1000
        total_s = total_ms // 1000
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
    elif precision == 2:
        total_cs = int(round(seconds * 100))
        cs = total_cs % 100
        total_s = total_cs // 100
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}.{cs:02d}"
    elif precision == 1:
        total_ds = int(round(seconds * 10))
        ds = total_ds % 10
        total_s = total_ds // 10
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}.{ds:01d}"
    else:
        total_s = int(round(seconds))
        s = total_s % 60
        total_m = total_s // 60
        m = total_m % 60
        h = total_m // 60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"


def play_sound(freq: int = 880, duration_ms: int = 80) -> None:
    """Play subtle non-blocking sound tone on Windows."""
    if winsound:
        try:
            # winsound.Beep is synchronous, but short (50-80ms) runs seamlessly.
            winsound.Beep(freq, duration_ms)
        except Exception:
            pass


def get_storage_path(filename: str) -> Path:
    """Return local path in the script's directory for robust portable use."""
    base_dir = Path(__file__).resolve().parent
    return base_dir / filename


# ============================================================================
# PERSISTENCE MANAGER
# ============================================================================

class StorageManager:
    """Safe, fault-tolerant persistence for configuration and sessions."""

    @staticmethod
    def load_config() -> Dict[str, Any]:
        path = get_storage_path(CONFIG_FILE_NAME)
        config = dict(DEFAULT_SETTINGS)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        config.update(data)
            except Exception:
                pass  # Fall back cleanly to defaults
        return config

    @staticmethod
    def save_config(config: Dict[str, Any]) -> None:
        path = get_storage_path(CONFIG_FILE_NAME)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def load_sessions() -> List[TimingSession]:
        path = get_storage_path(SESSIONS_FILE_NAME)
        sessions: List[TimingSession] = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if isinstance(raw, list):
                        for item in raw:
                            if isinstance(item, dict):
                                try:
                                    sessions.append(TimingSession.from_dict(item))
                                except Exception:
                                    continue
            except Exception:
                pass
        return sessions

    @staticmethod
    def save_sessions(sessions: List[TimingSession]) -> None:
        path = get_storage_path(SESSIONS_FILE_NAME)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in sessions], f, indent=2)
        except Exception as e:
            messagebox.showwarning("Warning", f"Could not persist session history: {e}")


# ============================================================================
# STOPWATCH TIMING ENGINE
# ============================================================================

class StopwatchState:
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"


class StopwatchEngine:
    """Drift-free timing engine using monotonic time.perf_counter()."""

    def __init__(self) -> None:
        self.state: str = StopwatchState.IDLE
        self._start_time: float = 0.0
        self._accumulated_elapsed: float = 0.0
        self.laps: List[LapRecord] = []
        self._last_split_time: float = 0.0

    @property
    def elapsed(self) -> float:
        if self.state == StopwatchState.RUNNING:
            return self._accumulated_elapsed + (time.perf_counter() - self._start_time)
        return self._accumulated_elapsed

    def start(self) -> bool:
        if self.state in (StopwatchState.IDLE, StopwatchState.STOPPED):
            self.reset()
            self._start_time = time.perf_counter()
            self.state = StopwatchState.RUNNING
            return True
        elif self.state == StopwatchState.PAUSED:
            self._start_time = time.perf_counter()
            self.state = StopwatchState.RUNNING
            return True
        return False

    def pause(self) -> bool:
        if self.state == StopwatchState.RUNNING:
            self._accumulated_elapsed += time.perf_counter() - self._start_time
            self._start_time = 0.0
            self.state = StopwatchState.PAUSED
            return True
        return False

    def resume(self) -> bool:
        return self.start()

    def stop(self) -> bool:
        if self.state == StopwatchState.RUNNING:
            self._accumulated_elapsed += time.perf_counter() - self._start_time
            self._start_time = 0.0
            self.state = StopwatchState.STOPPED
            return True
        elif self.state == StopwatchState.PAUSED:
            self.state = StopwatchState.STOPPED
            return True
        return False

    def reset(self) -> None:
        self.state = StopwatchState.IDLE
        self._start_time = 0.0
        self._accumulated_elapsed = 0.0
        self.laps.clear()
        self._last_split_time = 0.0

    def restart(self) -> None:
        self.reset()
        self.start()

    def record_lap(self, label: str = "", note: str = "") -> Optional[LapRecord]:
        if self.state not in (StopwatchState.RUNNING, StopwatchState.PAUSED):
            return None

        current_split = self.elapsed
        lap_duration = max(0.0, current_split - self._last_split_time)
        delta = 0.0
        if self.laps:
            delta = lap_duration - self.laps[-1].lap_time

        lap = LapRecord(
            lap_num=len(self.laps) + 1,
            lap_time=lap_duration,
            split_time=current_split,
            delta=delta,
            label=label,
            note=note,
        )
        self.laps.append(lap)
        self._last_split_time = current_split
        return lap

    def undo_lap(self) -> Optional[LapRecord]:
        if not self.laps:
            return None
        removed = self.laps.pop()
        self._last_split_time = self.laps[-1].split_time if self.laps else 0.0
        return removed


# ============================================================================
# DIALOGS & TOOLS
# ============================================================================

class LapEditDialog(tk.Toplevel):
    """Clean modal dialog for editing lap labels and notes."""

    def __init__(self, parent: tk.Widget, lap: LapRecord, theme: Dict[str, str], on_save: Callable[[str, str], None]):
        super().__init__(parent)
        self.title(f"Edit Lap #{lap.lap_num}")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self.configure(bg=theme["bg_card"])
        self.on_save = on_save

        frame = tk.Frame(self, bg=theme["bg_card"], padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text=f"Lap #{lap.lap_num} Details", font=(UI_FONT[0], 12, "bold"),
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(anchor="w", pady=(0, 10))

        tk.Label(frame, text="Label:", bg=theme["bg_card"], fg=theme["fg_secondary"],
                 font=(UI_FONT[0], 9)).pack(anchor="w")
        self.entry_label = tk.Entry(frame, width=32, bg=theme["entry_bg"], fg=theme["entry_fg"],
                                    insertbackground=theme["fg_primary"], relief=tk.SOLID, bd=1)
        self.entry_label.insert(0, lap.label)
        self.entry_label.pack(fill=tk.X, pady=(2, 10))

        tk.Label(frame, text="Note:", bg=theme["bg_card"], fg=theme["fg_secondary"],
                 font=(UI_FONT[0], 9)).pack(anchor="w")
        self.entry_note = tk.Entry(frame, width=32, bg=theme["entry_bg"], fg=theme["entry_fg"],
                                   insertbackground=theme["fg_primary"], relief=tk.SOLID, bd=1)
        self.entry_note.insert(0, lap.note)
        self.entry_note.pack(fill=tk.X, pady=(2, 16))

        btn_box = tk.Frame(frame, bg=theme["bg_card"])
        btn_box.pack(fill=tk.X)

        tk.Button(btn_box, text="Save", command=self._save, bg=theme["accent"], fg="#FFFFFF",
                  relief=tk.FLAT, padx=12, pady=4, cursor="hand2").pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btn_box, text="Cancel", command=self.destroy, bg=theme["btn_bg"], fg=theme["btn_fg"],
                  relief=tk.FLAT, padx=12, pady=4, cursor="hand2").pack(side=tk.RIGHT)

        self.entry_label.focus_set()
        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

    def _save(self) -> None:
        self.on_save(self.entry_label.get().strip(), self.entry_note.get().strip())
        self.destroy()


class SettingsDialog(tk.Toplevel):
    """Preferences and configuration dialog."""

    def __init__(self, parent: tk.Widget, current_cfg: Dict[str, Any], theme: Dict[str, str], on_apply: Callable[[Dict[str, Any]], None]):
        super().__init__(parent)
        self.title("Preferences")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self.cfg = dict(current_cfg)
        self.theme = theme
        self.on_apply = on_apply
        self.configure(bg=theme["bg_card"])

        f = tk.Frame(self, bg=theme["bg_card"], padx=24, pady=20)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="Stopwatch Settings", font=(UI_FONT[0], 12, "bold"),
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(anchor="w", pady=(0, 14))

        # Theme Option
        self.var_theme = tk.StringVar(value=self.cfg.get("theme", "light"))
        row1 = tk.Frame(f, bg=theme["bg_card"])
        row1.pack(fill=tk.X, pady=6)
        tk.Label(row1, text="Theme:", width=18, anchor="w", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT)
        theme_menu = ttk.Combobox(row1, textvariable=self.var_theme, values=["light", "dark"], state="readonly", width=12)
        theme_menu.pack(side=tk.LEFT)

        # Precision Option
        self.var_prec = tk.IntVar(value=self.cfg.get("precision", 3))
        row2 = tk.Frame(f, bg=theme["bg_card"])
        row2.pack(fill=tk.X, pady=6)
        tk.Label(row2, text="Display Precision:", width=18, anchor="w", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT)
        prec_menu = ttk.Combobox(row2, textvariable=self.var_prec, values=[0, 1, 2, 3], state="readonly", width=12)
        prec_menu.pack(side=tk.LEFT)
        tk.Label(row2, text="(0=sec, 2=cs, 3=ms)", font=(UI_FONT[0], 8), bg=theme["bg_card"], fg=theme["fg_muted"]).pack(side=tk.LEFT, padx=6)

        # Timer Font Size
        self.var_fsize = tk.IntVar(value=self.cfg.get("font_size", 42))
        row3 = tk.Frame(f, bg=theme["bg_card"])
        row3.pack(fill=tk.X, pady=6)
        tk.Label(row3, text="Timer Font Size:", width=18, anchor="w", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT)
        size_menu = ttk.Combobox(row3, textvariable=self.var_fsize, values=[32, 38, 42, 48, 56, 64], state="readonly", width=12)
        size_menu.pack(side=tk.LEFT)

        # Checkboxes
        self.var_top = tk.BooleanVar(value=self.cfg.get("always_on_top", False))
        self.var_sound = tk.BooleanVar(value=self.cfg.get("sound_enabled", True))
        self.var_confirm = tk.BooleanVar(value=self.cfg.get("confirm_reset", True))

        cb1 = tk.Checkbutton(f, text="Always on top of other windows", variable=self.var_top,
                             bg=theme["bg_card"], fg=theme["fg_primary"], activebackground=theme["bg_card"], selectcolor=theme["bg_card"])
        cb1.pack(anchor="w", pady=(8, 2))

        cb2 = tk.Checkbutton(f, text="Enable audio feedback on lap and stop", variable=self.var_sound,
                             bg=theme["bg_card"], fg=theme["fg_primary"], activebackground=theme["bg_card"], selectcolor=theme["bg_card"])
        cb2.pack(anchor="w", pady=2)

        cb3 = tk.Checkbutton(f, text="Confirm before clearing recorded laps", variable=self.var_confirm,
                             bg=theme["bg_card"], fg=theme["fg_primary"], activebackground=theme["bg_card"], selectcolor=theme["bg_card"])
        cb3.pack(anchor="w", pady=2)

        # Actions
        actions = tk.Frame(f, bg=theme["bg_card"])
        actions.pack(fill=tk.X, pady=(18, 0))

        tk.Button(actions, text="Save Settings", command=self._save, bg=theme["accent"], fg="#FFFFFF",
                  relief=tk.FLAT, padx=14, pady=5, cursor="hand2").pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(actions, text="Cancel", command=self.destroy, bg=theme["btn_bg"], fg=theme["btn_fg"],
                  relief=tk.FLAT, padx=12, pady=5, cursor="hand2").pack(side=tk.RIGHT)

    def _save(self) -> None:
        self.cfg["theme"] = self.var_theme.get()
        self.cfg["precision"] = int(self.var_prec.get())
        self.cfg["font_size"] = int(self.var_fsize.get())
        self.cfg["always_on_top"] = bool(self.var_top.get())
        self.cfg["sound_enabled"] = bool(self.var_sound.get())
        self.cfg["confirm_reset"] = bool(self.var_confirm.get())
        self.on_apply(self.cfg)
        self.destroy()


class SessionManagerDialog(tk.Toplevel):
    """View, reopen, compare, and manage saved sessions."""

    def __init__(self, parent: "StopwatchApp", theme: Dict[str, str]):
        super().__init__(parent)
        self.parent_app = parent
        self.theme = theme
        self.title("Session History")
        self.geometry("720x460")
        self.minsize(550, 350)
        self.transient(parent)
        self.grab_set()
        self.configure(bg=theme["bg_main"])

        # Header
        top_bar = tk.Frame(self, bg=theme["bg_main"], padx=14, pady=10)
        top_bar.pack(fill=tk.X)
        tk.Label(top_bar, text="Saved Timing Sessions", font=(UI_FONT[0], 12, "bold"),
                 bg=theme["bg_main"], fg=theme["fg_primary"]).pack(side=tk.LEFT)

        # Session Table
        cols = ("name", "date", "duration", "laps", "mode")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("name", text="Session Name")
        self.tree.heading("date", text="Created")
        self.tree.heading("duration", text="Duration")
        self.tree.heading("laps", text="Laps")
        self.tree.heading("mode", text="Mode")

        self.tree.column("name", width=220, anchor="w")
        self.tree.column("date", width=140, anchor="center")
        self.tree.column("duration", width=100, anchor="e")
        self.tree.column("laps", width=60, anchor="center")
        self.tree.column("mode", width=80, anchor="center")

        scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=14, pady=4)
        scroll.place(in_=self.tree, relx=1.0, relheight=1.0, bordermode="outside")

        # Bottom Buttons
        btn_bar = tk.Frame(self, bg=theme["bg_main"], padx=14, pady=10)
        btn_bar.pack(fill=tk.X)

        tk.Button(btn_bar, text="Load Selected", command=self._load_session,
                  bg=theme["accent"], fg="#FFFFFF", relief=tk.FLAT, padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_bar, text="Compare Two Sessions", command=self._compare_sessions,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Button(btn_bar, text="Delete", command=self._delete_session,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=6)
        tk.Button(btn_bar, text="Close", command=self.destroy,
                  bg=theme["btn_bg"], fg=theme["btn_fg"], relief=tk.FLAT, padx=10, pady=4, cursor="hand2").pack(side=tk.RIGHT)

        self._refresh_list()

    def _refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.parent_app.sessions:
            created_str = s.created_at[:16].replace("T", " ")
            self.tree.insert("", tk.END, iid=s.id, values=(
                s.name,
                created_str,
                format_time(s.total_elapsed, 2),
                len(s.laps),
                s.mode.capitalize(),
            ))

    def _load_session(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select Session", "Please select a session from the list.")
            return
        target_id = sel[0]
        session = next((s for s in self.parent_app.sessions if s.id == target_id), None)
        if session:
            self.parent_app.load_session(session)
            self.destroy()

    def _compare_sessions(self) -> None:
        sel = self.tree.selection()
        if len(sel) != 2:
            messagebox.showinfo("Compare Sessions", "Please select exactly two sessions to compare.")
            return
        s1 = next((s for s in self.parent_app.sessions if s.id == sel[0]), None)
        s2 = next((s for s in self.parent_app.sessions if s.id == sel[1]), None)
        if s1 and s2:
            SessionComparisonDialog(self, s1, s2, self.theme)

    def _delete_session(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm Delete", f"Delete {len(sel)} selected session(s)?"):
            self.parent_app.sessions = [s for s in self.parent_app.sessions if s.id not in sel]
            StorageManager.save_sessions(self.parent_app.sessions)
            self._refresh_list()


class SessionComparisonDialog(tk.Toplevel):
    """Side-by-side comparison modal for two recorded sessions."""

    def __init__(self, parent: tk.Widget, s1: TimingSession, s2: TimingSession, theme: Dict[str, str]):
        super().__init__(parent)
        self.title("Session Comparison")
        self.geometry("600x420")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.configure(bg=theme["bg_card"])

        f = tk.Frame(self, bg=theme["bg_card"], padx=20, pady=16)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="Session Comparison", font=(UI_FONT[0], 13, "bold"),
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(anchor="w", pady=(0, 12))

        # Grid of metrics
        metrics = [
            ("Session Name", s1.name, s2.name),
            ("Created At", s1.created_at[:16].replace("T", " "), s2.created_at[:16].replace("T", " ")),
            ("Total Duration", format_time(s1.total_elapsed, 3), format_time(s2.total_elapsed, 3)),
            ("Laps Recorded", str(len(s1.laps)), str(len(s2.laps))),
        ]

        def get_best_worst_avg(laps: List[LapRecord]):
            if not laps:
                return "-", "-", "-"
            times = [lap.lap_time for lap in laps]
            best = min(times)
            worst = max(times)
            avg = sum(times) / len(times)
            return format_time(best, 3), format_time(worst, 3), format_time(avg, 3)

        b1, w1, a1 = get_best_worst_avg(s1.laps)
        b2, w2, a2 = get_best_worst_avg(s2.laps)

        metrics.extend([
            ("Fastest Lap", b1, b2),
            ("Slowest Lap", w1, w2),
            ("Average Lap", a1, a2),
        ])

        # Header row
        table = tk.Frame(f, bg=theme["border"], bd=1)
        table.pack(fill=tk.BOTH, expand=True, pady=6)

        headers = ["Metric", "Session A", "Session B"]
        for col_idx, h in enumerate(headers):
            cell = tk.Label(table, text=h, font=(UI_FONT[0], 9, "bold"), bg=theme["bg_subtle"],
                            fg=theme["fg_primary"], padx=8, pady=6, anchor="w")
            cell.grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)

        for row_idx, (m, v1, v2) in enumerate(metrics, start=1):
            bg_c = theme["bg_card"] if row_idx % 2 == 0 else theme["bg_main"]
            tk.Label(table, text=m, font=(UI_FONT[0], 9, "bold"), bg=bg_c, fg=theme["fg_secondary"],
                     padx=8, pady=4, anchor="w").grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)
            tk.Label(table, text=v1, font=(UI_FONT[0], 9), bg=bg_c, fg=theme["fg_primary"],
                     padx=8, pady=4, anchor="w").grid(row=row_idx, column=1, sticky="nsew", padx=1, pady=1)
            tk.Label(table, text=v2, font=(UI_FONT[0], 9), bg=bg_c, fg=theme["fg_primary"],
                     padx=8, pady=4, anchor="w").grid(row=row_idx, column=2, sticky="nsew", padx=1, pady=1)

        table.grid_columnconfigure(0, weight=2)
        table.grid_columnconfigure(1, weight=3)
        table.grid_columnconfigure(2, weight=3)

        tk.Button(f, text="Close", command=self.destroy, bg=theme["btn_bg"], fg=theme["btn_fg"],
                  relief=tk.FLAT, padx=12, pady=4, cursor="hand2").pack(side=tk.RIGHT, pady=(12, 0))


class CountdownTimerDialog(tk.Toplevel):
    """Reliable non-blocking countdown utility."""

    def __init__(self, parent: tk.Widget, theme: Dict[str, str]):
        super().__init__(parent)
        self.title("Countdown Timer")
        self.geometry("380x300")
        self.resizable(False, False)
        self.configure(bg=theme["bg_card"])
        self.theme = theme

        self._target_sec: float = 60.0
        self._remain_sec: float = 60.0
        self._start_perf: float = 0.0
        self._is_running: bool = False
        self._after_id: Optional[str] = None

        f = tk.Frame(self, bg=theme["bg_card"], padx=20, pady=16)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="Countdown Timer", font=(UI_FONT[0], 12, "bold"),
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(anchor="w", pady=(0, 10))

        # Inputs
        inp_box = tk.Frame(f, bg=theme["bg_card"])
        inp_box.pack(pady=4)

        self.sp_h = tk.Spinbox(inp_box, from_=0, to=99, width=3, font=(UI_FONT[0], 11), justify="center")
        self.sp_m = tk.Spinbox(inp_box, from_=0, to=59, width=3, font=(UI_FONT[0], 11), justify="center")
        self.sp_s = tk.Spinbox(inp_box, from_=0, to=59, width=3, font=(UI_FONT[0], 11), justify="center")
        self.sp_m.delete(0, tk.END)
        self.sp_m.insert(0, "1")
        self.sp_h.delete(0, tk.END)
        self.sp_h.insert(0, "0")
        self.sp_s.delete(0, tk.END)
        self.sp_s.insert(0, "0")

        self.sp_h.pack(side=tk.LEFT)
        tk.Label(inp_box, text="h :", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT, padx=3)
        self.sp_m.pack(side=tk.LEFT)
        tk.Label(inp_box, text="m :", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT, padx=3)
        self.sp_s.pack(side=tk.LEFT)
        tk.Label(inp_box, text="s", bg=theme["bg_card"], fg=theme["fg_secondary"]).pack(side=tk.LEFT, padx=3)

        # Big Display
        self.lbl_disp = tk.Label(f, text="00:01:00.0", font=(MONO_FONT[0], 28, "bold"),
                                 bg=theme["bg_card"], fg=theme["fg_primary"])
        self.lbl_disp.pack(pady=14)

        # Control Buttons
        btns = tk.Frame(f, bg=theme["bg_card"])
        btns.pack()

        self.btn_toggle = tk.Button(btns, text="Start", command=self._toggle, bg=theme["accent"],
                                    fg="#FFFFFF", relief=tk.FLAT, padx=12, pady=4, cursor="hand2")
        self.btn_toggle.pack(side=tk.LEFT, padx=4)

        self.btn_reset = tk.Button(btns, text="Reset", command=self._reset, bg=theme["btn_bg"],
                                   fg=theme["btn_fg"], relief=tk.FLAT, padx=12, pady=4, cursor="hand2")
        self.btn_reset.pack(side=tk.LEFT, padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle(self) -> None:
        if self._is_running:
            # Pause
            self._is_running = False
            self.btn_toggle.config(text="Resume")
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
        else:
            # Start/Resume
            if self._remain_sec <= 0.05:
                # Read from spinboxes
                try:
                    h = int(self.sp_h.get())
                    m = int(self.sp_m.get())
                    s = int(self.sp_s.get())
                    self._target_sec = max(1.0, float(h * 3600 + m * 60 + s))
                    self._remain_sec = self._target_sec
                except ValueError:
                    self._remain_sec = 60.0

            self._start_perf = time.perf_counter()
            self._is_running = True
            self.btn_toggle.config(text="Pause")
            self._tick()

    def _tick(self) -> None:
        if not self._is_running:
            return
        now = time.perf_counter()
        delta = now - self._start_perf
        self._start_perf = now
        self._remain_sec -= delta

        if self._remain_sec <= 0.0:
            self._remain_sec = 0.0
            self._is_running = False
            self.lbl_disp.config(text="00:00:00.0")
            self.btn_toggle.config(text="Start")
            play_sound(1200, 300)
            messagebox.showinfo("Countdown Complete", "The countdown timer has finished!")
            return

        self.lbl_disp.config(text=format_time(self._remain_sec, 1))
        self._after_id = self.after(50, self._tick)

    def _reset(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._is_running = False
        try:
            h = int(self.sp_h.get())
            m = int(self.sp_m.get())
            s = int(self.sp_s.get())
            self._remain_sec = float(h * 3600 + m * 60 + s)
        except ValueError:
            self._remain_sec = 60.0
        self.lbl_disp.config(text=format_time(self._remain_sec, 1))
        self.btn_toggle.config(text="Start")

    def _on_close(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        self.destroy()


class IntervalTimerDialog(tk.Toplevel):
    """Work / Rest / Rounds interval training timer."""

    def __init__(self, parent: tk.Widget, theme: Dict[str, str]):
        super().__init__(parent)
        self.title("Interval Timer")
        self.geometry("380x340")
        self.resizable(False, False)
        self.configure(bg=theme["bg_card"])
        self.theme = theme

        self._work_sec: float = 30.0
        self._rest_sec: float = 10.0
        self._total_rounds: int = 5
        self._current_round: int = 1
        self._stage: str = "WORK"  # WORK or REST
        self._remain_sec: float = 30.0
        self._is_running: bool = False
        self._after_id: Optional[str] = None
        self._last_perf: float = 0.0

        f = tk.Frame(self, bg=theme["bg_card"], padx=20, pady=16)
        f.pack(fill=tk.BOTH, expand=True)

        tk.Label(f, text="Interval / Repetition Timer", font=(UI_FONT[0], 12, "bold"),
                 bg=theme["bg_card"], fg=theme["fg_primary"]).pack(anchor="w", pady=(0, 8))

        # Setup parameters
        cfg_box = tk.Frame(f, bg=theme["bg_card"])
        cfg_box.pack(fill=tk.X, pady=4)

        tk.Label(cfg_box, text="Work (s):", bg=theme["bg_card"], fg=theme["fg_secondary"]).grid(row=0, column=0, sticky="w", pady=2)
        self.sp_work = tk.Spinbox(cfg_box, from_=5, to=600, width=5)
        self.sp_work.delete(0, tk.END)
        self.sp_work.insert(0, "30")
        self.sp_work.grid(row=0, column=1, sticky="w", padx=6, pady=2)

        tk.Label(cfg_box, text="Rest (s):", bg=theme["bg_card"], fg=theme["fg_secondary"]).grid(row=1, column=0, sticky="w", pady=2)
        self.sp_rest = tk.Spinbox(cfg_box, from_=0, to=600, width=5)
        self.sp_rest.delete(0, tk.END)
        self.sp_rest.insert(0, "10")
        self.sp_rest.grid(row=1, column=1, sticky="w", padx=6, pady=2)

        tk.Label(cfg_box, text="Rounds:", bg=theme["bg_card"], fg=theme["fg_secondary"]).grid(row=2, column=0, sticky="w", pady=2)
        self.sp_rounds = tk.Spinbox(cfg_box, from_=1, to=99, width=5)
        self.sp_rounds.delete(0, tk.END)
        self.sp_rounds.insert(0, "5")
        self.sp_rounds.grid(row=2, column=1, sticky="w", padx=6, pady=2)

        # Stage indicator & Remaining
        self.lbl_stage = tk.Label(f, text="READY", font=(UI_FONT[0], 11, "bold"),
                                  bg=theme["bg_card"], fg=theme["accent"])
        self.lbl_stage.pack(pady=(8, 0))

        self.lbl_disp = tk.Label(f, text="00:30.0", font=(MONO_FONT[0], 28, "bold"),
                                 bg=theme["bg_card"], fg=theme["fg_primary"])
        self.lbl_disp.pack(pady=4)

        self.lbl_round_info = tk.Label(f, text="Round 1 of 5", font=(UI_FONT[0], 9),
                                       bg=theme["bg_card"], fg=theme["fg_muted"])
        self.lbl_round_info.pack(pady=(0, 10))

        # Buttons
        btns = tk.Frame(f, bg=theme["bg_card"])
        btns.pack()

        self.btn_toggle = tk.Button(btns, text="Start Sequence", command=self._toggle, bg=theme["accent"],
                                    fg="#FFFFFF", relief=tk.FLAT, padx=12, pady=4, cursor="hand2")
        self.btn_toggle.pack(side=tk.LEFT, padx=4)

        self.btn_reset = tk.Button(btns, text="Reset", command=self._reset, bg=theme["btn_bg"],
                                   fg=theme["btn_fg"], relief=tk.FLAT, padx=12, pady=4, cursor="hand2")
        self.btn_reset.pack(side=tk.LEFT, padx=4)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _toggle(self) -> None:
        if self._is_running:
            self._is_running = False
            self.btn_toggle.config(text="Resume")
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
        else:
            if self._stage == "READY":
                self._apply_inputs()
            self._last_perf = time.perf_counter()
            self._is_running = True
            self.btn_toggle.config(text="Pause")
            self._tick()

    def _apply_inputs(self) -> None:
        try:
            self._work_sec = float(self.sp_work.get())
            self._rest_sec = float(self.sp_rest.get())
            self._total_rounds = int(self.sp_rounds.get())
        except ValueError:
            self._work_sec, self._rest_sec, self._total_rounds = 30.0, 10.0, 5
        self._current_round = 1
        self._stage = "WORK"
        self._remain_sec = self._work_sec
        self.lbl_stage.config(text="STAGE: WORK", fg=self.theme["accent"])
        self.lbl_round_info.config(text=f"Round {self._current_round} of {self._total_rounds}")

    def _tick(self) -> None:
        if not self._is_running:
            return
        now = time.perf_counter()
        delta = now - self._last_perf
        self._last_perf = now
        self._remain_sec -= delta

        if self._remain_sec <= 0.0:
            play_sound(1000, 120)
            if self._stage == "WORK":
                if self._rest_sec > 0:
                    self._stage = "REST"
                    self._remain_sec = self._rest_sec
                    self.lbl_stage.config(text="STAGE: REST", fg=self.theme["slowest_fg"])
                else:
                    self._advance_round()
            else:
                self._advance_round()

        self.lbl_disp.config(text=format_time(max(0.0, self._remain_sec), 1))
        self._after_id = self.after(50, self._tick)

    def _advance_round(self) -> None:
        self._current_round += 1
        if self._current_round > self._total_rounds:
            self._is_running = False
            self.lbl_stage.config(text="COMPLETED!", fg=self.theme["fastest_fg"])
            self.lbl_disp.config(text="00:00.0")
            self.btn_toggle.config(text="Start Sequence")
            play_sound(1400, 350)
            messagebox.showinfo("Workout Finished", "All interval rounds completed successfully.")
            return

        self._stage = "WORK"
        self._remain_sec = self._work_sec
        self.lbl_stage.config(text="STAGE: WORK", fg=self.theme["accent"])
        self.lbl_round_info.config(text=f"Round {self._current_round} of {self._total_rounds}")

    def _reset(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        self._is_running = False
        self._stage = "READY"
        self._current_round = 1
        self.lbl_stage.config(text="READY", fg=self.theme["accent"])
        self.lbl_round_info.config(text="Configured and waiting")
        self.btn_toggle.config(text="Start Sequence")
        try:
            w = float(self.sp_work.get())
        except ValueError:
            w = 30.0
        self.lbl_disp.config(text=format_time(w, 1))

    def _on_close(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
        self.destroy()


# ============================================================================
# MAIN STOPWATCH APPLICATION
# ============================================================================

class StopwatchApp(tk.Tk):
    """Main desktop application window and coordinator."""

    def __init__(self) -> None:
        super().__init__()

        self.config_data = StorageManager.load_config()
        self.sessions = StorageManager.load_sessions()
        self.current_theme_name = self.config_data.get("theme", "light")
        self.theme = THEMES.get(self.current_theme_name, THEMES["light"])

        self.engine = StopwatchEngine()
        self.current_session_id = str(time.time())
        self.current_session_name = "Session 1"
        self._after_id: Optional[str] = None
        self._last_stats_hash: str = ""

        # Window Setup
        self.title(APP_NAME)
        geom = self.config_data.get("window_geometry", "640x700")
        self.geometry(geom)
        self.minsize(440, 520)
        self.attributes("-topmost", self.config_data.get("always_on_top", False))

        # Build UI
        self._setup_styles()
        self._setup_menu()
        self._setup_layout()
        self._bind_shortcuts()

        # Lifecycle protocols
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Initial display refresh
        self._update_ui_state()
        self._render_stats()

    # ------------------------------------------------------------------------
    # STYLES & THEMING
    # ------------------------------------------------------------------------

    def _setup_styles(self) -> None:
        self.configure(bg=self.theme["bg_main"])
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("Treeview",
                        background=self.theme["bg_card"],
                        foreground=self.theme["fg_primary"],
                        fieldbackground=self.theme["bg_card"],
                        rowheight=24,
                        font=(UI_FONT[0], 9))
        style.configure("Treeview.Heading",
                        background=self.theme["bg_subtle"],
                        foreground=self.theme["fg_primary"],
                        font=(UI_FONT[0], 9, "bold"),
                        relief=tk.FLAT)
        style.map("Treeview",
                  background=[("selected", self.theme["tree_select"])],
                  foreground=[("selected", self.theme["fg_primary"])])

    def set_theme(self, theme_name: str) -> None:
        if theme_name not in THEMES:
            return
        self.current_theme_name = theme_name
        self.theme = THEMES[theme_name]
        self.config_data["theme"] = theme_name
        StorageManager.save_config(self.config_data)

        # Refresh all widgets
        self._setup_styles()
        self.configure(bg=self.theme["bg_main"])
        self.top_frame.configure(bg=self.theme["bg_main"])
        self.display_canvas.configure(bg=self.theme["bg_card"], highlightbackground=self.theme["border"])
        self.control_bar.configure(bg=self.theme["bg_main"])
        self.table_frame.configure(bg=self.theme["bg_main"])
        self.stats_card.configure(bg=self.theme["bg_card"], highlightbackground=self.theme["border"])
        self.status_bar.configure(bg=self.theme["bg_subtle"])
        self.lbl_status.configure(bg=self.theme["bg_subtle"], fg=self.theme["fg_secondary"])
        self.lbl_quick_hint.configure(bg=self.theme["bg_subtle"], fg=self.theme["fg_muted"])

        for lbl in self.stat_labels.values():
            lbl.configure(bg=self.theme["bg_card"])

        self._configure_tree_tags()
        self._update_display(force=True)
        self._refresh_table()

    def _configure_tree_tags(self) -> None:
        self.tree.tag_configure("fastest", background=self.theme["fastest_bg"], foreground=self.theme["fastest_fg"])
        self.tree.tag_configure("slowest", background=self.theme["slowest_bg"], foreground=self.theme["slowest_fg"])
        self.tree.tag_configure("normal", background=self.theme["bg_card"], foreground=self.theme["fg_primary"])

    # ------------------------------------------------------------------------
    # MENU BAR
    # ------------------------------------------------------------------------

    def _setup_menu(self) -> None:
        menubar = tk.Menu(self)

        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Session", accelerator="Ctrl+N", command=self.action_new_session)
        file_menu.add_command(label="Save Session to History", accelerator="Ctrl+S", command=self.action_save_session)
        file_menu.add_command(label="Session History...", accelerator="Ctrl+H", command=self.action_open_history)
        file_menu.add_separator()
        file_menu.add_command(label="Export to CSV...", accelerator="Ctrl+E", command=self.export_csv)
        file_menu.add_command(label="Export to JSON...", command=self.export_json)
        file_menu.add_command(label="Import JSON Session...", command=self.import_json)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit Menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo Last Lap", accelerator="Ctrl+Z", command=self.action_undo_lap)
        edit_menu.add_command(label="Edit Selected Lap...", accelerator="Enter", command=self.action_edit_selected_lap)
        edit_menu.add_command(label="Delete Selected Lap", accelerator="Del", command=self.action_delete_selected_lap)
        edit_menu.add_separator()
        edit_menu.add_command(label="Copy Elapsed Time", accelerator="Ctrl+C", command=self.copy_elapsed)
        edit_menu.add_command(label="Copy Session Summary", command=self.copy_summary)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # View Menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Toggle Theme (Light/Dark)", accelerator="F5", command=self.toggle_theme)
        view_menu.add_checkbutton(label="Always on Top", command=self.toggle_always_on_top)
        view_menu.add_separator()
        view_menu.add_command(label="Preferences...", accelerator="Ctrl+,", command=self.open_preferences)
        menubar.add_cascade(label="View", menu=view_menu)

        # Tools Menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="Countdown Timer...", command=lambda: CountdownTimerDialog(self, self.theme))
        tools_menu.add_command(label="Interval Timer...", command=lambda: IntervalTimerDialog(self, self.theme))
        menubar.add_cascade(label="Tools", menu=tools_menu)

        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)
        help_menu.add_command(label="About Stopwatch", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    # ------------------------------------------------------------------------
    # MAIN LAYOUT & CONTROLS
    # ------------------------------------------------------------------------

    def _setup_layout(self) -> None:
        # Top Container
        self.top_frame = tk.Frame(self, bg=self.theme["bg_main"], padx=18, pady=12)
        self.top_frame.pack(fill=tk.BOTH, expand=True)

        # Session Label / Header
        self.header_frame = tk.Frame(self.top_frame, bg=self.theme["bg_main"])
        self.header_frame.pack(fill=tk.X, pady=(0, 6))

        self.lbl_session_title = tk.Label(self.header_frame, text=self.current_session_name,
                                          font=(UI_FONT[0], 10, "bold"), bg=self.theme["bg_main"],
                                          fg=self.theme["fg_secondary"])
        self.lbl_session_title.pack(side=tk.LEFT)

        self.btn_rename_session = tk.Button(self.header_frame, text="Rename", font=(UI_FONT[0], 8),
                                            command=self.action_rename_session, relief=tk.FLAT,
                                            bg=self.theme["bg_main"], fg=self.theme["accent"], cursor="hand2")
        self.btn_rename_session.pack(side=tk.LEFT, padx=6)

        # Digital Timer Display Card
        fsize = int(self.config_data.get("font_size", 42))
        self.display_canvas = tk.Canvas(self.top_frame, height=92, bg=self.theme["bg_card"],
                                        bd=0, highlightthickness=1, highlightbackground=self.theme["border"])
        self.display_canvas.pack(fill=tk.X, pady=(0, 12))

        # Centered text item on canvas
        self.text_time_id = self.display_canvas.create_text(
            300, 46,
            text="00:00:00.000",
            font=(MONO_FONT[0], fsize, "bold"),
            fill=self.theme["fg_primary"],
            anchor="center"
        )
        self.display_canvas.bind("<Configure>", self._on_canvas_resize)

        # Control Buttons Bar
        self.control_bar = tk.Frame(self.top_frame, bg=self.theme["bg_main"])
        self.control_bar.pack(fill=tk.X, pady=(0, 12))

        btn_padding = {"padx": 14, "pady": 7, "font": (UI_FONT[0], 10, "bold"), "relief": tk.FLAT, "cursor": "hand2"}

        self.btn_start = tk.Button(self.control_bar, text="Start", bg=self.theme["accent"],
                                   fg="#FFFFFF", command=self.action_start_pause, **btn_padding)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 6), expand=True, fill=tk.X)

        self.btn_lap = tk.Button(self.control_bar, text="Lap", bg=self.theme["btn_bg"],
                                 fg=self.theme["btn_fg"], command=self.action_lap, **btn_padding)
        self.btn_lap.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        self.btn_stop = tk.Button(self.control_bar, text="Stop", bg=self.theme["btn_bg"],
                                  fg=self.theme["btn_fg"], command=self.action_stop, **btn_padding)
        self.btn_stop.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        self.btn_reset = tk.Button(self.control_bar, text="Reset", bg=self.theme["btn_bg"],
                                   fg=self.theme["btn_fg"], command=self.action_reset, **btn_padding)
        self.btn_reset.pack(side=tk.LEFT, padx=(6, 0), expand=True, fill=tk.X)

        # Lap History Table (Treeview)
        self.table_frame = tk.Frame(self.top_frame, bg=self.theme["bg_main"])
        self.table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        cols = ("num", "lap_time", "split", "delta", "label", "note")
        self.tree = ttk.Treeview(self.table_frame, columns=cols, show="headings", selectmode="browse")

        self.tree.heading("num", text="#", command=lambda: self._sort_column("num", False))
        self.tree.heading("lap_time", text="Lap Duration", command=lambda: self._sort_column("lap_time", False))
        self.tree.heading("split", text="Overall Split", command=lambda: self._sort_column("split", False))
        self.tree.heading("delta", text="Diff", command=lambda: self._sort_column("delta", False))
        self.tree.heading("label", text="Label")
        self.tree.heading("note", text="Note")

        self.tree.column("num", width=42, anchor="center")
        self.tree.column("lap_time", width=110, anchor="e")
        self.tree.column("split", width=110, anchor="e")
        self.tree.column("delta", width=95, anchor="e")
        self.tree.column("label", width=95, anchor="w")
        self.tree.column("note", width=120, anchor="w")

        scroll = ttk.Scrollbar(self.table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._configure_tree_tags()
        self.tree.bind("<Double-1>", lambda e: self.action_edit_selected_lap())
        self.tree.bind("<Return>", lambda e: self.action_edit_selected_lap())
        self.tree.bind("<Button-3>", self._show_tree_context_menu)

        # Statistics Summary Panel Card
        self.stats_card = tk.Frame(self.top_frame, bg=self.theme["bg_card"], bd=0,
                                   highlightthickness=1, highlightbackground=self.theme["border"], padx=12, pady=8)
        self.stats_card.pack(fill=tk.X, pady=(0, 2))

        self.stat_labels: Dict[str, tk.Label] = {}
        stat_keys = [("Fastest:", "lbl_fast"), ("Slowest:", "lbl_slow"),
                     ("Average:", "lbl_avg"), ("Median:", "lbl_med"), ("Laps:", "lbl_cnt")]

        for idx, (title, key) in enumerate(stat_keys):
            cell = tk.Frame(self.stats_card, bg=self.theme["bg_card"])
            cell.pack(side=tk.LEFT, expand=True, fill=tk.X)
            tk.Label(cell, text=title, font=(UI_FONT[0], 8), bg=self.theme["bg_card"],
                     fg=self.theme["fg_muted"]).pack(anchor="w")
            val_lbl = tk.Label(cell, text="--", font=(MONO_FONT[0], 9, "bold"),
                               bg=self.theme["bg_card"], fg=self.theme["fg_primary"])
            val_lbl.pack(anchor="w")
            self.stat_labels[key] = val_lbl

        # Bottom Discreet Status Bar
        self.status_bar = tk.Frame(self, bg=self.theme["bg_subtle"], height=24, padx=10)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_status = tk.Label(self.status_bar, text="Ready", font=(UI_FONT[0], 8),
                                   bg=self.theme["bg_subtle"], fg=self.theme["fg_secondary"])
        self.lbl_status.pack(side=tk.LEFT)

        self.lbl_quick_hint = tk.Label(self.status_bar, text="Space: Start/Pause | L: Lap | R: Reset",
                                       font=(UI_FONT[0], 8), bg=self.theme["bg_subtle"], fg=self.theme["fg_muted"])
        self.lbl_quick_hint.pack(side=tk.RIGHT)

        # Context Menu for Treeview
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Edit Label / Note", command=self.action_edit_selected_lap)
        self.tree_menu.add_command(label="Copy Lap Time", command=self.copy_selected_lap_time)
        self.tree_menu.add_command(label="Copy Full Row", command=self.copy_selected_lap_full)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Delete Lap", command=self.action_delete_selected_lap)

    def _on_canvas_resize(self, event: tk.Event) -> None:
        self.display_canvas.coords(self.text_time_id, event.width / 2, event.height / 2)

    def _show_tree_context_menu(self, event: tk.Event) -> None:
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.tree_menu.post(event.x_root, event.y_root)

    # ------------------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # ------------------------------------------------------------------------

    def _bind_shortcuts(self) -> None:
        def not_in_entry(fn: Callable[[], None]):
            def handler(event: tk.Event):
                # Avoid activating shortcuts when user is typing in Entry/Spinbox
                if isinstance(event.widget, (tk.Entry, ttk.Entry, tk.Spinbox, ttk.Combobox)):
                    return
                fn()
                return "break"
            return handler

        self.bind("<space>", not_in_entry(self.action_start_pause))
        self.bind("<Key-l>", not_in_entry(self.action_lap))
        self.bind("<Key-L>", not_in_entry(self.action_lap))
        self.bind("<Key-s>", not_in_entry(self.action_stop))
        self.bind("<Key-S>", not_in_entry(self.action_stop))
        self.bind("<Key-r>", not_in_entry(self.action_reset))
        self.bind("<Key-R>", not_in_entry(self.action_reset))

        self.bind("<Control-z>", lambda e: self.action_undo_lap())
        self.bind("<Control-e>", lambda e: self.export_csv())
        self.bind("<Control-s>", lambda e: self.action_save_session())
        self.bind("<Control-n>", lambda e: self.action_new_session())
        self.bind("<Control-h>", lambda e: self.action_open_history())
        self.bind("<Control-c>", lambda e: self.copy_elapsed())
        self.bind("<Control-comma>", lambda e: self.open_preferences())
        self.bind("<F5>", lambda e: self.toggle_theme())
        self.bind("<Delete>", lambda e: self.action_delete_selected_lap())

    # ------------------------------------------------------------------------
    # ENGINE & UI SYNCHRONIZATION
    # ------------------------------------------------------------------------

    def _update_display(self, force: bool = False) -> None:
        prec = self.config_data.get("precision", 3)
        time_str = format_time(self.engine.elapsed, prec)
        self.display_canvas.itemconfig(self.text_time_id, text=time_str, fill=self.theme["fg_primary"])
        if force:
            fsize = int(self.config_data.get("font_size", 42))
            self.display_canvas.itemconfig(self.text_time_id, font=(MONO_FONT[0], fsize, "bold"))

    def _timer_loop(self) -> None:
        if self.engine.state == StopwatchState.RUNNING:
            self._update_display()
            # Non-blocking 30-50ms refresh provides smooth updates with minimal CPU overhead
            self._after_id = self.after(35, self._timer_loop)

    def _update_ui_state(self) -> None:
        state = self.engine.state
        if state == StopwatchState.IDLE:
            self.btn_start.config(text="Start", bg=self.theme["accent"], fg="#FFFFFF", state=tk.NORMAL)
            self.btn_lap.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_reset.config(state=tk.DISABLED)
            self.lbl_status.config(text="Ready")
        elif state == StopwatchState.RUNNING:
            self.btn_start.config(text="Pause", bg=self.theme["btn_bg"], fg=self.theme["btn_fg"], state=tk.NORMAL)
            self.btn_lap.config(state=tk.NORMAL)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_reset.config(state=tk.NORMAL)
            self.lbl_status.config(text="Timing in progress...")
        elif state == StopwatchState.PAUSED:
            self.btn_start.config(text="Resume", bg=self.theme["accent"], fg="#FFFFFF", state=tk.NORMAL)
            self.btn_lap.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.NORMAL)
            self.btn_reset.config(state=tk.NORMAL)
            self.lbl_status.config(text="Paused")
        elif state == StopwatchState.STOPPED:
            self.btn_start.config(text="Restart", bg=self.theme["accent"], fg="#FFFFFF", state=tk.NORMAL)
            self.btn_lap.config(state=tk.DISABLED)
            self.btn_stop.config(state=tk.DISABLED)
            self.btn_reset.config(state=tk.NORMAL)
            self.lbl_status.config(text="Stopped")

    def _refresh_table(self) -> None:
        self.tree.delete(*self.tree.get_children())
        laps = self.engine.laps
        if not laps:
            return

        fastest_time = min(lap.lap_time for lap in laps)
        slowest_time = max(lap.lap_time for lap in laps)
        prec = self.config_data.get("precision", 3)

        # Show newest laps at top
        for lap in reversed(laps):
            tag = "normal"
            if len(laps) > 1:
                if math.isclose(lap.lap_time, fastest_time, rel_tol=1e-5):
                    tag = "fastest"
                elif math.isclose(lap.lap_time, slowest_time, rel_tol=1e-5):
                    tag = "slowest"

            delta_str = "--"
            if lap.lap_num > 1:
                sign = "+" if lap.delta >= 0 else "-"
                delta_str = f"{sign}{format_time(abs(lap.delta), min(2, prec))}"

            self.tree.insert("", tk.END, iid=str(lap.lap_num), values=(
                f"#{lap.lap_num}",
                format_time(lap.lap_time, prec),
                format_time(lap.split_time, prec),
                delta_str,
                lap.label,
                lap.note,
            ), tags=(tag,))

    def _render_stats(self) -> None:
        laps = self.engine.laps
        prec = min(2, self.config_data.get("precision", 3))

        if not laps:
            self.stat_labels["lbl_cnt"].config(text="0")
            self.stat_labels["lbl_fast"].config(text="--")
            self.stat_labels["lbl_slow"].config(text="--")
            self.stat_labels["lbl_avg"].config(text="--")
            self.stat_labels["lbl_med"].config(text="--")
            return

        times = [lap.lap_time for lap in laps]
        count = len(times)
        fastest = min(times)
        slowest = max(times)
        avg = sum(times) / count

        sorted_times = sorted(times)
        mid = count // 2
        median = sorted_times[mid] if count % 2 != 0 else (sorted_times[mid - 1] + sorted_times[mid]) / 2.0

        self.stat_labels["lbl_cnt"].config(text=str(count))
        self.stat_labels["lbl_fast"].config(text=format_time(fastest, prec))
        self.stat_labels["lbl_slow"].config(text=format_time(slowest, prec))
        self.stat_labels["lbl_avg"].config(text=format_time(avg, prec))
        self.stat_labels["lbl_med"].config(text=format_time(median, prec))

    # ------------------------------------------------------------------------
    # USER ACTIONS
    # ------------------------------------------------------------------------

    def action_start_pause(self) -> None:
        if self.engine.state == StopwatchState.RUNNING:
            self.engine.pause()
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
            self._update_display()
        elif self.engine.state in (StopwatchState.IDLE, StopwatchState.PAUSED):
            self.engine.start()
            self._timer_loop()
        elif self.engine.state == StopwatchState.STOPPED:
            self.action_restart()

        self._update_ui_state()

    def action_stop(self) -> None:
        if self.engine.state in (StopwatchState.RUNNING, StopwatchState.PAUSED):
            self.engine.stop()
            if self._after_id:
                self.after_cancel(self._after_id)
                self._after_id = None
            if self.config_data.get("sound_enabled", True):
                play_sound(750, 100)
            self._update_display()
            self._update_ui_state()

    def action_reset(self) -> None:
        if self.engine.laps and self.config_data.get("confirm_reset", True):
            if not messagebox.askyesno("Reset Stopwatch", "Clear recorded lap history and reset elapsed time to zero?"):
                return

        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        self.engine.reset()
        self._update_display()
        self._refresh_table()
        self._render_stats()
        self._update_ui_state()
        self.lbl_status.config(text="Reset to zero")

    def action_restart(self) -> None:
        self.engine.restart()
        self._refresh_table()
        self._render_stats()
        self._update_ui_state()
        self._timer_loop()

    def action_lap(self) -> None:
        lap = self.engine.record_lap()
        if lap:
            if self.config_data.get("sound_enabled", True):
                play_sound(1000, 60)
            self._refresh_table()
            self._render_stats()
            self.lbl_status.config(text=f"Lap #{lap.lap_num} recorded: {format_time(lap.lap_time, 2)}")

    def action_undo_lap(self) -> None:
        removed = self.engine.undo_lap()
        if removed:
            self._refresh_table()
            self._render_stats()
            self.lbl_status.config(text=f"Removed Lap #{removed.lap_num}")

    def action_edit_selected_lap(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select Lap", "Please select a lap row from the table to edit.")
            return

        lap_num = int(sel[0])
        target_lap = next((l for l in self.engine.laps if l.lap_num == lap_num), None)
        if not target_lap:
            return

        def on_save(new_label: str, new_note: str) -> None:
            target_lap.label = new_label
            target_lap.note = new_note
            self._refresh_table()

        LapEditDialog(self, target_lap, self.theme, on_save)

    def action_delete_selected_lap(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        lap_num = int(sel[0])
        if messagebox.askyesno("Delete Lap", f"Delete record for Lap #{lap_num}?"):
            self.engine.laps = [l for l in self.engine.laps if l.lap_num != lap_num]
            # Recalculate lap numbers and deltas cleanly
            prev_split = 0.0
            for idx, lap in enumerate(self.engine.laps, start=1):
                lap.lap_num = idx
                lap.delta = lap.lap_time - self.engine.laps[idx - 2].lap_time if idx > 1 else 0.0
                prev_split = lap.split_time

            self._refresh_table()
            self._render_stats()

    def action_rename_session(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Rename Session")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        dialog.configure(bg=self.theme["bg_card"])

        f = tk.Frame(dialog, bg=self.theme["bg_card"], padx=16, pady=16)
        f.pack()

        tk.Label(f, text="Session Name:", bg=self.theme["bg_card"], fg=self.theme["fg_primary"]).pack(anchor="w")
        ent = tk.Entry(f, width=28, bg=self.theme["entry_bg"], fg=self.theme["entry_fg"], insertbackground=self.theme["fg_primary"])
        ent.insert(0, self.current_session_name)
        ent.pack(pady=(4, 12))

        def save():
            val = ent.get().strip()
            if val:
                self.current_session_name = val
                self.lbl_session_title.config(text=val)
            dialog.destroy()

        tk.Button(f, text="Save", command=save, bg=self.theme["accent"], fg="#FFFFFF", relief=tk.FLAT, padx=10, pady=3).pack(side=tk.RIGHT)
        tk.Button(f, text="Cancel", command=dialog.destroy, bg=self.theme["btn_bg"], fg=self.theme["btn_fg"], relief=tk.FLAT, padx=10, pady=3).pack(side=tk.RIGHT, padx=6)
        ent.focus_set()
        ent.bind("<Return>", lambda e: save())

    def action_new_session(self) -> None:
        if self.engine.elapsed > 0:
            if not messagebox.askyesno("New Session", "Start a new session? Make sure current session is saved if needed."):
                return
        self.engine.reset()
        self.current_session_id = str(time.time())
        self.current_session_name = f"Session {len(self.sessions) + 1}"
        self.lbl_session_title.config(text=self.current_session_name)
        self._update_display()
        self._refresh_table()
        self._render_stats()
        self._update_ui_state()

    def action_save_session(self) -> None:
        session = TimingSession(
            id=self.current_session_id,
            name=self.current_session_name,
            created_at=datetime.datetime.now().isoformat(),
            total_elapsed=self.engine.elapsed,
            laps=list(self.engine.laps),
            mode="stopwatch",
        )
        # Update or append
        idx = next((i for i, s in enumerate(self.sessions) if s.id == session.id), None)
        if idx is not None:
            self.sessions[idx] = session
        else:
            self.sessions.append(session)

        StorageManager.save_sessions(self.sessions)
        self.lbl_status.config(text=f"Session '{session.name}' saved to history")
        messagebox.showinfo("Saved", f"Session '{session.name}' has been saved to history.")

    def action_open_history(self) -> None:
        SessionManagerDialog(self, self.theme)

    def load_session(self, session: TimingSession) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        self.engine.reset()
        self.current_session_id = session.id
        self.current_session_name = session.name
        self.lbl_session_title.config(text=session.name)

        self.engine._accumulated_elapsed = session.total_elapsed
        self.engine.state = StopwatchState.STOPPED
        self.engine.laps = [LapRecord.from_dict(lap.to_dict()) for lap in session.laps]

        self._update_display()
        self._refresh_table()
        self._render_stats()
        self._update_ui_state()
        self.lbl_status.config(text=f"Loaded session '{session.name}'")

    # ------------------------------------------------------------------------
    # CLIPBOARD & EXPORT / IMPORT
    # ------------------------------------------------------------------------

    def copy_elapsed(self) -> None:
        val = format_time(self.engine.elapsed, self.config_data.get("precision", 3))
        self.clipboard_clear()
        self.clipboard_append(val)
        self.lbl_status.config(text=f"Copied {val} to clipboard")

    def copy_selected_lap_time(self) -> None:
        sel = self.tree.selection()
        if sel:
            lap_num = int(sel[0])
            lap = next((l for l in self.engine.laps if l.lap_num == lap_num), None)
            if lap:
                val = format_time(lap.lap_time, self.config_data.get("precision", 3))
                self.clipboard_clear()
                self.clipboard_append(val)
                self.lbl_status.config(text=f"Copied lap time {val}")

    def copy_selected_lap_full(self) -> None:
        sel = self.tree.selection()
        if sel:
            lap_num = int(sel[0])
            lap = next((l for l in self.engine.laps if l.lap_num == lap_num), None)
            if lap:
                line = f"Lap #{lap.lap_num}: {format_time(lap.lap_time, 3)} (Split: {format_time(lap.split_time, 3)}) {lap.label} {lap.note}"
                self.clipboard_clear()
                self.clipboard_append(line)
                self.lbl_status.config(text="Copied lap row to clipboard")

    def copy_summary(self) -> None:
        total_str = format_time(self.engine.elapsed, 3)
        lap_cnt = len(self.engine.laps)
        summary = f"{self.current_session_name} - Total: {total_str}, Laps: {lap_cnt}"
        self.clipboard_clear()
        self.clipboard_append(summary)
        self.lbl_status.config(text="Copied session summary")

    def export_csv(self) -> None:
        if not self.engine.laps and self.engine.elapsed == 0.0:
            messagebox.showinfo("Export", "No timing data to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"{self.current_session_name.replace(' ', '_').lower()}_export.csv"
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Session Name", self.current_session_name])
                writer.writerow(["Total Duration", format_time(self.engine.elapsed, 3)])
                writer.writerow(["Exported At", datetime.datetime.now().isoformat()])
                writer.writerow([])
                writer.writerow(["Lap #", "Lap Time (s)", "Lap Time (Formatted)",
                                 "Cumulative Time (s)", "Cumulative (Formatted)", "Delta", "Label", "Note"])

                for lap in self.engine.laps:
                    writer.writerow([
                        lap.lap_num,
                        f"{lap.lap_time:.3f}",
                        format_time(lap.lap_time, 3),
                        f"{lap.split_time:.3f}",
                        format_time(lap.split_time, 3),
                        f"{lap.delta:.3f}",
                        lap.label,
                        lap.note,
                    ])
            self.lbl_status.config(text=f"Exported to {Path(filename).name}")
            messagebox.showinfo("Export Complete", "Session successfully exported to CSV.")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write CSV file:\n{e}")

    def export_json(self) -> None:
        session = TimingSession(
            id=self.current_session_id,
            name=self.current_session_name,
            created_at=datetime.datetime.now().isoformat(),
            total_elapsed=self.engine.elapsed,
            laps=list(self.engine.laps),
            mode="stopwatch",
        )
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            initialfile=f"{self.current_session_name.replace(' ', '_').lower()}.json"
        )
        if not filename:
            return

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(session.to_dict(), f, indent=2)
            self.lbl_status.config(text=f"Exported to {Path(filename).name}")
            messagebox.showinfo("Export Complete", "Session successfully exported to JSON.")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not write JSON file:\n{e}")

    def import_json(self) -> None:
        filename = filedialog.askopenfilename(
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not filename:
            return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            session = TimingSession.from_dict(data)
            self.load_session(session)
            messagebox.showinfo("Import Complete", f"Session '{session.name}' imported successfully.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Invalid or incompatible JSON session file:\n{e}")

    # ------------------------------------------------------------------------
    # SETTINGS & VIEW TOGGLES
    # ------------------------------------------------------------------------

    def toggle_theme(self) -> None:
        new_theme = "dark" if self.current_theme_name == "light" else "light"
        self.set_theme(new_theme)

    def toggle_always_on_top(self) -> None:
        curr = self.attributes("-topmost")
        new_val = not curr
        self.attributes("-topmost", new_val)
        self.config_data["always_on_top"] = new_val
        StorageManager.save_config(self.config_data)

    def open_preferences(self) -> None:
        def on_apply(new_cfg: Dict[str, Any]):
            self.config_data.update(new_cfg)
            StorageManager.save_config(self.config_data)
            self.attributes("-topmost", self.config_data.get("always_on_top", False))
            if self.config_data.get("theme") != self.current_theme_name:
                self.set_theme(self.config_data.get("theme", "light"))
            else:
                self._update_display(force=True)
                self._refresh_table()

        SettingsDialog(self, self.config_data, self.theme, on_apply)

    def _sort_column(self, col: str, reverse: bool) -> None:
        """Sort Treeview rows by column without mutating internal engine sequence."""
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        def sort_key(t):
            val = t[0].replace("#", "").replace("+", "")
            try:
                # Try parsing as time string (HH:MM:SS.mmm)
                parts = val.split(":")
                if len(parts) == 3:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                return float(val)
            except ValueError:
                return val

        items.sort(key=sort_key, reverse=reverse)
        for index, (_, k) in enumerate(items):
            self.tree.move(k, "", index)

        # Toggle sort order for next click
        self.tree.heading(col, command=lambda: self._sort_column(col, not reverse))

    # ------------------------------------------------------------------------
    # HELP & ABOUT
    # ------------------------------------------------------------------------

    def show_shortcuts(self) -> None:
        msg = (
            "Keyboard Shortcuts:\n\n"
            "• Space: Start / Pause / Resume\n"
            "• L: Record Lap\n"
            "• S: Stop\n"
            "• R: Reset\n"
            "• Ctrl + Z: Undo Last Lap\n"
            "• Ctrl + S: Save Session\n"
            "• Ctrl + H: Session History\n"
            "• Ctrl + N: New Session\n"
            "• Ctrl + E: Export to CSV\n"
            "• Ctrl + C: Copy Elapsed Time\n"
            "• Ctrl + ,: Preferences\n"
            "• F5: Toggle Light/Dark Theme\n"
            "• Enter / Double-Click: Edit Selected Lap\n"
            "• Delete: Delete Selected Lap\n"
        )
        messagebox.showinfo("Shortcuts", msg)

    def show_about(self) -> None:
        msg = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "A high-precision, drift-free desktop stopwatch application.\n"
            "Crafted with pure Python standard library.\n\n"
            "Data files stored locally in application folder:\n"
            f"• {CONFIG_FILE_NAME}\n"
            f"• {SESSIONS_FILE_NAME}"
        )
        messagebox.showinfo("About", msg)

    # ------------------------------------------------------------------------
    # CLEAN EXIT HANDLER
    # ------------------------------------------------------------------------

    def _on_close(self) -> None:
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        # Save window geometry
        self.config_data["window_geometry"] = self.geometry()
        StorageManager.save_config(self.config_data)

        self.destroy()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main() -> None:
    # Ensure working directory is set to script location for double-click launch
    script_dir = Path(__file__).resolve().parent
    try:
        os.chdir(script_dir)
    except Exception:
        pass

    app = StopwatchApp()
    app.mainloop()


if __name__ == "__main__":
    main()
