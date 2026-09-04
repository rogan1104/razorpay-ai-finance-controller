import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "@tanstack/react-router";
import { getExceptions } from "@/api/client";
import { ExceptionTable } from "@/components/ExceptionTable";
import { ExceptionDetail } from "@/components/ExceptionDetail";
import { Filters, type FilterValues } from "@/components/Filters";
import { Button, Card, EmptyState, ErrorState, Skeleton } from "@/components/ui-kit";
import { useRun } from "@/state/run-context";
import { fmtInt } from "@/lib/format";
import type { ReconRow } from "@/types/reconciliation";

const PAGE_SIZE = 25;

export function ResultsWorkspace({
  heading,
  description,
  emptyTitle,
  emptyDescription,
  countLabel,
}: {
  heading: string;
  description: string;
  emptyTitle: string;
  emptyDescription?: string | undefined;
  countLabel: "exceptions" | "reconciliation results";
}) {
  const { run, hydrated } = useRun();
  const runId = run?.run_id ?? "";

  const [filters, setFilters] = useState<FilterValues>({
    status: "ALL",
    priority: "ALL",
    search: "",
  });
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<ReconRow | null>(null);

  const query = useQuery({
    queryKey: ["exceptions", runId, filters.status, filters.priority, filters.search, offset],
    queryFn: () => getExceptions(runId, { ...filters, limit: PAGE_SIZE, offset }),
    enabled: Boolean(runId),
    retry: false,
  });

  function updateFilters(next: FilterValues) {
    setFilters(next);
    setOffset(0);
    setSelected(null);
  }

  if (!hydrated) {
    return (
      <div className="flex flex-col gap-3">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!runId) {
    return (
      <EmptyState
        title="No active reconciliation run"
        description="Start a run from the Reconcile page to review results here."
        glyph="⇅"
        action={
          <Link to="/">
            <Button size="sm">Go to reconciliation</Button>
          </Link>
        }
      />
    );
  }

  const page = query.data;
  const displayedCount = page?.items.length ?? 0;
  const totalCount =
    countLabel === "exceptions"
      ? (run?.summary.exception_count ?? 0)
      : (run?.summary.total_results ?? 0);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">{heading}</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
        </div>
        <p className="num text-xs text-muted-foreground">
          {page
            ? `Showing ${fmtInt(displayedCount)} of ${fmtInt(totalCount)} ${countLabel}`
            : "Loading…"}{" "}
          · run {runId.slice(0, 12)}
        </p>
      </div>

      <Card as="section">
        <Filters value={filters} onChange={updateFilters} />
      </Card>

      {query.isError ? (
        <ErrorState
          title="Could not load results"
          message={query.error instanceof Error ? query.error.message : "Unknown error."}
          onRetry={() => void query.refetch()}
        />
      ) : null}

      <div
        className={
          selected ? "grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]" : "grid gap-6 grid-cols-1"
        }
      >
        <div className="min-w-0">
          {query.isLoading && !page ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : (
            <ExceptionTable
              rows={page?.items ?? []}
              total={page?.total ?? 0}
              limit={page?.limit ?? PAGE_SIZE}
              offset={page?.offset ?? offset}
              onPageChange={(next) => {
                setOffset(next);
                setSelected(null);
              }}
              onSelect={(row) => setSelected(row)}
              selectedId={typeof selected?.bank_txn_id === "string" ? selected.bank_txn_id : null}
              loading={query.isFetching}
              emptyTitle={emptyTitle}
              emptyDescription={emptyDescription}
            />
          )}
        </div>

        {selected ? (
          <ExceptionDetail runId={runId} row={selected} onClose={() => setSelected(null)} />
        ) : null}
      </div>
    </div>
  );
}
