import csv
import io
import json
import re
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from . import config, domain as D
from .db import get_db
from .deps import can_act, current_user, require_roles, visible_query
from .engine import concepts as K
from .engine.matching import get_index
from .models import AuditLog, Case, CaseAction, Institution, User, now_iso
from .security import (audit, clear_fails, make_token, pii_hash, record_fail, throttled, verify_chain, verify_password)

router = APIRouter(prefix="/api")


# ---------- serializers ----------
def inst_out(i: Institution | None):
    return None if not i else {"id": i.id, "aicte_id": i.aicte_id, "name": i.name, "city": i.city, "state": i.state,
                               "region": i.region, "address": i.address, "aliases": json.loads(i.aliases or "[]")}


def case_out(c: Case) -> dict:
    today = date.today(); active = c.status != "Disposed"
    return {"id": c.id, "case_no": c.case_no, "institution": inst_out(c.institution), "institution_ref": c.institution_ref,
            "category": c.category, "category_label": D.CATEGORIES[c.category][0], "priority": c.priority,
            "subject": c.subject, "description": c.description, "lang": c.lang, "received_on": c.received_on.isoformat(),
            "status": c.status, "bureau": c.bureau, "officer": c.officer.name if c.officer else None,
            "last_action": c.last_action, "next_action": c.next_action, "last_action_on": c.last_action_on.isoformat(),
            "due_on": c.due_on.isoformat(), "overdue": active and c.due_on < today,
            "days_to_due": (c.due_on - today).days if active else None, "sealed": c.sealed}


def get_visible_case(db: Session, user: User, case_id: int) -> Case:
    c = db.scalar(visible_query(user).where(Case.id == case_id))
    if not c:
        raise HTTPException(404, "Case not found")
    return c


def least_loaded(db: Session, bureau: str, region: str | None = None) -> User | None:
    q = select(User).where(User.bureau == bureau, User.role.in_(["OFFICER", "REGIONAL"]))
    if bureau == "RO" and region:
        q = q.where(User.region == region)
    best, load = None, 10**9
    for u in db.scalars(q):
        n = db.scalar(select(func.count()).select_from(Case).where(Case.officer_id == u.id, Case.status != "Disposed"))
        if n < load:
            best, load = u, n
    return best


# ---------- auth ----------
class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    key = f"{request.client.host if request.client else '-'}:{body.username.lower()}"
    if throttled(key):
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    u = db.scalar(select(User).where(User.username == body.username.lower()))
    if not u or not verify_password(body.password, u.pw_hash):
        record_fail(key); audit(db, body.username[:50], "LOGIN_FAILED", "user", "-"); db.commit()
        raise HTTPException(401, "Invalid username or password")
    clear_fails(key); audit(db, u.username, "LOGIN", "user", u.id); db.commit()
    response.set_cookie("session", make_token(u.id, u.role), httponly=True, samesite="lax",
                        secure=config.COOKIE_SECURE, max_age=config.TOKEN_HOURS * 3600)
    return me_out(u)


@router.post("/auth/logout")
def logout(response: Response):
    response.delete_cookie("session"); return {"ok": True}


def me_out(u: User):
    return {"id": u.id, "username": u.username, "name": u.name, "role": u.role, "bureau": u.bureau, "region": u.region}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return me_out(user)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta(user: User = Depends(current_user)):
    return {"bureaus": D.BUREAUS, "regions": D.REGIONS, "statuses": D.STATUSES, "priorities": D.PRIORITIES,
            "categories": {k: {"label": v[0], "sla_days": v[1], "default_bureau": v[2], "sealed": v[3]} for k, v in D.CATEGORIES.items()},
            "action_kinds": D.ACTION_KINDS}


# ---------- cases ----------
@router.get("/cases")
def list_cases(q: str = "", bureau: str = "", region: str = "", category: str = "", status: str = "",
               institution_id: int = 0, date_from: str = "", date_to: str = "", overdue: bool = False,
               page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=200),
               db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = visible_query(user)
    if q:
        like = f"%{q}%"
        s = s.where(or_(Case.case_no.ilike(like), Institution.name.ilike(like), Institution.aicte_id.ilike(like), Case.institution_ref.ilike(like)))
    for val, col in ((bureau, Case.bureau), (region, Institution.region), (category, Case.category), (status, Case.status)):
        if val:
            s = s.where(col == val)
    if institution_id:
        s = s.where(Case.institution_id == institution_id)
    if date_from:
        s = s.where(Case.received_on >= date.fromisoformat(date_from))
    if date_to:
        s = s.where(Case.received_on <= date.fromisoformat(date_to))
    if overdue:
        s = s.where(Case.status != "Disposed", Case.due_on < date.today())
    total = db.scalar(select(func.count()).select_from(s.subquery()))
    rows = db.scalars(s.order_by(Case.received_on.desc(), Case.id.desc()).offset((page - 1) * size).limit(size)).unique().all()
    return {"total": total, "page": page, "size": size, "items": [case_out(c) for c in rows]}


@router.get("/cases/{case_id}")
def get_case(case_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = get_visible_case(db, user, case_id)
    if c.sealed:
        audit(db, user.username, "VIEW_SEALED", "case", c.id); db.commit()  # every view of a sealed case is logged
    hist = db.scalars(select(CaseAction).where(CaseAction.case_id == c.id).order_by(CaseAction.id)).all()
    return {"case": case_out(c), "can_act": can_act(user, c),
            "history": [{"ts": h.ts, "bureau": h.bureau, "actor": h.actor, "action": h.action, "kind": h.kind,
                         "remarks": h.remarks, "doc": h.doc} for h in hist]}


class CaseIn(BaseModel):
    subject: str = Field(min_length=5, max_length=300)
    description: str = Field(min_length=10, max_length=5000)
    category: str
    institution_id: int | None = None
    institution_ref: str = Field("", max_length=300)
    complainant_contact: str = ""
    bureau: str | None = None
    priority: str = "Normal"
    lang: str = "en"


@router.post("/cases", status_code=201)
def create_case(body: CaseIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if body.category not in D.CATEGORIES:
        raise HTTPException(422, "Unknown category")
    label, sla, default_b, sealed = D.CATEGORIES[body.category]
    bureau = body.bureau or default_b
    if bureau not in D.BUREAUS or body.priority not in D.PRIORITIES:
        raise HTTPException(422, "Invalid bureau or priority")
    inst = db.get(Institution, body.institution_id) if body.institution_id else None
    if body.institution_id and not inst:
        raise HTTPException(422, "Unknown institution")
    today = date.today()
    seq = (db.scalar(select(func.max(Case.id))) or 0) + 1
    off = least_loaded(db, bureau, inst.region if inst else None)
    c = Case(case_no=f"AICTE/{bureau}/{today.year}/{seq:05d}", institution_id=inst.id if inst else None,
             institution_ref=body.institution_ref or (inst.name if inst else ""), category=body.category,
             priority=body.priority, subject=body.subject, description=body.description, lang=body.lang, received_on=today,
             status="Pending", bureau=bureau, officer_id=off.id if off else None, last_action="Received and registered",
             next_action="Initial examination", last_action_on=today, due_on=today + timedelta(days=sla), sealed=sealed,
             complainant_hash=pii_hash(body.complainant_contact))
    db.add(c); db.flush()
    db.add(CaseAction(case_id=c.id, ts=now_iso(), bureau=bureau, actor=user.name, action="received", kind="note", remarks="Complaint registered"))
    audit(db, user.username, "CASE_CREATE", "case", c.id, c.case_no); db.commit()
    return case_out(c)


class ActionIn(BaseModel):
    action: str  # update | accept | transfer | escalate | dispose | reopen
    kind: str = "note"
    remarks: str = Field("", max_length=3000)
    next_action: str = ""
    to_bureau: str | None = None
    doc: str = ""


@router.post("/cases/{case_id}/actions")
def act(case_id: int, body: ActionIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    c = get_visible_case(db, user, case_id)
    if not can_act(user, c):
        raise HTTPException(403, "Only the Bureau/Cell holding this case can act on it")
    if body.kind not in D.ACTION_KINDS:
        raise HTTPException(422, "Unknown action kind")
    a, st = body.action, c.status
    if a != "reopen" and st == "Disposed":
        raise HTTPException(409, "Case is disposed; reopen it first")
    summary = body.remarks[:120] or a.title()
    if a == "update":
        c.status = "Under Process"
    elif a == "accept":
        if st != "Transferred":
            raise HTTPException(409, "Only transferred cases can be accepted")
        c.status = "Under Process"
    elif a == "transfer":
        if body.to_bureau not in D.BUREAUS or body.to_bureau == c.bureau:
            raise HTTPException(422, "Choose a different, valid Bureau/Cell")
        summary = f"Transferred {c.bureau} -> {body.to_bureau}. {body.remarks[:80]}"
        c.bureau, c.status = body.to_bureau, "Transferred"
        o = least_loaded(db, c.bureau, c.institution.region if c.institution else None); c.officer_id = o.id if o else None
    elif a == "escalate":
        c.status = "Escalated"
    elif a == "dispose":
        if st == "Escalated" and user.role != "ADMIN":
            raise HTTPException(403, "Escalated cases can only be disposed by the Competent Authority")
        c.status, c.next_action = "Disposed", "-"
    elif a == "reopen":
        if st != "Disposed" or user.role not in ("ADMIN", "HEAD"):
            raise HTTPException(403, "Only a Head/Competent Authority can reopen a disposed case")
        c.status = "Under Process"
    else:
        raise HTTPException(422, "Unknown action")
    c.last_action, c.last_action_on = summary, date.today()
    if body.next_action and a != "dispose":
        c.next_action = body.next_action
    db.add(CaseAction(case_id=c.id, ts=now_iso(), bureau=c.bureau, actor=user.name, action=a, kind=body.kind, remarks=body.remarks, doc=body.doc))
    audit(db, user.username, f"CASE_{a.upper()}", "case", c.id, f"{st} -> {c.status}"); db.commit()
    return case_out(c)


# ---------- institutions ----------
@router.get("/institutions")
def institutions(q: str = "", region: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    s = select(Institution)
    if q:
        s = s.where(or_(Institution.name.ilike(f"%{q}%"), Institution.aicte_id.ilike(f"%{q}%"), Institution.city.ilike(f"%{q}%")))
    if region:
        s = s.where(Institution.region == region)
    insts = db.scalars(s.order_by(Institution.name).limit(300)).all()
    active = dict(db.execute(visible_query(user).with_only_columns(Case.institution_id, func.count())
                             .where(Case.status != "Disposed").group_by(Case.institution_id)).all())
    return [{**inst_out(i), "active_cases": active.get(i.id, 0)} for i in insts]


@router.get("/institutions/{inst_id}")
def institution(inst_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    i = db.get(Institution, inst_id)
    if not i:
        raise HTTPException(404, "Institution not found")
    cases = db.scalars(visible_query(user).where(Case.institution_id == i.id).order_by(Case.received_on.desc())).unique().all()
    return {"institution": inst_out(i), "cases": [case_out(c) for c in cases],
            "bureaus_active": sorted({c.bureau for c in cases if c.status != "Disposed"})}


# ---------- dashboard ----------
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), user: User = Depends(current_user)):
    cases = db.scalars(visible_query(user)).unique().all(); today = date.today()
    cnt = Counter(c.status for c in cases); active = [c for c in cases if c.status != "Disposed"]
    ageing = Counter()
    for c in active:
        a = (today - c.received_on).days
        ageing["0-15" if a <= 15 else "16-30" if a <= 30 else "31-60" if a <= 60 else "60+"] += 1
    wl = {b: {"active": 0, "overdue": 0, "total": 0} for b in D.BUREAUS}
    for c in cases:
        wl[c.bureau]["total"] += 1
        if c.status != "Disposed":
            wl[c.bureau]["active"] += 1; wl[c.bureau]["overdue"] += c.due_on < today
    inst = Counter(c.institution.name for c in active if c.institution)
    monthly = Counter(c.received_on.strftime("%Y-%m") for c in cases)
    multi = {}
    for c in active:
        if c.institution_id:
            multi.setdefault(c.institution_id, set()).add(c.bureau)
    return {"total": len(cases), "by_status": {s: cnt.get(s, 0) for s in D.STATUSES},
            "overdue": sum(c.due_on < today for c in active), "due_in_7_days": sum(0 <= (c.due_on - today).days <= 7 for c in active),
            "multi_bureau_institutions": sum(len(b) > 1 for b in multi.values()), "bureau_workload": wl,
            "ageing": {k: ageing.get(k, 0) for k in ("0-15", "16-30", "31-60", "60+")},
            "top_institutions": [{"name": n, "active": v} for n, v in inst.most_common(8)],
            "monthly_inflow": [{"month": m, "received": v} for m, v in sorted(monthly.items())],
            "disposal_rate": round(100 * cnt.get("Disposed", 0) / max(1, len(cases)), 1)}


# ---------- audit ----------
@router.get("/audit")
def audit_log(limit: int = Query(100, le=500), db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"id": r.id, "ts": r.ts, "actor": r.actor, "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
             "detail": r.detail, "hash": r.hash[:12]} for r in rows]


@router.get("/audit/verify")
def audit_verify(db: Session = Depends(get_db), user: User = Depends(require_roles("ADMIN"))):
    return verify_chain(db)


# ---------- documents ----------
@router.post("/cases/{case_id}/documents")
async def upload_document(
    case_id: int,
    file: UploadFile = File(...),
    remarks: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    c = get_visible_case(db, user, case_id)
    if not can_act(user, c):
        raise HTTPException(403, "Only the Bureau/Cell holding this case can upload documents")
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"]:
        raise HTTPException(400, "Only PDF, image, DOCX, or text files are supported")
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_token = uuid.uuid4().hex[:10]
    cleaned_base = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", Path(file.filename or "doc").stem)[:30]
    stored_filename = f"{c.id}_{safe_token}_{cleaned_base}{ext}"
    target_path = config.UPLOAD_DIR / stored_filename
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "File exceeds maximum 10MB limit")
    target_path.write_bytes(contents)

    doc_summary = remarks.strip() or f"Attached: {file.filename}"
    db.add(CaseAction(
        case_id=c.id,
        ts=now_iso(),
        bureau=c.bureau,
        actor=user.name,
        action="document",
        kind="document",
        remarks=doc_summary,
        doc=stored_filename,
    ))
    audit(db, user.username, "DOC_UPLOAD", "case", c.id, stored_filename)
    db.commit()
    return {"filename": stored_filename, "original_name": file.filename, "remarks": doc_summary}


@router.get("/documents/{filename}")
def get_document(filename: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not re.match(r"^\d+_[a-f0-9]+_[a-zA-Z0-9_\-\.]+$", filename):
        raise HTTPException(400, "Invalid document filename")
    file_path = config.UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(404, "Document not found")
    case_id = int(filename.split("_")[0])
    c = db.scalar(visible_query(user).where(Case.id == case_id))
    if not c:
        raise HTTPException(403, "Access to this case document is not permitted")
    if c.sealed:
        audit(db, user.username, "VIEW_SEALED_DOC", "case", c.id, filename)
        db.commit()
    return FileResponse(file_path, filename=filename)


# ---------- public grievance tracking ----------
@router.get("/public/track/{case_no:path}")
def track_case(case_no: str, db: Session = Depends(get_db)):
    clean_no = case_no.strip()
    c = db.scalar(select(Case).where(Case.case_no.ilike(clean_no)))
    if not c:
        c = db.scalar(select(Case).where(Case.case_no.ilike(clean_no.replace("-", "/"))))
    if not c:
        raise HTTPException(404, "No grievance found with this reference number. Please check the AICTE Case Number.")
    today = date.today()
    if c.sealed:
        return {
            "case_no": c.case_no,
            "status": "Under Process",
            "received_on": c.received_on.isoformat(),
            "bureau": c.bureau,
            "bureau_label": D.BUREAUS.get(c.bureau, c.bureau),
            "category_label": "Confidential Inquiry",
            "institution_name": "Protected Institution Record",
            "city": "",
            "state": "",
            "last_action": "Under review by the competent committee",
            "last_action_date": c.last_action_on.isoformat(),
            "expected_disposal": c.due_on.isoformat(),
            "days_remaining": max(0, (c.due_on - today).days),
            "milestones": [
                {"title": "Grievance Registered", "date": c.received_on.isoformat(), "done": True},
                {"title": "Confidential Committee Review", "date": c.last_action_on.isoformat(), "done": True},
                {"title": "Final Redressal", "date": c.due_on.isoformat(), "done": c.status == "Disposed"},
            ],
        }

    cat_label = D.CATEGORIES.get(c.category, (c.category,))[0]
    actions = db.scalars(select(CaseAction).where(CaseAction.case_id == c.id).order_by(CaseAction.id)).all()
    milestones = [{"title": "Grievance Registered", "date": c.received_on.isoformat(), "done": True}]
    for act in actions:
        if act.action == "transfer":
            milestones.append({"title": f"Transferred to {act.bureau}", "date": act.ts[:10], "done": True})
        elif act.action in ("hearing", "inspection", "show_cause"):
            milestones.append({"title": act.action.replace("_", " ").title(), "date": act.ts[:10], "done": True})
        elif act.action == "dispose":
            milestones.append({"title": "Final Disposal / Redressal", "date": act.ts[:10], "done": True})

    if c.status != "Disposed":
        milestones.append({"title": "Expected Disposal", "date": c.due_on.isoformat(), "done": False})

    return {
        "case_no": c.case_no,
        "status": c.status,
        "received_on": c.received_on.isoformat(),
        "bureau": c.bureau,
        "bureau_label": D.BUREAUS.get(c.bureau, c.bureau),
        "category_label": cat_label,
        "institution_name": c.institution.name if c.institution else c.institution_ref,
        "city": c.institution.city if c.institution else "",
        "state": c.institution.state if c.institution else "",
        "last_action": c.last_action,
        "last_action_date": c.last_action_on.isoformat(),
        "expected_disposal": c.due_on.isoformat(),
        "days_remaining": max(0, (c.due_on - today).days) if c.status != "Disposed" else 0,
        "milestones": milestones,
    }


# ---------- bulk CSV import ----------
@router.get("/cases/import/template")
def get_import_template():
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["institution_ref", "subject", "description", "category", "bureau", "priority", "complainant_contact"])
    w.writerow(["Aryabhatta Institute of Technology", "Fee refund not processed", "Student withdrew admission within 15 days, college withholding Rs 45000", "fee_refund", "PGRC", "Normal", "student@example.com"])
    w.writerow(["Vivekananda College of Engineering", "Irregular faculty cadre ratio", "College employs unqualified lecturers not meeting APH norms", "faculty_norms", "RB", "High", "faculty@example.com"])
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=aicte_complaints_import_template.csv"})


@router.post("/cases/import/preview")
async def preview_import(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(current_user)):
    content = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(422, "Empty or invalid CSV file")
    idx = get_index(db)
    items = []
    for row_idx, r in enumerate(reader, start=2):
        inst_ref = (r.get("institution_ref") or r.get("institution") or "").strip()
        subj = (r.get("subject") or "").strip()
        desc = (r.get("description") or "").strip()
        cat = (r.get("category") or "").strip().lower()
        bureau = (r.get("bureau") or "").strip().upper()
        prio = (r.get("priority") or "Normal").strip().title()
        contact = (r.get("complainant_contact") or "").strip()

        errors = []
        if len(subj) < 5:
            errors.append("Subject must be at least 5 characters")
        if len(desc) < 10:
            errors.append("Description must be at least 10 characters")

        inst_match = idx.resolve(inst_ref) if inst_ref else {"institution_id": None, "score": 0.0, "band": "none", "reason": "No institution specified", "candidates": []}
        sugg_cat, conf, hit, _ = K.classify(subj + " " + desc)
        if not cat:
            cat = sugg_cat or "fee_refund"
        elif cat not in D.CATEGORIES:
            errors.append(f"Invalid category '{cat}'")

        default_b = D.CATEGORIES.get(cat, ("", 30, "RB", False))[2]
        final_bureau = bureau or default_b
        if final_bureau not in D.BUREAUS:
            errors.append(f"Invalid bureau '{final_bureau}'")
        if prio not in D.PRIORITIES:
            prio = "Normal"

        overlap_warning = None
        if inst_match["institution_id"]:
            active_cases = db.scalars(select(Case).where(Case.institution_id == inst_match["institution_id"], Case.status != "Disposed")).all()
            burs = {c.bureau for c in active_cases}
            if any(b != final_bureau for b in burs):
                overlap_warning = f"Institution already active in {', '.join(burs)}"

        inst_obj = db.get(Institution, inst_match["institution_id"]) if inst_match["institution_id"] else None

        items.append({
            "row": row_idx,
            "valid": len(errors) == 0,
            "errors": errors,
            "institution_ref": inst_ref,
            "institution_matched": inst_obj.name if inst_obj else None,
            "institution_id": inst_match["institution_id"],
            "match_band": inst_match["band"],
            "match_score": inst_match["score"],
            "subject": subj,
            "description": desc,
            "category": cat,
            "category_label": D.CATEGORIES.get(cat, (cat,))[0] if cat in D.CATEGORIES else cat,
            "bureau": final_bureau,
            "priority": prio,
            "complainant_contact": contact,
            "overlap_warning": overlap_warning,
        })

    return {
        "total_rows": len(items),
        "valid_rows": sum(1 for p in items if p["valid"]),
        "items": items,
    }


class CommitRowIn(BaseModel):
    subject: str
    description: str
    category: str
    bureau: str | None = None
    priority: str = "Normal"
    institution_id: int | None = None
    institution_ref: str = ""
    complainant_contact: str = ""
    valid: bool = True


class CommitIn(BaseModel):
    items: list[CommitRowIn]


@router.post("/cases/import/commit")
def commit_import(body: CommitIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    today = date.today()
    created_cases = []

    for row in body.items:
        if not row.valid:
            continue
        cat = row.category
        if cat not in D.CATEGORIES:
            continue
        label, sla, default_b, sealed = D.CATEGORIES[cat]
        bureau = row.bureau or default_b
        if bureau not in D.BUREAUS:
            continue
        prio = row.priority if row.priority in D.PRIORITIES else "Normal"
        iid = row.institution_id
        inst = db.get(Institution, iid) if iid else None

        seq = (db.scalar(select(func.max(Case.id))) or 0) + 1
        off = least_loaded(db, bureau, inst.region if inst else None)
        c = Case(
            case_no=f"AICTE/{bureau}/{today.year}/{seq:05d}",
            institution_id=inst.id if inst else None,
            institution_ref=row.institution_ref or (inst.name if inst else ""),
            category=cat,
            priority=prio,
            subject=row.subject,
            description=row.description,
            lang="en",
            received_on=today,
            status="Pending",
            bureau=bureau,
            officer_id=off.id if off else None,
            last_action="Registered via bulk CSV import",
            next_action="Initial examination",
            last_action_on=today,
            due_on=today + timedelta(days=sla),
            sealed=sealed,
            complainant_hash=pii_hash(row.complainant_contact),
        )
        db.add(c)
        db.flush()
        db.add(CaseAction(
            case_id=c.id,
            ts=now_iso(),
            bureau=bureau,
            actor=user.name,
            action="received",
            kind="note",
            remarks=f"Registered via bulk CSV import by {user.name}",
        ))
        created_cases.append(c)

    audit(db, user.username, "BULK_IMPORT", "cases", f"count:{len(created_cases)}")
    db.commit()
    return {"imported": len(created_cases), "cases": [case_out(c) for c in created_cases]}

