"""Authentication + server-side RBAC. Every permission rule lives here, never in the client."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .db import get_db
from .models import Case, Institution, User
from .security import read_token


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    tok = request.cookies.get("session")
    if not tok and request.headers.get("authorization", "").lower().startswith("bearer "):
        tok = request.headers["authorization"][7:]
    uid = read_token(tok) if tok else None
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "Not authenticated")
    return user


def require_roles(*roles):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Insufficient role")
        return user
    return dep


def visible_query(user: User):
    """Cases this user may SEE. Sealed (sensitive) cases are need-to-know: admin or owning bureau only."""
    q = select(Case).outerjoin(Institution, Case.institution_id == Institution.id)
    if user.role == "ADMIN":
        return q
    if user.role == "REGIONAL":
        return q.where(Institution.region == user.region, Case.sealed.is_(False))
    return q.where(or_(Case.sealed.is_(False), Case.bureau == user.bureau))


def can_act(user: User, case: Case) -> bool:
    if user.role == "ADMIN":
        return True
    if user.role in ("HEAD", "OFFICER"):
        return case.bureau == user.bureau
    if user.role == "REGIONAL":
        return case.bureau == "RO" and case.institution is not None and case.institution.region == user.region
    return False
