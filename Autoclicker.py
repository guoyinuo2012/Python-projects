import pyautogui
import keyboard
import threading
import time
import random
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font
import json
import os

class AutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title("AutoClicker")
        self.root.geometry("550x750")
        self.root.resizable(False, False)
        
        # Set modern theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Color scheme
        self.colors = {
            'bg': '#2b2b2b',
            'fg': '#ffffff',
            'accent': '#007acc',
            'accent_hover': '#005a9e',
            'success': '#4caf50',
            'danger': '#f44336',
            'warning': '#ff9800',
            'frame_bg': '#3c3c3c',
            'entry_bg': '#4a4a4a',
            'text': '#e0e0e0'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        self.clicking = False
        self.click_thread = None
        self.click_count = 0
        self.start_time = None
        self.clicks_per_second = 0.0
        self.click_history = []
        
        self.setup_ui()
        
    def setup_ui(self):
        # Custom fonts
        title_font = font.Font(family="Segoe UI", size=18, weight="bold")
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        label_font = font.Font(family="Segoe UI", size=9)
        button_font = font.Font(family="Segoe UI", size=10, weight="bold")
        
        # Main container with padding
        main_container = tk.Frame(self.root, bg=self.colors['bg'])
        main_container.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title with icon
        title_frame = tk.Frame(main_container, bg=self.colors['bg'])
        title_frame.pack(fill="x", pady=(0, 15))
        
        title_label = tk.Label(title_frame, text="⚡ AutoClicker", 
                              font=title_font, bg=self.colors['bg'], fg=self.colors['accent'])
        title_label.pack()
        
        subtitle_label = tk.Label(title_frame, text="Advanced Mouse Automation Tool", 
                                 font=label_font, bg=self.colors['bg'], fg=self.colors['text'])
        subtitle_label.pack()
        
        # Create notebook for tabs
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill="both", expand=True)
        
        # Tab 1: Basic Settings
        basic_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(basic_tab, text="Basic")
        
        # Click Limit Section
        limit_frame = self.create_section_frame(basic_tab, "Click Limits", header_font)
        limit_frame.pack(fill="x", pady=10)
        
        limit_container = tk.Frame(limit_frame, bg=self.colors['frame_bg'])
        limit_container.pack(fill="x", padx=10, pady=10)
        
        # Click count limit
        self.enable_click_limit = tk.BooleanVar(value=False)
        limit_check = tk.Checkbutton(limit_container, text="Enable click limit", 
                                    variable=self.enable_click_limit, font=label_font,
                                    bg=self.colors['frame_bg'], fg=self.colors['text'],
                                    selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                                    activeforeground=self.colors['text'], command=self.toggle_limit_inputs)
        limit_check.pack(anchor="w", pady=2)
        
        click_limit_frame = tk.Frame(limit_container, bg=self.colors['frame_bg'])
        click_limit_frame.pack(anchor="w", pady=2)
        
        tk.Label(click_limit_frame, text="Max clicks:", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).pack(side="left")
        self.click_limit_var = tk.IntVar(value=100)
        self.click_limit_entry = tk.Entry(click_limit_frame, textvariable=self.click_limit_var, 
                                         width=8, font=label_font, bg=self.colors['entry_bg'], 
                                         fg=self.colors['text'], insertbackground=self.colors['accent'],
                                         state="disabled")
        self.click_limit_entry.pack(side="left", padx=5)
        
        # Time limit
        self.enable_time_limit = tk.BooleanVar(value=False)
        time_limit_check = tk.Checkbutton(limit_container, text="Enable time limit", 
                                         variable=self.enable_time_limit, font=label_font,
                                         bg=self.colors['frame_bg'], fg=self.colors['text'],
                                         selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                                         activeforeground=self.colors['text'], command=self.toggle_limit_inputs)
        time_limit_check.pack(anchor="w", pady=2)
        
        time_limit_frame = tk.Frame(limit_container, bg=self.colors['frame_bg'])
        time_limit_frame.pack(anchor="w", pady=2)
        
        tk.Label(time_limit_frame, text="Max time (seconds):", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).pack(side="left")
        self.time_limit_var = tk.IntVar(value=60)
        self.time_limit_entry = tk.Entry(time_limit_frame, textvariable=self.time_limit_var, 
                                        width=8, font=label_font, bg=self.colors['entry_bg'], 
                                        fg=self.colors['text'], insertbackground=self.colors['accent'],
                                        state="disabled")
        self.time_limit_entry.pack(side="left", padx=5)
        
        # Click Interval Section
        interval_frame = self.create_section_frame(basic_tab, "Click Interval", header_font)
        interval_frame.pack(fill="x", pady=10)
        
        interval_container = tk.Frame(interval_frame, bg=self.colors['frame_bg'])
        interval_container.pack(fill="x", padx=10, pady=10)
        
        tk.Label(interval_container, text="Interval (seconds):", 
                font=label_font, bg=self.colors['frame_bg'], fg=self.colors['text']).grid(row=0, column=0, sticky="w", pady=5)
        
        self.interval_var = tk.DoubleVar(value=0.1)
        self.interval_entry = tk.Entry(interval_container, textvariable=self.interval_var, 
                                      width=12, font=label_font, bg=self.colors['entry_bg'], 
                                      fg=self.colors['text'], insertbackground=self.colors['accent'])
        self.interval_entry.grid(row=0, column=1, padx=10, pady=5)
        
        # Quick interval buttons
        quick_frame = tk.Frame(interval_container, bg=self.colors['frame_bg'])
        quick_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        for interval in [0.01, 0.1, 0.5, 1.0]:
            btn = tk.Button(quick_frame, text=str(interval), 
                          command=lambda i=interval: self.interval_var.set(i),
                          font=("Segoe UI", 8), bg=self.colors['accent'], fg="white",
                          relief="flat", padx=8, pady=2)
            btn.pack(side="left", padx=2)
        
        # Random interval option
        self.random_interval_var = tk.BooleanVar(value=False)
        random_check = tk.Checkbutton(interval_container, text="Random interval (±20%)", 
                                     variable=self.random_interval_var, font=label_font,
                                     bg=self.colors['frame_bg'], fg=self.colors['text'],
                                     selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                                     activeforeground=self.colors['text'])
        random_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=5)
        
        # Click Type Section
        click_frame = self.create_section_frame(basic_tab, "Click Type", header_font)
        click_frame.pack(fill="x", pady=10)
        
        click_container = tk.Frame(click_frame, bg=self.colors['frame_bg'])
        click_container.pack(fill="x", padx=10, pady=10)
        
        self.click_type = tk.StringVar(value="left")
        click_types = [("Left Click", "left"), ("Right Click", "right"), ("Middle Click", "middle")]
        
        for i, (text, value) in enumerate(click_types):
            rb = tk.Radiobutton(click_container, text=text, variable=self.click_type, value=value,
                              font=label_font, bg=self.colors['frame_bg'], fg=self.colors['text'],
                              selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                              activeforeground=self.colors['text'])
            rb.pack(anchor="w", pady=3)
        
        # Click Mode Section
        mode_frame = self.create_section_frame(basic_tab, "Click Mode", header_font)
        mode_frame.pack(fill="x", pady=10)
        
        mode_container = tk.Frame(mode_frame, bg=self.colors['frame_bg'])
        mode_container.pack(fill="x", padx=10, pady=10)
        
        self.click_mode = tk.StringVar(value="single")
        click_modes = [("Single Click", "single"), ("Double Click", "double"), ("Hold", "hold")]
        
        for i, (text, value) in enumerate(click_modes):
            rb = tk.Radiobutton(mode_container, text=text, variable=self.click_mode, value=value,
                              font=label_font, bg=self.colors['frame_bg'], fg=self.colors['text'],
                              selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                              activeforeground=self.colors['text'], command=self.update_click_mode)
            rb.pack(anchor="w", pady=3)
        
        # Hold duration for hold mode
        self.hold_frame = tk.Frame(mode_container, bg=self.colors['frame_bg'])
        
        hold_duration_frame = tk.Frame(self.hold_frame, bg=self.colors['frame_bg'])
        hold_duration_frame.pack(anchor="w", pady=5)
        
        tk.Label(hold_duration_frame, text="Hold duration (seconds):", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).pack(side="left")
        self.hold_duration_var = tk.DoubleVar(value=0.5)
        tk.Entry(hold_duration_frame, textvariable=self.hold_duration_var, 
                width=8, font=label_font, bg=self.colors['entry_bg'], 
                fg=self.colors['text'], insertbackground=self.colors['accent']).pack(side="left", padx=5)
        
        tk.Label(hold_duration_frame, text="Hold duration (seconds):", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).pack(side="left")
        self.hold_duration_var = tk.DoubleVar(value=0.5)
        tk.Entry(hold_duration_frame, textvariable=self.hold_duration_var, 
                width=8, font=label_font, bg=self.colors['entry_bg'], 
                fg=self.colors['text'], insertbackground=self.colors['accent']).pack(side="left", padx=5)
        
        # Tab 2: Advanced Settings
        advanced_tab = tk.Frame(notebook, bg=self.colors['bg'])
        notebook.add(advanced_tab, text="Advanced")
        
        # Hotkey Configuration Section
        hotkey_frame = self.create_section_frame(advanced_tab, "Hotkey Configuration", header_font)
        hotkey_frame.pack(fill="x", pady=10)
        
        hotkey_container = tk.Frame(hotkey_frame, bg=self.colors['frame_bg'])
        hotkey_container.pack(fill="x", padx=10, pady=10)
        
        tk.Label(hotkey_container, text="Toggle Hotkey:", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).grid(row=0, column=0, sticky="w", pady=5)
        self.hotkey_var = tk.StringVar(value="f6")
        hotkey_combo = ttk.Combobox(hotkey_container, textvariable=self.hotkey_var, 
                                   values=["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"],
                                   width=8, font=label_font)
        hotkey_combo.grid(row=0, column=1, padx=5, pady=5)
        hotkey_combo.bind("<<ComboboxSelected>>", self.update_hotkey)
        
        # Presets Section
        preset_frame = self.create_section_frame(advanced_tab, "Presets", header_font)
        preset_frame.pack(fill="x", pady=10)
        
        preset_container = tk.Frame(preset_frame, bg=self.colors['frame_bg'])
        preset_container.pack(fill="x", padx=10, pady=10)
        
        preset_button_frame = tk.Frame(preset_container, bg=self.colors['frame_bg'])
        preset_button_frame.pack(fill="x", pady=5)
        
        save_btn = tk.Button(preset_button_frame, text="💾 Save Preset", command=self.save_preset,
                            font=("Segoe UI", 9), bg=self.colors['accent'], fg="white",
                            relief="flat", padx=10, pady=5, cursor="hand2")
        save_btn.pack(side="left", padx=5)
        
        load_btn = tk.Button(preset_button_frame, text="📂 Load Preset", command=self.load_preset,
                            font=("Segoe UI", 9), bg=self.colors['accent'], fg="white",
                            relief="flat", padx=10, pady=5, cursor="hand2")
        load_btn.pack(side="left", padx=5)
        
        # Click Position Section
        position_frame = self.create_section_frame(advanced_tab, "Click Position", header_font)
        position_frame.pack(fill="x", pady=10)
        
        position_container = tk.Frame(position_frame, bg=self.colors['frame_bg'])
        position_container.pack(fill="x", padx=10, pady=10)
        
        self.position_mode = tk.StringVar(value="current")
        
        # Position mode buttons
        mode_frame = tk.Frame(position_container, bg=self.colors['frame_bg'])
        mode_frame.pack(fill="x", pady=5)
        
        modes = [("Current Position", "current"), ("Fixed Coordinates", "fixed"), ("Random Area", "random")]
        for i, (text, value) in enumerate(modes):
            rb = tk.Radiobutton(mode_frame, text=text, variable=self.position_mode, value=value,
                              font=label_font, bg=self.colors['frame_bg'], fg=self.colors['text'],
                              selectcolor=self.colors['accent'], activebackground=self.colors['frame_bg'],
                              activeforeground=self.colors['text'], command=self.update_position_mode)
            rb.pack(anchor="w", pady=2)
        
        # Fixed coordinates inputs
        self.fixed_frame = tk.Frame(position_container, bg=self.colors['frame_bg'])
        
        coord_frame = tk.Frame(self.fixed_frame, bg=self.colors['frame_bg'])
        coord_frame.pack()
        
        tk.Label(coord_frame, text="X:", font=label_font, bg=self.colors['frame_bg'], 
                fg=self.colors['text']).grid(row=0, column=0, padx=5)
        self.x_var = tk.IntVar(value=100)
        tk.Entry(coord_frame, textvariable=self.x_var, width=8, font=label_font,
                bg=self.colors['entry_bg'], fg=self.colors['text'], 
                insertbackground=self.colors['accent']).grid(row=0, column=1, padx=5)
        
        tk.Label(coord_frame, text="Y:", font=label_font, bg=self.colors['frame_bg'], 
                fg=self.colors['text']).grid(row=0, column=2, padx=5)
        self.y_var = tk.IntVar(value=100)
        tk.Entry(coord_frame, textvariable=self.y_var, width=8, font=label_font,
                bg=self.colors['entry_bg'], fg=self.colors['text'], 
                insertbackground=self.colors['accent']).grid(row=0, column=3, padx=5)
        
        # Random area inputs
        self.random_frame = tk.Frame(position_container, bg=self.colors['frame_bg'])
        
        area_frame = tk.Frame(self.random_frame, bg=self.colors['frame_bg'])
        area_frame.pack()
        
        tk.Label(area_frame, text="Area (X1, Y1) to (X2, Y2):", font=label_font, 
                bg=self.colors['frame_bg'], fg=self.colors['text']).grid(row=0, column=0, columnspan=4, pady=5)
        
        self.x1_var = tk.IntVar(value=0)
        self.y1_var = tk.IntVar(value=0)
        self.x2_var = tk.IntVar(value=500)
        self.y2_var = tk.IntVar(value=500)
        
        coords = [("X1:", self.x1_var), ("Y1:", self.y1_var), ("X2:", self.x2_var), ("Y2:", self.y2_var)]
        for i, (label, var) in enumerate(coords):
            tk.Label(area_frame, text=label, font=label_font, bg=self.colors['frame_bg'], 
                    fg=self.colors['text']).grid(row=1, column=i*2, padx=2)
            tk.Entry(area_frame, textvariable=var, width=6, font=label_font,
                    bg=self.colors['entry_bg'], fg=self.colors['text'], 
                    insertbackground=self.colors['accent']).grid(row=1, column=i*2+1, padx=2)
        
        # Status section
        status_frame = self.create_section_frame(main_container, "Status", header_font)
        status_frame.pack(fill="x", pady=(15, 10))
        
        status_container = tk.Frame(status_frame, bg=self.colors['frame_bg'])
        status_container.pack(fill="x", padx=10, pady=10)
        
        self.click_count_label = tk.Label(status_container, text="Clicks: 0", 
                                         font=("Segoe UI", 10, "bold"), 
                                         bg=self.colors['frame_bg'], fg=self.colors['accent'])
        self.click_count_label.pack(anchor="w")
        
        self.cps_label = tk.Label(status_container, text="CPS: 0.0", 
                                 font=("Segoe UI", 10, "bold"), 
                                 bg=self.colors['frame_bg'], fg=self.colors['success'])
        self.cps_label.pack(anchor="w")
        
        self.time_label = tk.Label(status_container, text="Time: 0.0s", 
                                  font=("Segoe UI", 10), 
                                  bg=self.colors['frame_bg'], fg=self.colors['text'])
        self.time_label.pack(anchor="w")
        
        self.status_label = tk.Label(status_container, text="Ready", 
                                    font=label_font, bg=self.colors['frame_bg'], fg=self.colors['text'])
        self.status_label.pack(anchor="w")
        
        # Hotkey info
        self.hotkey_info_label = tk.Label(status_container, text="🔥 Press F6 to toggle clicking", 
                                        font=("Segoe UI", 9, "italic"), 
                                        bg=self.colors['frame_bg'], fg=self.colors['warning'])
        self.hotkey_info_label.pack(anchor="w", pady=(5, 0))
        
        # Control Buttons
        button_frame = tk.Frame(main_container, bg=self.colors['bg'])
        button_frame.pack(fill="x", pady=(10, 0))
        
        self.start_button = tk.Button(button_frame, text="▶ START", command=self.start_clicking, 
                                     font=button_font, bg=self.colors['success'], fg="white",
                                     relief="flat", padx=20, pady=8, cursor="hand2")
        self.start_button.pack(side="left", padx=5, expand=True, fill="x")
        
        self.stop_button = tk.Button(button_frame, text="⏹ STOP", command=self.stop_clicking, 
                                    font=button_font, bg=self.colors['danger'], fg="white",
                                    relief="flat", padx=20, pady=8, cursor="hand2", state="disabled")
        self.stop_button.pack(side="left", padx=5, expand=True, fill="x")
        
        # Add hover effects
        self.add_hover_effect(self.start_button, self.colors['success'], "#45a049")
        self.add_hover_effect(self.stop_button, self.colors['danger'], "#da190b")
        
        # Setup hotkey
        keyboard.add_hotkey('f6', self.toggle_clicking)
        
        # Initialize UI state
        self.update_click_mode()
        self.update_position_mode()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def create_section_frame(self, parent, title, font):
        frame = tk.LabelFrame(parent, text=title, font=font, 
                            bg=self.colors['bg'], fg=self.colors['accent'],
                            bd=2, relief="groove")
        return frame
    
    def add_hover_effect(self, button, normal_color, hover_color):
        def on_enter(e):
            button.config(bg=hover_color)
        def on_leave(e):
            button.config(bg=normal_color)
        button.bind("<Enter>", on_enter)
        button.bind("<Leave>", on_leave)
    
    def toggle_limit_inputs(self):
        state = "normal" if self.enable_click_limit.get() else "disabled"
        self.click_limit_entry.config(state=state)
        
        state = "normal" if self.enable_time_limit.get() else "disabled"
        self.time_limit_entry.config(state=state)
    
    def update_click_mode(self):
        mode = self.click_mode.get()
        if mode == "hold":
            self.hold_frame.pack(anchor="w", pady=5)
        else:
            self.hold_frame.pack_forget()
    
    def update_position_mode(self):
        mode = self.position_mode.get()
        if mode == "fixed":
            self.fixed_frame.pack(anchor="w", pady=5)
            self.random_frame.pack_forget()
        elif mode == "random":
            self.random_frame.pack(anchor="w", pady=5)
            self.fixed_frame.pack_forget()
        else:
            self.fixed_frame.pack_forget()
            self.random_frame.pack_forget()
    
    def update_hotkey(self, event=None):
        new_hotkey = self.hotkey_var.get()
        keyboard.unhook_all()
        keyboard.add_hotkey(new_hotkey, self.toggle_clicking)
        self.hotkey_info_label.config(text=f"🔥 Press {new_hotkey.upper()} to toggle clicking")
    
    def save_preset(self):
        preset_data = {
            'interval': self.interval_var.get(),
            'random_interval': self.random_interval_var.get(),
            'click_type': self.click_type.get(),
            'click_mode': self.click_mode.get(),
            'hold_duration': self.hold_duration_var.get(),
            'position_mode': self.position_mode.get(),
            'x': self.x_var.get(),
            'y': self.y_var.get(),
            'x1': self.x1_var.get(),
            'y1': self.y1_var.get(),
            'x2': self.x2_var.get(),
            'y2': self.y2_var.get(),
            'enable_click_limit': self.enable_click_limit.get(),
            'click_limit': self.click_limit_var.get(),
            'enable_time_limit': self.enable_time_limit.get(),
            'time_limit': self.time_limit_var.get(),
            'hotkey': self.hotkey_var.get()
        }
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Preset"
        )
        
        if file_path:
            try:
                with open(file_path, 'w') as f:
                    json.dump(preset_data, f, indent=4)
                messagebox.showinfo("Success", "Preset saved successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preset: {str(e)}")
    
    def load_preset(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Preset"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    preset_data = json.load(f)
                
                # Apply preset values
                self.interval_var.set(preset_data.get('interval', 0.1))
                self.random_interval_var.set(preset_data.get('random_interval', False))
                self.click_type.set(preset_data.get('click_type', 'left'))
                self.click_mode.set(preset_data.get('click_mode', 'single'))
                self.hold_duration_var.set(preset_data.get('hold_duration', 0.5))
                self.position_mode.set(preset_data.get('position_mode', 'current'))
                self.x_var.set(preset_data.get('x', 100))
                self.y_var.set(preset_data.get('y', 100))
                self.x1_var.set(preset_data.get('x1', 0))
                self.y1_var.set(preset_data.get('y1', 0))
                self.x2_var.set(preset_data.get('x2', 500))
                self.y2_var.set(preset_data.get('y2', 500))
                self.enable_click_limit.set(preset_data.get('enable_click_limit', False))
                self.click_limit_var.set(preset_data.get('click_limit', 100))
                self.enable_time_limit.set(preset_data.get('enable_time_limit', False))
                self.time_limit_var.set(preset_data.get('time_limit', 60))
                self.hotkey_var.set(preset_data.get('hotkey', 'f6'))
                
                # Update UI state
                self.toggle_limit_inputs()
                self.update_hotkey()
                
                messagebox.showinfo("Success", "Preset loaded successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load preset: {str(e)}")
        
    def get_click_position(self):
        mode = self.position_mode.get()
        if mode == "current":
            return pyautogui.position()
        elif mode == "fixed":
            return (self.x_var.get(), self.y_var.get())
        elif mode == "random":
            x1, y1 = self.x1_var.get(), self.y1_var.get()
            x2, y2 = self.x2_var.get(), self.y2_var.get()
            x = random.randint(min(x1, x2), max(x1, x2))
            y = random.randint(min(y1, y2), max(y1, y2))
            return (x, y)
        return pyautogui.position()
    
    def get_click_interval(self):
        interval = self.interval_var.get()
        if self.random_interval_var.get():
            interval = interval * random.uniform(0.8, 1.2)
        return interval
    
    def click(self):
        x, y = self.get_click_position()
        click_type = self.click_type.get()
        click_mode = self.click_mode.get()
        
        if click_mode == "single":
            if click_type == "left":
                pyautogui.click(x, y)
            elif click_type == "right":
                pyautogui.rightClick(x, y)
            elif click_type == "middle":
                pyautogui.middleClick(x, y)
        elif click_mode == "double":
            if click_type == "left":
                pyautogui.doubleClick(x, y)
            elif click_type == "right":
                pyautogui.click(x, y, button='right', clicks=2)
            elif click_type == "middle":
                pyautogui.click(x, y, button='middle', clicks=2)
        elif click_mode == "hold":
            if click_type == "left":
                pyautogui.mouseDown(x, y, button='left')
                time.sleep(self.hold_duration_var.get())
                pyautogui.mouseUp(x, y, button='left')
            elif click_type == "right":
                pyautogui.mouseDown(x, y, button='right')
                time.sleep(self.hold_duration_var.get())
                pyautogui.mouseUp(x, y, button='right')
            elif click_type == "middle":
                pyautogui.mouseDown(x, y, button='middle')
                time.sleep(self.hold_duration_var.get())
                pyautogui.mouseUp(x, y, button='middle')
    
    def clicking_loop(self):
        while self.clicking:
            try:
                # Check click limit
                if self.enable_click_limit.get() and self.click_count >= self.click_limit_var.get():
                    self.stop_clicking()
                    messagebox.showinfo("Limit Reached", f"Click limit of {self.click_limit_var.get()} reached!")
                    break
                
                # Check time limit
                if self.enable_time_limit.get() and self.start_time:
                    elapsed = time.time() - self.start_time
                    if elapsed >= self.time_limit_var.get():
                        self.stop_clicking()
                        messagebox.showinfo("Limit Reached", f"Time limit of {self.time_limit_var.get()} seconds reached!")
                        break
                
                self.click()
                self.click_count += 1
                self.click_count_label.config(text=f"Clicks: {self.click_count}")
                
                # Update statistics
                if self.start_time:
                    elapsed = time.time() - self.start_time
                    self.time_label.config(text=f"Time: {elapsed:.1f}s")
                    if elapsed > 0:
                        self.clicks_per_second = self.click_count / elapsed
                        self.cps_label.config(text=f"CPS: {self.clicks_per_second:.1f}")
                
                interval = self.get_click_interval()
                time.sleep(interval)
            except Exception as e:
                self.stop_clicking()
                messagebox.showerror("Error", f"Clicking error: {str(e)}")
                break
    
    def start_clicking(self):
        if not self.clicking:
            self.clicking = True
            self.click_count = 0
            self.start_time = time.time()
            self.clicks_per_second = 0.0
            self.click_count_label.config(text=f"Clicks: {self.click_count}")
            self.cps_label.config(text=f"CPS: 0.0")
            self.time_label.config(text=f"Time: 0.0s")
            self.click_thread = threading.Thread(target=self.clicking_loop, daemon=True)
            self.click_thread.start()
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.status_label.config(text="Clicking...", fg=self.colors['success'])
    
    def stop_clicking(self):
        self.clicking = False
        self.start_time = None
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text="Stopped", fg=self.colors['danger'])
    
    def toggle_clicking(self):
        if self.clicking:
            self.stop_clicking()
        else:
            self.start_clicking()
    
    def on_close(self):
        self.stop_clicking()
        keyboard.unhook_all()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = AutoClicker(root)
    root.mainloop()
