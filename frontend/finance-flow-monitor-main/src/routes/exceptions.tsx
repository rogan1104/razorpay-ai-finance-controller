import { createFileRoute } from "@tanstack/react-router";
import { ResultsWorkspace } from "@/components/ResultsWorkspace";

export const Route = createFileRoute("/exceptions")({
  head: () => ({
    meta: [
      { title: "AI Finance Controller | Reconciliation Operations Console" },
      {
        name: "description",
        content:
          "Filter, sort and inspect reconciliation exceptions with match analysis and supporting intelligence.",
      },
      { property: "og:title", content: "Exception Review — AI Finance Controller" },
      {
        property: "og:description",
        content: "Review prioritised reconciliation exceptions and their match evidence.",
      },
    ],
  }),
  component: ExceptionsPage,
});

function ExceptionsPage() {
  return (
    <ResultsWorkspace
      heading="Exception review"
      description="Exceptions returned by the reconciliation engine for the current run. Select a row to inspect match evidence, categorisation and anomaly signals."
      emptyTitle="No exceptions match these filters"
      emptyDescription="Adjust the status, priority or search filters to widen the result set."
      countLabel="exceptions"
    />
  );
}
