import json
import os
import sys
import ctypes
import threading
from ctypes import wintypes
from datetime import datetime
import tkinter as tk
from tkinter import messagebox, ttk
from PIL import Image, ImageDraw
import pystray
from plyer import notification

# 1. PERMANENT DATA DIRECTORY (AppData/Roaming/TodoReminderApp)
APPDATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "TodoReminderApp"
)
os.makedirs(APPDATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(APPDATA_DIR, "todos.json")
BACKUP_DIR = os.path.join(APPDATA_DIR, "backups")
LOCK_FILE = os.path.join(APPDATA_DIR, "app.lock")
INTERVAL_MS = 6 * 3600 * 1000  # 6 hours in milliseconds

os.makedirs(BACKUP_DIR, exist_ok=True)

# 2. SINGLE-INSTANCE LOCK
lock_handle = None


def acquire_single_instance_lock():
    global lock_handle
    try:
        if os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                return False
        lock_handle = open(LOCK_FILE, "w")
        lock_handle.write(str(os.getpid()))
        lock_handle.flush()
        return True
    except Exception:
        return False


if not acquire_single_instance_lock():
    sys.exit(0)


def load_tasks():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_tasks(tasks):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}")


def create_daily_backup(tasks):
    today_str = datetime.now().strftime("%Y-%m-%d")
    backup_file = os.path.join(BACKUP_DIR, f"todos_backup_{today_str}.json")

    if not os.path.exists(backup_file):
        try:
            with open(backup_file, "w") as f:
                json.dump(tasks, f, indent=4)
        except Exception:
            pass


class TodoApp:

    def __init__(self):
        self.tasks = load_tasks()

        # Initialize Main Tkinter Window
        self.root = tk.Tk()
        self.root.title("To-Do List Reminder")
        self.root.geometry("490x450")
        self.root.resizable(False, False)

        self.center_window(self.root, 490, 450)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.build_gui()

        self.icon = None
        self.start_tray_icon()

        # Start background poller for Windows Lock Screen Unlock
        self.start_session_monitor()

        # Start 6-hour scheduler inside Tkinter loop
        self.root.after(2000, self.trigger_reminder)
        self.schedule_next_popup()

        # Start 9 AM daily backup timer checker
        self.last_backup_date = None
        self.check_daily_backup_schedule()

    def center_window(self, win, width, height, parent=None):
        win.update_idletasks()
        if parent:
            p_x = parent.winfo_x()
            p_y = parent.winfo_y()
            p_w = parent.winfo_width()
            p_h = parent.winfo_height()
            x = p_x + (p_w // 2) - (width // 2)
            y = p_y + (p_h // 2) - (height // 2)
        else:
            s_w = win.winfo_screenwidth()
            s_h = win.winfo_screenheight()
            x = (s_w // 2) - (width // 2)
            y = (s_h // 2) - (height // 2)

        win.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def build_gui(self):
        frame = ttk.Frame(self.root, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame, text="Task Description:", font=("Segoe UI", 10, "bold")
        ).pack(anchor=tk.W)

        self.entry_task = ttk.Entry(frame, font=("Segoe UI", 10))
        self.entry_task.pack(fill=tk.X, pady=(5, 10))
        self.entry_task.bind("<Return>", lambda e: self.add_task())

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(btn_frame, text="Add Task", command=self.add_task).pack(
            side=tk.LEFT, padx=(0, 4)
        )
        ttk.Button(btn_frame, text="Modify", command=self.modify_task).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_frame, text="Delete", command=self.delete_task).pack(
            side=tk.LEFT, padx=4
        )
        ttk.Button(btn_frame, text="Exit App", command=self.quit_app).pack(
            side=tk.RIGHT, padx=(4, 0)
        )

        ttk.Label(
            frame, text="Pending Tasks:", font=("Segoe UI", 10, "bold")
        ).pack(anchor=tk.W, pady=(5, 2))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        arrow_frame = ttk.Frame(list_frame, padding=(5, 0))
        arrow_frame.pack(side=tk.RIGHT, fill=tk.Y)

        btn_up = ttk.Button(
            arrow_frame, text="▲", width=3, command=self.move_task_up
        )
        btn_up.pack(side=tk.TOP, pady=(15, 5))

        btn_down = ttk.Button(
            arrow_frame, text="▼", width=3, command=self.move_task_down
        )
        btn_down.pack(side=tk.TOP, pady=5)

        self.task_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
            activestyle="none",
        )
        self.task_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.task_listbox.yview)

        self.populate_listbox()

    def populate_listbox(self):
        self.task_listbox.delete(0, tk.END)
        for task in self.tasks:
            self.task_listbox.insert(tk.END, f"  •  {task}")

    def add_task(self):
        task_text = self.entry_task.get().strip()
        if task_text:
            self.tasks.append(task_text)
            save_tasks(self.tasks)
            self.populate_listbox()
            self.entry_task.delete(0, tk.END)

    def modify_task(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning(
                "Select Task", "Please select a task to modify."
            )
            return

        idx = selected[0]
        current_val = self.tasks[idx]

        edit_win = tk.Toplevel(self.root)
        edit_win.title("Modify Task")
        edit_win.resizable(False, False)

        self.center_window(edit_win, 350, 130, parent=self.root)
        edit_win.grab_set()

        ttk.Label(edit_win, text="Edit task description:").pack(
            anchor=tk.W, padx=15, pady=(12, 5)
        )
        entry = ttk.Entry(edit_win, width=42, font=("Segoe UI", 10))
        entry.insert(0, current_val)
        entry.pack(padx=15, pady=5)
        entry.focus()
        entry.select_range(0, tk.END)

        def save_edit():
            new_text = entry.get().strip()
            if new_text:
                self.tasks[idx] = new_text
                save_tasks(self.tasks)
                self.populate_listbox()
                edit_win.destroy()

        entry.bind("<Return>", lambda e: save_edit())

        btn_box = ttk.Frame(edit_win)
        btn_box.pack(pady=8)
        ttk.Button(btn_box, text="Save", command=save_edit).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_box, text="Cancel", command=edit_win.destroy).pack(
            side=tk.LEFT, padx=5
        )

    def delete_task(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning(
                "Select Task", "Please select a task to delete."
            )
            return

        idx = selected[0]
        del self.tasks[idx]
        save_tasks(self.tasks)
        self.populate_listbox()

    def move_task_up(self):
        selected = self.task_listbox.curselection()
        if not selected:
            return

        idx = selected[0]
        if idx == 0:
            return

        self.tasks[idx], self.tasks[idx - 1] = (
            self.tasks[idx - 1],
            self.tasks[idx],
        )
        save_tasks(self.tasks)

        self.populate_listbox()
        self.task_listbox.selection_set(idx - 1)
        self.task_listbox.see(idx - 1)

    def move_task_down(self):
        selected = self.task_listbox.curselection()
        if not selected:
            return

        idx = selected[0]
        if idx >= len(self.tasks) - 1:
            return

        self.tasks[idx], self.tasks[idx + 1] = (
            self.tasks[idx + 1],
            self.tasks[idx],
        )
        save_tasks(self.tasks)

        self.populate_listbox()
        self.task_listbox.selection_set(idx + 1)
        self.task_listbox.see(idx + 1)

    def start_session_monitor(self):
        """Monitors Windows Workstation Lock/Unlock states continuously."""

        def monitor():
            import time

            was_locked = False
            while True:
                # Open Desktop station handle
                user32 = ctypes.windll.user32
                h_desk = user32.OpenInputDesktop(0, False, 0x0100)

                if h_desk == 0:
                    # Input Desktop is inaccessible (Screen is Locked)
                    was_locked = True
                else:
                    user32.CloseDesktop(h_desk)
                    if was_locked:
                        # Screen was just unlocked! Trigger popup
                        was_locked = False
                        time.sleep(0.8)  # Wait for Windows shell transition
                        self.root.after(0, self.trigger_reminder)

                time.sleep(1)

        threading.Thread(target=monitor, daemon=True).start()

    def check_daily_backup_schedule(self):
        now = datetime.now()
        today_date = now.strftime("%Y-%m-%d")

        if now.hour >= 9 and self.last_backup_date != today_date:
            create_daily_backup(self.tasks)
            self.last_backup_date = today_date

        self.root.after(60000, self.check_daily_backup_schedule)

    def force_foreground(self):
        """Bypasses Windows Foreground Lockout policy using Win32 API."""
        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()

            # Restore window if minimized
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE

            # Simulate ALT key press to allow SetForegroundWindow permission
            ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)  # ALT Down
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)  # ALT Up

            self.root.attributes("-topmost", True)
            self.root.update()
            self.root.attributes("-topmost", False)
            self.root.focus_force()
        except Exception:
            pass

    def show_window(self):
        self.root.deiconify()
        self.root.state("normal")
        self.force_foreground()

    def hide_window(self):
        self.root.withdraw()

    def trigger_reminder(self):
        try:
            notification.notify(
                title="To-Do List Reminder",
                message=f"You have {len(self.tasks)} active task(s). Click to review!",
                timeout=8,
            )
        except Exception:
            pass

        self.show_window()

    def schedule_next_popup(self):
        self.root.after(INTERVAL_MS, self.trigger_reminder)
        self.root.after(INTERVAL_MS, self.schedule_next_popup)

    def start_tray_icon(self):
        image = Image.new("RGB", (64, 64), color=(0, 120, 215))
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill=(255, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem(
                "Open To-Do List", lambda: self.root.after(0, self.show_window)
            ),
            pystray.MenuItem(
                "Exit App", lambda: self.root.after(0, self.quit_app)
            ),
        )
        self.icon = pystray.Icon("TodoReminder", image, "To-Do Reminder", menu)

        threading.Thread(target=self.icon.run, daemon=True).start()

    def quit_app(self):
        global lock_handle
        if self.icon:
            self.icon.stop()
        if lock_handle:
            try:
                lock_handle.close()
                os.remove(LOCK_FILE)
            except Exception:
                pass
        self.root.destroy()
        os._exit(0)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = TodoApp()
    app.run()