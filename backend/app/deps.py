from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, User
from app.security import COOKIE_NAME, read_token

DB = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(COOKIE_NAME)
    user_id = read_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def audit(db: Session, user: User | None, action: str, target: str = "", detail: dict | None = None,
          request: Request | None = None) -> None:
    db.add(AuditLog(user_id=user.id if user else None, action=action, target=target, detail=detail or {},
                    ip=(request.client.host if request and request.client else "")))
