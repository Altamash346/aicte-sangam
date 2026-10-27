from datetime import date
from types import SimpleNamespace
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import domain as D
from .api import case_out, get_visible_case
from .db import get_db
from .deps import current_user, require_roles, visible_query
from .engine import concepts as K, conflicts as CF, overlap as OV
from .engine.matching import get_index
from .models import Case, CaseAction, OverlapReview, User, now_iso
from .security import audit

router = APIRouter(prefix="/api")


def _reviews(db):
    return {r.pair_key: {"status": r.status, "lead_bureau": r.lead_bureau, "note": r.note, "by": r.reviewed_by} for r in db.scalars(select(OverlapReview))}


def _visible(db, user):
    return db.scalars(visible_query(user)).unique().all()


@router.get("/overlaps")
def overlaps(min_severity: str = "Info", db: Session = Depends(get_db), user: User = Depends(current_user)):
    g = OV.detect(db, _visible(db, user), _reviews(db))
    return [x for x in g if OV.SEV[x["severity"]] >= OV.SEV.get(min_severity, 1)]


@router.get("/conflicts")
def conflicts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    return CF.detect(db, _visible(db, user))


@router.get("/cases/{case_id}/overlaps")
def case_overlaps(case_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = get_visible_case(db, user, case_id); iid = OV.effective_institution(c, get_index(db))[0]
    groups = [g for g in OV.detect(db, _visible(db, user), _reviews(db)) if g["institution_id"] == iid] if iid else []
    mine = [p for g in groups for p in g["pairs"] if case_id in (p["id_a"], p["id_b"])]
    cf = [x for x in CF.detect(db, _visible(db, user)) if c.case_no in (x["case_a"], x["case_b"])]
    return {"banner": "Potential Overlapping Cases - Coordination Required" if mine else None, "pairs": mine, "conflicts": cf,
            "bureaus_active": groups[0]["bureaus"] if groups else []}


@router.get("/institutions/resolve/match")
def resolve(q: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return get_index(db).resolve(q)


class IntakeIn(BaseModel):
    institution_ref: str = ""
    institution_id: int | None = None
    subject: str = ""
    description: str = Field(min_length=5)
    category: str | None = None


@router.post("/intake/analyze")
def analyze(body: IntakeIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Pre-registration check: who is the institution, what is this about, who else is already acting."""
    idx = get_index(db)
    m = {"institution_id": body.institution_id, "score": 1.0, "band": "auto", "reason": "Selected by officer", "candidates": []} \
        if body.institution_id else idx.resolve(body.institution_ref)
    cat, conf, hit, allscores = K.classify(body.subject + " " + body.description)
    category = body.category or cat; flags = []
    if len(allscores) > 1 and sorted(allscores.values())[-2] >= 0.4:
        flags.append("Complaint mixes several issues - more than one Bureau/Cell is likely to act")
    out = {"institution": m, "suggested_category": cat, "category_confidence": conf, "triggering_concepts": hit,
           "suggested_bureau": D.CATEGORIES[category][2] if category in D.CATEGORIES else None, "flags": flags, "similar_cases": [], "banner": None}
    if m["institution_id"] and category in D.CATEGORIES:
        tmp = SimpleNamespace(description=body.description, subject=body.subject, category=category, received_on=date.today(),
                              complainant_hash="", bureau=out["suggested_bureau"])
        for c in _visible(db, user):
            if c.status != "Disposed" and OV.effective_institution(c, idx)[0] == m["institution_id"]:
                s, p = OV.score_pair(tmp, c)
                if s >= 0.30:
                    out["similar_cases"].append({"case": case_out(c), "score": s, "likely_duplicate": s >= OV.HIGH, "explanation": OV.explain(tmp, c, s, p, False)})
        out["similar_cases"].sort(key=lambda x: -x["score"])
        if any(x["score"] >= OV.MEDIUM for x in out["similar_cases"]):
            out["banner"] = "Potential Overlapping Cases - Coordination Required"
    return out


class ReviewIn(BaseModel):
    case_a: int
    case_b: int
    decision: str  # acknowledge | designate_lead | not_related
    lead_bureau: str | None = None
    note: str = Field("", max_length=1000)


@router.post("/overlaps/review")
def review(body: ReviewIn, db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "HEAD", "OFFICER"))):
    a, b = get_visible_case(db, user, body.case_a), get_visible_case(db, user, body.case_b)
    key = OV.pair_key(a, b); status = {"acknowledge": "Acknowledged", "designate_lead": "Coordinating", "not_related": "Not related"}.get(body.decision)
    if not status:
        raise HTTPException(422, "Unknown decision")
    if body.decision == "designate_lead" and body.lead_bureau not in (a.bureau, b.bureau):
        raise HTTPException(422, "Lead must be one of the Bureaus/Cells handling these cases")
    r = db.scalar(select(OverlapReview).where(OverlapReview.pair_key == key)) or OverlapReview(pair_key=key)
    r.status, r.lead_bureau, r.note, r.reviewed_by, r.ts = status, body.lead_bureau, body.note, user.username, now_iso(); db.add(r)
    if status == "Coordinating":
        for c in (a, b):  # write the coordination decision into BOTH case histories
            db.add(CaseAction(case_id=c.id, ts=now_iso(), bureau=user.bureau or "-", actor=user.name, action="coordination", kind="note",
                              remarks=f"Linked with {(b if c is a else a).case_no}. Lead: {body.lead_bureau}. {body.note}"))
    audit(db, user.username, "OVERLAP_" + body.decision.upper(), "overlap", key, body.note[:100]); db.commit()
    return {"pair_key": key, "status": status, "lead_bureau": body.lead_bureau}


@router.get("/evaluation")
def evaluation(db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN", "HEAD"))):
    from .engine.evaluate import run
    return run(db)
