import { Button } from "@/components/ui-kit";
import { fmtInt } from "@/lib/format";

/**
 * Dataset sizes are the documented shape of the bundled synthetic dataset, not
 * results. Every reconciliation figure shown after a run comes from the backend.
 */
const DEMO_BANK_RECORDS = 2116;
const DEMO_LEDGER_RECORDS = 1925;

export function DemoCard({
  onRun,
  disabled,
  running,
}: {
  onRun: () => void;
  disabled?: boolean | undefined;
  running?: boolean | undefined;
}) {
  return (
    <section
      aria-labelledby="demo-heading"
      className="rounded-xl border border-sky/25 bg-sky-soft/60 p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-6">
        <div className="min-w-[16rem] flex-1">
          <p
            id="demo-heading"
            className="text-[11px] font-semibold uppercase tracking-wider text-sky"
          >
            Try the demo
          </p>
          <h2 className="mt-1.5 text-base font-semibold tracking-tight text-foreground">
            Run the reconciliation engine on the included synthetic dataset
          </h2>
          <p className="mt-1 max-w-xl text-sm text-muted-foreground">
            No file upload required. The backend loads the bundled bank and merchant ledger extracts
            and executes the same reconciliation pipeline used for uploads.
          </p>

          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Bank records
              </dt>
              <dd className="num text-lg font-semibold text-foreground">
                {fmtInt(DEMO_BANK_RECORDS)}
              </dd>
            </div>
            <div>
              <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
                Ledger records
              </dt>
              <dd className="num text-lg font-semibold text-foreground">
                {fmtInt(DEMO_LEDGER_RECORDS)}
              </dd>
            </div>
          </dl>

          <p className="mt-3 text-xs text-muted-foreground">
            Uses the bundled synthetic reconciliation dataset. The ground-truth file is an offline
            evaluation artifact and is never used during a run.
          </p>
        </div>

        <div className="flex flex-col items-start gap-2">
          <Button size="lg" onClick={onRun} disabled={disabled}>
            <span aria-hidden="true">▶</span>
            {running ? "Running demo…" : "Run Demo Reconciliation"}
          </Button>
        </div>
      </div>
    </section>
  );
}
