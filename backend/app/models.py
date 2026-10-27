from datetime import date, datetime, timezone
from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20))
    bureau: Mapped[str | None] = mapped_column(String(10))
    region: Mapped[str | None] = mapped_column(String(30))
    pw_hash: Mapped[str] = mapped_column(String(200))


class Institution(Base):
    __tablename__ = "institutions"
    id: Mapped[int] = mapped_column(primary_key=True)
    aicte_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    aliases: Mapped[str] = mapped_column(Text, default="[]")  # JSON list: former names, abbreviations
    city: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(60))
    region: Mapped[str] = mapped_column(String(30), index=True)
    address: Mapped[str] = mapped_column(String(300), default="")


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (Index("ix_case_scan", "status", "bureau", "institution_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    case_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    institution_id: Mapped[int | None] = mapped_column(ForeignKey("institutions.id"), index=True)
    institution_ref: Mapped[str] = mapped_column(String(300), default="")  # text exactly as the complainant wrote it
    category: Mapped[str] = mapped_column(String(30), index=True)
    priority: Mapped[str] = mapped_column(String(10), default="Normal")
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    lang: Mapped[str] = mapped_column(String(5), default="en")
    received_on: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    bureau: Mapped[str] = mapped_column(String(10), index=True)
    officer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    last_action: Mapped[str] = mapped_column(String(300), default="")
    next_action: Mapped[str] = mapped_column(String(300), default="")
    last_action_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    sealed: Mapped[bool] = mapped_column(Boolean, default=False)
    complainant_hash: Mapped[str] = mapped_column(String(64), default="")  # salted hash only, never raw PII
    institution: Mapped[Institution | None] = relationship(lazy="joined")
    officer: Mapped[User | None] = relationship(lazy="joined")


class CaseAction(Base):
    __tablename__ = "case_actions"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    ts: Mapped[str] = mapped_column(String(25))
    bureau: Mapped[str] = mapped_column(String(10))
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(40))  # received/update/transfer/accept/escalate/dispose/reopen
    kind: Mapped[str] = mapped_column(String(30), default="note")  # semantic tag used by the conflict detector
    remarks: Mapped[str] = mapped_column(Text, default="")
    doc: Mapped[str] = mapped_column(String(200), default="")


class AuditLog(Base):
    """Append-only, hash-chained: each row commits to the previous one, so edits/deletions are detectable."""
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[str] = mapped_column(String(25))
    actor: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64))


class OverlapReview(Base):
    """Officer decision on a flagged pair. The engine only advises - humans decide, nothing is auto-merged."""
    __tablename__ = "overlap_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    pair_key: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20))  # Acknowledged | Coordinating | Not related
    lead_bureau: Mapped[str | None] = mapped_column(String(10))
    note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[str] = mapped_column(String(50))
    ts: Mapped[str] = mapped_column(String(25))
