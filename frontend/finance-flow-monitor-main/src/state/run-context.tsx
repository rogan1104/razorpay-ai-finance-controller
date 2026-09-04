import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import type { RunResponse, RunSource } from "@/types/reconciliation";

const STORAGE_KEY = "afc.current_run";

interface RunContextValue {
  run: RunResponse | null;
  source: RunSource | null;
  setRun: (run: RunResponse | null, source?: RunSource) => void;
  hydrated: boolean;
}

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: ReactNode }) {
  const [run, setRunState] = useState<RunResponse | null>(null);
  const [source, setSource] = useState<RunSource | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = window.sessionStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as RunResponse & { __source?: RunSource };
        setRunState(parsed);
        setSource(parsed.__source ?? null);
      }
    } catch {
      /* ignore malformed cache */
    }
    setHydrated(true);
  }, []);

  const setRun = useCallback((next: RunResponse | null, nextSource?: RunSource) => {
    setRunState(next);
    setSource(next ? (nextSource ?? null) : null);
    try {
      if (next)
        window.sessionStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({ ...next, results: undefined, __source: nextSource ?? null }),
        );
      else window.sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* storage unavailable */
    }
  }, []);

  const value = useMemo(() => ({ run, source, setRun, hydrated }), [run, source, setRun, hydrated]);
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRun(): RunContextValue {
  const ctx = useContext(RunContext);
  if (!ctx) throw new Error("useRun must be used inside RunProvider");
  return ctx;
}
