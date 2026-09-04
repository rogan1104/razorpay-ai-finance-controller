import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { API_BASE_URL, checkHealth } from "@/api/client";
import { useRun } from "@/state/run-context";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Reconcile" },
  { to: "/exceptions", label: "Exceptions" },
  { to: "/transactions", label: "Transactions" },
] as const;

function BackendStatus() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: checkHealth,
    refetchInterval: 30_000,
    retry: false,
  });

  const state = isLoading ? "checking" : isError ? "offline" : "online";
  const label =
    state === "checking"
      ? "Checking backend"
      : state === "offline"
        ? "Backend unreachable"
        : `Backend ${String(data?.status ?? "online")}`;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-md border px-2.5 py-1 text-[11px] font-semibold",
        state === "online" && "border-mint/25 bg-mint-soft text-mint",
        state === "offline" && "border-coral/25 bg-coral-soft text-coral",
        state === "checking" && "border-border bg-surface text-muted-foreground",
      )}
      title={API_BASE_URL}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-2 w-2 rounded-full",
          state === "online" && "bg-mint",
          state === "offline" && "bg-coral",
          state === "checking" && "bg-border-strong",
        )}
      />
      {label}
    </span>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const { run, source } = useRun();


  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border bg-card/90 backdrop-blur">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-4 px-6 py-3">
          <Link to="/" className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground"
            >
              AF
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold text-foreground">CloseControl</span>
              <span className="text-[11px] text-muted-foreground">
                AI Finance Controller
              </span>
            </span>
          </Link>

          <nav aria-label="Primary" className="ml-2 flex items-center gap-1">
            {NAV.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                activeOptions={{ exact: item.to === "/" }}
                className="rounded-lg px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                activeProps={{ className: "bg-primary-soft text-primary font-medium" }}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-3">
            {run?.run_id ? (
              <span className="num hidden rounded-md border border-border bg-surface px-2.5 py-1 text-[11px] text-muted-foreground sm:inline-flex">
                Run {run.run_id.slice(0, 12)}
              </span>
            ) : null}
            <BackendStatus />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px] px-6 py-8">{children}</main>

      <footer className="border-t border-border px-6 py-5">
        <p className="mx-auto max-w-[1400px] text-xs text-muted-foreground">
          CloseControl · AI Finance Controller · Razorpay AI Buildathon 2026 · Track 04
        </p>
      </footer>
    </div>
  );
}
