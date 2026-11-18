"""
XTTS-v2 synthesis with shloka-aware chunking + natural pauses.
Male voice cloned from the neutral Marathi reference clip.
"""
import os, re, numpy as np
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["COQUI_TOS_AGREED"] = "1"
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

REF_WAV = os.environ.get("HINDITTS_REF_WAV", "prompts/reference.wav")
SR = 24000
_TTS = None
_LATENTS = None

# pause lengths (ms)
GAP_SUB = 180      # within a sentence (after comma / short pada)
GAP_SENT = 450     # after a full sentence (danda)
GAP_BLOCK = 800    # between a shloka block and its commentary


def _load():
    global _TTS, _LATENTS
    if _TTS is None:
        import torch
        from TTS.api import TTS
        _TTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
        _TTS.to("mps" if torch.backends.mps.is_available() else "cpu")
        # precompute speaker latents once (big speedup vs re-encoding ref each call)
        gpt, spk = _TTS.synthesizer.tts_model.get_conditioning_latents(audio_path=[REF_WAV])
        _LATENTS = (gpt, spk)
    return _TTS


def clean(text: str) -> str:
    text = re.sub(r'[“”‘’"\'\[\]()*•★◊π‹›«»]', " ", text)
    text = re.sub(r"[०-९]+", " ", text)         # drop verse-marker numbers
    text = text.replace("॥", "।").replace("ऽ", "")
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"\s*।\s*(?=।)", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _subsplit(s, max_chars):
    """Break one over-long sentence on commas/dashes/spaces into <=max_chars pieces."""
    if len(s) <= max_chars:
        return [s]
    pieces, buf = [], ""
    for tok in re.split(r"(?<=[,–-])\s+|\s+", s):
        if len(buf) + len(tok) + 1 <= max_chars:
            buf = (buf + " " + tok).strip()
        else:
            if buf: pieces.append(buf)
            buf = tok
    if buf: pieces.append(buf)
    return pieces

def chunks_with_gaps(text: str, max_chars: int = 140):
    """Yield (chunk_text, trailing_gap_ms). PACKS consecutive sentences into full
    ~max_chars chunks (internal dandas stay inside the chunk, XTTS reads them fine;
    babble only happens at chunk seams, so fewer seams = far less gibberish)."""
    text = clean(text)
    sents = [s.strip() for s in re.split(r"(?<=।)\s*", text) if s.strip()]
    buf = ""
    for s in sents:
        if not buf:
            if len(s) <= max_chars:
                buf = s
            else:
                for p in _subsplit(s, max_chars):
                    if p.strip(): yield p.strip(), GAP_SUB
        elif len(buf) + 1 + len(s) <= max_chars:
            buf = buf + " " + s
        else:
            yield buf.strip(), GAP_SENT
            if len(s) <= max_chars:
                buf = s
            else:
                buf = ""
                for p in _subsplit(s, max_chars):
                    if p.strip(): yield p.strip(), GAP_SUB
    if buf.strip():
        yield buf.strip(), GAP_SENT


def _dev_chars(s):
    return sum(1 for c in s if 0x900 <= ord(c) <= 0x97f)

def synth(text: str, temperature: float = 0.6, max_chars: int = 140,
          rep_penalty: float = 3.0, anti_hallucinate: bool = False):
    """anti_hallucinate: per-chunk, if the audio runs far longer than the text
    warrants (XTTS repetition), re-roll that chunk at lower temperature and keep
    the shortest clean take."""
    tts = _load()
    gpt, spk = _LATENTS
    out = []
    for chunk, gap in chunks_with_gaps(text, max_chars):
        if not any(0x900 <= ord(c) <= 0x97f for c in chunk):
            continue
        expected = _dev_chars(chunk) * 0.085          # ~ Hindi seconds for this chunk
        limit = max(1.3, expected * 1.7)
        temps = [temperature, 0.35, 0.25, 0.2] if anti_hallucinate else [temperature]
        best = None
        for temp in temps:
            wav = tts.synthesizer.tts_model.inference(
                chunk, "hi", gpt, spk,
                temperature=temp, length_penalty=1.0, repetition_penalty=rep_penalty,
                enable_text_splitting=False)["wav"]
            wav = np.asarray(wav, dtype=np.float32)
            if best is None or len(wav) < len(best):
                best = wav
            if len(wav) / SR <= limit:                # good take, stop re-rolling
                break
        out.append(best)
        out.append(np.zeros(int(SR * gap / 1000), dtype=np.float32))
    return (np.concatenate(out) if out else np.zeros(1, np.float32)), SR


def save_mp3(wav, sr, path, bitrate="96k"):
    import soundfile as sf, subprocess, tempfile, os
    peak = float(np.max(np.abs(wav))) or 1.0
    wav = (wav / peak * 0.97).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, wav, sr); wp = tmp.name
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wp,
                    "-b:a", bitrate, path], check=True)
    os.unlink(wp)


if __name__ == "__main__":
    import sys, soundfile as sf, time
    txt = sys.stdin.read()
    t = time.time()
    wav, sr = synth(txt)
    sf.write(sys.argv[1], wav, sr)
    print(f"{len(wav)/sr:.1f}s audio in {time.time()-t:.1f}s -> {sys.argv[1]}")
