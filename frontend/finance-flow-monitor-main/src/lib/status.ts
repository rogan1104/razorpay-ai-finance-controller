import { STATUSES, type Priority, type ReconStatus } from "@/types/reconciliation";

export interface StatusMeta {
  label: string;
  /** background / text / bar utility classes built from semantic tokens */
  chip: string;
  bar: string;
  /** short glyph so status is not communicated by color alone */
  glyph: string;
  description: string;
}

export const STATUS_META: Record<ReconStatus, StatusMeta> = {
  MATCH: {
    label: "MATCH",
    chip: "bg-mint-soft text-mint border-mint/25",
    bar: "bg-mint",
    glyph: "✓",
    description: "Deterministically matched bank and ledger records",
  },
  AMOUNT_MISMATCH: {
    label: "AMOUNT_MISMATCH",
    chip: "bg-peach-soft text-peach border-peach/25",
    bar: "bg-peach",
    glyph: "≠",
    description: "Records paired but amounts differ",
  },
  DUPLICATE: {
    label: "DUPLICATE",
    chip: "bg-butter-soft text-butter border-butter/25",
    bar: "bg-butter",
    glyph: "⧉",
    description: "More than one candidate record for the same transaction",
  },
  AMBIGUOUS: {
    label: "AMBIGUOUS",
    chip: "bg-sky-soft text-sky border-sky/25",
    bar: "bg-sky",
    glyph: "?",
    description: "Multiple plausible pairings, no single confident match",
  },
  UNMATCHED_BANK: {
    label: "UNMATCHED_BANK",
    chip: "bg-coral-soft text-coral border-coral/25",
    bar: "bg-coral",
    glyph: "◐",
    description: "Bank record with no ledger counterpart",
  },
  UNMATCHED_LEDGER: {
    label: "UNMATCHED_LEDGER",
    chip: "bg-slate-soft text-slate border-slate/25",
    bar: "bg-slate",
    glyph: "◑",
    description: "Ledger record with no bank counterpart",
  },
};

export function statusMeta(status: unknown): StatusMeta {
  const key = typeof status === "string" ? (status.toUpperCase() as ReconStatus) : undefined;
  if (key && key in STATUS_META) return STATUS_META[key];
  return {
    label: typeof status === "string" && status ? status : "UNKNOWN",
    chip: "bg-muted text-muted-foreground border-border",
    bar: "bg-border-strong",
    glyph: "•",
    description: "Status reported by the reconciliation engine",
  };
}

export const PRIORITY_META: Record<Priority, { chip: string; glyph: string }> = {
  HIGH: { chip: "bg-coral-soft text-coral border-coral/25", glyph: "▲" },
  MEDIUM: { chip: "bg-butter-soft text-butter border-butter/25", glyph: "◆" },
  LOW: { chip: "bg-sky-soft text-sky border-sky/25", glyph: "▼" },
};

export function priorityMeta(priority: unknown) {
  const key = typeof priority === "string" ? (priority.toUpperCase() as Priority) : undefined;
  if (key && key in PRIORITY_META) return { ...PRIORITY_META[key], label: key };
  return { chip: "bg-muted text-muted-foreground border-border", glyph: "•", label: "—" };
}

export const ALL_STATUSES = STATUSES;
