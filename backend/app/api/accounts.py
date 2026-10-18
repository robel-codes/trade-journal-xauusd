import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.deps import DB, CurrentUser, audit
from app.models import Instrument, TradingAccount
from app.schemas import AccountIn, AccountOut

router = APIRouter(tags=["accounts"])


@router.get("/accounts", response_model=list[AccountOut])
def list_accounts(user: CurrentUser, db: DB):
    return db.scalars(select(TradingAccount).where(TradingAccount.user_id == user.id).order_by(TradingAccount.created_at)).all()


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountIn, user: CurrentUser, db: DB):
    acc = TradingAccount(user_id=user.id, **body.model_dump())
    db.add(acc)
    audit(db, user, "account_create", body.name)
    db.commit()
    return acc


def _own(db, user, account_id: uuid.UUID) -> TradingAccount:
    acc = db.get(TradingAccount, account_id)
    if acc is None or acc.user_id != user.id:
        raise HTTPException(404, "Account not found.")
    return acc


@router.put("/accounts/{account_id}", response_model=AccountOut)
def update_account(account_id: uuid.UUID, body: AccountIn, user: CurrentUser, db: DB):
    acc = _own(db, user, account_id)
    for k, v in body.model_dump().items():
        setattr(acc, k, v)
    db.commit()
    return acc


@router.post("/accounts/{account_id}/archive", response_model=AccountOut)
def archive_account(account_id: uuid.UUID, user: CurrentUser, db: DB):
    acc = _own(db, user, account_id)
    acc.archived = True
    audit(db, user, "account_archive", str(acc.id))
    db.commit()
    return acc


@router.get("/instruments")
def list_instruments(user: CurrentUser, db: DB):
    return [{"id": i.id, "symbol": i.symbol, "description": i.description, "tick_size": i.tick_size,
             "price_precision": i.price_precision, "quote_currency": i.quote_currency}
            for i in db.scalars(select(Instrument).order_by(Instrument.symbol))]
