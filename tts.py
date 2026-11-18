"""
MMS-TTS synthesis: Unicode Hindi text -> waveform -> MP3.
Hindi voice (facebook/mms-tts-hin) reads Devanagari (incl. Sanskrit shlokas).
"""
import os, re, subprocess, tempfile
import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_MODEL = None
_TOK = None
_SR = 16000

DIGIT_WORDS = {"०": "शून्य", "१": "एक", "२": "दो", "३": "तीन", "४": "चार",
               "५": "पाँच", "६": "छह", "७": "सात", "८": "आठ", "९": "नौ"}


def _load():
    global _MODEL, _TOK, _SR
    if _MODEL is None:
        import torch
        from transformers import VitsModel, AutoTokenizer
        torch.set_num_threads(max(1, (os.cpu_count() or 4)))
        _TOK = AutoTokenizer.from_pretrained("facebook/mms-tts-hin")
        _MODEL = VitsModel.from_pretrained("facebook/mms-tts-hin").eval()
        _SR = _MODEL.config.sampling_rate
    return _MODEL, _TOK


def clean_for_tts(text: str) -> str:
    # drop quotes / brackets / decorative, keep inner words
    text = re.sub(r'[“”‘’"\'\[\]()*•★◊π‹›«»]', " ", text)
    # drop standalone numbers (verse markers ॥१॥ and citations), they are not prose
    text = re.sub(r"[०-९]+", " ", text)
    # treat danda/double-danda as sentence stops; collapse empties
    text = text.replace("॥", "।")
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    text = re.sub(r"\s*।\s*(?=।)", "", text)   # collapse runs of dandas
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = 200):
    text = clean_for_tts(text)
    parts = re.split(r"(?<=[।!?])\s+", text)
    chunks, cur = [], ""
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # hard-split very long sentences on commas/spaces
        while len(p) > max_chars:
            cut = p.rfind(",", 0, max_chars)
            if cut < 40:
                cut = p.rfind(" ", 0, max_chars)
            if cut < 40:
                cut = max_chars
            chunks.append(p[:cut].strip())
            p = p[cut:].strip()
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + " " + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)
    return [c for c in chunks if any(0x900 <= ord(ch) <= 0x97f for ch in c)]


def synth_chapter(text: str, gap_ms: int = 250):
    import torch
    model, tok = _load()
    gap = np.zeros(int(_SR * gap_ms / 1000), dtype=np.float32)
    out = []
    for ch in chunk_text(text):
        inputs = tok(ch, return_tensors="pt")
        with torch.no_grad():
            wav = model(**inputs).waveform[0].cpu().numpy().astype(np.float32)
        out.append(wav)
        out.append(gap)
    if not out:
        return np.zeros(1, dtype=np.float32), _SR
    return np.concatenate(out), _SR


def save_mp3(wav, sr, path, bitrate="96k"):
    import soundfile as sf
    peak = float(np.max(np.abs(wav))) or 1.0
    wav = (wav / peak * 0.97).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        sf.write(tmp.name, wav, sr)
        wavpath = tmp.name
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wavpath,
                    "-b:a", bitrate, path], check=True)
    os.unlink(wavpath)
