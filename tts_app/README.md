# TTS Application

A modular Text-to-Speech application using Coqui XTTS v2.

## Structure

- `main.py`: Entry point for the application
- `config.py`: Configuration constants, colors, and voice settings
- `engine.py`: Neural TTS engine wrapper
- `text_utils.py`: Text processing and language detection utilities
- `audio_utils.py`: Audio file merging utilities
- `ui.py`: Tkinter GUI application
- `audio_file/`: Directory containing reference audio files

## Running

```bash
python main.py
```

## Original File

The original monolithic `tts.py` has been renamed to `tts_original.py` for reference.