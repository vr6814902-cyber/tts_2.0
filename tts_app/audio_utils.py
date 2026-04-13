import wave
import os

def merge_wav_files(paths: list, out_path: str) -> bool:
    """
    Merges temp WAV files into one output file.
    Validates sample-rate & channel count before merging to prevent
    garbled / sped-up / slowed-down audio.
    Deletes temp files after a successful merge.
    """
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        return False

    try:
        def _params(fp):
            with wave.open(fp, 'rb') as w:
                return w.getparams()

        ref = _params(paths[0])

        with wave.open(out_path, 'wb') as out:
            out.setparams(ref)
            for fp in paths:
                p = _params(fp)
                if p.framerate != ref.framerate or p.nchannels != ref.nchannels:
                    print(f"[merge] skipping {fp} — param mismatch "
                          f"({p.framerate}Hz/{p.nchannels}ch vs "
                          f"{ref.framerate}Hz/{ref.nchannels}ch)")
                    continue
                with wave.open(fp, 'rb') as w:
                    out.writeframes(w.readframes(w.getnframes()))

        for fp in paths:
            try:
                os.remove(fp)
            except OSError:
                pass

        return True

    except Exception as e:
        print(f"[merge] error: {e}")
        return False