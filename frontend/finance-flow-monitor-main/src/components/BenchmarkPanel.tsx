import { useQuery } from "@tanstack/react-query";
import { getBenchmark } from "@/api/client";
import { Card, SectionHeading } from "@/components/ui-kit";
import { fmtInt, fmtRate, fmtThroughput } from "@/lib/format";

const dash = (v: number | undefined, fmt: (n: number) => string) =>
  typeof v === "number" ? fmt(v) : "—";

/**
 * Offline evaluation artifact. Rendered only when the backend actually exposes
 * benchmark metrics — nothing here is computed or hardcoded in the frontend.
 */
export function BenchmarkPanel() {
  const { data } = useQuery({
    queryKey: ["benchmark"],
    queryFn: getBenchmark,
    retry: false,
    staleTime: 5 * 60_000,
  });

  if (!data) return null;

  const hasHeadline =
    typeof data.accuracy === "number" ||
    typeof data.macro_f1 === "number" ||
    typeof data.weighted_f1 === "number" ||
    typeof data.evaluated_cases === "number" ||
    typeof data.match_resolution === "number";

  if (!hasHeadline && data.per_class.length === 0) return null;

  return (
    <Card className="border-dashed">
      <SectionHeading
        title="Offline benchmark"
        subtitle="The reconciliation engine was independently evaluated against a separate ground-truth benchmark. These figures are not produced by the run above."
      />

      <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Evaluated cases
          </dt>
          <dd className="num text-base text-foreground">{dash(data.evaluated_cases, fmtInt)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Accuracy</dt>
          <dd className="num text-base text-foreground">{dash(data.accuracy, fmtRate)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">Macro F1</dt>
          <dd className="num text-base text-foreground">{dash(data.macro_f1, fmtRate)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
            MATCH resolution
          </dt>
          <dd className="num text-base text-foreground">{dash(data.match_resolution, fmtRate)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Incorrect cases
          </dt>
          <dd className="num text-base text-foreground">{dash(data.incorrect_cases, fmtInt)}</dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Benchmark throughput
          </dt>
          <dd className="num text-base text-foreground">
            {dash(data.benchmark_throughput_records_per_second, fmtThroughput)}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] uppercase tracking-wider text-muted-foreground">
            Weighted F1
          </dt>
          <dd className="num text-base text-foreground">{dash(data.weighted_f1, fmtRate)}</dd>
        </div>
      </dl>

      {data.per_class.length > 0 ? (
        <div className="mt-5 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="py-2 pr-4 font-semibold">Class</th>
                <th className="py-2 pr-4 text-right font-semibold">Precision</th>
                <th className="py-2 pr-4 text-right font-semibold">Recall</th>
                <th className="py-2 pr-4 text-right font-semibold">F1</th>
                <th className="py-2 text-right font-semibold">Support</th>
              </tr>
            </thead>
            <tbody>
              {data.per_class.map((c) => (
                <tr key={c.label} className="border-b border-border last:border-0">
                  <td className="py-2 pr-4 text-foreground">{c.label}</td>
                  <td className="num py-2 pr-4 text-right">{dash(c.precision, fmtRate)}</td>
                  <td className="num py-2 pr-4 text-right">{dash(c.recall, fmtRate)}</td>
                  <td className="num py-2 pr-4 text-right">{dash(c.f1, fmtRate)}</td>
                  <td className="num py-2 text-right">{dash(c.support, fmtInt)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <p className="mt-4 text-xs text-muted-foreground">
        Frozen offline evaluation. Ground truth is used only for scoring and is never used during a
        live reconciliation run.
      </p>
    </Card>
  );
}
