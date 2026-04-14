import os

# ── Colors ────────────────────────────────────────────────────────────────────
C_BG       = "#f5f5f3"   # page background
C_SURFACE  = "#ffffff"   # card surface
C_BORDER   = "#e0dfd8"   # card border
C_ACCENT   = "#22c77a"   # green action
C_ACCENT_H = "#1aad69"   # green hover
C_TEXT     = "#1a1a18"   # primary text
C_MUTED    = "#6b6b66"   # secondary text
C_DANGER   = "#e03b3b"   # error


# ── File paths ────────────────────────────────────────────────────────────────
_DIR       = os.path.dirname(os.path.abspath(__file__))
_AUDIO_DIR = os.path.join(_DIR, "audio_file")
OUTPUT_WAV = os.path.join(_DIR, "output_final.wav")

VOICE_CONFIG = {
    "Female": {
        "wav":  os.path.join(_AUDIO_DIR, "audio.wav"),
        "lang": "en",
    },
    "Male": {
        "wav":  os.path.join(_AUDIO_DIR, "hindi.wav"),
        "lang": "hi",
    },
}
