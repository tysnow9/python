import tkinter as tk
from tkinter import ttk
from datetime import datetime
import time
import os
from PIL import Image
from config.settings import CAMERA_SETTINGS

class CameraGUI:
    """Tkinter-based GUI for IS8502C camera control and image display."""

    def __init__(self, root, camera_controller, image_processor, settings, logger):
        self.root = root
        self.root.title("Sky View")
        self.camera_controller = camera_controller
        self.image_processor = image_processor
        self.settings = settings
        self.logger = logger
        self.image_dir = settings.get("image_dir", "data/images/")
        self.streaming = False
        self.photo = None
        self.latest_img = None
        self.last_canvas_size = None
        self.no_image_count = 0
        self.last_no_image_log = 0
        self.update_task = None
        self.placeholder_loaded = False
        self.setup_styles()
        self.setup_layout()
        self.setup_controls()
        self.root.update_idletasks()
        self.load_placeholder_image()
        self.initialize_camera_settings()
        self.logger.info("GUI initialized.")

    def setup_styles(self):
        """Configure styles for panels and widgets."""
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("TFrame", background="#1E1E1E")
        self.style.configure("Panel.TFrame", background="#1E1E1E")
        self.style.configure("LeftPanel.TFrame", background="#151515")
        self.style.configure("TLabel", background="#151515", foreground="#D4D4D4", font=("Segoe UI", 10))
        self.style.configure("TEntry", fieldbackground="#151515", foreground="#D4D4D4", font=("Segoe UI", 10))
        self.style.configure("Log.TButton", background="#3C3C3C", foreground="#D4D4D4", 
                            font=("Segoe UI", 10), borderwidth=0, padding=5)
        self.style.map("Log.TButton", background=[("active", "#4A4A4A"), ("pressed", "#2A2A2A")],
                    foreground=[("active", "#FFFFFF")])
        self.style.configure("TScale", background="#3C3C3C", troughcolor="#3C3C3C", sliderlength=20)
        self.style.map("TScale", background=[("active", "#3C3C3C")])
        self.style.configure("TPanedWindow", background="#1E1E1E", sashwidth=1, sashrelief="flat", 
                            bordercolor="#222222", sashcolor="#222222")

    def setup_layout(self):
        """Set up main layout with resizable panels."""
        window_size = self.settings.get("window_size", "1200x800")
        window_width, window_height = map(int, window_size.split("x"))
        canvas_width = 960
        canvas_height = 540
        left_panel_width = 200
        bottom_panel_height = 200
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(True, True)

        left_min_width = 200
        bottom_min_height = 150
        min_window_width = left_min_width + 200
        min_window_height = bottom_min_height + 200
        self.root.minsize(min_window_width, min_window_height)

        self.root.update_idletasks()
        width = self.root.winfo_screenwidth()
        height = self.root.winfo_screenheight()
        x = (width - window_width) // 2
        y = (height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        self.paned_window = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill="both", expand=True)

        self.left_panel = ttk.Frame(self.paned_window, style="LeftPanel.TFrame", borderwidth=0, relief="flat")
        self.paned_window.add(self.left_panel)

        self.left_border_canvas = tk.Canvas(self.left_panel, bg="#151515", highlightthickness=0, width=1)
        self.left_border_canvas.pack(side="right", fill="y")
        self.left_border_canvas.bind("<Configure>", self.update_left_border)

        self.right_panel = ttk.Frame(self.paned_window, style="Panel.TFrame", borderwidth=0, relief="flat")
        self.paned_window.add(self.right_panel)
        self.root.update_idletasks()
        self.paned_window.sashpos(0, left_panel_width)

        self.right_paned_window = ttk.PanedWindow(self.right_panel, orient=tk.VERTICAL)
        self.right_paned_window.pack(fill="both", expand=True)

        self.image_canvas = tk.Canvas(self.right_paned_window, bg="#1E1E1E", highlightthickness=0)
        self.right_paned_window.add(self.image_canvas)

        self.bottom_panel = ttk.Frame(self.right_paned_window, style="LeftPanel.TFrame", borderwidth=0, relief="flat")
        self.right_paned_window.add(self.bottom_panel)
        self.root.update()
        self.right_paned_window.sashpos(0, window_height - bottom_panel_height - 10)

        self.bottom_border_canvas = tk.Canvas(self.bottom_panel, bg="#151515", highlightthickness=0, height=1)
        self.bottom_border_canvas.pack(side="top", fill="x")
        self.bottom_border_canvas.bind("<Configure>", self.update_bottom_border)

        self.root.bind("<Configure>", self.on_window_resize)
        self.image_canvas.bind("<Configure>", self.on_resize)

    def setup_controls(self):
        """Set up control panel with buttons, sliders, and command input."""
        self.control_frame = ttk.Frame(self.left_panel, style="LeftPanel.TFrame")
        self.control_frame.pack(pady=10, padx=10, fill="x")

        uniform_height = 30

        self.start_button = ttk.Button(self.control_frame, text="Start", command=self.start_camera, 
                                    style="Log.TButton")
        self.start_button.pack(fill="x", pady=5, ipady=(uniform_height - 28) // 2)

        self.stop_button = ttk.Button(self.control_frame, text="Stop", command=self.stop_camera, 
                                    style="Log.TButton")
        self.stop_button.pack(fill="x", pady=5, ipady=(uniform_height - 28) // 2)

        ttk.Label(self.control_frame, text="Exposure (ms):", style="TLabel").pack(anchor="w", pady=(10, 0))
        self.exposure_var = tk.DoubleVar(value=0.0)
        self.exposure_entry = ttk.Entry(self.control_frame, textvariable=self.exposure_var, style="TEntry")
        self.exposure_entry.pack(fill="x", pady=5, ipady=(uniform_height - 20) // 2)
        self.exposure_entry.bind("<Return>", self.update_exposure_from_entry)
        self.exposure_slider = ttk.Scale(self.control_frame, from_=0, to=1000, orient=tk.HORIZONTAL, 
                                        variable=self.exposure_var, command=self.update_exposure, style="TScale")
        self.exposure_slider.pack(fill="x", pady=5)

        ttk.Label(self.control_frame, text="Gain:", style="TLabel").pack(anchor="w", pady=(10, 0))
        self.gain_var = tk.DoubleVar(value=0.0)
        self.gain_entry = ttk.Entry(self.control_frame, textvariable=self.gain_var, style="TEntry")
        self.gain_entry.pack(fill="x", pady=5, ipady=(uniform_height - 20) // 2)
        self.gain_entry.bind("<Return>", self.update_gain_from_entry)
        self.gain_slider = ttk.Scale(self.control_frame, from_=0, to=240, orient=tk.HORIZONTAL, 
                                    variable=self.gain_var, command=self.update_gain, style="TScale")
        self.gain_slider.pack(fill="x", pady=5)

        ttk.Label(self.control_frame, text="Interval (ms):", style="TLabel").pack(anchor="w", pady=(10, 0))
        self.interval_var = tk.DoubleVar(value=self.camera_controller.settings["stream_interval"] * 1000)
        self.interval_entry = ttk.Entry(self.control_frame, textvariable=self.interval_var, style="TEntry")
        self.interval_entry.pack(fill="x", pady=5, ipady=(uniform_height - 20) // 2)
        self.interval_entry.bind("<Return>", self.update_interval_from_entry)
        self.interval_slider = ttk.Scale(self.control_frame, from_=0, to=10000, orient=tk.HORIZONTAL, 
                                        variable=self.interval_var, command=self.update_interval, style="TScale")
        self.interval_slider.pack(fill="x", pady=5)

        ttk.Label(self.control_frame, text="Native Command:", style="TLabel").pack(anchor="w", pady=(10, 0))
        self.command_entry = ttk.Entry(self.control_frame, style="TEntry")
        self.command_entry.pack(fill="x", pady=5, ipady=(uniform_height - 20) // 2)
        self.command_entry.bind("<Return>", self.send_command)
        self.send_button = ttk.Button(self.control_frame, text="Send", command=self.send_command, 
                                    style="Log.TButton")
        self.send_button.pack(fill="x", pady=5, ipady=(uniform_height - 28) // 2)

        self.bottom_content_frame = ttk.Frame(self.bottom_panel, style="LeftPanel.TFrame")
        self.bottom_content_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.log_text = tk.Text(self.bottom_content_frame, height=10, bg="#151515", fg="#D4D4D4", 
                                font=("Segoe UI", 10), borderwidth=0, wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.clear_log_button = ttk.Button(self.bottom_content_frame, text="Clear Log", 
                                        command=self.clear_log, style="Log.TButton")
        self.clear_log_button.pack(side="top", anchor="ne", padx=5, pady=5)

    def update_interval(self, *args):
        """Update stream_interval with value rounded to nearest 0.1, converted to seconds."""
        value = round(self.interval_var.get(), 1)
        self.interval_var.set(value)
        seconds = value / 1000.0
        if 0 <= seconds <= 10.0:
            self.camera_controller.settings["stream_interval"] = seconds
            self.add_log_message(f"Stream interval set to {value} ms ({seconds} s)")
        else:
            self.add_log_message(f"Error: Interval value {value} ms out of range (0-10000)")

    def update_interval_from_entry(self, event):
        """Update interval from entry field with rounded value."""
        try:
            value = float(self.interval_entry.get())
            value = round(value, 1)
            if 0 <= value <= 10000:
                self.interval_var.set(value)
                self.update_interval()
            else:
                self.add_log_message(f"Error: Interval value {value} out of range (0-10000)")
        except ValueError:
            self.add_log_message("Error: Invalid interval value")

    def update_left_border(self, event):
        """Update left panel's right border line on resize."""
        self.left_border_canvas.delete("all")
        self.left_border_canvas.create_line(0, 0, 0, event.height, fill="#222222", width=1)

    def update_bottom_border(self, event):
        """Update bottom panel's top border line on resize."""
        self.bottom_border_canvas.delete("all")
        self.bottom_border_canvas.create_line(0, 0, event.width, 0, fill="#222222", width=1)

    def on_window_resize(self, event):
        """Handle window resize to enforce minimum panel sizes and update image."""
        if event.widget != self.root:
            return

        window_width = self.root.winfo_width()
        left_min_width = 200
        current_sash_pos = self.paned_window.sashpos(0)
        if window_width - current_sash_pos < left_min_width:
            new_sash_pos = max(left_min_width, window_width - left_min_width)
            self.paned_window.sashpos(0, new_sash_pos)

        window_height = self.root.winfo_height()
        bottom_min_height = 150
        current_sash_pos = self.right_paned_window.sashpos(0)
        current_bottom_height = window_height - current_sash_pos
        desired_bottom_height = 200
        desired_sash_pos = window_height - desired_bottom_height
        if current_bottom_height < bottom_min_height:
            new_sash_pos = window_height - bottom_min_height
            if new_sash_pos > 0:
                self.right_paned_window.sashpos(0, new_sash_pos)
        elif current_bottom_height > desired_bottom_height:
            if desired_sash_pos > 0:
                self.right_paned_window.sashpos(0, desired_sash_pos)

        self.on_resize(event)

    def on_resize(self, event):
        if event.widget not in (self.root, self.image_canvas):
            return
        canvas_width = max(self.image_canvas.winfo_width(), 960)
        canvas_height = max(self.right_paned_window.winfo_height() - self.bottom_panel.winfo_height() - 10, 540)
        if self.latest_img is not None:
            resized_img = self.image_processor.resize_image(
                self.latest_img, canvas_width, canvas_height, margin=10, max_width=1600, max_height=1200
            )
            self.photo = self.image_processor.convert_to_photo(resized_img)
            self.image_canvas.delete("all")
            self.image_canvas.create_image(
                canvas_width // 2, canvas_height // 2, image=self.photo, anchor="center"
            )
            self.last_canvas_size = (canvas_width, canvas_height)

    def initialize_camera_settings(self):
        """Retrieve and set initial Exposure and Gain values from camera."""
        success, msg = self.camera_controller.send_native_command("GVA005")
        if success:
            try:
                value = float(msg.split("\n")[1])
                if 0 <= value <= 1000:
                    self.exposure_var.set(round(value, 1))
                    self.add_log_message(f"Initial Exposure set to {value} ms")
                else:
                    self.add_log_message(f"Error: Initial Exposure {value} out of range (0-1000)")
            except (IndexError, ValueError):
                self.add_log_message(f"Error parsing GVA005 response: {msg}")
        else:
            self.add_log_message(msg)

        success, msg = self.camera_controller.send_native_command("GVB005")
        if success:
            try:
                value = float(msg.split("\n")[1])
                int_value = int(round(value))
                if 0 <= int_value <= 240:
                    self.gain_var.set(int_value)
                    self.add_log_message(f"Initial Gain set to {int_value}")
                else:
                    self.add_log_message(f"Error: Initial Gain {int_value} out of range (0-240)")
            except (IndexError, ValueError):
                self.add_log_message(f"Error parsing GVB005 response: {msg}")
        else:
            self.add_log_message(msg)

    def start_camera(self):
        """Start live streaming and image updates."""
        if not self.streaming:
            success, msg = self.camera_controller.start_live_stream()
            self.add_log_message(msg)
            if success:
                self.streaming = True
                self.no_image_count = 0
                self.placeholder_loaded = False
                self.update_task = self.root.after(500, self.update_live_image)

    def stop_camera(self):
        """Stop live streaming but keep the last image and camera connection."""
        if self.streaming:
            self.streaming = False
            if self.update_task:
                self.root.after_cancel(self.update_task)
                self.update_task = None
            self.drain_queue()
            success, msg = self.camera_controller.pause_streaming()
            self.add_log_message(msg)
            image_count = len([f for f in os.listdir(self.image_dir) if f.endswith((".bmp", ".jpeg"))])
            self.add_log_message(f"Total images saved: {image_count}")

    def drain_queue(self):
        canvas_width = max(self.image_canvas.winfo_width(), 960)
        canvas_height = max(self.right_paned_window.winfo_height() - self.bottom_panel.winfo_height() - 10, 540)
        latest_img = None
        time.sleep(0.1)
        while True:
            try:
                success, img, msg = self.camera_controller.get_image_from_queue()
                if not success and "No image available" in msg:
                    break
                self.add_log_message(msg)
                if success and img is not None:
                    success, save_msg = self.image_processor.save_image(img)
                    self.add_log_message(save_msg)
                    resized_img = self.image_processor.resize_image(img, canvas_width, canvas_height, max_width=1600, max_height=1200)
                    latest_img = resized_img
                elif not success and "stopped at time" in msg.lower():
                    self.streaming = False
                    if self.update_task:
                        self.root.after_cancel(self.update_task)
                        self.update_task = None
                    break
            except Exception as e:
                self.add_log_message(f"Error draining queue: {e}")
                break
        if latest_img is not None:
            self.photo = self.image_processor.convert_to_photo(latest_img)
            self.latest_img = latest_img
            self.image_canvas.delete("all")
            self.image_canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor="center")
            self.last_canvas_size = (canvas_width, canvas_height)
        self.add_log_message("Drained queue: Processed remaining images.")

    def send_command(self, event=None):
        """Send native command from text entry."""
        command = self.command_entry.get().strip()
        if not command:
            self.add_log_message("Error: No command entered")
            return
        success, msg = self.camera_controller.send_native_command(command)
        self.add_log_message(msg)

    def update_exposure(self, *args):
        """Send exposure command with value rounded to nearest 0.1 and validate."""
        value = round(self.exposure_var.get(), 1)
        if 0 <= value <= 1000:
            self.exposure_var.set(value)
            success, msg = self.camera_controller.send_native_command(f"SFA005 {value}")
            self.add_log_message(msg)
            if success:
                time.sleep(0.1)
                success, verify_msg = self.camera_controller.send_native_command("GVA005")
                if success:
                    try:
                        current_value = float(verify_msg.split("\n")[1])
                        if abs(current_value - value) < 0.1:
                            self.add_log_message(f"Exposure verified: {current_value} ms")
                        else:
                            self.add_log_message(f"Exposure verification failed: got {current_value}, expected {value}")
                    except (IndexError, ValueError):
                        self.add_log_message(f"Error verifying Exposure: {verify_msg}")
                else:
                    self.add_log_message(verify_msg)
        else:
            self.add_log_message(f"Error: Exposure value {value} out of range (0-1000)")

    def update_exposure_from_entry(self, event):
        """Update exposure from entry field with rounded value."""
        try:
            value = float(self.exposure_entry.get())
            value = round(value, 1)
            if 0 <= value <= 1000:
                self.exposure_var.set(value)
                self.update_exposure()
            else:
                self.add_log_message(f"Error: Exposure value {value} out of range (0-1000)")
        except ValueError:
            self.add_log_message("Error: Invalid exposure value")

    def update_gain(self, *args):
        """Send gain command with integer value and validate."""
        value = int(round(self.gain_var.get()))
        if 0 <= value <= 240:
            self.gain_var.set(value)
            success, msg = self.camera_controller.send_native_command(f"SIB005 {value}")
            self.add_log_message(msg)
            if success:
                time.sleep(0.1)
                success, verify_msg = self.camera_controller.send_native_command("GVB005")
                if success:
                    try:
                        current_value = float(verify_msg.split("\n")[1])
                        int_current_value = int(round(current_value))
                        if int_current_value == value:
                            self.add_log_message(f"Gain verified: {int_current_value}")
                        else:
                            self.add_log_message(f"Gain verification failed: got {int_current_value}, expected {value}")
                    except (IndexError, ValueError):
                        self.add_log_message(f"Error verifying Gain: {verify_msg}")
                else:
                    self.add_log_message(verify_msg)
        else:
            self.add_log_message(f"Error: Gain value {value} out of range (0-240)")

    def update_gain_from_entry(self, event):
        """Update gain from entry field with integer value."""
        try:
            value = float(self.gain_entry.get())
            value = int(round(value))
            if 0 <= value <= 240:
                self.gain_var.set(value)
                self.update_gain()
            else:
                self.add_log_message(f"Error: Gain value {value} out of range (0-240)")
        except ValueError:
            self.add_log_message("Error: Invalid gain value")

    def update_live_image(self):
        if self.streaming and not self.camera_controller.paused:
            canvas_width = max(self.image_canvas.winfo_width(), 960)
            canvas_height = max(self.right_paned_window.winfo_height() - self.bottom_panel.winfo_height() - 10, 540)
            success, img, msg = self.camera_controller.get_image_from_queue()
            current_time = time.time()
            if not success and "No image available" in msg:
                self.no_image_count += 1
                if self.no_image_count >= 6 and current_time - self.last_no_image_log >= 1:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    self.add_log_message(f"No images available at {timestamp}")
                    self.no_image_count = 3
                    self.last_no_image_log = current_time
            elif not success and "stopped at time" in msg.lower():
                self.streaming = False
                if self.update_task:
                    self.root.after_cancel(self.update_task)
                    self.update_task = None
                self.add_log_message(msg)
                self.drain_queue()
                image_count = len([f for f in os.listdir(self.image_dir) if f.endswith((".bmp", ".jpeg"))])
                self.add_log_message(f"Total images saved: {image_count}")
                return
            elif success and img is not None:
                self.no_image_count = 0
                self.add_log_message(msg)
                success, save_msg = self.image_processor.save_image(img)
                self.add_log_message(save_msg)
                resized_img = self.image_processor.resize_image(img, canvas_width, canvas_height, margin=10, max_width=1600, max_height=1200)
                self.latest_img = resized_img
                self.photo = self.image_processor.convert_to_photo(resized_img)
                self.image_canvas.delete("all")
                self.image_canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor="center")
                self.last_canvas_size = (canvas_width, canvas_height)
            self.update_task = self.root.after(10, self.update_live_image)

    def load_placeholder_image(self):
        if not self.placeholder_loaded:
            placeholder_path = self.settings.get("placeholder_image_path", "data/placeholder.bmp")
            result = self.image_processor.load_placeholder(placeholder_path)
            self.root.update()
            canvas_width = max(self.image_canvas.winfo_width(), 960)
            canvas_height = max(self.right_paned_window.winfo_height() - self.bottom_panel.winfo_height() - 10, 540)
            if not isinstance(result, Image.Image):
                self.add_log_message(f"Failed to load placeholder: {result}")
                self.image_canvas.create_text(5, 5, text=str(result), anchor="nw", fill="#D4D4D4", font=("Segoe UI", 10))
            else:
                img = result
                resized_img = self.image_processor.resize_image(img, canvas_width, canvas_height, margin=10, max_width=960, max_height=540)
                self.photo = self.image_processor.convert_to_photo(resized_img)
                self.latest_img = resized_img
                self.image_canvas.delete("all")
                self.image_canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor="center")
                self.last_canvas_size = (canvas_width, canvas_height)
                self.add_log_message(f"Loaded placeholder from {placeholder_path}")
            self.placeholder_loaded = True

    def add_log_message(self, message, level="info"):
        """Add timestamped message to GUI log window."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        full_message = f"[{timestamp}] {message}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert("end", full_message)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def clear_log(self):
        """Clear log window."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.add_log_message("Log cleared")