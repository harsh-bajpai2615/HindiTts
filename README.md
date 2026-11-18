# HindiTts

Turns a Hindi book PDF into one MP3 per chapter, locally and for free. I built it to make an
audiobook of *Radha Rasa Sudha Nidhi* (Hindi), 278 chapters and about 43 hours of audio

The hard part was not the speech. The PDF stores its text in a Krutidev-family legacy font
(AAText / AAVishal): the bytes are Latin code points that only look like Hindi because of the
embedded font, so any TTS engine reads them as gibberish. `krutidev.py` converts them to real
Unicode Devanagari first

## How it works

1. **Legacy font to Unicode** (`krutidev.py`). Maps the 174 distinct code points in the font,
   including about 40 font-specific conjunct ligatures, to Unicode. The pre-base i-matra and
   the reph are swapped for placeholders, then moved to the right side of their consonant
   cluster. The mapping was worked out by comparing the PDF's raw bytes with the rendered
   pages. About 99.96% of characters map cleanly; the rest are very rare glyphs that are
   dropped
2. **Chapters** (`book.py`). Reads the PDF with PyMuPDF and splits it by font size: large
   headings start front-matter sections, and a large shloka line after smaller commentary
   starts a new verse. The two alphabetical indexes are skipped (`SKIP_HEADINGS`)
3. **Speech**. Two engines:
   - `tts_xtts.py`, XTTS-v2 with a cloned voice from a reference clip, shloka-aware chunking
     and pauses after commas, dandas and verse blocks. This is what I used for the final audio
   - `tts.py`, Meta's MMS Hindi model (`facebook/mms-tts-hin`). Needs no reference clip and
     runs well on CPU, but the voice is fixed
4. **Runner** (`run.py`). Synthesises every chapter to MP3, skips the ones already done, and
   writes an `.m3u` playlist in book order

## Setup

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg
```

## Usage

```bash
export HINDITTS_PDF="/path/to/book.pdf"
export HINDITTS_OUT="audio"                        # where the MP3s go
export HINDITTS_REF_WAV="prompts/reference.wav"    # voice to clone, XTTS only

python run.py --list           # chapter list
python run.py                  # all chapters, skipping finished ones
python run.py --only 5         # just chapter 5
python run.py --range 5 12     # chapters 5 to 12
python run.py --engine mms     # use MMS instead of XTTS
```

`book.py` is tuned to this book's layout (`MAIN_START`, `HEAD_SIZE`, `SHLOKA_SIZE`). For a
different PDF those three numbers will need changing

## Speed

On an Apple Silicon Mac, MMS renders at about 11x real time on CPU. XTTS on MPS is much
slower, between about half and one and a half times real time depending on the chapter

## Licences

The code is MIT. The models have their own terms: XTTS-v2 is under the Coqui Public Model
License (non-commercial) and MMS-TTS under CC BY-NC 4.0. No book text or audio is included
here
