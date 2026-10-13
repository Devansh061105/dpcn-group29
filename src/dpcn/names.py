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


# --------------------------------------------------------------------------- matching (S03)

from rapidfuzz import fuzz  # noqa: E402

SURNAME_MIN = 92   # siddiqi/siddiqui = 93 is one name; kumar/kumari, singh/singha = 91 are different names
GIVEN_MIN = 88     # venkat/venkata = 92; given names are policed by the first-name alignment below


def name_tokens(raw: str) -> list[str]:
    """Tokens of a person's name, splitting run-together initials: 'Sreedhar AS' -> sreedhar a s.

    Splitting is skipped when the whole name is upper case ('RAKESH KUMAR MISHRA').
    """
    raw = (raw or "").replace(",", " ")
    if not raw.isupper():
        raw = " ".join(" ".join(t) if t.isalpha() and t.isupper() and 2 <= len(t) <= 3 else t
                       for t in raw.split())
    return norm(raw).split()


def _tok_match(x: str, y: str) -> bool:
    """Same given name, allowing an initial for a full name and small spelling variants."""
    return (x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y))
            or (len(x) > 3 and len(y) > 3 and fuzz.ratio(x, y) >= GIVEN_MIN))


def _surname_options(t: list[str]) -> list[tuple[str, str]]:
    """Where the family name may sit, as (token, role): last word, first word (surname-first) or last full word."""
    opts = [(t[-1], "last"), (t[0], "first")]
    full = [x for x in t if len(x) > 1]
    if full:
        opts.append((full[-1], "lastfull"))
    seen, out = set(), []
    for tok, role in opts:
        if len(tok) > 1 and (tok, role) not in seen:
            seen.add((tok, role))
            out.append((tok, role))
    return out


def initials_compatible(a: str, b: str) -> bool:
    """Could `a` and `b` be the same person?

    Needs (1) a shared family name (fuzzy >= SURNAME_MIN), (2) the first given names to line up
    (equal, or one is the other's initial), and (3) every remaining given-name token of the shorter
    side to match one on the longer side. 'R. K. Mishra' ~ 'Rakesh Kumar Mishra'; surname-first order is
    fine ('Sreedhar Amere Subbarao'); 'Prem P Yadav' !~ 'Pooja Yadav'; 'Pankaj Gupta' !~ 'Pawan Gupta'.

    A name may only be read surname-first on BOTH sides when what follows is initials ('Sreedhar AS'),
    otherwise 'Pradeep Kumar' would match 'Pradeep Kumar Tiwari' with 'Pradeep' as the family name.

    Known leniency: near-identical given names (Kumar/Kumari) count as the same, so 'Rahul Kumar' ~ 'Rahul Kumari'.
    S03 sends such pairs to review whenever two different people could match, so this is deliberate.
    """
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return False
    if len(ta) > 1 and len(tb) > 1 and fuzz.ratio("".join(ta), "".join(tb)) >= 96:
        return True                                   # 'Das Gupta' vs 'Dasgupta'
    for sa, role_a in _surname_options(ta):
        for sb, role_b in _surname_options(tb):
            if fuzz.ratio(sa, sb) < SURNAME_MIN:
                continue
            ra, rb = list(ta), list(tb)
            ra.remove(sa)
            rb.remove(sb)
            if role_a == "first" and role_b == "first" and not all(len(x) == 1 for x in ra + rb):
                continue
            if ra and rb and not _tok_match(ra[0], rb[0]):
                continue                              # first given names differ
            short, long_ = (ra, rb) if len(ra) <= len(rb) else (rb, ra)
            long_ = list(long_)
            ok = True
            for s in short:
                hit = next((l for l in long_ if _tok_match(s, l)), None)
                if hit is None:
                    ok = False
                    break
                long_.remove(hit)
            if ok:
                return True
    return False


def name_score(roster_name: str, cand_names: list[str]) -> float:
    """0..100 similarity between a roster name and a candidate's names (best over all of them)."""
    best = 0.0
    for c in cand_names:
        if not c:
            continue
        s = fuzz.token_set_ratio(norm(roster_name), norm(c))
        if initials_compatible(roster_name, c):
            s = max(s, 90) + 5
        best = max(best, min(s, 100.0))
    return best


def weak_name_match(roster_name: str, cand_name: str) -> bool:
    """True if the roster name has first and last names written out but the candidate has only one full
    word plus initials ('P Gupta' for 'Pawan Gupta'): compatible, but too weak to accept without other evidence."""
    full = lambda s: [t for t in name_tokens(s) if len(t) > 1]
    return len(full(roster_name)) >= 2 and len(full(cand_name)) <= 1
