import io
import zipfile
from pathlib import Path

from app.models import Strategy, StrategyVersion
from app.services.strategy_import import import_scripts

FIX = Path(__file__).parent / "fixtures" / "pine"


def fixture_files(*names):
    return [(n, (FIX / n).read_bytes()) for n in names]


def statuses(rep):
    return [(i.filename, i.status) for i in rep.items]


def test_batch_import_creates_one_strategy_per_script(session, user):
    rep = import_scripts(session, user.id, fixture_files("ema_cross_atr.pine", "rsi_indicator.pine", "legacy_v4.txt"))
    session.commit()
    assert rep.counts == {"imported": 3}
    by_name = {i.strategy_name: i for i in rep.items}
    assert by_name["XAU EMA Cross ATR"].classification == "partial"
    assert by_name["RSI Zones"].script_kind == "indicator"
    assert by_name["RSI Zones"].classification == "unsupported"
    assert session.query(Strategy).count() == 3


def test_source_is_stored_byte_for_byte(session, user):
    raw = b'\xef\xbb\xbf//@version=5\r\nstrategy("BOM CRLF")\r\nstrategy.entry("L", strategy.long)\r\n'
    rep = import_scripts(session, user.id, [("bom.pine", raw)])
    session.commit()
    v = session.get(StrategyVersion, rep.items[0].version_id)
    assert v.source.encode("utf-8") == raw
    assert v.pine_version == 5  # analysis sees through the BOM and CRLF


def test_exact_and_near_duplicates_are_detected(session, user):
    import_scripts(session, user.id, fixture_files("ema_cross_atr.pine"))
    session.commit()
    original = (FIX / "ema_cross_atr.pine").read_bytes()
    reformatted = original.replace(b"\n", b"\r\n").replace(b"// EMA crossover", b"// different comment")
    rep = import_scripts(session, user.id, [("copy.pine", original), ("reformatted.pine", reformatted)])
    assert statuses(rep) == [("copy.pine", "duplicate"), ("reformatted.pine", "duplicate")]
    rep2 = import_scripts(session, user.id, [("reformatted.pine", reformatted)])
    assert rep2.items[0].status == "near_duplicate"


def test_same_title_with_changed_logic_becomes_new_version(session, user):
    import_scripts(session, user.id, fixture_files("ema_cross_atr.pine"))
    session.commit()
    changed = (FIX / "ema_cross_atr.pine").read_text().replace('input.int(9, "Fast EMA"', 'input.int(12, "Fast EMA"')
    rep = import_scripts(session, user.id, [("ema_v2.pine", changed.encode())])
    session.commit()
    assert rep.items[0].status == "new_version"
    st = session.get(Strategy, rep.items[0].strategy_id)
    assert [v.version_number for v in st.versions] == [1, 2]
    assert st.versions[0].source == (FIX / "ema_cross_atr.pine").read_text()  # v1 untouched

    rep2 = import_scripts(session, user.id, [("ema_fork.pine", changed.replace("12", "13").encode())],
                          on_title_match="new_strategy")
    assert rep2.items[0].status == "imported"


def test_zip_import_with_hostile_members(session, user):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("strategies/ema.pine", (FIX / "ema_cross_atr.pine").read_bytes())
        zf.writestr("strategies/old.txt", (FIX / "legacy_v4.txt").read_bytes())
        zf.writestr("../escape.pine", b'//@version=5\nstrategy("x")')
        zf.writestr("inner.zip", b"PK")
        zf.writestr("readme.md", b"# hi")
        zf.writestr("__MACOSX/._ema.pine", b"junk")
        zf.writestr("latin1.pine", "//@version=5\nstrategy(\"caf\xe9\")".encode("latin-1"))
        zf.writestr("bomb.pine", b"/" * 2_000_000)
    rep = import_scripts(session, user.id, [("pack.zip", buf.getvalue())])
    got = dict(statuses(rep))
    assert got["pack.zip/strategies/ema.pine"] == "imported"
    assert got["pack.zip/strategies/old.txt"] == "imported"
    assert got["pack.zip/../escape.pine"] == "error"
    assert got["pack.zip/inner.zip"] == "error"
    assert got["pack.zip/readme.md"] == "error"
    assert got["pack.zip/latin1.pine"] == "error"
    assert got["pack.zip/bomb.pine"] == "error"
    assert not any("__MACOSX" in k for k in got)
    msg = next(i.message for i in rep.items if i.filename.endswith("latin1.pine"))
    assert "UTF-8" in msg


def test_rejects_wrong_types_and_bad_archives(session, user):
    rep = import_scripts(session, user.id, [("x.py", b"print(1)"), ("broken.zip", b"not a zip"), ("empty.pine", b"  \n")])
    assert [i.status for i in rep.items] == ["error", "error", "error"]


def test_duplicate_inside_one_upload(session, user):
    raw = (FIX / "rsi_indicator.pine").read_bytes()
    rep = import_scripts(session, user.id, [("a.pine", raw), ("b.pine", raw)])
    assert statuses(rep) == [("a.pine", "imported"), ("b.pine", "duplicate")]


def test_users_do_not_see_each_others_duplicates(session, user):
    from tests.conftest import make_user
    other = make_user(session, "other@example.com")
    import_scripts(session, user.id, fixture_files("ema_cross_atr.pine"))
    session.commit()
    rep = import_scripts(session, other.id, fixture_files("ema_cross_atr.pine"))
    assert rep.items[0].status == "imported"
