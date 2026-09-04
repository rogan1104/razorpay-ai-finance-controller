import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  hint,
  accent = "neutral",
  icon,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: "neutral" | "mint" | "peach" | "sky" | "butter" | "coral";
  icon?: ReactNode;
}) {
  const accentBar: Record<string, string> = {
    neutral: "bg-border-strong",
    mint: "bg-mint",
    peach: "bg-peach",
    sky: "bg-sky",
    butter: "bg-butter",
    coral: "bg-coral",
  };

  return (
    <div className="card-surface relative overflow-hidden p-5">
      <span aria-hidden="true" className={cn("absolute inset-x-0 top-0 h-1", accentBar[accent])} />
      <div className="flex items-start justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {icon ? (
          <span aria-hidden="true" className="text-muted-foreground">
            {icon}
          </span>
        ) : null}
      </div>
      <p className="num mt-3 text-2xl font-semibold text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
