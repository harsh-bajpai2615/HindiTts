"""
Krutidev / AAText (legacy Devanagari font encoding) -> Unicode Devanagari converter.

The "Radha Rasa Sudha Nidhi" PDF stores text in a Krutidev-family legacy font
(basefonts AAText-Normal / AAVishal-Bold).  The bytes are Latin / high-Latin code
points that only render as Devanagari through the embedded font.  This module maps
that finite alphabet (174 distinct code points) back to real Unicode Devanagari.

Algorithm
  1. Greedy longest-token substitution to Unicode, using PLACEHOLDERS for the
     pre-base i-matra ('f' -> <I>) and the reph ('Z' -> <R>) so they can be
     reordered afterwards.
  2. Reorder <I> (ि) to AFTER the following consonant cluster.
  3. Reorder <R> (र्) to BEFORE the preceding consonant cluster (skipping matras).

Mappings were derived empirically by decoding the PDF's raw bytes against the
rendered page images (ground truth).
"""
import re

I_MARK = ""   # pre-base i-matra placeholder (legacy 'f')
R_MARK = ""   # reph placeholder (legacy 'Z')

MAP = {
    # ---- multi-char vowels / independent vowels (longest first) ----
    "vkS": "औ", "vks": "ओ", "vk": "आ", "bZ": "ई", ",s": "ऐ",
    "kS": "ौ", "ks": "ो",
    # ---- multi-char consonants / conjuncts ----
    ".k": "ण", "/k": "ध", "Fk": "थ", "Hk": "भ", "?k": "घ",
    '"k': "ष", "[k": "ख", "Kk": "ज्ञ", "{k": "क्ष",
    "'k": "श",              # full SHA is two chars in this font
    "Ëk": "ध",              # alternate DHA glyph (two chars)
    "Ÿk": "त्त",            # TTA-conjunct glyph absorbs a following 'k' (like Ëk)
    "èk": "ध",              # bold-font DHA glyph (carrier-k); è alone handled below
    "‹k": "श",              # bold-font SHA glyph (carrier-k)
    "M+": "ड़", "<+": "ढ़", "Q+": "फ़", "T+": "ज़", "d+": "क़", "x+": "ग़",
    # ---- independent vowels (single) ----
    "v": "अ", "b": "इ", "m": "उ", "Å": "ऊ", ",": "ए", "_": "ऋ",
    # ---- consonants (single) ----
    "d": "क", "x": "ग", "³": "ङ",
    "p": "च", "t": "ज", ">": "झ", "¥": "ञ", "N": "छ",
    "V": "ट", "B": "ठ", "M": "ड", "<": "ढ",
    "r": "त", "n": "द", "u": "न",
    "i": "प", "Q": "फ", "c": "ब", "e": "म",
    ";": "य", "j": "र", "y": "ल", "o": "व",
    "'": "श्", "l": "स", "g": "ह",
    '"': "ष्",              # half SHA/SSA
    "Ë": "ध",
    # ---- matras (single) ----
    "k": "ा", "h": "ी", "q": "ु", "w": "ू", "`": "ृ", "s": "े", "S": "ै",
    ":": "रू",              # this font: colon -> RU
    "a": "ं", "¡": "ँ", "°": "ँ", "%": "ः",
    # ---- half-letters / explicit virama forms ----
    "~": "्",
    "H": "भ्", "F": "थ्", "T": "ट्", "K": "ज्ञ्", "L": "स्",
    "E": "म्", "U": "न्", "R": "त्", "I": "प्", "P": "च्", "D": "क्",
    "Y": "ल्", "O": "व्", "C": "ब्", "X": "ग्", "[": "ख्", "G": "घ्",
    "J": "श्र",             # SHRA ligature
    "Z": R_MARK, "f": I_MARK,
    # ---- nukta / danda / punctuation ----
    "+": "़", "&": "-", "]": ",", "A": "।", "@": "।", "µ": "।",
    "=": "त्र", "z": "्र", "}": "क्ष", "{": "क्ष्",
    # ---- font-specific high-bit conjunct ligatures (decoded from images) ----
    "œ": "कृ", "Ï": "कृ", "Ÿ": "त्त्",
    "Ä": "ञ्च", "‰": "क्त", "˘": "द्म", "ç": "श्च", "‡": "ह्व",
    "¬": "ङ्ग", "⁄": "द्भ", "|": "द्य", "#": "रु", "˚": "॥", "û": "॥",
    "Ê": "द्र", "æ": "द्र", "º": "द्ध", "è": "ध", "ÿ": "क्र",
    "∑": "ऽ", "≈": "ऊ", "ë": "ञ्ज", "Ì": "द्द", "·": "ह्य",
    "∏": "य्", "È": "त्प", ".": "ण्", "\\": "।",
    "±": "ं", "\x7f": " ", "\xa0": " ", "˛": " ", "˝": " ",
    # ---- bold-font (AAVishal) conjunct glyphs (decoded from raw context) ----
    "‘": "ष्ट", "¼": "द्ध", "Ù": "त्त", "Í": "ट्ट", "ê": "ट्ट",
    "ù": "द्म", "ã": "ह्म", "à": "ह्व", "™": "्र", "Ø": "क्र",
    "∫": "ह्", "Õ": "ह्ल", "â": "हृ", "£": "र्", "¸": "य्",
    "´": "त्र्", "≥": "ङ", "W": "ॉ", "Ü": "श", "Ó": "्य",
    "Œ": "द", "Î": "द", "Ú": "स्र", "å": "॰", "¦": " ",
    # ---- digits -> Devanagari ----
    "1": "१", "2": "२", "3": "३", "4": "४", "5": "५",
    "6": "६", "7": "७", "8": "८", "9": "९", "0": "०",
    # ---- quotes / decorative (kept simple; stripped before TTS) ----
    "ﬂ": "“", "ﬁ": "”", "„": "ह्म", "‚": "हृ", "^": "‘", "*": "’",
    "‹": "श्", "›": "’", "•": " ", "π": " ", "◊": " ", "★": " ",
}

MAP["Z"] = R_MARK
MAP["f"] = I_MARK

_KEYS = sorted(MAP.keys(), key=len, reverse=True)

# Devanagari character classes for reordering
_CONS = r"क-हक़-य़"
_MATRA = r"़ँ-ःा-्ॢॣ"
_cluster = rf"(?:[{_CONS}]़?्)*[{_CONS}]़?"

_i_re = re.compile(I_MARK + "(" + _cluster + ")")
_r_re = re.compile("(" + _cluster + ")([" + _MATRA + "]*)" + R_MARK)


def convert(text: str) -> str:
    out = []
    i, n = 0, len(text)
    while i < n:
        for k in _KEYS:
            if text.startswith(k, i):
                out.append(MAP[k])
                i += len(k)
                break
        else:
            out.append(text[i])
            i += 1
    s = "".join(out)
    s = _i_re.sub(lambda m: m.group(1) + "ि", s)          # pre-base i reorder
    s = _r_re.sub(lambda m: "र्" + m.group(1) + m.group(2), s)  # reph reorder
    s = s.replace(I_MARK, "ि").replace(R_MARK, "र्")
    s = _rakar_re.sub(r"्र\1", s)                         # rakar after matra -> before
    s = _repair(s)
    return s


_rakar_re = re.compile(r"([ा-ौ])्र")   # matra + ्र  ->  ्र + matra (प्रेम, ध्रुव, भ्रू)


# --- repair illegal vowel adjacencies left by font "carrier" glyphs ---
# Valid Devanagari never has two dependent vowel signs in a row, nor virama+vowel.
_M = "ा-ौ"          # primary matras ा..ौ (incl. ृ ॄ)
_repairs = [
    (re.compile(f"([{_M}])\\1+"), r"\1"),         # doubled matra -> single  (राधाा->राधा)
    (re.compile(f"्(?=[{_M}])"), ""),          # virama+matra -> full cons (कैस्ी->कैसी)
    (re.compile(f"ा(?=[ि-ौ])"), ""),     # carrier ा before another matra (मधाुर->मधुर)
    (re.compile(f"(?<=[ि-ौ])ा"), ""),    # carrier ा after another matra (राधिाका->राधिका)
    (re.compile(f"[{_M}](?=[{_M}])"), ""),  # any remaining matra-pair: drop carrier (बोलीे->बोले)
]


def _repair(s: str) -> str:
    for rx, rep in _repairs:
        s = rx.sub(rep, s)
    return s


if __name__ == "__main__":
    import sys
    print(convert(sys.stdin.read()))
