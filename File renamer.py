import datetime
import json
from pathlib import Path
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class TransactionalRollbackEngine:
    """Handles mutation logging, persistence, and atomic rollback operations."""

    @staticmethod
    def generate_ledger_filename() -> str:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"rename_rollback_{timestamp}.json"

    @staticmethod
    def write_ledger(target_dir: Path, ledger_data: dict[str, str]) -> Path:
        ledger_path = target_dir / TransactionalRollbackEngine.generate_ledger_filename()
        with open(ledger_path, "w", encoding="utf-8") as f:
            json.dump(ledger_data, f, indent=2)
        return ledger_path

    @staticmethod
    def get_latest_ledger(target_dir: Path) -> Path | None:
        ledgers = sorted(
            target_dir.glob("rename_rollback_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return ledgers[0] if ledgers else None

    @staticmethod
    def execute_rollback(ledger_path: Path) -> tuple[int, list[str]]:
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger: dict[str, str] = json.load(f)

        restored_count = 0
        errors: list[str] = []

        for original_str, current_str in reversed(list(ledger.items())):
            current_path = Path(current_str)
            original_path = Path(original_str)

            if not current_path.exists():
                errors.append(f"MISSING: File {current_path.name} not found on disk.")
                continue

            if original_path.exists() and original_path != current_path:
                errors.append(f"COLLISION: Target restore path {original_path.name} already exists.")
                continue

            try:
                current_path.rename(original_path)
                restored_count += 1
            except (OSError, PermissionError) as e:
                errors.append(f"ERROR: Failed to restore {current_path.name} -> {e}")

        return restored_count, errors


class BatchFileMutatorApp(tk.Tk):
    """Clean, Human-Designed Desktop Utility."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Batch File Renamer")
        self.geometry("820x620")
        self.minsize(720, 500)

        # Color Palette - Professional Slate Theme
        self.bg_color = "#1E2022"
        self.card_bg = "#282A2D"
        self.text_muted = "#9DA4B0"
        self.text_fg = "#F0F2F5"
        self.accent_color = "#2563EB"
        self.accent_hover = "#1D4ED8"
        self.terminal_bg = "#18191B"

        self.configure(bg=self.bg_color)

        # Reactive Variables
        self.dir_path_var = tk.StringVar(self)
        self.prefix_var = tk.StringVar(self, value="asset")
        self.ext_filter_var = tk.StringVar(self, value=".png, .jpg, .raw")
        self.padding_var = tk.IntVar(self, value=3)
        self.recursive_var = tk.BooleanVar(self, value=False)

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")

        # Frame and Label Styles
        style.configure("MainFrame.TFrame", background=self.bg_color)
        style.configure("Card.TFrame", background=self.card_bg, relief="flat")
        
        style.configure(
            "CardTitle.TLabel",
            background=self.card_bg,
            foreground=self.text_muted,
            font=("TkDefaultFont", 9, "bold")
        )
        style.configure(
            "FieldLabel.TLabel",
            background=self.card_bg,
            foreground=self.text_fg,
            font=("TkDefaultFont", 9)
        )
        style.configure(
            "Header.TLabel",
            background=self.bg_color,
            foreground=self.text_fg,
            font=("TkDefaultFont", 13, "bold")
        )
        style.configure(
            "SubHeader.TLabel",
            background=self.bg_color,
            foreground=self.text_muted,
            font=("TkDefaultFont", 9)
        )

        # Entry Styling
        style.configure(
            "TEntry",
            fieldbackground="#18191B",
            foreground="#FFFFFF",
            insertcolor="#FFFFFF",
            borderwidth=1,
            lightcolor="#3A3D40",
            darkcolor="#3A3D40"
        )

        # Checkbutton Styling
        style.configure(
            "TCheckbutton",
            background=self.card_bg,
            foreground=self.text_fg,
            font=("TkDefaultFont", 9)
        )
        style.map("TCheckbutton", background=[("active", self.card_bg)])

        # Button Styling
        style.configure(
            "TButton",
            font=("TkDefaultFont", 9),
            padding=(12, 6),
            background="#3A3D42",
            foreground="#FFFFFF",
            borderwidth=0
        )
        style.map("TButton", background=[("active", "#4A4D52")])

        style.configure(
            "Primary.TButton",
            font=("TkDefaultFont", 9, "bold"),
            background=self.accent_color,
            foreground="#FFFFFF"
        )
        style.map("Primary.TButton", background=[("active", self.accent_hover)])

    def _build_ui(self) -> None:
        # Main Outer Wrapper
        main_container = ttk.Frame(self, style="MainFrame.TFrame", padding=16)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Header Section
        header_frame = ttk.Frame(main_container, style="MainFrame.TFrame")
        header_frame.pack(fill=tk.X, pady=(0, 14))

        title_lbl = ttk.Label(header_frame, text="Batch File Renamer", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)

        subtitle_lbl = ttk.Label(
            header_frame,
            text="Safe, transactional file renaming with full rollback support.",
            style="SubHeader.TLabel"
        )
        subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 1. Target Directory Section
        dir_card = ttk.Frame(main_container, style="Card.TFrame", padding=12)
        dir_card.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(dir_card, text="DIRECTORY", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 8))

        dir_inner = ttk.Frame(dir_card, style="Card.TFrame")
        dir_inner.pack(fill=tk.X)

        dir_entry = ttk.Entry(dir_inner, textvariable=self.dir_path_var)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        browse_btn = ttk.Button(dir_inner, text="Browse", command=self._browse_directory)
        browse_btn.pack(side=tk.RIGHT)

        # 2. Options Grid Section
        cfg_card = ttk.Frame(main_container, style="Card.TFrame", padding=12)
        cfg_card.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(cfg_card, text="RULES & FILTERS", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=7, sticky=tk.W, pady=(0, 10)
        )

        ttk.Label(cfg_card, text="Prefix:", style="FieldLabel.TLabel").grid(row=1, column=0, sticky=tk.W, padx=(0, 6))
        ttk.Entry(cfg_card, textvariable=self.prefix_var, width=14).grid(row=1, column=1, sticky=tk.W, padx=(0, 16))

        ttk.Label(cfg_card, text="Extensions:", style="FieldLabel.TLabel").grid(row=1, column=2, sticky=tk.W, padx=(0, 6))
        ttk.Entry(cfg_card, textvariable=self.ext_filter_var, width=18).grid(row=1, column=3, sticky=tk.W, padx=(0, 16))

        ttk.Label(cfg_card, text="Digits:", style="FieldLabel.TLabel").grid(row=1, column=4, sticky=tk.W, padx=(0, 6))
        ttk.Entry(cfg_card, textvariable=self.padding_var, width=4).grid(row=1, column=5, sticky=tk.W, padx=(0, 16))

        ttk.Checkbutton(cfg_card, text="Subfolders", variable=self.recursive_var).grid(row=1, column=6, sticky=tk.W)

        # 3. Log Output Window
        log_card = ttk.Frame(main_container, style="Card.TFrame", padding=12)
        log_card.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        ttk.Label(log_card, text="ACTIVITY LOG", style="CardTitle.TLabel").pack(anchor=tk.W, pady=(0, 8))

        terminal_container = ttk.Frame(log_card, style="Card.TFrame")
        terminal_container.pack(fill=tk.BOTH, expand=True)

        self.log_terminal = tk.Text(
            terminal_container,
            bg=self.terminal_bg,
            fg="#D1D5DB",
            selectbackground="#374151",
            selectforeground="#FFFFFF",
            insertbackground="#FFFFFF",
            wrap=tk.NONE,
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=8
        )

        scroll_y = ttk.Scrollbar(terminal_container, orient=tk.VERTICAL, command=self.log_terminal.yview)
        scroll_x = ttk.Scrollbar(terminal_container, orient=tk.HORIZONTAL, command=self.log_terminal.xview)
        self.log_terminal.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.log_terminal.pack(fill=tk.BOTH, expand=True)

        # 4. Action Bar
        action_bar = ttk.Frame(main_container, style="MainFrame.TFrame")
        action_bar.pack(fill=tk.X)

        self.btn_dry_run = ttk.Button(
            action_bar,
            text="Preview Changes",
            command=lambda: self._process_batch(dry_run=True),
        )
        self.btn_dry_run.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_execute = ttk.Button(
            action_bar,
            text="Apply Rename",
            style="Primary.TButton",
            command=lambda: self._process_batch(dry_run=False),
        )
        self.btn_execute.pack(side=tk.LEFT)

        self.btn_undo = ttk.Button(
            action_bar,
            text="Undo Last Action",
            command=self._execute_undo,
        )
        self.btn_undo.pack(side=tk.RIGHT)

    def _log(self, message: str) -> None:
        timestamp = datetime.datetime.now().strftime("[%H:%M:%S]")
        self.log_terminal.insert(tk.END, f"{timestamp} {message}\n")
        self.log_terminal.see(tk.END)

    def _browse_directory(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.dir_path_var.set(selected)

    def _get_validated_path(self) -> Path:
        raw_path = self.dir_path_var.get().strip()
        if not raw_path:
            raise ValueError("Directory pathway cannot be empty.")

        resolved_path = Path(raw_path).resolve()
        if not resolved_path.exists():
            raise FileNotFoundError(f"Directory missing or inaccessible: {resolved_path}")
        if not resolved_path.is_dir():
            raise NotADirectoryError(f"Target path is not a valid directory: {resolved_path}")

        return resolved_path

    def _parse_extension_filter(self) -> set[str]:
        raw = self.ext_filter_var.get().strip()
        if not raw:
            return set()

        parsed = set()
        for ext in raw.split(","):
            ext_clean = ext.strip().lower()
            if ext_clean:
                if not ext_clean.startswith("."):
                    ext_clean = f".{ext_clean}"
                parsed.add(ext_clean)
        return parsed

    def _extract_compound_extension(self, path: Path) -> str:
        suffixes = path.suffixes
        return "".join(suffixes) if suffixes else ""

    def _discover_and_filter_files(self, target_dir: Path, extensions: set[str]) -> list[Path]:
        pattern = "**/*" if self.recursive_var.get() else "*"
        candidates = target_dir.glob(pattern)

        valid_files: list[Path] = []
        for path in candidates:
            if not path.is_file() or path.is_symlink():
                continue

            if path.name in {".DS_Store", "Thumbs.db"} or path.name.startswith("rename_rollback_"):
                continue

            if extensions:
                comp_ext = self._extract_compound_extension(path).lower()
                single_ext = path.suffix.lower()
                if comp_ext not in extensions and single_ext not in extensions:
                    continue

            valid_files.append(path)

        return sorted(valid_files, key=lambda p: p.name.lower())

    def _process_batch(self, dry_run: bool) -> None:
        try:
            target_dir = self._get_validated_path()
            extensions = self._parse_extension_filter()
            try:
                padding = max(1, int(self.padding_var.get()))
            except Exception:
                padding = 3
            prefix = self.prefix_var.get().strip()
        except Exception as e:
            messagebox.showerror("Configuration Error", str(e))
            self._log(f"[ERROR] Configuration failed: {e}")
            return

        files = self._discover_and_filter_files(target_dir, extensions)
        if not files:
            self._log("[WARNING] No matching files found for processing.")
            return

        mode_str = "DRY-RUN PREVIEW" if dry_run else "LIVE COMMIT"
        self._log(f"--- Session: {mode_str} ({len(files)} items matched) ---")

        mutation_ledger: dict[str, str] = {}
        collisions = 0
        executed = 0

        for index, src_path in enumerate(files, start=1):
            comp_ext = self._extract_compound_extension(src_path)
            index_str = str(index).zfill(padding)
            target_name = f"{prefix}_{index_str}{comp_ext}" if prefix else f"{index_str}{comp_ext}"
            dst_path = src_path.parent / target_name

            if dst_path.exists() and dst_path != src_path:
                self._log(f"[SKIP] Collides with existing: '{target_name}'")
                collisions += 1
                continue

            log_msg = f"{src_path.relative_to(target_dir)}  ➔  {dst_path.relative_to(target_dir)}"

            if dry_run:
                self._log(f"[PREVIEW] {log_msg}")
                executed += 1
            else:
                try:
                    src_path.rename(dst_path)
                    mutation_ledger[str(src_path.resolve())] = str(dst_path.resolve())
                    self._log(f"[DONE] {log_msg}")
                    executed += 1
                except (OSError, PermissionError) as e:
                    self._log(f"[ERROR] Could not rename {src_path.name}: {e}")

        if not dry_run and mutation_ledger:
            ledger_file = TransactionalRollbackEngine.write_ledger(target_dir, mutation_ledger)
            self._log(f"[SAVED] Rollback ledger created: {ledger_file.name}")

        self._log(f"--- Complete: {executed} Processed | {collisions} Skipped ---\n")

    def _execute_undo(self) -> None:
        try:
            target_dir = self._get_validated_path()
        except Exception as e:
            messagebox.showerror("Configuration Error", str(e))
            return

        ledger_path = TransactionalRollbackEngine.get_latest_ledger(target_dir)
        if not ledger_path:
            self._log(f"[WARNING] No rollback ledger found in {target_dir}")
            messagebox.showwarning("Rollback Aborted", "No transaction ledger found in target directory.")
            return

        if not messagebox.askyesno("Confirm Undo", f"Revert files using ledger:\n{ledger_path.name}?"):
            return

        self._log(f"--- Executing Undo via {ledger_path.name} ---")
        restored, errors = TransactionalRollbackEngine.execute_rollback(ledger_path)

        for err in errors:
            self._log(f"[UNDO FAIL] {err}")

        self._log(f"[UNDO SUCCESS] Restored {restored} files.")

        try:
            ledger_path.unlink()
            self._log(f"[CLEANUP] Removed ledger {ledger_path.name}")
        except OSError as e:
            self._log(f"[WARNING] Failed to remove ledger: {e}")

        self._log("--- Undo Complete ---\n")


if __name__ == "__main__":
    try:
        app = BatchFileMutatorApp()
        app.mainloop()
    except Exception:
        err_trace = traceback.format_exc()
        try:
            with open("crash_log.txt", "w", encoding="utf-8") as f:
                f.write(err_trace)
        except Exception:
            pass
        print("=== CRASH DETECTED ===")
        print(err_trace)
