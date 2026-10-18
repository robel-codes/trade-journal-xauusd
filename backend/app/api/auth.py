from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import func, select

from app.config import get_settings
from app.deps import DB, CurrentUser, audit
from app.models import User
from app.schemas import LoginIn, UserOut
from app.security import COOKIE_NAME, issue_token, login_limiter, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(body: LoginIn, request: Request, response: Response, db: DB):
    s = get_settings()
    ip = request.client.host if request.client else "unknown"
    if not login_limiter.allow(f"login:{ip}", s.login_attempts_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many sign-in attempts. Wait a minute and try again.")
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.strip().lower()))
    if user is None or not user.is_active or not verify_password(user.password_hash, body.password):
        audit(db, None, "login_failed", body.email.strip().lower()[:255], request=request)
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    response.set_cookie(COOKIE_NAME, issue_token(user.id), httponly=True, samesite="lax", secure=s.cookie_secure,
                        max_age=s.session_hours * 3600, path="/")
    audit(db, user, "login", request=request)
    db.commit()
    return user


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
