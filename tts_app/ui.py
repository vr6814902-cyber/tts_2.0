import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
import os
import sys
import subprocess
import tempfile
import threading
import torch

from config import *
from engine import NeuralEngine
from text_utils import detect_language, normalize_text_for_tts, smart_chunk_text
from audio_utils import merge_wav_files


# ── UI ─────────────────────────────────────────────────────────────────────────
class TTSApp:
    PAD = 16
    GAP = 10

    def __init__(self, root: tk.Tk):
        self.root   = root
        self.root.title("Text to Speech")
        self.root.geometry("820x760")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)

        self.device  = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine  = NeuralEngine(self.device)
        self._busy   = False
        self._cancel = threading.Event()

        self._build()
        self._verify_reference_files()
        self._set_status("Loading model…", 0)
        self.engine.load_async(self._on_model_ready)

    # ── Startup check (from first code) ──────────────────────────────────────

    def _verify_reference_files(self):
        missing = [name for name, cfg in VOICE_CONFIG.items()
                   if not os.path.exists(cfg["wav"])]
        if missing:
            lines = "\n".join(
                f"  • {name}:\n    {VOICE_CONFIG[name]['wav']}" for name in missing
            )
            messagebox.showwarning(
                "Bundled Voice Files Missing",
                f"The following reference WAV files were not found:\n\n{lines}\n\n"
                "Please ensure the audio_file/ folder is in the same directory as this script."
            )

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        p = self.PAD

        # ── Header bar ──────────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C_SURFACE, height=52,
                       highlightbackground=C_BORDER, highlightthickness=1)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        self._dot = tk.Canvas(hdr, width=10, height=10, bg=C_SURFACE,
                              highlightthickness=0)
        self._dot.pack(side=tk.LEFT, padx=(20, 6), pady=0)
        self._dot.create_oval(1, 1, 9, 9, fill="#f0c040", outline="")

        tk.Label(hdr, text="Text to Speech", font=("Segoe UI", 13, "bold"),
                 bg=C_SURFACE, fg=C_TEXT).pack(side=tk.LEFT)

        hw_txt = "GPU · CUDA" if self.device == "cuda" else "CPU"
        tk.Label(hdr, text=hw_txt, font=("Segoe UI", 10),
                 bg="#f0f0ec", fg=C_MUTED,
                 padx=10, pady=3, relief=tk.FLAT,
                 highlightbackground=C_BORDER, highlightthickness=1
                 ).pack(side=tk.RIGHT, padx=20, pady=12)

        # ── Scrollable content ───────────────────────────────────────────────
        content = tk.Frame(self.root, bg=C_BG)
        content.pack(fill=tk.BOTH, expand=True, padx=p, pady=p)

        self._card(content, "Voice profile", self._build_voice_card).pack(
            fill=tk.X, pady=(0, self.GAP))

        self._card(content, "Input text", self._build_text_card).pack(
            fill=tk.X, pady=(0, self.GAP))

        self._card(content, "Progress", self._build_progress_card).pack(
            fill=tk.X, pady=(0, self.GAP))

        # ── Action footer ────────────────────────────────────────────────────
        footer = tk.Frame(content, bg=C_BG)
        footer.pack(fill=tk.X)

        self.btn_play = tk.Button(
            footer, text="▶  Play output",
            command=self._play,
            bg=C_SURFACE, fg=C_TEXT,
            activebackground="#ececec",
            font=("Segoe UI", 11), relief=tk.FLAT, padx=20, pady=10,
            highlightbackground=C_BORDER, highlightthickness=1,
            cursor="hand2",
        )
        self.btn_play.pack(side=tk.LEFT)
        self._refresh_play_button()

        self.btn_run = tk.Button(
            footer, text="Synthesize",
            command=self._run,
            bg=C_ACCENT, fg="#0a2a1a",
            activebackground=C_ACCENT_H,
            font=("Segoe UI", 11, "bold"), relief=tk.FLAT,
            padx=30, pady=10, state=tk.DISABLED,
            cursor="hand2",
        )
        self.btn_run.pack(side=tk.RIGHT)

        self.btn_cancel = tk.Button(
            footer, text="Cancel",
            command=self._cancel_synthesis,
            bg=C_SURFACE, fg=C_DANGER,
            activebackground="#fde8e8",
            font=("Segoe UI", 11), relief=tk.FLAT, padx=20, pady=10,
            highlightbackground=C_BORDER, highlightthickness=1,
            cursor="hand2", state=tk.DISABLED,
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(0, 8))

    def _card(self, parent, title: str, builder_fn) -> tk.Frame:
        outer = tk.Frame(parent, bg=C_SURFACE,
                         highlightbackground=C_BORDER, highlightthickness=1)
        tk.Label(outer, text=title, font=("Segoe UI", 10),
                 bg=C_SURFACE, fg=C_MUTED).pack(anchor=tk.W, padx=16, pady=(12, 4))
        inner = tk.Frame(outer, bg=C_SURFACE)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 14))
        builder_fn(inner)
        return outer

    def _build_voice_card(self, f: tk.Frame):
        self.voice_var = tk.StringVar(value=list(VOICE_CONFIG.keys())[0])
        row = tk.Frame(f, bg=C_SURFACE)
        row.pack(fill=tk.X)
        for name in VOICE_CONFIG:
            tk.Radiobutton(
                row, text=name, variable=self.voice_var, value=name,
                bg=C_SURFACE, fg=C_TEXT, selectcolor=C_SURFACE,
                activebackground=C_SURFACE,
                font=("Segoe UI", 11), borderwidth=0,
                cursor="hand2",
            ).pack(side=tk.LEFT, padx=(0, 20))

    def _build_text_card(self, f: tk.Frame):
        self.txt = scrolledtext.ScrolledText(
            f, bg="#fafaf8", fg=C_TEXT,
            insertbackground=C_ACCENT, relief=tk.FLAT,
            font=("Segoe UI", 11), padx=12, pady=10,
            highlightthickness=1, highlightbackground=C_BORDER,
            height=8,
        )
        self.txt.pack(fill=tk.BOTH, expand=True)

        stats = tk.Frame(f, bg=C_SURFACE)
        stats.pack(fill=tk.X, pady=(8, 0))
        self._lbl_words = tk.Label(stats, text="Words: 0", font=("Segoe UI", 10),
                                   bg=C_SURFACE, fg=C_MUTED)
        self._lbl_words.pack(side=tk.LEFT, padx=(0, 16))
        self._lbl_sents = tk.Label(stats, text="Chunks: 0", font=("Segoe UI", 10),
                                   bg=C_SURFACE, fg=C_MUTED)
        self._lbl_sents.pack(side=tk.LEFT)
        self._lbl_lang = tk.Label(stats, text="", font=("Segoe UI", 10),
                                  bg=C_SURFACE, fg=C_MUTED)
        self._lbl_lang.pack(side=tk.LEFT, padx=(16, 0))
        self.txt.bind("<KeyRelease>", self._update_stats)

    def _build_progress_card(self, f: tk.Frame):
        self.status_var = tk.StringVar(value="Loading model…")
        tk.Label(f, textvariable=self.status_var, font=("Segoe UI", 10),
                 bg=C_SURFACE, fg=C_MUTED, anchor=tk.W).pack(fill=tk.X)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("App.Horizontal.TProgressbar",
                        troughcolor="#ebebea",
                        background=C_ACCENT,
                        thickness=5, borderwidth=0,
                        lightcolor=C_ACCENT, darkcolor=C_ACCENT)
        self.prog = ttk.Progressbar(f, style="App.Horizontal.TProgressbar",
                                    mode="determinate")
        self.prog.pack(fill=tk.X, pady=(6, 2))

        self._chunk_frame = tk.Frame(f, bg=C_SURFACE)
        self._chunk_frame.pack(fill=tk.X, pady=(8, 0))
        self._chunk_labels: list = []

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_model_ready(self, success: bool, error):
        if success:
            self.root.after(0, self._activate)
        else:
            self.root.after(0, lambda: messagebox.showerror(
                "Model load failed", f"Could not load XTTS model:\n{error}"))

    def _activate(self):
        self._dot.itemconfig(1, fill=C_ACCENT)
        self.btn_run.config(state=tk.NORMAL)
        self._set_status("Ready", 0)

    def _update_stats(self, _event=None):
        text = self.txt.get("1.0", tk.END).strip()
        if not text:
            self._lbl_words.config(text="Words: 0")
            self._lbl_sents.config(text="Chunks: 0")
            self._lbl_lang.config(text="")
            return

        words  = len(text.split())
        normalized = normalize_text_for_tts(text)
        chunks = smart_chunk_text(normalized)
        lang   = detect_language(text)

        self._lbl_words.config(text=f"Words: {words}")
        self._lbl_sents.config(text=f"Chunks: {len(chunks)}")
        self._lbl_lang.config(text=f"Lang: {'Hindi' if lang == 'hi' else 'English'}")

    def _refresh_play_button(self):
        state = tk.NORMAL if os.path.exists(OUTPUT_WAV) else tk.DISABLED
        self.btn_play.config(state=state)

    def _play(self):
        if not os.path.exists(OUTPUT_WAV):
            return
        if sys.platform == "win32":
            os.startfile(OUTPUT_WAV)
        elif sys.platform == "darwin":
            subprocess.run(["open", OUTPUT_WAV])
        else:
            subprocess.run(["xdg-open", OUTPUT_WAV])

    def _run(self):
        raw = self.txt.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("Empty input", "Please enter some text first.")
            return

        cfg = VOICE_CONFIG[self.voice_var.get()]
        if not os.path.exists(cfg["wav"]):
            messagebox.showerror(
                "Missing audio file",
                f"Speaker WAV not found:\n{cfg['wav']}\n\n"
                "Place the reference audio in the audio_file/ folder."
            )
            return

        self._busy = True
        self._cancel.clear()
        self.btn_run.config(state=tk.DISABLED, bg="#cccccc")
        self.btn_cancel.config(state=tk.NORMAL)
        self.btn_play.config(state=tk.DISABLED)
        threading.Thread(target=self._worker, args=(raw, cfg), daemon=True).start()

    def _cancel_synthesis(self):
        self._cancel.set()
        self._set_status("Cancelling…", self.prog["value"])

    def _worker(self, raw_text: str, cfg: dict):
        # ── Use first code's superior text pipeline ────────────────────────
        lang           = detect_language(raw_text)
        processed_text = normalize_text_for_tts(raw_text)
        chunks         = smart_chunk_text(processed_text)

        if not chunks:
            self.root.after(0, lambda: messagebox.showwarning(
                "Empty Text", "No speakable text was found after processing."))
            self.root.after(0, self._finalize)
            return

        # Override config lang with auto-detected language
        effective_lang = lang

        self.root.after(0, lambda: self._init_chunk_ui(len(chunks)))

        temps = []
        try:
            for i, chunk in enumerate(chunks):
                if self._cancel.is_set():
                    self.root.after(0, lambda: self._set_status("Cancelled", 0))
                    return

                self.root.after(0, lambda i=i: self._set_status(
                    f"Synthesizing chunk {i + 1} of {len(chunks)} — Lang: {effective_lang.upper()}…",
                    int(i / len(chunks) * 90)
                ))
                self.root.after(0, lambda i=i: self._mark_chunk(i, "active"))

                # ── XTTS hallucination fix (from first code) ───────────────
                chunk = chunk.strip()
                if effective_lang == "hi" and not chunk.endswith(('।', '.', '!', '?')):
                    chunk += '।'
                elif effective_lang == "en" and not chunk.endswith(('.', '!', '?')):
                    chunk += '.'
                # ──────────────────────────────────────────────────────────

                fd, path = tempfile.mkstemp(suffix=".wav")
                os.close(fd)

                try:
                    self.engine.synthesize(chunk, cfg["wav"], effective_lang, path)

                    # Validate output — a 44-byte file is just the WAV header (no audio)
                    if os.path.exists(path) and os.path.getsize(path) > 44:
                        temps.append(path)
                        self.root.after(0, lambda i=i: self._mark_chunk(i, "done"))
                    else:
                        print(f"[chunk {i+1}] empty output — skipping: {repr(chunk)}")
                        self.root.after(0, lambda i=i: self._mark_chunk(i, "skip"))
                        try:
                            os.remove(path)
                        except OSError:
                            pass

                except Exception as chunk_err:
                    print(f"[chunk {i+1}] error: {chunk_err}\n  text: {repr(chunk)}")
                    self.root.after(0, lambda i=i: self._mark_chunk(i, "skip"))

            if not temps:
                self.root.after(0, lambda: messagebox.showerror(
                    "No Audio Generated",
                    "All chunks produced empty output.\nCheck the console for details."
                ))
                self.root.after(0, lambda: self._set_status("Failed — no audio", 0))
                return

            self.root.after(0, lambda: self._set_status("Merging audio…", 95))
            success = merge_wav_files(temps, OUTPUT_WAV)

            if success and os.path.exists(OUTPUT_WAV):
                self.root.after(0, lambda: self._set_status("Done ✓", 100))
                self.root.after(0, lambda: messagebox.showinfo(
                    "Complete", f"Audio saved to:\n{OUTPUT_WAV}"))
            else:
                self.root.after(0, lambda: messagebox.showerror(
                    "Merge Failed", "Audio parts could not be merged.\nCheck the console."))
                self.root.after(0, lambda: self._set_status("Merge failed", 0))

        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.root.after(0, lambda exc=exc: messagebox.showerror(
                "Synthesis error", str(exc)))
            self.root.after(0, lambda: self._set_status("Error", 0))

        finally:
            # Temp files are removed inside merge_wav_files on success;
            # clean up any stragglers on failure/cancel.
            for t in temps:
                try:
                    os.remove(t)
                except OSError:
                    pass
            self.root.after(0, self._finalize)

    # ── UI helpers ─────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, value: float):
        self.status_var.set(msg)
        self.prog["value"] = value

    def _init_chunk_ui(self, n: int):
        for w in self._chunk_frame.winfo_children():
            w.destroy()
        self._chunk_labels = []
        for i in range(n):
            row = tk.Frame(self._chunk_frame, bg=C_SURFACE)
            row.pack(fill=tk.X, pady=1)
            dot = tk.Label(row, text="○", font=("Segoe UI", 10),
                           bg=C_SURFACE, fg=C_MUTED, width=2)
            dot.pack(side=tk.LEFT)
            lbl = tk.Label(row, text=f"Chunk {i + 1}", font=("Segoe UI", 10),
                           bg=C_SURFACE, fg=C_MUTED, anchor=tk.W)
            lbl.pack(side=tk.LEFT, padx=4)
            self._chunk_labels.append((dot, lbl))

    def _mark_chunk(self, index: int, state: str):
        if index >= len(self._chunk_labels):
            return
        dot, lbl = self._chunk_labels[index]
        if state == "active":
            dot.config(text="◉", fg=C_ACCENT)
            lbl.config(fg=C_TEXT)
        elif state == "done":
            dot.config(text="●", fg=C_ACCENT)
            lbl.config(fg=C_MUTED)
        elif state == "skip":
            dot.config(text="✕", fg=C_DANGER)
            lbl.config(fg=C_DANGER)

    def _finalize(self):
        self._busy = False
        self.btn_run.config(state=tk.NORMAL, bg=C_ACCENT)
        self.btn_cancel.config(state=tk.DISABLED)
        self._refresh_play_button()