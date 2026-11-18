"""
Structure + text extraction for "Radha Rasa Sudha Nidhi".

Produces a list of chapters: front-matter sections (by large-font headings)
and per-verse units in the main stotra (a new verse begins at the first
large-font shloka line that follows smaller-font commentary).
"""
import os
import re
import fitz
from krutidev import convert

PDF = os.environ.get("HINDITTS_PDF", "book.pdf")
MAIN_START = 24                       # first page of the stotra proper
HEAD_SIZE = 24.0                      # >= this == a section heading
SHLOKA_SIZE = 17.5                    # >= this (in main body) == a verse shloka line
SKIP_HEADINGS = ("श्लोक-सूची", "छन्द-सूचिका", "श्लोक-सूचि")  # alphabetical indexes: skip for audio


def _lines(page):
    """Yield (text, max_size) per visual line, in reading order."""
    d = page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines", []):
            spans = l.get("spans", [])
            txt = "".join(s["text"] for s in spans)
            if not txt.strip():
                continue
            size = max((s["size"] for s in spans if s["text"].strip()), default=0)
            yield convert(txt), size


def build_chapters():
    doc = fitz.open(PDF)
    chapters = []            # list of dicts: {title, kind, text}
    cur = None

    def flush():
        nonlocal cur
        if cur and cur["text"].strip():
            chapters.append(cur)
        cur = None

    in_main = False
    prev_size = 0
    for p in range(doc.page_count):
        if p >= MAIN_START:
            in_main = True
        for txt, size in _lines(doc[p]):
            digits = re.findall(r"[०-९]+", txt)
            if not in_main:
                # front matter: split on big headings
                if size >= HEAD_SIZE and len(txt.strip()) <= 60:
                    flush()
                    cur = {"title": txt.strip(), "kind": "front", "text": ""}
                else:
                    if cur is None:
                        cur = {"title": "आरम्भ", "kind": "front", "text": ""}
                    cur["text"] += txt + "\n"
            else:
                # main body: a verse starts at first big (shloka) line after small text
                is_shloka_line = size >= SHLOKA_SIZE
                if is_shloka_line and prev_size < SHLOKA_SIZE:
                    flush()
                    cur = {"title": None, "kind": "verse", "text": ""}
                if cur is None:
                    cur = {"title": "मुख्य", "kind": "verse", "text": ""}
                cur["text"] += txt + "\n"
                # capture verse number from a ॥N॥ marker
                m = re.search(r"॥\s*([०-९]+)\s*॥", txt)
                if m and cur.get("title") is None:
                    cur["title"] = f"श्लोक {m.group(1)}"
            prev_size = size

    flush()

    # drop skipped index sections
    chapters = [c for c in chapters
                if not any(s in (c["title"] or "") for s in SKIP_HEADINGS)]

    # merge adjacent verse chapters that share the same verse number
    # (a verse's shloka block and its commentary block come out as two pieces)
    merged = []
    for c in chapters:
        if (merged and c["kind"] == "verse" and merged[-1]["kind"] == "verse"
                and c["title"] and merged[-1]["title"] == c["title"]):
            merged[-1]["text"] += c["text"]
        elif (merged and c["kind"] == "verse" and merged[-1]["kind"] == "verse"
                and not c["title"]):
            merged[-1]["text"] += c["text"]
        else:
            merged.append(c)

    # number any trailing unnumbered verse blocks (concluding section)
    tail = 0
    for c in merged:
        if c["kind"] == "verse" and not c["title"]:
            tail += 1
            c["title"] = f"समापन-खण्ड {tail}"
    return merged


if __name__ == "__main__":
    chs = build_chapters()
    print(f"TOTAL CHAPTERS: {len(chs)}\n")
    for i, c in enumerate(chs):
        n = len(c["text"])
        print(f"{i:3d} [{c['kind']:5s}] {c['title'][:40]:40s}  {n:6d} chars  ~{n/13.5/60:4.1f} min")
