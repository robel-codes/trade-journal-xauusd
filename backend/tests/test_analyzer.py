from pathlib import Path

import pytest

from app.models import Compatibility, ScriptKind
from app.pine.analyzer import analyze, normalized_hash
from app.pine.scanner import mask

FIX = Path(__file__).parent / "fixtures" / "pine"


def codes(result):
    return {f.code for f in result.findings}


def test_mask_blanks_comments_and_strings_but_keeps_offsets():
    src = 'a = "x // y" // strategy.order(\nb = 1'
    m = mask(src)
    assert len(m) == len(src)
    assert "strategy.order" not in m
    assert m.index("\n") == src.index("\n")
    assert m.startswith('a = "')


def test_ema_cross_is_partial_with_inputs_and_settings():
    r = analyze((FIX / "ema_cross_atr.pine").read_text())
    assert r.script_kind is ScriptKind.strategy
    assert r.pine_version == 5
    assert r.classification is Compatibility.partial
    assert r.declared_title == "XAU EMA Cross ATR"
    assert r.declaration["initial_capital"] == 10000
    assert r.declaration["commission_value"] == 0.07
    assert r.declaration["default_qty_type"] == "strategy.percent_of_equity"
    by_var = {i.variable: i for i in r.inputs}
    assert by_var["fastLen"].default_value == {"value": 9}
    assert by_var["fastLen"].options == {"minval": 1, "group": "Trend"}
    assert by_var["slowLen"].title == "Slow EMA"
    assert by_var["atrMult"].input_type == "float" and by_var["atrMult"].options["step"] == 0.1
    assert by_var["sess"].input_type == "session"
    assert by_var["src"].default_value == {"value": "close"}
    assert by_var["fastLen"].line == 5
    assert r.function_usage["ta.ema"]["count"] == 2
    assert r.function_usage["ta.ema"]["status"] == "supported"
    assert "no_stop_loss" not in codes(r)
    assert "lookahead_leak" not in codes(r)
    # session filter passes an explicit timezone, so it is informational only
    sess = next(f for f in r.findings if f.code == "session_filter")
    assert sess.severity == "info"


def test_lookahead_without_offset_is_critical_and_needs_manual_conversion():
    r = analyze((FIX / "htf_lookahead.pine").read_text())
    assert r.classification is Compatibility.manual
    leak = [f for f in r.findings if f.code == "lookahead_leak"]
    assert len(leak) == 1 and leak[0].severity == "critical" and leak[0].lines == [3]
    # the [1]-offset form on line 4 is the accepted non-repainting pattern
    assert any(f.code == "lookahead_offset" and f.lines == [4] for f in r.findings)
    for code in ("calc_on_every_tick", "varip", "barstate", "pivot_delay", "strategy_order", "other_symbol",
                 "trailing_stop", "tick_distances"):
        assert code in codes(r), code


def test_indicator_is_never_backtestable():
    r = analyze((FIX / "rsi_indicator.pine").read_text())
    assert r.script_kind is ScriptKind.indicator
    assert r.classification is Compatibility.unsupported
    assert "not_a_strategy" in codes(r)
    assert r.inputs[0].input_type == "int"


def test_legacy_v4_requires_manual_conversion():
    r = analyze((FIX / "legacy_v4.txt").read_text())
    assert r.pine_version == 4
    assert r.classification is Compatibility.manual
    assert "legacy_version" in codes(r)
    assert "no_stop_loss" in codes(r)
    assert r.inputs[0].input_type == "int"


def test_analyzer_never_claims_validated():
    for f in FIX.iterdir():
        assert analyze(f.read_text()).classification is not Compatibility.validated


def test_constructs_inside_comments_and_strings_are_ignored():
    src = '//@version=5\nstrategy("S")\n// strategy.order("x", strategy.long, 1)\nlabel.new(bar_index, high, "uses varip and timenow")\nstrategy.entry("L", strategy.long, stop=low - 1)\nstrategy.exit("X", "L", stop=low - 2)\n'
    r = analyze(src)
    assert {"strategy_order", "varip", "timenow"}.isdisjoint(codes(r))
    assert r.classification is Compatibility.partial


@pytest.mark.parametrize("src,code", [
    ('//@version=5\nstrategy("S")\nx = request.financial(syminfo.tickerid, "EPS", "FQ")\nstrategy.entry("L", strategy.long)\n', "unreproducible_data"),
    ('//@version=5\nstrategy("S")\nx = request.security_lower_tf(syminfo.tickerid, "1", close)\nstrategy.entry("L", strategy.long)\n', "lower_tf"),
    ('//@version=5\nstrategy("S")\nimport TradingView/ta/7 as tvta\nstrategy.entry("L", strategy.long)\n', "library_import"),
    ('strategy("S")\nstrategy.entry("L", strategy.long)\n', "no_version"),
    ('//@version=5\nstrategy("S")\nif timenow > time\n    strategy.entry("L", strategy.long)\n', "timenow"),
    ('//@version=5\nstrategy("S")\nh = ta.pivothigh(high, 3, 3)\nstrategy.entry("L", strategy.long)\n', "pivot_delay"),
    ('//@version=5\nstrategy("S")\nx = ta.someNewThing(close)\nstrategy.entry("L", strategy.long)\n', "unsupported_builtins"),
])
def test_individual_rules(src, code):
    assert code in codes(analyze(src))


def test_unreproducible_data_blocks_execution():
    src = '//@version=5\nstrategy("S")\nx = request.economic("US", "GDP")\nstrategy.entry("L", strategy.long)\n'
    assert analyze(src).classification is Compatibility.unsupported


def test_multiline_call_arguments_are_parsed():
    src = '//@version=5\nstrategy("Multi",\n     overlay=true,\n     pyramiding=3)\nlen = input.int(\n    20,\n    "Length",\n    minval=2)\nstrategy.entry("L", strategy.long)\n'
    r = analyze(src)
    assert r.declaration["pyramiding"] == 3
    assert r.inputs[0].default_value == {"value": 20} and r.inputs[0].title == "Length" and r.inputs[0].line == 5
    assert "pyramiding" in codes(r)


def test_normalized_hash_ignores_comments_whitespace_and_line_endings_only():
    a = '//@version=5\nstrategy("S")\nx = 1  // note\n'
    b = '//@version=5\r\nstrategy("S")\r\n\r\nx  =  1\r\n'
    c = '//@version=5\nstrategy("S")\nx = 2\n'
    assert normalized_hash(a) == normalized_hash(b)
    assert normalized_hash(a) != normalized_hash(c)
    # string contents are significant
    assert normalized_hash('s = "a b"') != normalized_hash('s = "a  b"')
