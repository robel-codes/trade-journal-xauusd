from fastapi import APIRouter

from app.deps import DB, CurrentUser
from app.models import ApplicationSettings
from app.schemas import SettingsIn, SettingsOut

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_SESSIONS = [
    # Defined in each market's own timezone so daylight-saving shifts follow the local rules.
    {"key": "asia", "label": "Asian", "timezone": "Asia/Tokyo", "start": "09:00", "end": "18:00"},
    {"key": "london", "label": "London", "timezone": "Europe/London", "start": "08:00", "end": "17:00"},
    {"key": "new_york", "label": "New York", "timezone": "America/New_York", "start": "08:00", "end": "17:00"},
    {"key": "ldn_ny_overlap", "label": "London/NY overlap", "timezone": "America/New_York", "start": "08:00", "end": "12:00"},
]


def get_or_create(db, user) -> ApplicationSettings:
    s = db.get(ApplicationSettings, user.id)
    if s is None:
        s = ApplicationSettings(user_id=user.id, sessions=DEFAULT_SESSIONS)
        db.add(s)
        db.commit()
    return s


@router.get("", response_model=SettingsOut)
def read(user: CurrentUser, db: DB):
    return get_or_create(db, user)


@router.put("", response_model=SettingsOut)
def update(body: SettingsIn, user: CurrentUser, db: DB):
    s = get_or_create(db, user)
    data = body.model_dump(exclude_none=True)
    if "sessions" in data:
        data["sessions"] = [w.model_dump() for w in body.sessions]
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    return s
