"""Name cleaning and normalisation (guide §5.3). Matching helpers are added in S03."""
from __future__ import annotations

import re

from unidecode import unidecode

TITLES = {"dr", "prof", "professor", "mr", "mrs", "ms", "shri", "sh", "smt", "er"}
_HONORIFIC = re.compile(r"^\s*(dr|prof|professor|mr|mrs|ms|shri|smt|sh)\b\.?\s*", re.I)
_PAREN = re.compile(r"\s*\(([^)]*)\)\s*")


def clean_name(raw: str) -> tuple[str, str]:
    """Display name without honorifics, plus any parenthetical note.

    'Dr. Manoj Kumar (On-lien)' -> ('Manoj Kumar', 'On-lien');  'Dr.Neeraj Khatri' -> ('Neeraj Khatri', '')
    """
    s = " ".join((raw or "").replace("\xa0", " ").split())
    notes = [n for n in _PAREN.findall(s) if not _HONORIFIC.fullmatch(n.strip() + " ")]   # drop '(Ms.)'
    s = _PAREN.sub(" ", s).strip()
    while True:
        new = _HONORIFIC.sub("", s, count=1)
        if new == s:
            break
        s = new
    s = re.sub(r"\.(?=\S)", ". ", s)   # 'Mohd.S Akhtar' -> 'Mohd. S Akhtar'
    return " ".join(s.split()), "; ".join(n.strip() for n in notes if n.strip())


def norm(s: str) -> str:
    """Lowercase ASCII tokens without titles or punctuation: 'Dr. R.K. Mishra' -> 'r k mishra'."""
    s = unidecode(s or "").lower().replace(".", " ")
    s = re.sub(r"[^a-z\s\-]", " ", s)
    toks = [t for t in re.split(r"[\s\-]+", s) if t and t not in TITLES]
    return " ".join(toks)


def tokens(s: str) -> list[str]:
    return norm(s).split()
