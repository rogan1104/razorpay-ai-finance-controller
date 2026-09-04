import { useQuery } from "@tanstack/react-query";
import { Button, Chip, DataRow, ErrorState, SectionHeading, Skeleton } from "@/components/ui-kit";
import { getExceptionDetail } from "@/api/client";
import { priorityMeta, statusMeta } from "@/lib/status";
import {
  EMPTY,
  fmtAmount,
  fmtNum,
  fmtSimilarity,
  fmtText,
  fmtTimestamp,
} from "@/lib/format";
import type { ReconRow } from "@/types/reconciliation";

function pick(row: ReconRow, keys: string[]): unknown {
  for (const k of keys) {
    const v = row[k];
    if (v !== undefined && v !== null && v !== "") return v;
  }
  return undefined;
}

function RecordCard({
  title,
  merchant,
  reference,
  amount,
  direction,
  timestamp,
}: {
  title: string;
  merchant: unknown;
  reference: unknown;
  amount: unknown;
  direction: unknown;
  timestamp: unknown;
}) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </p>
      <dl className="mt-2">
        <DataRow label="Merchant" value={fmtText(merchant)} />
        <DataRow label="Reference" value={fmtText(reference)} />
        <DataRow
          label="Amount"
          value={typeof amount === "number" ? fmtAmount(amount) : EMPTY}
        />
        <DataRow label="Direction" value={fmtText(direction)} />
        <DataRow label="Timestamp" value={fmtTimestamp(timestamp)} />
      </dl>
    </div>
  );
}

export function ExceptionDetail({
  runId,
  row,
  onClose,
}: {
  runId: string;
  row: ReconRow;
  onClose: () => void;
}) {
  const bankTxnId = typeof row.bank_txn_id === "string" ? row.bank_txn_id : "";

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["exception", runId, bankTxnId],
    queryFn: () => getExceptionDetail(runId, bankTxnId),
    enabled: Boolean(runId && bankTxnId),
    retry: false,
  });

  const detail: ReconRow = { ...row, ...(data ?? {}) };
  const meta = statusMeta(detail.predicted_status);
  const prio = priorityMeta(detail.priority);
  const reasons = Array.isArray(detail.priority_reasons)
    ? detail.priority_reasons
    : typeof detail.priority_reasons === "string" && detail.priority_reasons
      ? [detail.priority_reasons]
      : [];

  return (
    <aside
      aria-label="Exception detail"
      className="card-surface flex h-fit flex-col p-5 lg:sticky lg:top-24"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="num text-sm font-semibold text-foreground">{fmtText(detail.bank_txn_id)}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Chip className={meta.chip} glyph={meta.glyph}>
              {meta.label}
            </Chip>
            <Chip className={prio.chip} glyph={prio.glyph}>
              {prio.label}
            </Chip>
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close detail panel">
          Close
        </Button>
      </div>

      {isLoading ? (
        <div className="mt-5 flex flex-col gap-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </div>
      ) : null}

      {isError ? (
        <div className="mt-5">
          <ErrorState
            title="Could not load full detail"
            message={error instanceof Error ? error.message : "Unknown error."}
            onRetry={() => void refetch()}
          />
        </div>
      ) : null}

      <div className="mt-5">
        <SectionHeading title="Match analysis" level={3} />
        <dl>
          <DataRow label="Ledger ID" value={fmtText(detail.ledger_id)} />
          <DataRow label="Match method" value={fmtText(detail.match_method)} />
          <DataRow label="Confidence" value={fmtSimilarity(detail.match_confidence)} />
          <DataRow
            label="Amount difference"
            value={
              typeof detail.amount_difference === "number"
                ? fmtAmount(detail.amount_difference)
                : EMPTY
            }
          />
          <DataRow
            label="Timestamp difference"
            value={
              typeof detail.timestamp_difference === "number"
                ? `${fmtNum(detail.timestamp_difference, 2)}s`
                : EMPTY
            }
          />
          <DataRow label="Merchant similarity" value={fmtSimilarity(detail.merchant_similarity)} />
          <DataRow label="Reference similarity" value={fmtSimilarity(detail.reference_similarity)} />
        </dl>
        {detail.reason ? (
          <p className="mt-3 rounded-lg border border-border bg-surface p-3 text-sm text-foreground/80">
            {fmtText(detail.reason)}
          </p>
        ) : null}
      </div>

      <div className="mt-6">
        <SectionHeading title="Supporting intelligence" level={3} />
        <dl>
          <DataRow label="Category" value={fmtText(detail.category)} />
          <DataRow
            label="Category confidence"
            value={fmtSimilarity(detail.categorization_confidence)}
          />
          <DataRow label="Category source" value={fmtText(detail.categorization_source)} />
          <DataRow label="Anomaly" value={fmtText(detail.anomaly_flag ?? detail.anomaly_status)} />
          <DataRow
            label="Anomaly score"
            value={
              typeof detail.anomaly_score === "number" ? fmtNum(detail.anomaly_score, 4) : EMPTY
            }
          />
        </dl>
        {detail.anomaly_reason ? (
          <p className="mt-3 text-sm text-muted-foreground">{fmtText(detail.anomaly_reason)}</p>
        ) : null}
        {reasons.length > 0 ? (
          <ul className="mt-3 flex flex-col gap-1.5">
            {reasons.map((r, i) => (
              <li key={`${String(r)}-${i}`} className="flex gap-2 text-sm text-foreground/80">
                <span aria-hidden="true" className="text-muted-foreground">
                  •
                </span>
                {String(r)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="mt-6 grid gap-3">
        <RecordCard
          title="Bank record"
          merchant={pick(detail, ["bank_merchant", "merchant"])}
          reference={pick(detail, ["bank_reference", "reference"])}
          amount={pick(detail, ["bank_amount", "amount"])}
          direction={pick(detail, ["bank_direction", "direction"])}
          timestamp={pick(detail, ["bank_timestamp", "timestamp"])}
        />
        <RecordCard
          title="Ledger record"
          merchant={detail.ledger_merchant}
          reference={detail.ledger_reference}
          amount={detail.ledger_amount}
          direction={detail.ledger_direction}
          timestamp={detail.ledger_timestamp}
        />
      </div>
    </aside>
  );
}
