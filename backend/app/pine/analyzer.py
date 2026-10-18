"""Static compatibility analysis for Pine Script.

This module reads a script as text and reports what it does and which constructs the native
engine can or cannot model. It never executes the script and never modifies it.

Classification is deliberately conservative:
* The analyzer can never return VALIDATED. That requires a native adapter plus parity tests against a
  TradingView Strategy Tester export, and is set elsewhere.
* PARTIAL means every construct found is one the native engine is designed to model. A reviewed
  translation is still required before any backtest runs.
* MANUAL means at least one construct needs a human decision during translation.
* UNSUPPORTED means the script cannot currently be backtested reliably (not a strategy, or it depends
  on data the platform cannot reproduce).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field

from app.models import Compatibility, ScriptKind
from app.pine.scanner import Call, LineIndex, literal, mask, parse_call, strip_comments

ANALYZER_VERSION = "0.1.0"

# Functions the native engine is designed to model (Phase 3 target set). Anything outside this set
# in the ta.* namespace is reported as requiring manual conversion.
SUPPORTED_TA = {
    "sma", "ema", "rma", "wma", "vwma", "hma", "swma", "alma", "linreg",
    "atr", "tr", "rsi", "macd", "stoch", "bb", "bbw", "kc", "kcw", "cci", "mfi", "mom", "roc",
    "stdev", "variance", "dev", "highest", "lowest", "highestbars", "lowestbars",
    "crossover", "crossunder", "cross", "change", "rising", "falling", "barssince", "valuewhen",
    "pivothigh", "pivotlow", "supertrend", "dmi", "sar", "vwap", "cum", "median", "percentrank",
    "correlation", "obv", "wpr", "tsi", "cmo",
}
SUPPORTED_STRATEGY_CALLS = {
    "strategy.entry", "strategy.exit", "strategy.close", "strategy.close_all",
    "strategy.cancel", "strategy.cancel_all",
}
STRATEGY_PROPERTIES_SUPPORTED = {
    "strategy.position_size", "strategy.position_avg_price", "strategy.equity", "strategy.initial_capital",
    "strategy.netprofit", "strategy.openprofit", "strategy.opentrades", "strategy.closedtrades",
    "strategy.long", "strategy.short", "strategy.fixed", "strategy.cash", "strategy.percent_of_equity",
    "strategy.wintrades", "strategy.losstrades", "strategy.grossprofit", "strategy.grossloss",
    "strategy.max_drawdown", "strategy.commission.percent", "strategy.commission.cash_per_contract",
    "strategy.commission.cash_per_order", "strategy.position_entry_name",
}
VISUAL_ONLY = {
    "plot", "plotshape", "plotchar", "plotarrow", "plotcandle", "plotbar", "hline", "fill", "bgcolor",
    "barcolor",
}
VISUAL_NAMESPACES = {"line", "label", "box", "table", "linefill", "polyline", "chart.point", "color"}
KNOWN_NAMESPACES = {
    "ta", "math", "str", "array", "matrix", "map", "request", "strategy", "input", "color", "line", "label",
    "box", "table", "linefill", "polyline", "chart", "syminfo", "timeframe", "ticker", "session", "runtime",
    "log", "barstate", "time", "dayofweek", "barmerge", "currency", "display", "extend", "format", "location",
    "position", "scale", "shape", "size", "text", "xloc", "yloc", "font", "order", "alert", "hline",
    "plot", "earnings", "dividends", "splits", "adjustment", "backadjustment", "settlement_as_close",
}
KNOWN_FUNCTIONS = VISUAL_ONLY | {
    "strategy", "indicator", "library", "study", "input", "nz", "na", "fixnan", "int", "float", "bool",
    "string", "color", "time", "time_close", "timestamp", "year", "month", "weekofyear", "dayofmonth",
    "dayofweek", "hour", "minute", "second", "alert", "alertcondition", "max_bars_back", "runtime.error",
    "switch", "if", "for", "while", "array.from", "label", "line", "box", "table",
}
# Pine v4-and-earlier un-namespaced names, used only to explain version findings.
LEGACY_V4 = SUPPORTED_TA | {"security", "study", "iff", "nz", "tostring", "valuewhen", "barssince", "change"}
UNREPRODUCIBLE_REQUESTS = {
    "request.financial": "company fundamentals",
    "request.economic": "macroeconomic series",
    "request.quandl": "Nasdaq Data Link series",
    "request.dividends": "dividend history",
    "request.earnings": "earnings history",
    "request.splits": "split history",
    "request.seed": "user-maintained GitHub data",
    "request.currency_rate": "currency conversion rates",
}

_CALL = re.compile(r"(?<![\w.])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?:<[\w\s,.]*>)?\s*\(")
_KEYWORDS = {"if", "for", "while", "switch", "not", "and", "or", "else", "var", "varip", "return", "to", "by", "in"}
_PROPERTY = re.compile(r"(?<![\w.])(strategy(?:\.[A-Za-z_]\w*)+)\b(?!\s*\()")
_BARSTATE = re.compile(r"(?<![\w.])barstate\.(\w+)")
_VERSION = re.compile(r"^\s*//\s*@version\s*=\s*(\d+)", re.M)
_USER_FUNC = re.compile(r"^(?:export\s+)?(?:method\s+)?([A-Za-z_]\w*)\s*\(([^()\n]*)\)\s*=>", re.M)
_IMPORT = re.compile(r"^\s*import\s+([\w/.-]+)(?:\s+as\s+(\w+))?", re.M)
_ASSIGN_BEFORE = re.compile(r"(?:^|[\s(])(?:var\s+|varip\s+)?(?:(?:simple|series|const)\s+)?(?:\w+\s+)?([A-Za-z_]\w*)\s*:?=\s*$")
_WS_OUTSIDE_STRINGS = re.compile(r"(\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')|\s+")
_HISTORY_REF = re.compile(r"\[\s*\d+\s*\]")


@dataclass
class Finding:
    code: str
    severity: str  # info | warning | critical
    impact: str  # none | caution | manual | blocking
    title: str
    detail: str
    lines: list[int] = field(default_factory=list)


@dataclass
class InputParam:
    position: int
    variable: str
    input_type: str
    title: str
    default_raw: str
    default_value: dict
    options: dict
    line: int


@dataclass
class AnalysisResult:
    analyzer_version: str
    script_kind: ScriptKind
    pine_version: int | None
    declared_title: str
    declaration: dict
    inputs: list[InputParam]
    function_usage: dict  # name -> {"count": n, "lines": [...], "status": supported|unsupported|visual|unknown|user}
    user_functions: list[str]
    imports: list[str]
    findings: list[Finding]
    classification: Compatibility
    summary: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["script_kind"] = self.script_kind.value
        d["classification"] = self.classification.value
        return d


def normalized_hash(source: str) -> str:
    """Hash that ignores comments, whitespace and line endings, to catch near-identical duplicates."""
    text = strip_comments(source.removeprefix("\ufeff").replace("\r\n", "\n"))
    collapsed = _WS_OUTSIDE_STRINGS.sub(lambda m: m.group(1) or " ", text).strip()
    return hashlib.sha256(collapsed.encode("utf-8")).hexdigest()


class _Ctx:
    def __init__(self, source: str):
        self.source = source.replace("\r\n", "\n").removeprefix("\ufeff")
        self.masked = mask(self.source)
        self.lines = LineIndex(self.source)
        self.calls: list[Call] = []
        for m in _CALL.finditer(self.masked):
            name = m.group(1)
            self.calls.append(parse_call(self.source, self.masked, name, m.start(1), m.end() - 1))

    def line(self, offset: int) -> int:
        return self.lines.line_of(offset)

    def calls_named(self, *names: str) -> list[Call]:
        return [c for c in self.calls if c.name in names]

    def lines_matching(self, pattern: re.Pattern | str) -> list[int]:
        pat = re.compile(pattern) if isinstance(pattern, str) else pattern
        return sorted({self.line(m.start()) for m in pat.finditer(self.masked)})


def analyze(source: str) -> AnalysisResult:
    ctx = _Ctx(source)
    findings: list[Finding] = []

    def add(code, severity, impact, title, detail, lines=()):
        findings.append(Finding(code, severity, impact, title, detail, sorted(set(lines))[:50]))

    # ---- version
    vm = _VERSION.search(ctx.source)
    pine_version = int(vm.group(1)) if vm else None

    # ---- declaration
    kind, decl_call = ScriptKind.unknown, None
    for c in ctx.calls:
        if c.name in ("strategy", "indicator", "study", "library"):
            line_start = ctx.lines.line_start(c.start)
            if ctx.masked[line_start:c.start].strip() == "":
                decl_call = c
                kind = {"study": ScriptKind.indicator}.get(c.name) or ScriptKind(c.name)
                break
    declaration: dict = {}
    declared_title = ""
    if decl_call:
        ok, title = literal(decl_call.arg("title", 0))
        declared_title = title if ok and isinstance(title, str) else ""
        for k, v in decl_call.keywords.items():
            ok, val = literal(v)
            declaration[k] = val if ok else {"expression": v}
        declaration["_line"] = ctx.line(decl_call.start)

    # ---- user functions & imports
    user_functions = sorted({m.group(1) for m in _USER_FUNC.finditer(ctx.masked)})
    imports = []
    aliases = set()
    for m in _IMPORT.finditer(ctx.masked):
        path = ctx.source[m.start(1):m.end(1)]
        imports.append(path)
        parts = path.split("/")
        aliases.add(m.group(2) or (parts[-2] if len(parts) >= 2 else path))

    # ---- function usage
    usage: dict[str, dict] = {}
    for c in ctx.calls:
        if c.name in _KEYWORDS:
            continue
        u = usage.setdefault(c.name, {"count": 0, "lines": [], "status": _status(c.name, user_functions, aliases)})
        u["count"] += 1
        ln = ctx.line(c.start)
        if ln not in u["lines"] and len(u["lines"]) < 50:
            u["lines"].append(ln)
    for m in _PROPERTY.finditer(ctx.masked):
        name = m.group(1)
        if name in usage:
            continue
        u = usage.setdefault(name, {"count": 0, "lines": [], "status": "property"})
        u["count"] += 1
        ln = ctx.line(m.start())
        if ln not in u["lines"] and len(u["lines"]) < 50:
            u["lines"].append(ln)

    # ---- inputs
    inputs = _extract_inputs(ctx)

    # =========================================================== rules
    if kind is ScriptKind.unknown:
        add("no_declaration", "critical", "blocking", "No strategy(), indicator() or library() declaration",
            "The file does not look like a Pine Script. It was stored unchanged but cannot be analyzed further.")
    elif kind is ScriptKind.indicator:
        add("not_a_strategy", "critical", "blocking", "Indicator, not a strategy",
            "This script plots values but places no orders, so it has no backtest of its own. It can be used "
            "as a signal source once entry, exit and sizing rules are defined in a separate strategy.",
            [declaration.get("_line", 1)])
    elif kind is ScriptKind.library:
        add("library", "info", "blocking", "Pine library",
            "Libraries export functions for other scripts. Import the strategies that use it; the library "
            "itself is not backtested.", [declaration.get("_line", 1)])

    if pine_version is None:
        add("no_version", "warning", "manual", "No //@version annotation",
            "Without a version annotation TradingView compiles the script as Pine v1, whose semantics differ "
            "substantially. Confirm the intended version before translating.")
    elif pine_version < 5:
        legacy = [n for n in usage if n in LEGACY_V4]
        add("legacy_version", "warning", "manual", f"Pine v{pine_version}",
            "Pine v4 and earlier use different built-in names (security(), study(), un-namespaced ta functions) "
            "and different defaults. Translation targets v5/v6 semantics, so behavior must be checked against a "
            "TradingView export of this exact script." + (f" Legacy calls found: {', '.join(sorted(legacy))}." if legacy else ""),
            [usage[n]["lines"][0] for n in legacy])

    # strategy() settings
    if kind is ScriptKind.strategy:
        d = declaration
        if d.get("calc_on_every_tick") is True:
            add("calc_on_every_tick", "warning", "caution", "calc_on_every_tick = true",
                "On live charts the script recalculates on every tick, but historical bars only have OHLC, so "
                "TradingView's own backtest and live behavior already differ. The engine evaluates at bar close.",
                [d["_line"]])
        if d.get("calc_on_order_fills") is True:
            add("calc_on_order_fills", "warning", "manual", "calc_on_order_fills = true",
                "The script recalculates inside a bar after each fill, which depends on TradingView's intrabar "
                "price-path assumptions. The engine must emulate this explicitly; results can differ.", [d["_line"]])
        if d.get("process_orders_on_close") is True:
            add("process_orders_on_close", "info", "none", "process_orders_on_close = true",
                "Market orders fill at the signal bar's close instead of the next bar's open. The engine supports "
                "this setting and will use it.", [d["_line"]])
        if d.get("use_bar_magnifier") is True:
            add("bar_magnifier", "info", "caution", "use_bar_magnifier = true",
                "TradingView resolved fills with lower-timeframe bars. Matching this requires lower-timeframe data "
                "for the same feed; without it, intrabar ambiguity is flagged.", [d["_line"]])
        pyr = d.get("pyramiding")
        if isinstance(pyr, int) and pyr > 1:
            add("pyramiding", "info", "caution", f"Pyramiding up to {pyr} entries",
                "Multiple same-direction entries are allowed. The engine models pyramiding, but exit allocation "
                "across entries (FIFO vs. by entry id) must match TradingView's rules.", [d["_line"]])
        if "commission_value" not in d and "commission_type" not in d:
            add("no_commission", "info", "none", "No commission set in strategy()",
                "TradingView defaults to zero commission. Original settings will be recorded as zero cost; cost "
                "scenarios are applied separately and labelled as modified configurations.", [d["_line"]])
        if "slippage" not in d:
            add("no_slippage", "info", "none", "No slippage set in strategy()",
                "TradingView defaults to zero slippage, which overstates results for stop and market fills.",
                [d["_line"]])
        if "margin_long" in d or "margin_short" in d:
            add("margin", "info", "caution", "Margin settings declared",
                "Margin calls are simulated by TradingView when margin is set. The engine will model margin only "
                "with the broker profile's leverage; check that they agree.", [d["_line"]])
        if not any(n in usage for n in ("strategy.entry", "strategy.order")):
            add("no_entries", "warning", "manual", "No strategy.entry() or strategy.order() calls",
                "The strategy declares itself as a strategy but places no orders that the analyzer can see.")

    # orders
    if "strategy.order" in usage:
        add("strategy_order", "warning", "manual", "strategy.order() used",
            "strategy.order() does not auto-reverse and ignores pyramiding limits; it can net positions in ways "
            "strategy.entry() does not. Each call needs explicit translation.", usage["strategy.order"]["lines"])
    exit_calls = ctx.calls_named("strategy.exit")
    if exit_calls:
        trail = [c for c in exit_calls if any(k in c.keywords for k in ("trail_points", "trail_offset", "trail_price"))]
        if trail:
            add("trailing_stop", "info", "caution", "Trailing stop via strategy.exit()",
                "Trailing stops activate and move intrabar in TradingView. On OHLC bars the engine updates the "
                "trail once per bar and uses a conservative fill; small differences are expected.",
                [ctx.line(c.start) for c in trail])
        partial = [c for c in exit_calls if any(k in c.keywords for k in ("qty_percent", "qty"))]
        if partial:
            add("partial_exits", "info", "none", "Partial exits",
                "strategy.exit() closes part of the position. Partial exits are supported.",
                [ctx.line(c.start) for c in partial])
        ticks = [c for c in exit_calls if any(k in c.keywords for k in ("profit", "loss", "trail_points", "trail_offset"))]
        if ticks:
            add("tick_distances", "warning", "caution", "Stops or targets in ticks",
                "profit/loss/trail values are in ticks (syminfo.mintick). XAUUSD tick size differs between feeds "
                "(0.01 vs 0.001), so the same script can place stops 10x apart on different data. The dataset's "
                "tick size is used and recorded.", [ctx.line(c.start) for c in ticks])
        dynamic = [c for c in exit_calls if any(k in c.keywords and not literal(c.keywords[k])[0] for k in ("stop", "limit"))]
        if dynamic:
            add("dynamic_levels", "info", "none", "Dynamic stop or limit levels",
                "Stop/limit prices are computed from series values and re-sent each bar. Supported; the level in "
                "force at each bar is recorded per trade.", [ctx.line(c.start) for c in dynamic])
    if kind is ScriptKind.strategy and not exit_calls and not any(n in usage for n in ("strategy.close", "strategy.close_all")):
        add("no_exits", "warning", "caution", "No exit calls",
            "Positions only close on reversal or end of data. Check that this is intended.")
    if kind is ScriptKind.strategy and not any(
        "stop" in c.keywords or "loss" in c.keywords or "trail_points" in c.keywords for c in exit_calls
    ) and "strategy.order" not in usage:
        add("no_stop_loss", "warning", "none", "No stop-loss detected",
            "No strategy.exit() call sets stop=, loss= or a trail. Risk per trade and R-multiples cannot be "
            "computed from the script's own rules, and drawdown can be unbounded.")

    for name in ("strategy.risk.max_intraday_loss", "strategy.risk.max_drawdown", "strategy.risk.max_intraday_filled_orders",
                 "strategy.risk.max_cons_loss_days", "strategy.risk.max_position_size", "strategy.risk.allow_entry_in"):
        if name in usage:
            add("risk_rule", "info", "caution", f"{name}()",
                "TradingView risk-management rule. The engine has equivalent daily-loss and drawdown halts; the "
                "exact halt timing (intraday, session reset) must be checked.", usage[name]["lines"])

    # data requests
    for c in ctx.calls_named("request.security", "security"):
        ln = ctx.line(c.start)
        look = c.arg("lookahead", 4) or ""
        expr = c.arg("expression", 2) or ""
        if "lookahead_on" in look:
            if _HISTORY_REF.search(expr):
                add("lookahead_offset", "info", "caution", "Lookahead on with a [1] offset",
                    "This is the standard non-repainting pattern for higher-timeframe values. The engine aligns "
                    "the previous completed higher-timeframe bar.", [ln])
            else:
                add("lookahead_leak", "critical", "manual", "Lookahead without offset (future data)",
                    "request.security() with lookahead=barmerge.lookahead_on and no [1] offset returns the "
                    "higher-timeframe bar's final value before it has closed. Historical results use future data "
                    "and are not achievable live. The engine will not reproduce this; the translation must use the "
                    "previous closed bar, which will change results.", [ln])
        else:
            add("htf_dependency", "warning", "caution", "Higher-timeframe data via request.security()",
                "In history, TradingView shows the higher-timeframe value only once that bar closes (lookahead off), "
                "but on realtime bars it updates intrabar, so live signals can appear and disappear. The engine uses "
                "confirmed higher-timeframe bars only.", [ln])
        sym = c.arg("symbol", 0) or ""
        if sym and "syminfo.tickerid" not in sym and "syminfo.ticker" not in sym:
            add("other_symbol", "warning", "manual", "Requests another symbol",
                f"request.security() reads {sym.strip()}. A dataset for that symbol, aligned to the same timestamps, "
                "is required.", [ln])
    if "request.security_lower_tf" in usage:
        add("lower_tf", "warning", "manual", "request.security_lower_tf()",
            "Returns arrays of intrabar values. Needs lower-timeframe data from the same feed and explicit "
            "translation of the array logic.", usage["request.security_lower_tf"]["lines"])
    for name, what in UNREPRODUCIBLE_REQUESTS.items():
        if name in usage:
            add("unreproducible_data", "critical", "blocking", f"{name}()",
                f"Depends on {what} from TradingView's data services, which the platform cannot reproduce.",
                usage[name]["lines"])

    # repainting / realtime-only constructs
    if re.search(r"(?<![\w.])varip\b", ctx.masked):
        add("varip", "warning", "manual", "varip variables",
            "varip values persist across realtime ticks. On historical bars they behave like var, so the "
            "script's live behavior cannot be backtested on OHLC data.", ctx.lines_matching(r"(?<![\w.])varip\b"))
    if re.search(r"(?<![\w.])timenow\b", ctx.masked):
        add("timenow", "critical", "manual", "timenow used",
            "timenow is the current wall-clock time, so logic using it behaves differently on every historical "
            "bar and on every reload.", ctx.lines_matching(r"(?<![\w.])timenow\b"))
    bs = {}
    for m in _BARSTATE.finditer(ctx.masked):
        bs.setdefault(m.group(1), []).append(ctx.line(m.start()))
    realtime_states = {k: v for k, v in bs.items() if k in ("isrealtime", "isnew", "islast", "isconfirmed", "islastconfirmedhistory", "ishistory")}
    if realtime_states:
        add("barstate", "warning", "caution", "Bar-state conditions: " + ", ".join(f"barstate.{k}" for k in sorted(realtime_states)),
            "These values differ between historical and realtime bars. On historical bars isconfirmed and isnew are "
            "always true and isrealtime is false, so live behavior may not match the backtest.",
            [ln for v in realtime_states.values() for ln in v])
    pivots = [n for n in ("ta.pivothigh", "ta.pivotlow", "pivothigh", "pivotlow") if n in usage]
    if pivots:
        add("pivot_delay", "info", "caution", "Pivot functions (confirmation delay)",
            "A pivot is only known after `rightbars` further bars. A signal referencing a pivot is available that "
            "many bars late; any logic that plots or acts at the pivot bar itself would be using future bars. "
            "The engine evaluates pivots on the confirmation bar.", [ln for n in pivots for ln in usage[n]["lines"]])
    if re.search(r"(?<![\w.])(?:fill_orders_on_standard_ohlc|ticker\.heikinashi|ticker\.renko|ticker\.kagi|ticker\.pointfigure|ticker\.linebreak)", ctx.masked):
        add("synthetic_chart", "critical", "manual", "Non-standard chart type",
            "The script requests Heikin Ashi, Renko or similar synthetic bars. Fills on synthetic prices are not "
            "achievable in a real market; translation must fill on real OHLC.",
            ctx.lines_matching(r"ticker\.(heikinashi|renko|kagi|pointfigure|linebreak)"))

    # sessions & time
    sess_calls = [c for c in ctx.calls_named("time", "time_close") if c.arg("session", 1)]
    sess_inputs = [p for p in inputs if p.input_type == "session"]
    if sess_calls or sess_inputs:
        no_tz = [c for c in sess_calls if not c.arg("timezone", 2)]
        detail = "Session windows are evaluated in the symbol's exchange timezone unless a timezone is passed. "
        if no_tz:
            detail += ("Some calls pass no timezone, so the window shifts with the data feed's exchange timezone and "
                       "with daylight saving. The engine will use the dataset's declared exchange timezone; confirm it "
                       "matches TradingView's for this feed.")
        else:
            detail += "All session calls pass an explicit timezone."
        add("session_filter", "info" if not no_tz else "warning", "caution" if no_tz else "none", "Session or time filter",
            detail, [ctx.line(c.start) for c in sess_calls] + [p.line for p in sess_inputs])
    if any(n in usage for n in ("hour", "minute", "dayofweek")) or re.search(r"(?<![\w.(])(?:hour|minute|dayofweek)\b(?!\s*\()", ctx.masked):
        add("time_fields", "info", "caution", "hour / minute / dayofweek used",
            "These built-ins use the exchange timezone of the chart's symbol, which varies by XAUUSD feed.",
            ctx.lines_matching(r"(?<![\w.])(?:hour|minute|dayofweek)\b"))
    if re.search(r"(?<![\w.])timeframe\.(?:period|multiplier|isintraday|isminutes|isseconds|isdaily|in_seconds)\b", ctx.masked):
        add("timeframe_dependent", "info", "none", "Timeframe-dependent logic",
            "The script changes behavior with the chart timeframe. Results are reported per timeframe.",
            ctx.lines_matching(r"timeframe\.(?:period|multiplier|isintraday|isminutes|isseconds|isdaily|in_seconds)"))

    # alerts
    alerts = [n for n in ("alert", "alertcondition") if n in usage]
    if alerts:
        add("alerts", "info", "none", "Alerts", "Alert calls have no effect on backtests and are ignored.",
            [ln for n in alerts for ln in usage[n]["lines"]])

    # imports and unknown functions
    if imports:
        add("library_import", "warning", "manual", "Imports external libraries: " + ", ".join(imports),
            "Functions from imported libraries are not visible to the analyzer. Import those libraries too, and "
            "translate their functions explicitly.", ctx.lines_matching(r"^\s*import\s"))
    unsupported_ta = sorted(n for n, u in usage.items() if u["status"] == "unsupported")
    if unsupported_ta:
        add("unsupported_builtins", "warning", "manual", "Built-ins outside the engine's supported set",
            "These need a native implementation and a parity check before the strategy can run: "
            + ", ".join(unsupported_ta) + ".",
            [ln for n in unsupported_ta for ln in usage[n]["lines"][:3]])
    unknown = sorted(n for n, u in usage.items() if u["status"] == "unknown")
    if unknown:
        add("unknown_functions", "warning", "caution", "Unrecognized calls",
            "Not built-ins or functions defined in this file: " + ", ".join(unknown[:20])
            + (" …" if len(unknown) > 20 else "") + ". They may be methods on user types or library functions.",
            [ln for n in unknown[:20] for ln in usage[n]["lines"][:2]])
    collections = sorted({n.split(".")[0] for n in usage if n.split(".")[0] in ("array", "matrix", "map")})
    if collections:
        add("collections", "info", "caution", "Uses " + ", ".join(collections),
            "Collection logic is translated by hand; check bar-to-bar state carefully.")
    if re.search(r"^\s*(?:export\s+)?type\s+\w+", ctx.masked, re.M):
        add("user_types", "info", "caution", "User-defined types",
            "Objects and methods are translated by hand.", ctx.lines_matching(r"^\s*(?:export\s+)?type\s+\w+"))

    classification = _classify(kind, findings)
    summary = _summary(kind, pine_version, classification, findings, declared_title)
    return AnalysisResult(
        analyzer_version=ANALYZER_VERSION,
        script_kind=kind,
        pine_version=pine_version,
        declared_title=declared_title,
        declaration=declaration,
        inputs=inputs,
        function_usage=usage,
        user_functions=user_functions,
        imports=imports,
        findings=findings,
        classification=classification,
        summary=summary,
    )


def _status(name: str, user_functions: list[str], aliases: set[str]) -> str:
    if name in user_functions:
        return "user"
    ns = name.split(".")[0]
    if ns in aliases:
        return "library"
    if name in VISUAL_ONLY or ns in VISUAL_NAMESPACES:
        return "visual"
    if name.startswith("ta."):
        return "supported" if name[3:] in SUPPORTED_TA else "unsupported"
    if name.startswith("strategy."):
        if name in SUPPORTED_STRATEGY_CALLS or name.startswith("strategy.risk."):
            return "supported"
        return "manual" if name == "strategy.order" else "supported"
    if name.startswith("request."):
        return "supported" if name == "request.security" else "unsupported"
    if name.startswith("input") or ns in ("math", "str", "array", "matrix", "map", "timeframe", "syminfo",
                                          "ticker", "runtime", "log", "chart", "session"):
        return "supported"
    if name in KNOWN_FUNCTIONS or ns in KNOWN_NAMESPACES:
        return "supported"
    if name in LEGACY_V4:
        return "supported"
    if "." in name:
        return "unknown"  # likely a method call on a user object
    return "unknown"


def _classify(kind: ScriptKind, findings: list[Finding]) -> Compatibility:
    impacts = {f.impact for f in findings}
    if kind is not ScriptKind.strategy or "blocking" in impacts:
        return Compatibility.unsupported
    if "manual" in impacts:
        return Compatibility.manual
    return Compatibility.partial


def _summary(kind, version, cls, findings, title) -> str:
    crit = sum(f.severity == "critical" for f in findings)
    warn = sum(f.severity == "warning" for f in findings)
    name = f"“{title}”" if title else "This script"
    what = {ScriptKind.strategy: "strategy", ScriptKind.indicator: "indicator", ScriptKind.library: "library"}.get(kind, "file")
    v = f"Pine v{version}" if version else "unversioned"
    verdict = {
        Compatibility.partial: "Every construct found is in the engine's supported set. It still needs a reviewed native translation and a parity check before results count as validated.",
        Compatibility.manual: "Some constructs need manual conversion decisions before it can be backtested.",
        Compatibility.unsupported: "It cannot currently be backtested reliably.",
        Compatibility.validated: "Validated against TradingView output.",
    }[cls]
    return f"{name} is a {v} {what}. {verdict} {crit} critical and {warn} warning findings."


def _extract_inputs(ctx: _Ctx) -> list[InputParam]:
    out: list[InputParam] = []
    for c in ctx.calls:
        if not (c.name == "input" or c.name.startswith("input.")):
            continue
        typ = c.name.split(".", 1)[1] if "." in c.name else ""
        default_raw = (c.arg("defval", 0) or "").strip()
        ok, val = literal(default_raw)
        if not typ:
            # Pine v4 `input(defval, title, type=input.integer)` or v5 generic `input(defval)`
            t = c.keywords.get("type", "")
            typ = t.split(".")[-1] if t else _infer_type(val) if ok else "expression"
            typ = {"integer": "int", "resolution": "timeframe"}.get(typ, typ)
        title_ok, title = literal(c.arg("title", 1))
        if typ in ("source",) and not ok:
            val, ok = default_raw, True
        opts = {}
        for key in ("minval", "maxval", "step", "options", "group", "tooltip", "inline", "confirm", "display"):
            if key in c.keywords:
                k_ok, k_val = literal(c.keywords[key])
                opts[key] = k_val if k_ok else {"expression": c.keywords[key]}
        before = ctx.masked[ctx.lines.line_start(c.start):c.start]
        m = _ASSIGN_BEFORE.search(before)
        out.append(InputParam(
            position=len(out),
            variable=m.group(1) if m else "",
            input_type=typ,
            title=title if title_ok and isinstance(title, str) else "",
            default_raw=default_raw,
            default_value={"value": val} if ok else {},
            options=opts,
            line=ctx.line(c.start),
        ))
    return out


def _infer_type(val) -> str:
    if isinstance(val, bool):
        return "bool"
    if isinstance(val, int):
        return "int"
    if isinstance(val, float):
        return "float"
    if isinstance(val, str):
        return "source" if val in ("close", "open", "high", "low", "hl2", "hlc3", "ohlc4") else "string"
    return "expression"
