"""Measures the engine against data/ground_truth.json (planted answers). SYNTHETIC data: use these numbers to detect
regressions and tune thresholds, NOT as evidence of accuracy on real AICTE complaints (needs expert-labelled real cases)."""
import json, sys
from itertools import combinations
from pathlib import Path
from sqlalchemy import select
from ..models import Case, Institution
from . import conflicts as CF, overlap as OV
from .matching import InstitutionIndex

TRUTH = Path(__file__).resolve().parents[2] / "data" / "ground_truth.json"


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0; r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0, "tp": tp, "fp": fp, "fn": fn}


def run(db) -> dict:
    t = json.loads(TRUTH.read_text()); insts = db.scalars(select(Institution)).all(); idx = InstitutionIndex(insts)
    by_aid = {i.aicte_id: i.id for i in insts}; cases = db.scalars(select(Case)).unique().all(); by_no = {c.case_no: c for c in cases}
    # 1) institution matcher on messy free-text references
    m = {"total": 0, "auto_correct": 0, "auto_wrong": 0, "review": 0, "review_contains_truth": 0, "unresolved": 0}
    for r in t["messy_refs"]:
        res = idx.resolve(r["ref"]); true = by_aid[r["true_institution"]]; m["total"] += 1
        if res["band"] == "auto":
            m["auto_correct" if res["institution_id"] == true else "auto_wrong"] += 1
        elif res["band"] == "review":
            m["review"] += 1; m["review_contains_truth"] += any(c["institution_id"] == true for c in res["candidates"])
        else:
            m["unresolved"] += 1
    m["auto_link_rate"] = round((m["auto_correct"] + m["auto_wrong"]) / max(1, m["total"]), 3)
    m["auto_precision"] = round(m["auto_correct"] / max(1, m["auto_correct"] + m["auto_wrong"]), 3)
    # 2) overlap pairs: candidates = every cross-bureau pair of ACTIVE cases at the same TRUE institution
    pos = {frozenset(p["cases"]) for p in t["planted_overlaps"]}; lang = {}
    truth_inst = {}
    for p in t["planted_overlaps"]:
        for n in p["cases"]:
            truth_inst[n] = by_aid[p["institution"]]
    active = [c for c in cases if c.status != "Disposed"]; grp = {}
    for c in active:
        grp.setdefault(truth_inst.get(c.case_no) or c.institution_id, []).append(c)
    scored = []
    for items in grp.values():
        for a, b in combinations(items, 2):
            if a.bureau != b.bureau:
                s, _ = OV.score_pair(a, b); scored.append((s, frozenset((a.case_no, b.case_no))))
    sweep = []
    for th in (0.30, 0.40, 0.50, 0.60, 0.70):
        tp = sum(1 for s, k in scored if s >= th and k in pos); fp = sum(1 for s, k in scored if s >= th and k not in pos)
        sweep.append({"threshold": th, **_prf(tp, fp, len(pos) - tp)})
    for p in t["planted_overlaps"]:  # recall by language of the complainant-side text
        a, b = (by_no[n] for n in p["cases"]); s, _ = OV.score_pair(a, b)
        d = lang.setdefault(a.lang, [0, 0]); d[0] += s >= OV.MEDIUM; d[1] += 1
    # 3) conflicts
    cf = CF.detect(db, cases); found = {frozenset((x["case_a"], x["case_b"])) for x in cf}; planted = {frozenset(c["cases"]) for c in t["planted_conflicts"]}
    return {"warning": "Synthetic data. Not evidence of real-world accuracy.", "institution_matcher": m,
            "overlap_threshold_sweep": sweep, "operating_threshold": OV.MEDIUM,
            "planted_overlap_recall_by_language": {k: {"found": v[0], "total": v[1]} for k, v in lang.items()},
            "conflicts": {"planted": len(planted), "found_planted": len(found & planted), "other_flags": len(found - planted)},
            "note": "Precision counts unlabelled background pairs as false positives; some may be genuine overlaps."}


if __name__ == "__main__":
    from ..db import SessionLocal
    with SessionLocal() as db:
        r = run(db)
    print(json.dumps(r, indent=1, ensure_ascii=False))
