import torch
import threading

from TTS.api import TTS

# Safer weight loading — only bypass weights_only for known TTS models
_original_load = torch.load
def _safe_load(*args, **kwargs):
    if "weights_only" not in kwargs:
        kwargs["weights_only"] = False
    return _original_load(*args, **kwargs)
torch.load = _safe_load


# ── Neural engine ──────────────────────────────────────────────────────────────
class NeuralEngine:
    """Wraps Coqui XTTS v2. Loading and inference run on a background thread."""

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"

    def __init__(self, device: str):
        self.device = device
        self.model  = None
        self.ready  = False
        self._lock  = threading.Lock()

    def load_async(self, on_done):
        """Load the model on a daemon thread; call on_done(True/False) when finished."""
        def _run():
            try:
                self.model = TTS(self.MODEL_NAME).to(self.device)
                self.ready = True
                on_done(True, None)
            except Exception as exc:
                on_done(False, str(exc))
        threading.Thread(target=_run, daemon=True).start()

    @torch.inference_mode()
    def synthesize(self, text: str, speaker_wav: str, lang: str, out_path: str):
        with self._lock:
            self.model.tts_to_file(
                text=text, speaker_wav=speaker_wav, language=lang, file_path=out_path
            )
        if self.device == "cuda":
            torch.cuda.empty_cache()