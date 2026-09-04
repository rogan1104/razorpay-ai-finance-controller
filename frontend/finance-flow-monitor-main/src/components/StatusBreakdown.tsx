import { ALL_STATUSES, statusMeta } from "@/lib/status";
import { fmtInt } from "@/lib/format";
import type { StatusCounts } from "@/types/reconciliation";
import { cn } from "@/lib/utils";

export function StatusBreakdown({
  counts,
  total,
}: {
  counts: StatusCounts;
  total?: number | undefined;
}) {
  const sum =
    typeof total === "number" && total > 0
      ? total
      : ALL_STATUSES.reduce((acc, s) => acc + (counts[s] ?? 0), 0);

  return (
    <ul className="flex flex-col gap-3">
      {ALL_STATUSES.map((status) => {
        const meta = statusMeta(status);
        const count = counts[status] ?? 0;
        const pct = sum > 0 ? (count / sum) * 100 : 0;
        return (
          <li key={status}>
            <div className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2 text-xs font-semibold tracking-wide text-foreground">
                <span aria-hidden="true" className={cn("h-2.5 w-2.5 rounded-sm", meta.bar)} />
                {meta.label}
              </span>
              <span className="num text-xs text-muted-foreground">
                {fmtInt(count)}
                <span className="ml-2 text-foreground">{pct.toFixed(2)}%</span>
              </span>
            </div>
            <div
              className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted"
              role="img"
              aria-label={`${meta.label}: ${fmtInt(count)} records, ${pct.toFixed(2)} percent`}
            >
              <div
                className={cn("h-full rounded-full transition-[width] duration-500", meta.bar)}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
