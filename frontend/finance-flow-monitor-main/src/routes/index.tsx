import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ApiError, runDemoReconciliation, runReconciliation } from "@/api/client";
import { BenchmarkPanel } from "@/components/BenchmarkPanel";
import { DemoCard } from "@/components/DemoCard";
import { FileUpload } from "@/components/FileUpload";
import { ProcessingState, type ProcessingStep } from "@/components/ProcessingState";
import { RunSummary } from "@/components/RunSummary";
import { ClosingSection } from "@/components/ClosingSection";
import { Button, Card, Chip, EmptyState, ErrorState, SectionHeading } from "@/components/ui-kit";
import { useRun } from "@/state/run-context";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "CloseControl — AI Finance Controller" },
      {
        name: "description",
        content:
          "Run the bundled synthetic demo dataset or upload bank and ledger CSV extracts to reconcile on the engine.",
      },
      { property: "og:title", content: "CloseControl — AI Finance Controller" },
      {
        property: "og:description",
        content:
          "Run the bundled demo dataset or upload your own bank and ledger CSV extracts to start a reconciliation run.",
      },
    ],
  }),
  component: ReconcilePage,
});

type Mode = "demo" | "upload";

function ReconcilePage() {
  const { run, source, setRun, hydrated } = useRun();
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [ledgerFile, setLedgerFile] = useState<File | null>(null);
  const [step, setStep] = useState<ProcessingStep | null>(null);
  const [mode, setMode] = useState<Mode>("upload");
  const [error, setError] = useState<string | null>(null);

  const busy = step !== null;
  const canSubmit = Boolean(bankFile && ledgerFile) && !busy;

  function message(e: unknown, fallback: string) {
    return e instanceof ApiError || e instanceof Error ? e.message : fallback;
  }

  async function submit() {
    if (!bankFile || !ledgerFile) return;
    setError(null);
    setMode("upload");
    setStep("validating");
    try {
      setStep("matching");
      const result = await runReconciliation(bankFile, ledgerFile);
      setStep("preparing");
      setRun(result, "upload");
    } catch (e) {
      setError(message(e, "Reconciliation failed for an unknown reason."));
    } finally {
      setStep(null);
    }
  }

  async function submitDemo() {
    setError(null);
    setMode("demo");
    setStep("loading");
    try {
      setStep("validating");
      setStep("matching");
      const result = await runDemoReconciliation();
      setStep("preparing");
      setRun(result, "demo");
    } catch (e) {
      setError(message(e, "Demo run could not be completed."));
    } finally {
      setStep(null);
    }
  }

  function reset() {
    setRun(null);
    setBankFile(null);
    setLedgerFile(null);
    setError(null);
  }

  const isDemoRun = source === "demo";

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Reconciliation run</h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Run the bundled synthetic dataset, or submit a bank statement extract with the matching
            internal ledger extract. Matching, categorisation, anomaly detection and prioritisation
            are performed by the backend engine.
          </p>
        </div>
        {run ? (
          <div className="flex gap-2">
            <Link to="/exceptions">
              <Button variant="primary" size="sm">
                View Exceptions
              </Button>
            </Link>
            <Button variant="outline" size="sm" onClick={reset} disabled={busy}>
              Start New Run
            </Button>
          </div>
        ) : null}
      </div>

      <DemoCard
        onRun={() => {
          void submitDemo();
        }}
        disabled={busy}
        running={busy && mode === "demo"}
      />

      <div className="flex items-center gap-4" aria-hidden="true">
        <span className="h-px flex-1 bg-border" />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          or
        </span>
        <span className="h-px flex-1 bg-border" />
      </div>

      <Card as="section">
        <SectionHeading
          title="Upload your own data"
          subtitle="Two CSV extracts are required: bank transactions and merchant ledger entries."
          action={
            <Button onClick={() => void submit()} disabled={!canSubmit} size="md">
              {busy && mode === "upload" ? "Reconciling…" : "Run reconciliation"}
            </Button>
          }
        />
        <div className="grid gap-4 md:grid-cols-2">
          <FileUpload
            title="Bank statement CSV"
            expectedName="bank_transactions.csv"
            file={bankFile}
            onSelect={setBankFile}
            onClear={() => setBankFile(null)}
            disabled={busy}
            accent="sky"
          />
          <FileUpload
            title="Ledger CSV"
            expectedName="merchant_ledger.csv"
            file={ledgerFile}
            onSelect={setLedgerFile}
            onClear={() => setLedgerFile(null)}
            disabled={busy}
            accent="mint"
          />
        </div>
      </Card>

      {busy && step ? <ProcessingState current={step} mode={mode} /> : null}

      {error ? (
        <ErrorState
          title={mode === "demo" ? "Demo run could not be completed." : "Reconciliation failed"}
          message={error}
          onRetry={
            mode === "demo"
              ? () => {
                  void submitDemo();
                }
              : canSubmit
                ? () => {
                    void submit();
                  }
                : undefined
          }
        />
      ) : null}

      {run ? (
        <section aria-label="Run summary" className="flex flex-col gap-4">
          {isDemoRun ? (
            <div className="rounded-xl border border-mint/25 bg-mint-soft px-5 py-4">
              <p className="text-sm font-semibold text-mint">Demo reconciliation complete</p>
              <p className="mt-1 text-sm text-foreground/80">
                Data source: bundled synthetic reconciliation dataset. All figures below were
                produced by this backend execution.
              </p>
            </div>
          ) : null}

          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <h2 className="text-base font-semibold tracking-tight text-foreground">
                Run summary
              </h2>
              <Chip
                className={
                  isDemoRun
                    ? "border-sky/25 bg-sky-soft text-sky"
                    : "border-border bg-surface text-muted-foreground"
                }
                glyph={isDemoRun ? "▶" : "↑"}
              >
                {isDemoRun ? "DEMO RUN" : "UPLOADED DATA"}
              </Chip>
            </div>
            <p className="num text-xs text-muted-foreground" title={run.run_id}>
              Run ID {run.run_id.slice(0, 12)}
            </p>
          </div>
          <RunSummary run={run} />
          <BenchmarkPanel />
        </section>
      ) : hydrated && !busy ? (
        <EmptyState
          title="No reconciliation run yet"
          description="Run the bundled demo dataset or upload both CSV extracts to see match rates, status breakdown and exceptions."
          glyph="⇅"
        />
      ) : null}

      <ClosingSection />
    </div>
  );
}
