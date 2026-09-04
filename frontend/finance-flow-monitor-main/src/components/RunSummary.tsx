import { Card, Chip, SectionHeading } from "@/components/ui-kit";
import { MetricCard } from "@/components/MetricCard";
import { StatusBreakdown } from "@/components/StatusBreakdown";
import { priorityMeta } from "@/lib/status";
import { fmtInt, fmtRate, fmtSeconds, fmtThroughput } from "@/lib/format";
import { PRIORITIES, type RunResponse } from "@/types/reconciliation";

export function RunSummary({ run }: { run: RunResponse }) {
  const s = run.summary;
  const totalResults = s.total_results ?? s.total_source_records;
  const matchCount = run.status_counts.MATCH ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Bank records"
          value={fmtInt(s.bank_records)}
          hint="Rows ingested from bank statement"
          accent="sky"
        />
        <MetricCard
          label="Ledger records"
          value={fmtInt(s.ledger_records)}
          hint="Rows ingested from internal ledger"
          accent="neutral"
        />
        <MetricCard
          label="Match rate"
          value={fmtRate(s.match_rate)}
          hint={`${fmtInt(matchCount)} of ${fmtInt(totalResults)} reconciliation results classified as MATCH`}
          accent="mint"
        />
        <MetricCard
          label="Exceptions"
          value={fmtInt(s.exception_count)}
          hint="Records requiring review"
          accent="coral"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <SectionHeading
            title="Status breakdown"
            subtitle="Distribution of reconciliation outcomes reported by the engine"
          />
          <StatusBreakdown counts={run.status_counts} total={totalResults} />
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <SectionHeading
              title="Review priority distribution"
              subtitle="Priority assigned across reconciliation results by the engine."
            />
            <ul className="flex flex-col gap-2.5">
              {PRIORITIES.map((p) => {
                const meta = priorityMeta(p);
                return (
                  <li key={p} className="flex items-center justify-between gap-3">
                    <Chip className={meta.chip} glyph={meta.glyph}>
                      {p}
                    </Chip>
                    <span className="num text-sm text-foreground">
                      {fmtInt(run.priority_counts[p])}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Card>

          <Card>
            <SectionHeading title="Performance" subtitle="Reported runtime" />
            <dl className="flex flex-col gap-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Total source records</dt>
                <dd className="num">{fmtInt(s.total_source_records)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Reconciliation</dt>
                <dd className="num">{fmtSeconds(s.reconciliation_runtime_seconds)}</dd>
              </div>

              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Intelligence</dt>
                <dd className="num">{fmtSeconds(s.intelligence_runtime_seconds)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Total</dt>
                <dd className="num">{fmtSeconds(s.total_runtime_seconds)}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Throughput</dt>
                <dd className="num">{fmtThroughput(s.throughput_records_per_second)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>

      <Card>
        <SectionHeading title="AI enrichment" subtitle="Signals added to reconciliation results" />
        <p className="max-w-3xl text-sm text-muted-foreground">
          AI enrichment adds transaction categorisation, confidence signals, and exception-priority
          intelligence to reconciliation results.
        </p>
      </Card>
    </div>
  );
}
