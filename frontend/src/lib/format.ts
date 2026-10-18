const nf = (min: number, max: number) => new Intl.NumberFormat("en-US", { minimumFractionDigits: min, maximumFractionDigits: max });
const money2 = nf(2, 2);

export function money(v: number | null | undefined, opts: { sign?: boolean; currency?: string } = {}): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const sym = opts.currency && opts.currency !== "USD" ? `${opts.currency} ` : "$";
  const s = `${sym}${money2.format(Math.abs(v))}`;
  return v < 0 ? `−${s}` : opts.sign && v > 0 ? `+${s}` : s;
}

export function pct(v: number | null | undefined, digits = 1, sign = false): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const s = `${nf(digits, digits).format(Math.abs(v * 100))}%`;
  return v < 0 ? `−${s}` : sign && v > 0 ? `+${s}` : s;
}

export function ratio(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return nf(digits, digits).format(v);
}

export function rmult(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v < 0 ? "−" : v > 0 ? "+" : ""}${nf(2, 2).format(Math.abs(v))}R`;
}

export function tone(v: number | null | undefined): string {
  if (v === null || v === undefined || v === 0) return "";
  return v > 0 ? "text-pos" : "text-neg";
}

/** Render a UTC instant in the user's configured timezone. */
export function dateTime(iso: string | null | undefined, tz: string, withTime = true): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: tz, year: "numeric", month: "short", day: "2-digit",
    ...(withTime ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" } : {}),
  }).format(d);
}

export function bytes(n: number): string {
  return n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`;
}
