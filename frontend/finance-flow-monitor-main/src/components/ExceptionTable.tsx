import { useMemo, useState } from "react";
import { Button, Chip, EmptyState } from "@/components/ui-kit";
import { priorityMeta, statusMeta } from "@/lib/status";
import { EMPTY, fmtAmount, fmtSimilarity, fmtText } from "@/lib/format";
import type { ReconRow } from "@/types/reconciliation";
import { cn } from "@/lib/utils";

type SortKey = "predicted_status" | "priority" | "amount_difference" | "match_confidence";

const SORTABLE: Array<{ key: SortKey; label: string }> = [
  { key: "predicted_status", label: "Status" },
  { key: "priority", label: "Priority" },
  { key: "amount_difference", label: "Amount Difference" },
  { key: "match_confidence", label: "Confidence" },
];

const PRIORITY_ORDER: Record<string, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 };

export function ExceptionTable({
  rows,
  total,
  limit,
  offset,
  onPageChange,
  onSelect,
  selectedId,
  loading,
  emptyTitle,
  emptyDescription,
}: {
  rows: ReconRow[];
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  onSelect: (row: ReconRow) => void;
  selectedId?: string | null | undefined;
  loading?: boolean | undefined;
  emptyTitle: string;
  emptyDescription?: string | undefined;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" } | null>(null);

  /** Sorting applies to the current server page only. */
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const factor = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (sort.key === "priority") {
        return (
          (PRIORITY_ORDER[String(av ?? "").toUpperCase()] ?? 0) -
            (PRIORITY_ORDER[String(bv ?? "").toUpperCase()] ?? 0)
        ) * factor;
      }
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * factor;
      return String(av ?? "").localeCompare(String(bv ?? "")) * factor;
    });
  }, [rows, sort]);

  const page = Math.floor(offset / Math.max(1, limit)) + 1;
  const pages = Math.max(1, Math.ceil(total / Math.max(1, limit)));

  if (!loading && rows.length === 0) {
    return <EmptyState title={emptyTitle} description={emptyDescription} glyph="⌕" />;
  }

  function toggleSort(key: SortKey) {
    setSort((prev) =>
      prev?.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" },
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full min-w-[1050px] border-collapse text-sm">
          <caption className="sr-only">Reconciliation exceptions</caption>
          <thead>
            <tr className="border-b border-border bg-surface">
              {SORTABLE.map((col) => {
                const active = sort?.key === col.key;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
                    className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
                  >
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className="inline-flex items-center gap-1 rounded hover:text-foreground"
                    >
                      {col.label}
                      <span aria-hidden="true" className="text-[9px]">
                        {active ? (sort.dir === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  </th>
                );
              })}
              <th
                scope="col"
                className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Bank Transaction
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Ledger Record
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Match Method
              </th>
              <th
                scope="col"
                className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
              >
                Reason
              </th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => {
              const meta = statusMeta(row.predicted_status);
              const prio = priorityMeta(row.priority);
              const id = row.bank_txn_id ?? `${row.ledger_id ?? "row"}-${i}`;
              return (
                <tr
                  key={`${id}-${i}`}
                  tabIndex={0}
                  role="button"
                  aria-label={`Open exception ${fmtText(row.bank_txn_id)}`}
                  onClick={() => onSelect(row)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(row);
                    }
                  }}
                  className={cn(
                    "cursor-pointer border-b border-border transition-colors last:border-0 hover:bg-surface",
                    selectedId && row.bank_txn_id === selectedId && "bg-primary-soft",
                  )}
                >
                  <td className="px-4 py-3">
                    <Chip className={meta.chip} glyph={meta.glyph}>
                      {meta.label}
                    </Chip>
                  </td>
                  <td className="px-4 py-3">
                    <Chip className={prio.chip} glyph={prio.glyph}>
                      {prio.label}
                    </Chip>
                  </td>
                  <td className="num px-4 py-3 text-foreground">
                    {row.amount_difference === null || row.amount_difference === undefined
                      ? EMPTY
                      : fmtAmount(row.amount_difference)}
                  </td>
                  <td className="num px-4 py-3 text-foreground">
                    {fmtSimilarity(row.match_confidence)}
                  </td>
                  <td className="num px-4 py-3 text-foreground">{fmtText(row.bank_txn_id)}</td>
                  <td className="num px-4 py-3 text-muted-foreground">{fmtText(row.ledger_id)}</td>
                  <td className="px-4 py-3 text-muted-foreground">{fmtText(row.match_method)}</td>
                  <td className="max-w-[22rem] px-4 py-3 text-muted-foreground">
                    <span className="line-clamp-2">{fmtText(row.reason)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="num text-xs text-muted-foreground">
          Showing {total === 0 ? 0 : offset + 1}–{Math.min(offset + rows.length, total)} of {total}
          {" "}exceptions · page {page} of {pages}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0 || loading}
            onClick={() => onPageChange(Math.max(0, offset - limit))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + limit >= total || loading}
            onClick={() => onPageChange(offset + limit)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
