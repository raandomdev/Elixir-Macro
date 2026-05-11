import time
import queue
import threading
import keyboard
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# Create paths directory
PATHS_DIR = Path("paths")
PATHS_DIR.mkdir(exist_ok=True)

# Path file mappings
PATH_FILES = {
    "1": PATHS_DIR / "obby_path.py",
    "2": PATHS_DIR / "potion_path.py",
    "3": PATHS_DIR / "item_collect.py",
    "4": PATHS_DIR / "auto_chailce.py"
}

# Global recording state for the keyboard callback (thread-safe)
recording_active = False
recording_mode = None
recording_start_time = 0.0

# Queue to send actions from callback to GUI
action_queue = queue.Queue()

class RecorderGUI:
    def __init__(self, master):
        self.master = master
        master.title("Keyboard Path Recorder")
        master.geometry("800x600")
        master.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Data storage
        self.current_actions = []          # list of (key, hold_duration, delay_since_last)
        self.last_action_press_time = 0.0  # used only for delay calculation in callback
        self.press_times = {}              # used in callback to track press times

        # Build UI
        self.setup_ui()

        # Start keyboard hook
        keyboard.hook(self.keyboard_callback)
        # Start queue processor
        self.process_queue()

        # Bind ESC to exit
        self.master.bind("<Escape>", lambda e: self.on_closing())

    def setup_ui(self):
        # Top frame for buttons
        btn_frame = ttk.Frame(self.master)
        btn_frame.pack(pady=5)

        ttk.Button(btn_frame, text="Record Obby (1)", command=lambda: self.start_recording("1")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Record Potion (2)", command=lambda: self.start_recording("2")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Record Item (3)", command=lambda: self.start_recording("3")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Record Chailce (4)", command=lambda: self.start_recording("4")).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Stop & Save", command=self.stop_recording).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.cancel_recording).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Quit", command=self.on_closing).pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Idle")
        status_label = ttk.Label(self.master, textvariable=self.status_var, font=("Arial", 12))
        status_label.pack(pady=5)

        # Treeview to display recorded actions
        columns = ("Key", "Hold (ms)", "Delay (ms)")
        self.tree = ttk.Treeview(self.master, columns=columns, show="headings", height=12)
        self.tree.heading("Key", text="Key")
        self.tree.heading("Hold (ms)", text="Hold (ms)")
        self.tree.heading("Delay (ms)", text="Delay (ms)")
        self.tree.column("Key", width=100)
        self.tree.column("Hold (ms)", width=100)
        self.tree.column("Delay (ms)", width=100)
        self.tree.pack(pady=5, fill=tk.BOTH, expand=True)

        # Code preview area
        preview_frame = ttk.LabelFrame(self.master, text="Generated Code Preview")
        preview_frame.pack(pady=5, fill=tk.BOTH, expand=True)
        self.code_text = scrolledtext.ScrolledText(preview_frame, height=10, width=80)
        self.code_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Add scrollbar to treeview
        scrollbar = ttk.Scrollbar(self.master, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # ---------- Keyboard callback (runs in background thread) ----------
    def keyboard_callback(self, event):
        global recording_active, recording_start_time
        if not recording_active:
            return

        current_time = time.time() - recording_start_time
        key = event.name

        if event.event_type == keyboard.KEY_DOWN:
            # Store press time
            self.press_times[key] = current_time
        elif event.event_type == keyboard.KEY_UP:
            if key in self.press_times:
                press_time = self.press_times.pop(key)
                hold = current_time - press_time

                # Compute delay since last action
                if self.current_actions:
                    last_press = self.last_action_press_time
                else:
                    last_press = 0.0
                delay = press_time - last_press

                # Put action into queue for GUI
                action_queue.put((key, hold, delay))
                # Update last press time for next action
                self.last_action_press_time = press_time

    # ---------- GUI methods ----------
    def start_recording(self, mode):
        global recording_active, recording_mode, recording_start_time
        if recording_active:
            messagebox.showinfo("Info", f"Already recording mode {recording_mode}. Stop first.")
            return

        # Reset data
        self.current_actions.clear()
        self.tree.delete(*self.tree.get_children())
        self.code_text.delete(1.0, tk.END)
        self.press_times.clear()
        self.last_action_press_time = 0.0

        # Set global flags
        recording_active = True
        recording_mode = mode
        recording_start_time = time.time()

        self.status_var.set(f"Recording mode {mode} ... (press Stop when done)")

    def stop_recording(self):
        global recording_active
        if not recording_active:
            messagebox.showinfo("Info", "No active recording.")
            return

        # Stop recording
        recording_active = False
        self.status_var.set("Idle")

        if not self.current_actions:
            messagebox.showinfo("Info", "No actions recorded.")
            return

        # Save the recording
        self.save_recording()
        # Update preview
        self.update_code_preview()

    def cancel_recording(self):
        global recording_active
        if not recording_active:
            messagebox.showinfo("Info", "No active recording to cancel.")
            return

        recording_active = False
        self.current_actions.clear()
        self.tree.delete(*self.tree.get_children())
        self.code_text.delete(1.0, tk.END)
        self.status_var.set("Idle")
        messagebox.showinfo("Info", "Recording cancelled.")

    def save_recording(self):
        """Save recorded actions as walk_send with hold durations"""
        if not self.current_actions:
            return

        filename = PATH_FILES[recording_mode]

        # Generate the code lines
        lines = []
        for key, hold, delay in self.current_actions:
            if delay > 0:
                lines.append(f"walk_sleep({delay:.3f})")

            # Handle special keys
            if key in ['space', 'enter', 'ctrl', 'alt', 'shift', 'tab', 'esc']:
                lines.append(f'walk_send(Key.{key}, {hold:.3f})')
            else:
                lines.append(f'walk_send("{key}", {hold:.3f})')

        content = "\n".join(lines)
        filename.write_text(content)
        print(f"Saved {len(self.current_actions)} actions to {filename}")
        messagebox.showinfo("Saved", f"Recording saved to {filename}")

    def update_code_preview(self):
        """Update the code preview text widget"""
        if not self.current_actions:
            self.code_text.delete(1.0, tk.END)
            return

        lines = []
        for key, hold, delay in self.current_actions:
            if delay > 0:
                lines.append(f"walk_sleep({delay:.3f})")
            if key in ['space', 'enter', 'ctrl', 'alt', 'shift', 'tab', 'esc']:
                lines.append(f'walk_send(Key.{key}, {hold:.3f})')
            else:
                lines.append(f'walk_send("{key}", {hold:.3f})')
        content = "\n".join(lines)

        self.code_text.delete(1.0, tk.END)
        self.code_text.insert(1.0, content)

    def add_action_to_display(self, key, hold, delay):
        """Add an action to the treeview and internal list"""
        self.current_actions.append((key, hold, delay))
        hold_ms = hold * 1000
        delay_ms = delay * 1000
        self.tree.insert("", tk.END, values=(key, f"{hold_ms:.2f}", f"{delay_ms:.2f}"))
        # Auto-scroll to bottom
        self.tree.yview_moveto(1.0)

    def process_queue(self):
        """Periodically process actions from the background thread"""
        try:
            while True:
                key, hold, delay = action_queue.get_nowait()
                self.add_action_to_display(key, hold, delay)
                self.update_code_preview()
        except queue.Empty:
            pass
        # Schedule next check (100 ms)
        self.master.after(100, self.process_queue)

    def on_closing(self):
        """Clean up and exit"""
        keyboard.unhook_all()
        self.master.destroy()

def main():
    root = tk.Tk()
    app = RecorderGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()