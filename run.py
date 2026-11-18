"""
Orchestrator: build chapters, then synthesize each to a per-chapter MP3 (resumable).
Usage:
  python run.py            # synthesize ALL chapters (skips ones already done)
  python run.py --list     # just print the chapter list
  python run.py --only 5   # synthesize only chapter index 5
  python run.py --range 5 12
  python run.py --engine mms   # MMS instead of XTTS (no reference voice needed)
"""
import os, sys, time, re
from book import build_chapters

OUT = os.environ.get("HINDITTS_OUT", "audio")
DEV2ASCII = str.maketrans("०१२३४५६७८९", "0123456789")
FRONT_NAMES = {  # clean labels for the non-verse front matter
    "आरम्भ": "00_Title", "(स्तोत्रकाव्य)": "01_Title_Page", "समर्पण": "02_Samarpan",
    "भूमिका": "03_Bhumika", "कृतज्ञ्ता-ज्ञपन": "04_Kritagyata",
    "कृतज्ञता-ज्ञापन": "04_Kritagyata",
}


def chapter_filenames(chs):
    """Return a filename per chapter: Shloka_<N>.mp3 for verses (N continues for
    any unnumbered trailing/closing verses), clean labels for front matter."""
    names, last = [], 0
    front_i = 0
    for c in chs:
        if c["kind"] == "verse":
            m = re.search(r"[०-९]+", c["title"] or "")
            if m:
                last = int(m.group().translate(DEV2ASCII))
            else:
                last += 1
            names.append(f"Shloka_{last}.mp3")
        else:
            label = FRONT_NAMES.get(c["title"].strip())
            if not label:
                label = f"{front_i:02d}_" + re.sub(r"[^\wऀ-ॿ]+", "_", c["title"]).strip("_")[:30]
            front_i += 1
            names.append(label + ".mp3")
    return names


def main():
    args = sys.argv[1:]
    if "--engine" in args and args[args.index("--engine") + 1] == "mms":
        import tts as engine
        synth = engine.synth_chapter
    else:
        import tts_xtts as engine
        synth = engine.synth
    chs = build_chapters()
    os.makedirs(OUT, exist_ok=True)

    names = chapter_filenames(chs)
    if "--list" in args:
        for i, c in enumerate(chs):
            print(f"{i:3d} [{c['kind']:5s}] {names[i]:18s}  {c['title']}  ({len(c['text'])} chars)")
        return

    only = rng = None
    if "--only" in args:
        only = int(args[args.index("--only") + 1])
    if "--range" in args:
        k = args.index("--range")
        rng = (int(args[k + 1]), int(args[k + 2]))

    # write playlist upfront in book order (so it's usable before render finishes)
    with open(os.path.join(OUT, "00_Playlist.m3u"), "w") as f:
        f.write("#EXTM3U\n" + "\n".join(names) + "\n")

    playlist = list(names)
    done = 0
    t0 = time.time()
    for i, c in enumerate(chs):
        fname = names[i]
        fpath = os.path.join(OUT, fname)
        if only is not None and i != only:
            continue
        if rng is not None and not (rng[0] <= i <= rng[1]):
            continue
        if os.path.exists(fpath) and os.path.getsize(fpath) > 1000:
            continue
        ts = time.time()
        wav, sr = synth(c["text"])
        engine.save_mp3(wav, sr, fpath)
        done += 1
        dur = len(wav) / sr
        print(f"[{i:3d}/{len(chs)}] {c['title']:22s} {dur/60:5.1f}min audio "
              f"in {time.time()-ts:5.1f}s -> {fname}", flush=True)

    # write m3u playlist in book order
    with open(os.path.join(OUT, "00_playlist.m3u"), "w") as f:
        f.write("#EXTM3U\n" + "\n".join(playlist) + "\n")
    print(f"\nDONE: synthesized {done} chapter(s) in {time.time()-t0:.0f}s. Audio in {OUT}")


if __name__ == "__main__":
    main()
