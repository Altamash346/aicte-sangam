"""Deterministic synthetic data. ALL DATA IS FICTIONAL. Also writes data/ground_truth.json (planted overlaps,
conflicts, messy-reference truths) which Phase 2 uses to MEASURE the overlap engine honestly."""
import json, random, sys
from datetime import date, timedelta
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import domain as D
from .db import Base, SessionLocal, engine
from .models import Case, CaseAction, Institution, User, now_iso
from .security import audit, hash_password, pii_hash

R = random.Random(26264)
PW = "Aicte@2026"
PREFIX = ["Aryabhatta", "Vivekananda", "Saraswati", "Narmada", "Kaveri", "Himalaya", "Sahyadri", "Godavari", "Ganga", "Brahmaputra",
          "Thar", "Deccan", "Coromandel", "Malabar", "Vindhya", "Aravali", "Konkan", "Nilgiri", "Sundarban", "Satpura"]
SUFFIX = ["Institute of Engineering and Technology", "College of Engineering", "Institute of Technology",
          "School of Management", "Institute of Pharmacy", "Polytechnic"]
CITIES = [("Pune", "Maharashtra", "Western"), ("Nagpur", "Maharashtra", "Western"), ("Ahmedabad", "Gujarat", "Western"),
          ("Lucknow", "Uttar Pradesh", "Northern"), ("Jaipur", "Rajasthan", "Northern"), ("Chandigarh", "Punjab", "Northern"),
          ("Kolkata", "West Bengal", "Eastern"), ("Bhubaneswar", "Odisha", "Eastern"), ("Patna", "Bihar", "Eastern"),
          ("Chennai", "Tamil Nadu", "Southern"), ("Bengaluru", "Karnataka", "Southern"), ("Kochi", "Kerala", "Southern"),
          ("Bhopal", "Madhya Pradesh", "Central"), ("Indore", "Madhya Pradesh", "Central"), ("Raipur", "Chhattisgarh", "Central"),
          ("Guwahati", "Assam", "North-Eastern"), ("Shillong", "Meghalaya", "North-Eastern")]
ABBR = [("Institute", "Instt."), ("Engineering", "Engg"), ("College", "Clg"), ("Technology", "Tech"), ("Management", "Mgmt")]
# category -> (English A [student voice], English B [official voice], Hinglish, Hindi)
TXT = {
    "fee_refund": ("The college refuses to refund Rs {a} after I withdrew admission before the cut-off date.",
                   "Reports of non-compliance with the AICTE fee refund policy; students not refunded after withdrawal.",
                   "Admission cancel karne ke baad bhi college Rs {a} fee wapas nahi kar raha hai.",
                   "प्रवेश रद्द करने के बाद भी संस्थान ₹{a} शुल्क वापस नहीं कर रहा है।"),
    "salary_delay": ("Teachers have not received salary for {m} months at this institute.",
                     "Allegation that faculty remuneration is not paid as per the prescribed pay scale and timelines.",
                     "Is college mein teachers ko {m} mahine se salary nahi mili hai.",
                     "इस संस्थान में शिक्षकों को {m} महीने से वेतन नहीं मिला है।"),
    "certificates": ("The institute is holding my original certificates and demanding extra money to release them.",
                     "Complaint of withholding of original documents of students contrary to AICTE directions.",
                     "College meri original marksheet aur certificates rok kar paise maang raha hai.",
                     "संस्थान मेरे मूल प्रमाणपत्र रोककर अतिरिक्त पैसे मांग रहा है।"),
    "unapproved_intake": ("The college admitted far more students in MBA than its approved intake.",
                          "Intake observed beyond the sanctioned limit in the approved programme.",
                          "College ne approved seats se bahut zyada students ka admission le liya hai.",
                          "कॉलेज ने स्वीकृत सीटों से कहीं अधिक विद्यार्थियों को प्रवेश दिया है।"),
    "infrastructure": ("Our laboratories have no working equipment and the library is almost empty.",
                       "Deficiency of laboratory equipment and library resources against approval norms.",
                       "Hamare college ki labs mein equipment nahi hai aur library bhi khaali hai.",
                       "हमारे कॉलेज की प्रयोगशालाओं में उपकरण नहीं हैं और पुस्तकालय लगभग खाली है।"),
    "faculty_norms": ("Unqualified teachers are taking classes and the college shows fake faculty on paper.",
                      "Faculty qualifications and student-teacher ratio do not meet APH norms.",
                      "College mein qualified faculty nahi hai, sirf kaagaz par naam dikhaye hain.",
                      "कॉलेज में योग्य शिक्षक नहीं हैं, केवल कागज़ों पर नाम दिखाए गए हैं।"),
    "ragging": ("Senior students are harassing first-year students in the hostel and the management ignores it.",
                "Anonymous report of ragging in the hostel; institute response awaited.",
                "Hostel mein seniors pehle saal ke students ko pareshan kar rahe hain.",
                "छात्रावास में वरिष्ठ विद्यार्थी प्रथम वर्ष के विद्यार्थियों को परेशान कर रहे हैं।"),
}
PLANT_CATS = ["fee_refund", "salary_delay", "unapproved_intake", "infrastructure", "faculty_norms", "certificates"]


def shorten(name):
    for a, b in ABBR:
        name = name.replace(a, b)
    return name


def typo(s):
    if len(s) < 6:
        return s
    i = R.randrange(2, len(s) - 2); return s[:i] + s[i + 1] + s[i] + s[i + 2:]


def text(cat, variant):
    return TXT[cat][variant].format(a=R.choice([12000, 35000, 135000, 48500]), m=R.choice([3, 4, 6]))


def seed(db: Session, write_truth: bool = True):
    users = [("chairman", "Chairman (Competent Authority)", "ADMIN", None, None), ("ms", "Member Secretary", "ADMIN", None, None)]
    for b in ("RB", "PGRC", "AB", "ARC"):
        users.append((f"{b.lower()}.head", f"{b} Head", "HEAD", b, None))
        for n in range(1, 4 if b in ("RB", "PGRC") else 2):
            users.append((f"{b.lower()}.officer{n}", f"{b} Officer {n}", "OFFICER", b, None))
    for reg in D.REGIONS:
        users.append((f"ro.{reg.lower()}", f"{reg} Regional Officer", "REGIONAL", "RO", reg))
    h = hash_password(PW)
    for u, n, role, b, reg in users:
        db.add(User(username=u, name=n, role=role, bureau=b, region=reg, pw_hash=h))
    db.flush()
    officers = {}
    for u in db.scalars(select(User).where(User.role.in_(["OFFICER", "REGIONAL"]))):
        officers.setdefault((u.bureau, u.region if u.bureau == "RO" else None), []).append(u)

    combos = [(p, s) for p in PREFIX for s in SUFFIX]; R.shuffle(combos); insts = []
    for k, (p, s) in enumerate(combos[:60]):
        city, state, region = R.choice(CITIES); full = f"{p} {s}"
        acr = "".join(w[0] for w in full.split() if w[0].isupper())
        db.add(Institution(aicte_id=f"1-{R.randint(10**8, 10**9 - 1)}", name=full, city=city, state=state, region=region,
                           address=f"Plot {R.randint(1, 99)}, Education Hub, {city}",
                           aliases=json.dumps([shorten(full), acr, f"{p} College"], ensure_ascii=False)))
    db.flush(); insts = db.scalars(select(Institution)).all(); today = date.today(); seq = [0]
    truth = {"planted_overlaps": [], "planted_conflicts": [], "messy_refs": []}

    def mkcase(inst, cat, bureau, status, age, variant, kind_hint=None, messy=False, resolved=True, lang=None):
        seq[0] += 1; label, sla, _, sealed = D.CATEGORIES[cat]; rec = today - timedelta(days=age)
        lang = lang or ("en" if variant < 2 else "hi-en" if variant == 2 else "hi")
        ref = inst.name
        if messy:
            ref = R.choice([typo(shorten(inst.name)), json.loads(inst.aliases)[0], f"{json.loads(inst.aliases)[1]}, {inst.city}", typo(inst.name)])
        pool = officers.get((bureau, inst.region if bureau == "RO" else None)) or officers.get((bureau, None)) or [None]
        off = R.choice(pool)
        c = Case(case_no=f"AICTE/{bureau}/{rec.year}/{seq[0]:05d}", institution_id=inst.id if resolved else None,
                 institution_ref=ref, category=cat, priority=R.choice(["Normal", "Normal", "High"]),
                 subject=label + " - " + inst.name.split()[0], description=text(cat, variant), lang=lang, received_on=rec,
                 status=status, bureau=bureau, officer_id=off.id if off else None, last_action="Received and registered",
                 next_action="-" if status == "Disposed" else "Examine reply and submit note", last_action_on=rec,
                 due_on=rec + timedelta(days=sla), sealed=sealed, complainant_hash=pii_hash(f"c{seq[0]}@mail.test"))
        db.add(c); db.flush()
        db.add(CaseAction(case_id=c.id, ts=rec.isoformat() + "T10:00:00", bureau=bureau, actor="Diary Section", action="received", kind="note", remarks="Complaint registered"))
        if status != "Pending":
            la = rec + timedelta(days=R.randint(1, max(1, min(age, 12)))); kind = kind_hint or R.choice(["show_cause", "inspection", "reply_received", "hearing"])
            txt = {"approval_withdrawn": "Approval withdrawn for the programme", "compliance_found": "Institution found compliant on verification",
                   "closure": "Case closed", "show_cause": "Show-cause notice issued", "inspection": "Inspection ordered",
                   "reply_received": "Reply received from institution", "hearing": "Hearing scheduled"}.get(kind, "Updated")
            c.last_action, c.last_action_on = txt, la
            db.add(CaseAction(case_id=c.id, ts=la.isoformat() + "T15:30:00", bureau=bureau, actor=off.name if off else "Officer", action="update", kind=kind, remarks=txt))
        if messy:
            truth["messy_refs"].append({"case_no": c.case_no, "ref": ref, "true_institution": inst.aicte_id, "resolved_in_db": resolved})
        return c

    # planted cross-bureau overlaps: same institution, PGRC (complainant voice) + RB (official voice), different wording/language
    chosen = R.sample(insts, 14)
    for k, inst in enumerate(chosen):
        cat = PLANT_CATS[k % len(PLANT_CATS)]; lang_v = [0, 2, 3, 0][k % 4]
        a = mkcase(inst, cat, "PGRC", "Under Process", R.randint(15, 40), lang_v, messy=(k % 3 == 0))
        kind_b = "approval_withdrawn" if k < 4 else None; kind_a = "compliance_found" if k < 4 else None
        b = mkcase(inst, cat, "RB", "Under Process", R.randint(3, 14), 1, kind_hint=kind_b)
        if kind_a:
            a.last_action = "Institution found compliant on verification"
            db.add(CaseAction(case_id=a.id, ts=now_iso(), bureau="PGRC", actor="PGRC Officer", action="update", kind=kind_a, remarks=a.last_action))
            truth["planted_conflicts"].append({"cases": [a.case_no, b.case_no], "type": "approval_withdrawn_vs_compliant"})
        truth["planted_overlaps"].append({"cases": [a.case_no, b.case_no], "institution": inst.aicte_id, "category": cat})

    # background noise (random bureaus/categories); ~10% unresolved free-text references
    for _ in range(190):
        inst = R.choice(insts); cat = R.choice(list(D.CATEGORIES)); b = D.CATEGORIES[cat][2] if (R.random() < .8 or D.CATEGORIES[cat][3]) else R.choice(["RB", "PGRC", "AB", "RO"])
        st = R.choices(D.STATUSES, [3, 4, 1, 1, 4])[0]; messy = R.random() < .3
        mkcase(inst, cat, b, st, R.randint(2, 120), R.randint(0, 3), messy=messy, resolved=not (messy and R.random() < .35))
    audit(db, "system", "SEED", "db", "-", f"{seq[0]} synthetic cases, {len(insts)} institutions"); db.commit()
    if write_truth:
        p = Path(__file__).resolve().parent.parent / "data"; p.mkdir(exist_ok=True)
        (p / "ground_truth.json").write_text(json.dumps(truth, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if "--reset" in sys.argv:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    print("seeded")
