const dash = "—";

export function fmtInt(v: unknown): string {
  return typeof v === "number" && Number.isFinite(v) ? Math.round(v).toLocaleString("en-US") : dash;
}

export function fmtNum(v: unknown, digits = 2): string {
  return typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : dash;
}

/** Backend match_rate may be a fraction (0-1) or already a percentage. */
export function fmtRate(v: unknown): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return dash;
  const pct = v <= 1 ? v * 100 : v;
  return `${pct.toFixed(2)}%`;
}

export function ratePercent(v: unknown): number | undefined {
  if (typeof v !== "number" || !Number.isFinite(v)) return undefined;
  return v <= 1 ? v * 100 : v;
}

export function fmtThroughput(v: unknown): string {
  return typeof v === "number" && Number.isFinite(v)
    ? `${Math.round(v).toLocaleString("en-US")} records/sec`
    : dash;
}

export function fmtSeconds(v: unknown): string {
  return typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(3)}s` : dash;
}

export function fmtAmount(v: unknown): string {
  return typeof v === "number" && Number.isFinite(v)
    ? v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : dash;
}

export function fmtSimilarity(v: unknown): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return dash;
  const pct = v <= 1 ? v * 100 : v;
  return `${pct.toFixed(1)}%`;
}

export function fmtText(v: unknown): string {
  if (v === null || v === undefined || v === "") return dash;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return String(v);
}

export function fmtFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function fmtTimestamp(v: unknown): string {
  if (typeof v !== "string" || !v) return dash;
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "medium" });
}

export const EMPTY = dash;
