"""Configurable domain rules. SLA days are ILLUSTRATIVE, not official AICTE norms - admin-editable in production."""
BUREAUS = {"RB": "Regulation Bureau", "PGRC": "Public Grievance Redressal Cell", "AB": "Approval Bureau",
           "ARC": "Anti-Ragging Cell", "RO": "Regional Office"}
REGIONS = ["Northern", "Eastern", "Western", "Southern", "Central", "North-Eastern"]
STATUSES = ["Pending", "Under Process", "Transferred", "Escalated", "Disposed"]
ROLES = ["ADMIN", "HEAD", "OFFICER", "REGIONAL"]
# code: (label, sla_days, default bureau, sealed by default)
CATEGORIES = {
    "faculty_norms": ("Faculty qualification / norms", 60, "RB", False),
    "salary_delay": ("Faculty salary not paid", 30, "PGRC", False),
    "fee_refund": ("Fee refund / excess fee", 30, "PGRC", False),
    "certificates": ("Certificates withheld", 15, "PGRC", False),
    "unapproved_intake": ("Admission beyond approved intake", 45, "RB", False),
    "infrastructure": ("Infrastructure deficiency", 60, "RB", False),
    "ragging": ("Ragging / harassment", 7, "ARC", True),
}
ACTION_KINDS = ["note", "show_cause", "inspection", "reply_received", "hearing", "approval_withdrawn",
                "compliance_found", "closure", "refund_ordered", "penalty"]
PRIORITIES = ["Low", "Normal", "High", "Critical"]
