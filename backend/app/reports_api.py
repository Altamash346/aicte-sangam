"""Alerts, reports (JSON/CSV) and the impact estimate. All scoped to what the signed-in user may see."""
import csv, io
from collections import defaultdict
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from . import domain as D
from .db import get_db
from .deps import current_user, visible_query
from .engine import conflicts as CF, overlap as OV
from .models import OverlapReview, User
from .engine_api import _reviews, _visible

router = APIRouter(prefix="/api")
LEVEL = {"high": 0, "medium": 1, "low": 2}


@router.get("/alerts")
def alerts(mine: bool = False, db: Session = Depends(get_db), user: User = Depends(current_user)):
    cases = _visible(db, user); today = date.today(); out = []

    def add(kind, level, c, detail, action):
        out.append({"type": kind, "level": level, "case_id": c.id, "case_no": c.case_no, "institution": c.institution.name if c.institution else c.institution_ref,
                    "bureau": c.bureau, "officer": c.officer.name if c.officer else None, "detail": detail, "suggested": action, "href": f"#/case/{c.id}"})
    for c in cases:
        if c.status == "Disposed" or (mine and c.officer_id != user.id):
            continue
        left, idle = (c.due_on - today).days, (today - c.last_action_on).days
        if left < 0:
            add("Timeline / SLA breached", "high", c, f"Overdue by {-left} day(s)", "Dispose, escalate or record progress")
        elif left <= 7:
            add("Approaching timeline", "medium", c, f"Due in {left} day(s)", "Prioritise this case")
        if idle >= 10 and left >= 0:
            add("Pending reminder", "low", c, f"No action for {idle} day(s)", "Record the next step")
        if c.status == "Escalated":
            add("Escalation", "medium", c, "Awaiting direction from the Competent Authority", "Review and give directions")
    if not mine:
        for g in OV.detect(db, cases, _reviews(db)):
            if g["severity"] in ("High", "Medium") and g["pairs"]:
                p = g["pairs"][0]
                out.append({"type": "Overlap", "level": "high" if g["severity"] == "High" else "medium", "case_id": p["id_a"], "case_no": f"{p['case_a']} / {p['case_b']}",
                            "institution": g["institution"], "bureau": " + ".join(g["bureaus"]), "officer": None, "detail": g["message"], "suggested": "Coordinate and designate a lead Bureau", "href": "#/overlaps"})
        for x in CF.detect(db, cases):
            out.append({"type": "Conflicting actions", "level": "high" if x["severity"] == "High" else "medium", "case_id": None, "case_no": f"{x['case_a']} / {x['case_b']}",
                        "institution": x["institution"], "bureau": f"{x['bureau_a']} vs {x['bureau_b']}", "officer": None, "detail": x["message"], "suggested": "Hold further orders until coordinated", "href": "#/overlaps"})
    out.sort(key=lambda a: LEVEL[a["level"]])
    return {"counts": {k: sum(a["level"] == k for a in out) for k in LEVEL}, "items": out[:400]}


def _agg(cases, keyf, label):
    today = date.today(); d = defaultdict(lambda: {"total": 0, "active": 0, "disposed": 0, "overdue": 0, "age": 0})
    for c in cases:
        r = d[keyf(c)]; r["total"] += 1
        if c.status == "Disposed":
            r["disposed"] += 1
        else:
            r["active"] += 1; r["overdue"] += c.due_on < today; r["age"] += (today - c.received_on).days
    cols = [label, "Total", "Active", "Disposed", "Overdue", "Disposal rate %", "Avg age of active (days)"]
    rows = [[k, v["total"], v["active"], v["disposed"], v["overdue"], round(100 * v["disposed"] / v["total"], 1), round(v["age"] / v["active"]) if v["active"] else 0]
            for k, v in sorted(d.items(), key=lambda kv: -kv[1]["total"])]
    return cols, rows


def build_report(db, user, kind):
    cases = _visible(db, user); today = date.today()
    if kind == "bureau": return _agg(cases, lambda c: f"{c.bureau} - {D.BUREAUS[c.bureau]}", "Bureau/Cell")
    if kind == "region": return _agg([c for c in cases if c.institution], lambda c: c.institution.region, "Region")
    if kind == "institution": return _agg(cases, lambda c: c.institution.name if c.institution else "(unresolved)", "Institution")
    if kind == "category": return _agg(cases, lambda c: D.CATEGORIES[c.category][0], "Category")
    if kind == "status":
        return ["Status", "Cases"], [[s, sum(c.status == s for c in cases)] for s in D.STATUSES]
    if kind == "ageing":
        b = defaultdict(lambda: defaultdict(int))
        for c in cases:
            if c.status != "Disposed":
                a = (today - c.received_on).days; b[c.bureau]["0-15" if a <= 15 else "16-30" if a <= 30 else "31-60" if a <= 60 else "60+"] += 1
        return ["Bureau/Cell", "0-15 days", "16-30 days", "31-60 days", "60+ days"], [[k, v["0-15"], v["16-30"], v["31-60"], v["60+"]] for k, v in sorted(b.items())]
    if kind in ("monthly", "quarterly"):
        key = (lambda d: d.strftime("%Y-%m")) if kind == "monthly" else (lambda d: f"{d.year}-Q{(d.month - 1) // 3 + 1}")
        m = defaultdict(lambda: [0, 0])
        for c in cases:
            m[key(c.received_on)][0] += 1
            if c.status == "Disposed":
                m[key(c.last_action_on)][1] += 1
        return ["Period", "Received", "Disposed"], [[k, v[0], v[1]] for k, v in sorted(m.items())]
    if kind == "overlaps":
        g = OV.detect(db, cases, _reviews(db))
        return ["Institution", "AICTE ID", "Bureaus/Cells", "Severity", "Match %", "Review status"], [
            [x["institution"], x["aicte_id"], " + ".join(x["bureaus"]), x["severity"], round(100 * x["score"]), (x["pairs"][0]["review"] or {}).get("status", "Open") if x["pairs"] else "-"] for x in g]
    raise HTTPException(404, "Unknown report")


@router.get("/reports/{kind}")
def report(kind: str, format: str = Query("json"), db: Session = Depends(get_db), user: User = Depends(current_user)):
    cols, rows = build_report(db, user, kind)
    if format == "csv":
        buf = io.StringIO(); w = csv.writer(buf); w.writerow(cols); w.writerows(rows)
        return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=aicte_{kind}_report.csv"})
    return {"kind": kind, "columns": cols, "rows": rows, "generated": date.today().isoformat()}


@router.get("/impact")
def impact(hours_per_duplicate: float = Query(6, ge=0, le=100), db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Transparent ESTIMATE: every number is derived from live data except the stated assumption (hours per duplicated case)."""
    cases = _visible(db, user); groups = OV.detect(db, cases, _reviews(db)); today = date.today()
    pairs = [p for g in groups for p in g["pairs"] if p["cross_bureau"]]
    active = [c for c in cases if c.status != "Disposed"]
    return {"institutions_with_overlap": len([g for g in groups if g["pairs"]]), "cross_bureau_pairs": len(pairs),
            "conflicts_caught": len(CF.detect(db, cases)), "duplicate_cases_at_risk": len(pairs),
            "est_hours_saved": round(len(pairs) * hours_per_duplicate), "overdue": sum(c.due_on < today for c in active),
            "due_in_7_days": sum(0 <= (c.due_on - today).days <= 7 for c in active), "coordination_decisions": len([1 for p in pairs if p["review"]]),
            "assumption": f"Each duplicated case is assumed to cost {hours_per_duplicate:g} officer-hours (adjustable). Estimate, not a measurement."}
