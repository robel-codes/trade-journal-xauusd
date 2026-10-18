"""Administrative commands: `uv run python -m app.cli bootstrap --email you@example.com`."""

import argparse
import getpass
import sys
from decimal import Decimal

from sqlalchemy import select

from app import db as dbmod
from app.models import ApplicationSettings, Instrument, User
from app.security import hash_password


def seed_instruments(session) -> None:
    if not session.scalar(select(Instrument).where(Instrument.symbol == "XAUUSD")):
        # Canonical instrument only. Broker-specific contract size, spread and tick size live in BrokerProfile.
        session.add(Instrument(symbol="XAUUSD", description="Spot gold vs US dollar", base_currency="XAU",
                               quote_currency="USD", tick_size=Decimal("0.01"), price_precision=2))


def bootstrap(email: str, password: str, name: str) -> None:
    from app.api.settings import DEFAULT_SESSIONS

    gen = dbmod.get_db()
    session = next(gen)
    seed_instruments(session)
    if session.scalar(select(User).where(User.email == email.lower())):
        print(f"User {email} already exists; instruments checked.")
    else:
        u = User(email=email.lower(), display_name=name, password_hash=hash_password(password))
        session.add(u)
        session.flush()
        session.add(ApplicationSettings(user_id=u.id, sessions=DEFAULT_SESSIONS))
        print(f"Created user {email}.")
    session.commit()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="app.cli")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bootstrap", help="Seed instruments and create the first user")
    b.add_argument("--email", required=True)
    b.add_argument("--name", default="")
    b.add_argument("--password", help="Omit to be prompted (recommended)")
    args = p.parse_args(argv)
    if args.cmd == "bootstrap":
        pw = args.password or getpass.getpass("Password: ")
        if len(pw) < 10:
            print("Use a password of at least 10 characters.", file=sys.stderr)
            return 2
        bootstrap(args.email, pw, args.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
