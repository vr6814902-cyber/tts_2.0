import tkinter as tk
from ui import TTSApp

# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app  = TTSApp(root)
    root.mainloop()