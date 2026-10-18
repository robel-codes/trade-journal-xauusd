import { describe, expect, it } from "vitest";
import { tokenizeLine } from "./pine-highlight";

const kinds = (s: string) => tokenizeLine(s).filter((t) => t.text.trim()).map((t) => `${t.kind}:${t.text.trim()}`);

describe("tokenizeLine", () => {
  it("separates annotation, calls, namespaces and literals", () => {
    expect(kinds("//@version=5")).toEqual(["annotation://@version=5"]);
    expect(kinds('fast = ta.ema(close, 9) // fast')).toEqual(["text:fast", "op:=", "namespace:ta.ema", "text:(", "builtin:close", "text:,", "number:9", "text:)", "comment:// fast"]);
  });
  it("does not treat comment markers inside strings as comments", () => {
    expect(kinds('s = "a // b"')).toEqual(["text:s", "op:=", 'string:"a // b"']);
  });
  it("round-trips the exact text", () => {
    const line = '  strategy.exit("XL", "L", stop=stop, limit=x + atr * 1.5)   ';
    expect(tokenizeLine(line).map((t) => t.text).join("")).toBe(line);
  });
  it("recognizes keywords and user calls", () => {
    expect(kinds("if longCond and myFunc(x)")).toEqual(["keyword:if", "text:longCond", "keyword:and", "call:myFunc", "text:(x)"]);
  });
});
