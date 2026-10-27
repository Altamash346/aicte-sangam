import hashlib, time
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import config
from .models import AuditLog, now_iso

_ph = PasswordHasher()
_fails: dict[str, list[float]] = {}


def hash_password(p: str) -> str:
    return _ph.hash(p)


def verify_password(p: str, h: str) -> bool:
    try:
        return _ph.verify(h, p)
    except (VerifyMismatchError, Exception):
        return False


def make_token(user_id: int, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=config.TOKEN_HOURS)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": exp}, config.SECRET_KEY, algorithm="HS256")


def read_token(tok: str) -> int | None:
    try:
        return int(jwt.decode(tok, config.SECRET_KEY, algorithms=["HS256"])["sub"])
    except Exception:
        return None


def throttled(key: str, limit: int = 5, window: int = 300) -> bool:
    t = time.time(); _fails[key] = [x for x in _fails.get(key, []) if t - x < window]
    return len(_fails[key]) >= limit


def record_fail(key: str):
    _fails.setdefault(key, []).append(time.time())


def clear_fails(key: str):
    _fails.pop(key, None)


def pii_hash(value: str) -> str:
    return hashlib.sha256((config.SECRET_KEY + (value or "").strip().lower()).encode()).hexdigest() if value else ""


def _h(prev, ts, actor, action, entity, eid, detail):
    return hashlib.sha256("|".join([prev, ts, actor, action, entity, str(eid), detail]).encode()).hexdigest()


def audit(db: Session, actor: str, action: str, entity: str, entity_id, detail: str = ""):
    last = db.scalar(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev = last.hash if last else "GENESIS"; ts = now_iso()
    db.add(AuditLog(ts=ts, actor=actor, action=action, entity=entity, entity_id=str(entity_id), detail=detail,
                    prev_hash=prev, hash=_h(prev, ts, actor, action, entity, entity_id, detail)))


def verify_chain(db: Session) -> dict:
    prev = "GENESIS"; n = 0
    for r in db.scalars(select(AuditLog).order_by(AuditLog.id)):
        n += 1
        if r.prev_hash != prev or r.hash != _h(prev, r.ts, r.actor, r.action, r.entity, r.entity_id, r.detail):
            return {"valid": False, "entries": n, "broken_at": r.id}
        prev = r.hash
    return {"valid": True, "entries": n, "broken_at": None}
