import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal as D
from pathlib import Path

import pytest

from app.models import Direction, ExecutionKind, Instrument, JournalTrade, TradeExecution
from tests.conftest import make_user

FIX = Path(__file__).parent / "fixtures" / "pine"

PROTECTED = [
    ("get", "/api/auth/me"), ("get", "/api/settings"), ("get", "/api/accounts"), ("get", "/api/strategies"),
    ("get", "/api/strategies/stats"), ("get", "/api/dashboard/overview"), ("post", "/api/strategies/import"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_routes_require_sign_in(anon, method, path):
    assert getattr(anon, method)(path).status_code == 401


def test_health_is_public(anon):
    assert anon.get("/api/health").json() == {"status": "ok"}


def test_login_rejects_bad_password_and_rate_limits(anon, user):
    for _ in range(10):
        assert anon.post("/api/auth/login", json={"email": "trader@example.com", "password": "nope"}).status_code == 401
    assert anon.post("/api/auth/login", json={"email": "trader@example.com", "password": "nope"}).status_code == 429


def test_session_cookie_is_httponly(anon, user):
    r = anon.post("/api/auth/login", json={"email": "TRADER@example.com", "password": "correct-horse-battery"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    assert anon.get("/api/auth/me").json()["email"] == "trader@example.com"


def test_tampered_cookie_is_rejected(anon, user):
    anon.cookies.set("xau_session", "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.bad")
    assert anon.get("/api/auth/me").status_code == 401


def test_settings_defaults_and_validation(client):
    s = client.get("/api/settings").json()
    assert s["timezone"] == "UTC" and {w["key"] for w in s["sessions"]} >= {"london", "new_york", "asia"}
    assert client.put("/api/settings", json={"timezone": "Mars/Olympus"}).status_code == 422
    r = client.put("/api/settings", json={"timezone": "Europe/London", "theme": "light"})
    assert r.json()["timezone"] == "Europe/London" and r.json()["theme"] == "light"


def upload(client, *names, **form):
    files = [("files", (n, (FIX / n).read_bytes(), "text/plain")) for n in names]
    return client.post("/api/strategies/import", files=files, data=form)


def test_import_list_detail_and_export_roundtrip(client):
    r = upload(client, "ema_cross_atr.pine", "htf_lookahead.pine")
    assert r.status_code == 200 and r.json()["counts"] == {"imported": 2}
    rows = client.get("/api/strategies").json()
    assert {r["classification"] for r in rows} == {"partial", "manual"}
    assert client.get("/api/strategies", params={"classification": "manual"}).json()[0]["name"] == "HTF Bias Leak"
    stats = client.get("/api/strategies/stats").json()
    assert stats == {"total": 2, "by_classification": {"partial": 1, "manual": 1}, "by_kind": {"strategy": 2}}

    sid = next(r["id"] for r in rows if r["name"] == "XAU EMA Cross ATR")
    detail = client.get(f"/api/strategies/{sid}").json()
    vid = detail["versions"][0]["id"]
    v = client.get(f"/api/strategies/{sid}/versions/{vid}").json()
    assert v["report"]["classification"] == "partial"
    assert [i["variable"] for i in v["inputs"]][:2] == ["fastLen", "slowLen"]
    src = client.get(f"/api/strategies/{sid}/versions/{vid}/source")
    assert src.content == (FIX / "ema_cross_atr.pine").read_bytes()

    z = client.post("/api/strategies/export", json=[r["id"] for r in rows])
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert sorted(names) == ["ema_cross_atr.pine", "htf_lookahead.pine"]


def test_patch_clone_version_and_diff(client):
    upload(client, "ema_cross_atr.pine")
    sid = client.get("/api/strategies").json()[0]["id"]
    r = client.patch(f"/api/strategies/{sid}", json={"tags": ["trend", "Trend", "atr"], "supported_timeframes": ["15m", "1h"],
                                                      "hypothesis": "Gold trends during London."})
    assert r.json()["tags"] == ["trend", "atr"]
    assert client.patch(f"/api/strategies/{sid}", json={"supported_timeframes": ["7m"]}).status_code == 422

    clone = client.post(f"/api/strategies/{sid}/clone", json={}).json()
    c = client.get(f"/api/strategies/{clone['id']}").json()
    assert c["name"].endswith("(copy)") and c["cloned_from_strategy_id"] == sid and c["tags"] == ["trend", "atr"]

    detail = client.get(f"/api/strategies/{sid}").json()
    v1 = detail["versions"][0]["id"]
    src = client.get(f"/api/strategies/{sid}/versions/{v1}").json()["source"]
    assert client.post(f"/api/strategies/{sid}/versions", json={"source": src}).status_code == 409
    nv = client.post(f"/api/strategies/{sid}/versions", json={"source": src.replace("input.int(9,", "input.int(10,"),
                                                              "change_note": "fast 10"}).json()
    assert nv["number"] == 2
    d = client.get(f"/api/strategies/{sid}/diff", params={"a": v1, "b": nv["id"]}).json()
    assert d["inputs_changed"] == ["fastLen"]
    assert any(line.startswith("+fastLen") for line in d["unified"])


def test_users_cannot_read_each_others_strategies(client, session):
    upload(client, "ema_cross_atr.pine")
    sid = client.get("/api/strategies").json()[0]["id"]
    make_user(session, "intruder@example.com", "intruder-password-1")
    from fastapi.testclient import TestClient

    from app.main import app
    other = TestClient(app)
    other.post("/api/auth/login", json={"email": "intruder@example.com", "password": "intruder-password-1"})
    assert other.get("/api/strategies").json() == []
    assert other.get(f"/api/strategies/{sid}").status_code == 404
    assert other.post("/api/strategies/export", json=[sid]).status_code == 404


def test_overview_is_empty_and_honest_without_data(client):
    o = client.get("/api/dashboard/overview").json()
    assert o["summary"]["trades"] == 0
    assert o["summary"]["win_rate"] is None and o["summary"]["profit_factor"] is None
    assert o["equity_curve"] == [] and o["recent_backtests"] == []
    assert any("No trading account" in w["message"] for w in o["warnings"])


def test_overview_computes_from_stored_executions(client, session, user):
    acc = client.post("/api/accounts", json={"name": "Demo", "kind": "demo", "starting_balance": "10000"}).json()
    sim = client.post("/api/accounts", json={"name": "Paper", "kind": "simulation", "starting_balance": "5000"}).json()
    xau = session.query(Instrument).filter_by(symbol="XAUUSD").one()

    def trade(account, direction, fills, stop):
        t = JournalTrade(user_id=user.id, account_id=account, instrument_id=xau.id, direction=direction,
                         initial_stop=stop, session="london", timeframe="15m")
        t.executions = [TradeExecution(kind=k, executed_at=at, price=p, quantity=q, commission=D("1")) for k, at, p, q in fills]
        session.add(t)

    d = lambda h: datetime(2026, 3, 2, h, tzinfo=UTC)  # noqa: E731
    # long 10 @ 2000 -> 2010, stop 1995: gross 100, fees 2 -> 98, R 98/50
    trade(acc["id"], Direction.long, [(ExecutionKind.entry, d(8), D(2000), D(10)), (ExecutionKind.exit, d(9), D(2010), D(10))], D(1995))
    # short 5 @ 2020 -> 2026, stop 2030: gross -30, fees 2 -> -32, R -32/50
    trade(acc["id"], Direction.short, [(ExecutionKind.entry, d(10), D(2020), D(5)), (ExecutionKind.exit, d(11), D(2026), D(5))], D(2030))
    # simulated trade, excluded from "actual"
    trade(sim["id"], Direction.long, [(ExecutionKind.entry, d(12), D(2000), D(1)), (ExecutionKind.exit, d(13), D(2100), D(1))], D(1990))
    session.commit()

    o = client.get("/api/dashboard/overview", params={"source": "actual"}).json()
    s = o["summary"]
    assert s["trades"] == 2 and s["net_pnl"] == pytest.approx(66)
    assert s["profit_factor"] == pytest.approx(98 / 32)
    assert s["avg_r"] == pytest.approx((98 / 50 - 32 / 50) / 2)
    assert s["starting_balance"] == 10000 and s["ending_equity"] == pytest.approx(10066)
    assert s["max_drawdown"] == pytest.approx(32)
    assert [r["key"] for r in o["by_direction"]] == ["long", "short"]
    assert o["by_session"][0]["key"] == "london"
    assert o["daily"] == {"2026-03-02": {"pnl": pytest.approx(66), "trades": 2}}

    all_ = client.get("/api/dashboard/overview").json()["summary"]
    assert all_["trades"] == 3 and all_["starting_balance"] == 15000
