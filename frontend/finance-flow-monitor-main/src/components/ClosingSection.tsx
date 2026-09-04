import { cn } from "@/lib/utils";

const PRINCIPLES = [
  {
    title: "DETERMINISTIC RECONCILIATION",
    body: "Financial decisions are made by reproducible matching rules — not an LLM.",
  },
  {
    title: "EXPLAINABLE EXCEPTIONS",
    body: "Every mismatch, duplicate, ambiguous match, and unmatched record comes with supporting evidence.",
  },
  {
    title: "AI-ASSISTED REVIEW",
    body: "AI helps categorize and prioritize transactions. It never changes the reconciliation result.",
  },
] as const;

export function ClosingSection() {
  return (
    <section
      aria-labelledby="closing-heading"
      className="rounded-xl bg-foreground px-6 py-7 text-background"
    >
      <h2 id="closing-heading" className="text-lg font-semibold tracking-tight">
        RECONCILIATION, WITH CONTROL BUILT IN.
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-relaxed text-background/70">
        Match bank transactions against the merchant ledger, identify exceptions, and give every
        decision a clear reason.
      </p>

      <div className="mt-6 grid gap-5 md:grid-cols-3 md:gap-0">
        {PRINCIPLES.map((principle, index) => (
          <div
            key={principle.title}
            className={cn(
              index > 0 && "border-t border-background/15 pt-5 md:border-l md:border-t-0 md:pt-0",
              index === 0 ? "md:pr-6" : "md:px-6",
              index === PRINCIPLES.length - 1 && "md:pr-0",
            )}
          >
            <h3 className="text-[11px] font-semibold uppercase tracking-wider text-background/55">
              {principle.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-background/80">{principle.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
