"""Cross-lingual (English / Hinglish / Hindi) concept extraction. Maps surface words to shared concepts so that
'refund' == 'wapas' == 'वापस'. Deterministic and admin-extendable; an embedding model can be plugged in later."""
import math, re
from functools import lru_cache
LEX = {
    "fee": "fee fees fee शुल्क फीस charges", "refund": "refund refunds refunded refunding wapas वापस repay लौटा",
    "withdrawal": "withdraw withdrew withdrawn withdrawal cancel cancelled cancellation रद्द radd",
    "admission": "admission admissions admit admitted enrol enrolled प्रवेश pravesh", "money": "rs rupees paise money पैसे पैसा amount ₹",
    "salary": "salary salaries remuneration wages wage pay paid unpaid payscale वेतन तनख्वाह",
    "faculty": "teacher teachers faculty staff professor professors lecturers शिक्षक शिक्षकों shikshak",
    "certificate": "certificate certificates marksheet marksheets document documents प्रमाणपत्र प्रमाणपत्रों degree",
    "withhold": "withhold withholding withheld holding hold rok रोककर रोक retain retaining",
    "intake": "intake seats seat सीटों सीट sanctioned", "excess": "beyond excess excessive more zyada अधिक exceeding extra अतिरिक्त",
    "lab": "laboratory laboratories labs lab equipment उपकरण प्रयोगशालाओं प्रयोगशाला upkaran",
    "library": "library libraries books पुस्तकालय pustakalaya", "qualification": "qualified unqualified qualification qualifications योग्य fake ghost",
    "norms": "norms norm aph standards regulations", "approval": "approval approved approve sanction स्वीकृत manzoor",
    "noncompliance": "noncompliance violation violations contrary breach refuses refused refuse refusing",
    "ragging": "ragging harassing harassment harass bullying pareshan परेशान torture", "hostel": "hostel hostels छात्रावास",
    "seniors": "senior seniors वरिष्ठ",
}
WEIGHT = {"money": .5, "norms": .7, "approval": .7, "excess": .8, "noncompliance": .6}
SURFACE = {w: c for c, ws in LEX.items() for w in ws.split()}
CAT_EVIDENCE = {"fee_refund": ["fee", "refund", "withdrawal"], "salary_delay": ["salary"], "certificates": ["certificate", "withhold"],
                "unapproved_intake": ["intake", "excess"], "infrastructure": ["lab", "library"],
                "faculty_norms": ["qualification", "faculty"], "ragging": ["ragging", "hostel", "seniors"]}
RELATED = {frozenset(p) for p in [("faculty_norms", "salary_delay"), ("fee_refund", "certificates"), ("unapproved_intake", "fee_refund")]}


def _lookup(t):
    for c in (t, t[:-1] if t.endswith("s") else t, t[:-2] if t.endswith("ed") else t, t[:-3] if t.endswith("ing") else t):
        if c in SURFACE:
            return SURFACE[c]
    return None


@lru_cache(maxsize=8192)
def concepts(text: str) -> dict[str, float]:  # cached: callers must treat the result as read-only
    toks = []
    for t in re.findall(r"[^\s.,;:!?()\"'।]+", (text or "").lower()):
        toks.append(t.strip("-"))
        if "-" in t:
            toks += t.split("-") + [t.replace("-", "")]
    out: dict[str, float] = {}
    for t in toks:
        c = _lookup(t)
        if c:
            out[c] = out.get(c, 0) + WEIGHT.get(c, 1.0)
    return out


def numbers(text: str) -> set[int]:
    return {int(n) for n in re.findall(r"\d{4,}", (text or "").replace(",", ""))}


def cosine(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0) for k, v in a.items())
    return dot / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def classify(text: str):
    """Suggest category from concept evidence; returns (category, confidence, triggering concepts, all scores)."""
    cs = concepts(text); scores = {}
    for cat, ev in CAT_EVIDENCE.items():
        hit = [c for c in ev if c in cs]
        if hit:
            scores[cat] = (sum(cs[c] for c in hit) / len(ev) * 0.5 + 0.5 * len(hit) / len(ev), hit)
    if not scores:
        return None, 0.0, [], {}
    best = max(scores, key=lambda k: scores[k][0]); tot = sum(v[0] for v in scores.values())
    return best, round(scores[best][0] / tot, 2), scores[best][1], {k: round(v[0], 2) for k, v in scores.items()}
