"""Conflicting-action detection: the PS asks to prevent 'conflicting or parallel actions' - not only parallel cases.
Flags contradictory outcomes by different Bureaus/Cells on related matters at the same institution."""
from itertools import combinations
from sqlalchemy import select
from ..models import CaseAction
from .overlap import effective_institution
from .matching import get_index
from . import concepts as K

RULES = [  # (kind X, kind Y, severity, message)
    ("approval_withdrawn", "compliance_found", "High", "One Bureau withdrew approval while another found the institution compliant"),
    ("penalty", "compliance_found", "High", "A penalty is being imposed while another Bureau found the institution compliant"),
    ("approval_withdrawn", "closure", "Medium", "Approval withdrawn by one Bureau while another closed a related case"),
    ("show_cause", "closure", "Medium", "Show-cause issued by one Bureau on a matter another Bureau has closed"),
]


def detect(db, cases):
    index = get_index(db); by_inst = {}
    for c in cases:
        iid, _, _ = effective_institution(c, index)
        if iid:
            by_inst.setdefault(iid, []).append(c)
    out = []
    for iid, cs in by_inst.items():
        if len({c.bureau for c in cs}) < 2:
            continue
        kinds = {}
        for a in db.scalars(select(CaseAction).where(CaseAction.case_id.in_([c.id for c in cs]))):
            kinds.setdefault(a.case_id, set()).add(a.kind)
        for a, b in combinations(cs, 2):
            if a.bureau == b.bureau:
                continue
            related = a.category == b.category or K.cosine(K.concepts(a.description), K.concepts(b.description)) >= 0.30
            if not related:
                continue
            for x, y, sev_, msg in RULES:
                for p, q in ((a, b), (b, a)):
                    if x in kinds.get(p.id, ()) and y in kinds.get(q.id, ()):
                        out.append({"institution_id": iid, "institution": index.items[iid].name, "severity": sev_, "rule": f"{x} vs {y}",
                                    "message": msg + ". Coordination required before further action.",
                                    "case_a": p.case_no, "bureau_a": p.bureau, "kind_a": x, "case_b": q.case_no, "bureau_b": q.bureau, "kind_b": y})
    seen, uniq = set(), []
    for o in out:
        k = (o["case_a"], o["case_b"], o["rule"])
        if k not in seen:
            seen.add(k); uniq.append(o)
    return sorted(uniq, key=lambda o: o["severity"] != "High")
