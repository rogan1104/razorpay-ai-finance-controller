import { cn } from "@/lib/utils";

export type ProcessingStep =
  | "loading"
  | "validating"
  | "matching"
  | "enriching"
  | "preparing";

const UPLOAD_STEPS: Array<{ key: ProcessingStep; label: string }> = [
  { key: "validating", label: "Validating files" },
  { key: "matching", label: "Matching transactions" },
  { key: "enriching", label: "Enriching exceptions" },
  { key: "preparing", label: "Preparing results" },
];

const DEMO_STEPS: Array<{ key: ProcessingStep; label: string }> = [
  { key: "loading", label: "Loading synthetic transaction batch" },
  { key: "validating", label: "Validating source files" },
  { key: "matching", label: "Reconciling bank and ledger records" },
  { key: "enriching", label: "Enriching exceptions" },
  { key: "preparing", label: "Preparing results" },
];

/**
 * Step state is derived from the real request lifecycle:
 * the client-side stages complete once the request is accepted by the server,
 * the remaining steps track the single server round-trip and only complete
 * when the response actually arrives. No backend sub-stage is claimed complete
 * unless the request itself has progressed past it.
 */
export function ProcessingState({
  current,
  mode = "upload",
}: {
  current: ProcessingStep;
  mode?: "upload" | "demo";
}) {
  const steps = mode === "demo" ? DEMO_STEPS : UPLOAD_STEPS;
  const currentIndex = steps.findIndex((s) => s.key === current);

  return (
    <div className="card-surface p-6" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-3">
        <span
          aria-hidden="true"
          className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
        />
        <h3 className="text-sm font-semibold text-foreground">
          {mode === "demo" ? "Running demo reconciliation…" : "Reconciling transactions…"}
        </h3>
      </div>
      <ol className="mt-5 flex flex-col gap-3">
        {steps.map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <li key={step.key} className="flex items-center gap-3 text-sm">
              <span
                aria-hidden="true"
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px]",
                  done && "border-mint/30 bg-mint-soft text-mint",
                  active && "border-primary/30 bg-primary-soft text-primary",
                  !done && !active && "border-border bg-surface text-muted-foreground",
                )}
              >
                {done ? "✓" : active ? "●" : "○"}
              </span>
              <span
                className={cn(
                  done && "text-foreground",
                  active && "font-medium text-foreground",
                  !done && !active && "text-muted-foreground",
                )}
              >
                {step.label}
              </span>
              <span className="sr-only">
                {done ? "completed" : active ? "in progress" : "pending"}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="mt-5 text-xs text-muted-foreground">
        Reconciliation runs on the backend engine. Keep this tab open — duplicate submissions are
        disabled while a run is in flight.
      </p>
    </div>
  );
}
