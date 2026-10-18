/** Minimal Pine Script tokenizer for display. It colors text; it does not validate or parse. */

export type TokenKind = "comment" | "annotation" | "string" | "number" | "keyword" | "namespace" | "call" | "builtin" | "op" | "text";
export type Token = { kind: TokenKind; text: string };

const KEYWORDS = new Set(["if", "else", "for", "to", "by", "while", "switch", "var", "varip", "and", "or", "not", "true", "false", "na",
  "import", "export", "as", "method", "type", "return", "continue", "break", "in", "int", "float", "bool", "string", "color",
  "series", "simple", "const", "array", "matrix", "map", "enum", "line", "label", "box", "table"]);
const NAMESPACES = new Set(["ta", "math", "str", "request", "strategy", "input", "array", "matrix", "map", "color", "line", "label", "box",
  "table", "syminfo", "timeframe", "barstate", "session", "ticker", "chart", "runtime", "log", "barmerge", "plot", "shape", "location", "size",
  "position", "display", "extend", "xloc", "yloc", "text", "font", "currency", "order", "alert", "dayofweek"]);
const BUILTIN_VARS = new Set(["open", "high", "low", "close", "volume", "time", "time_close", "bar_index", "last_bar_index", "hl2", "hlc3", "ohlc4",
  "hlcc4", "timenow", "year", "month", "dayofmonth", "hour", "minute", "second", "weekofyear"]);

const RULES: [TokenKind | "ident", RegExp][] = [
  ["annotation", /^\/\/\s*@\w+.*/],
  ["comment", /^\/\/.*/],
  ["string", /^"(?:\\.|[^"\\\n])*"?|^'(?:\\.|[^'\\\n])*'?/],
  ["number", /^(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|^#[0-9a-fA-F]{6,8}\b/],
  ["ident", /^[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*/],
  ["op", /^(?:=>|:=|==|!=|<=|>=|\?|:|[-+*/%<>=])/],
  ["text", /^\s+|^./],
];

export function tokenizeLine(line: string): Token[] {
  const out: Token[] = [];
  let rest = line;
  while (rest.length) {
    for (const [kind, re] of RULES) {
      const m = re.exec(rest);
      if (!m) continue;
      const text = m[0];
      if (kind === "ident") {
        const head = text.split(".")[0];
        const isCall = /^\s*(?:<[^>]*>)?\s*\(/.test(rest.slice(text.length));
        out.push({ kind: KEYWORDS.has(text) ? "keyword" : NAMESPACES.has(head) && text.includes(".") ? "namespace" : isCall ? "call" : BUILTIN_VARS.has(text) ? "builtin" : "text", text });
      } else out.push({ kind, text });
      rest = rest.slice(text.length);
      break;
    }
  }
  return merge(out);
}

function merge(tokens: Token[]): Token[] {
  const out: Token[] = [];
  for (const t of tokens) {
    const last = out.at(-1);
    if (last && last.kind === t.kind && t.kind === "text") last.text += t.text;
    else out.push({ ...t });
  }
  return out;
}

export const TOKEN_CLASS: Record<TokenKind, string> = {
  comment: "text-fg-faint italic", annotation: "text-accent", string: "text-pos", number: "text-[#d6a0ff] [[data-theme=light]_&]:text-[#7b3fc4]",
  keyword: "text-[#ff8f6b] [[data-theme=light]_&]:text-[#b4421d]", namespace: "text-info", call: "text-[#7fd6e0] [[data-theme=light]_&]:text-[#0e7480]",
  builtin: "text-warn", op: "text-fg-dim", text: "",
};
