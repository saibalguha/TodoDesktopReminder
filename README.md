# To-Do Desktop Reminder for Windows

A lightweight, background desktop application built with Python and Tkinter that reminds you of your pending tasks every 6 hours and whenever you unlock your Windows screen.

---

## 🚀 Quick Download & Installation

1. Go to the **[Releases](https://github.com/YOUR_GITHUB_USERNAME/TodoDesktopReminder/releases)** page.
2. Download **`todo_app.exe`**.
3. Move `todo_app.exe` to your preferred folder (e.g., `C:\Apps\TodoReminder\`).
4. Double-click `todo_app.exe` to run.

---

## ✨ Features

* **Periodic Reminders:** Automatically pops up every 6 hours to keep your tasks on track.
* **Unlock Trigger:** Pops up immediately when you unlock your Windows screen (`Win + L` -> Password).
* **Easy Management:** Add, modify, delete, and reorder tasks (▲ / ▼).
* **Automatic Backups:** Generates daily timestamped JSON backups at 9:00 AM in `%APPDATA%`.
* **Single Instance Protection:** Prevents duplicate background processes from running.

---

## 🔧 Building from Source

```bash
# Clone the repository
git clone [https://github.com/YOUR_GITHUB_USERNAME/TodoDesktopReminder.git](https://github.com/YOUR_GITHUB_USERNAME/TodoDesktopReminder.git)
cd TodoDesktopReminder

# Install dependencies
pip install pillow pystray plyer pywin32

# Run the app
python todo_app.py

# Build your own .exe
python -m PyInstaller --noconsole --onefile todo_app.py
