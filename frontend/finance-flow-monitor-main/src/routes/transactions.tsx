import { createFileRoute } from "@tanstack/react-router";
import { ResultsWorkspace } from "@/components/ResultsWorkspace";

export const Route = createFileRoute("/transactions")({
  head: () => ({
    meta: [
      { title: "AI Finance Controller | Reconciliation Operations Console" },
      {
        name: "description",
        content:
          "Browse reconciliation results for the current run, filtered by status, priority or free-text search.",
      },
      { property: "og:title", content: "Transactions — AI Finance Controller" },
      {
        property: "og:description",
        content: "Browse bank-to-ledger reconciliation results for the current run.",
      },
    ],
  }),
  component: TransactionsPage,
});

function TransactionsPage() {
  return (
    <ResultsWorkspace
      heading="Transactions"
      description="Reconciliation results for the current run as reported by the backend. Use the status filter to isolate matches or a specific exception type."
      emptyTitle="No records match these filters"
      emptyDescription="Clear the filters or start a new reconciliation run."
      countLabel="reconciliation results"
    />
  );
}
