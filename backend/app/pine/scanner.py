"""Low-level text utilities for Pine Script.

The analyzer never executes or fully parses Pine. It works on a *masked* copy of the source in which
comments and string contents are blanked out (same length, newlines kept), so regular expressions
over code cannot match inside strings or comments, and every offset maps back to the original.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass, field

_KW_ARG = re.compile(r"^\s*([A-Za-z_]\w*)\s*=(?!=)")


def mask(source: str) -> str:
    out = list(source)
    i, n = 0, len(source)
    while i < n:
        ch = source[i]
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            j = source.find("\n", i)
            j = n if j == -1 else j
            for k in range(i, j):
                out[k] = " "
            i = j
        elif ch in "\"'":
            quote = ch
            j = i + 1
            while j < n and source[j] != quote and source[j] != "\n":
                if source[j] == "\\" and j + 1 < n:
                    out[j] = " "
                    j += 1
                out[j] = " "
                j += 1
            i = j + 1
        else:
            i += 1
    return "".join(out)


def strip_comments(source: str) -> str:
    """Remove // comments while keeping string literals intact."""
    result, i, n = [], 0, len(source)
    while i < n:
        ch = source[i]
        if source.startswith("//", i):
            j = source.find("\n", i)
            i = n if j == -1 else j
        elif ch in "\"'":
            j = i + 1
            while j < n and source[j] not in (ch, "\n"):
                j += 2 if source[j] == "\\" else 1
            result.append(source[i:j + 1])
            i = j + 1
        else:
            result.append(ch)
            i += 1
    return "".join(result)


class LineIndex:
    def __init__(self, text: str):
        self.starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line_of(self, offset: int) -> int:
        return bisect.bisect_right(self.starts, offset)  # 1-based

    def line_start(self, offset: int) -> int:
        return self.starts[self.line_of(offset) - 1]


@dataclass
class Call:
    name: str
    start: int  # offset of the name
    open_paren: int
    close_paren: int  # -1 when unbalanced
    positional: list[str] = field(default_factory=list)
    keywords: dict[str, str] = field(default_factory=dict)

    def arg(self, keyword: str, position: int | None = None) -> str | None:
        if keyword in self.keywords:
            return self.keywords[keyword]
        if position is not None and position < len(self.positional):
            return self.positional[position]
        return None


_PAIRS = {"(": ")", "[": "]", "{": "}"}


def parse_call(source: str, masked: str, name: str, start: int, open_paren: int) -> Call:
    """Split the arguments of the call whose '(' is at `open_paren`, respecting nesting."""
    call = Call(name=name, start=start, open_paren=open_paren, close_paren=-1)
    depth = 0
    arg_start = open_paren + 1
    pieces: list[str] = []
    for i in range(open_paren, len(masked)):
        ch = masked[i]
        if ch in _PAIRS:
            depth += 1
        elif ch in ")]}":
            depth -= 1
            if depth == 0:
                pieces.append(source[arg_start:i])
                call.close_paren = i
                break
        elif ch == "," and depth == 1:
            pieces.append(source[arg_start:i])
            arg_start = i + 1
    for raw in pieces:
        text = raw.strip()
        if not text:
            continue
        m = _KW_ARG.match(text)
        if m:
            call.keywords[m.group(1)] = text[m.end():].strip()
        else:
            call.positional.append(text)
    return call


_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def literal(expr: str | None):
    """Best-effort literal evaluation. Returns (ok, value)."""
    if expr is None:
        return False, None
    e = expr.strip()
    if _NUM.match(e):
        v = float(e)
        return True, int(v) if re.match(r"^[+-]?\d+$", e) else v
    if e in ("true", "false"):
        return True, e == "true"
    if e == "na":
        return True, None
    if len(e) >= 2 and e[0] == e[-1] and e[0] in "\"'":
        return True, e[1:-1]
    if e.startswith("[") and e.endswith("]"):
        inner = e[1:-1]
        items, ok = [], True
        for part in _split_top(inner):
            good, val = literal(part)
            ok = ok and good
            items.append(val if good else part.strip())
        if ok:
            return True, items
    if re.match(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$", e):
        return True, e  # enum-like constant: strategy.percent_of_equity, color.red, barmerge.lookahead_on
    return False, None


def _split_top(text: str) -> list[str]:
    m = mask(text)
    out, depth, start = [], 0, 0
    for i, ch in enumerate(m):
        if ch in _PAIRS:
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            out.append(text[start:i])
            start = i + 1
    if text[start:].strip():
        out.append(text[start:])
    return out
