"""Cross-Bureau overlap detection. Two layers:
 Tier A (rule): institution has ACTIVE cases in >=2 Bureaus/Cells  -> coordination awareness.
 Tier B (score): pairwise explainable score  S = .45 text + .25 category + .12 time(gated) + .10 complainant + .08 amount
 Different matters at one institution are NOT flagged as overlaps (subject gating); nothing is auto-merged."""
import math
from itertools import combinations
from . import concepts as K
from .matching import get_index

W = {"text": .45, "cat": .25, "time": .12, "comp": .10, "amt": .08}
HIGH, MEDIUM = 0.60, 0.40
SEV = {"High": 3, "Medium": 2, "Info": 1}


def score_pair(a, b) -> tuple[float, dict]:
    ca, cb = K.concepts(a.description + " " + getattr(a, "subject", "")), K.concepts(b.description + " " + getattr(b, "subject", ""))
    text = K.cosine(ca, cb)
    cat = 1.0 if a.category == b.category else 0.5 if frozenset((a.category, b.category)) in K.RELATED else 0.0
    days = abs((a.received_on - b.received_on).days)
    time = math.pow(2, -days / 60) * min(1.0, text / 0.30)  # temporal proximity only counts if the subject is related
    comp = 1.0 if a.complainant_hash and a.complainant_hash == b.complainant_hash else 0.0
    amt = 1.0 if K.numbers(a.description) & K.numbers(b.description) else 0.0
    s = W["text"] * text + W["cat"] * cat + W["time"] * time + W["comp"] * comp + W["amt"] * amt
    if cat == 0 and text < 0.20 and not comp:
        s = min(s, 0.30)  # unrelated matters at the same institution
    shared = sorted(set(ca) & set(cb))
    return round(s, 3), {"text": round(text, 2), "category": cat, "days_apart": days, "same_complainant": bool(comp),
                         "shared_amount": bool(amt), "shared_concepts": shared}


def sev(s):
    return "High" if s >= HIGH else "Medium" if s >= MEDIUM else None


def explain(a, b, s, p, inferred) -> str:
    bits = [f"{a.bureau} and {b.bureau} are both acting on this institution" if a.bureau != b.bureau else f"Two cases at {a.bureau}"]
    if p["category"] == 1: bits.append("same complaint category")
    if p["shared_concepts"]: bits.append("shared subject: " + ", ".join(p["shared_concepts"]))
    if p["text"]: bits.append(f"{round(p['text'] * 100)}% content similarity (works across English/Hinglish/Hindi)")
    if p["same_complainant"]: bits.append("same complainant")
    if p["shared_amount"]: bits.append("same amount quoted")
    bits.append(f"filed {p['days_apart']} day(s) apart")
    if inferred: bits.append("institution linked by name matching (no clean AICTE ID quoted)")
    return "; ".join(bits)


def effective_institution(c, index):
    if c.institution_id:
        return c.institution_id, 1.0, False
    m = index.resolve(c.institution_ref)
    return (m["institution_id"], m["score"], True) if m["band"] == "auto" else (None, m["score"], False)


def pair_key(a, b):
    x, y = sorted((a.id, b.id)); return f"{x}-{y}"


def detect(db, cases, reviews: dict | None = None):
    reviews = reviews or {}; index = get_index(db); groups = {}
    for c in cases:
        if c.status == "Disposed":
            continue
        iid, conf, inf = effective_institution(c, index)
        if iid:
            groups.setdefault(iid, []).append((c, conf, inf))
    out = []
    for iid, items in groups.items():
        pairs = []
        for (a, _, ia), (b, _, ib) in combinations(items, 2):
            s, parts = score_pair(a, b); rv = reviews.get(pair_key(a, b))
            if sev(s) and not (rv and rv["status"] == "Not related"):
                pairs.append({"case_a": a.case_no, "case_b": b.case_no, "id_a": a.id, "id_b": b.id, "bureau_a": a.bureau,
                              "bureau_b": b.bureau, "score": s, "severity": sev(s), "cross_bureau": a.bureau != b.bureau,
                              "signals": parts, "explanation": explain(a, b, s, parts, ia or ib), "review": rv})
        bureaus = sorted({c.bureau for c, _, _ in items})
        if len(bureaus) < 2 and not pairs:
            continue
        pairs.sort(key=lambda p: -p["score"]); inst = index.items[iid]
        top = pairs[0]["severity"] if pairs else "Info"
        out.append({"institution_id": iid, "aicte_id": inst.aicte_id, "institution": inst.name, "bureaus": bureaus, "severity": top,
                    "message": "Potential Overlapping Cases - Coordination Required" if pairs else "Multiple Bureaus/Cells active - issues appear different (awareness only)",
                    "score": pairs[0]["score"] if pairs else 0, "pairs": pairs,
                    "cases": [{"id": c.id, "case_no": c.case_no, "bureau": c.bureau, "category": c.category, "status": c.status,
                               "inferred_institution": inf} for c, _, inf in items]})
    return sorted(out, key=lambda g: (-SEV[g["severity"]], -g["score"]))
