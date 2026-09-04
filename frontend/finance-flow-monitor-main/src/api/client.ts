import type {
  BenchmarkReport,
  ExceptionsPage,
  HealthResponse,
  PriorityCounts,
  ReconRow,
  ReconSummary,
  RunResponse,
  StatusCounts,
} from "@/types/reconciliation";

export const API_BASE_URL = (
  (import.meta.env["VITE_API_BASE_URL"] as string | undefined) ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "")
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const FRIENDLY: Record<number, string> = {
  400: "The backend rejected the request. Check that both CSV files are valid and contain the required columns.",
  404: "That reconciliation run could not be found. It may have expired — run reconciliation again.",
  413: "The uploaded files are too large for the backend to accept.",
  422: "The uploaded files could not be processed. Check for missing required columns or empty rows.",
  500: "The backend hit an internal error while processing this request.",
};

/** Strips anything that looks like a traceback, path, or internal detail. */
function sanitize(detail: unknown, status: number): string {
  const fallback = FRIENDLY[status] ?? `Request failed (HTTP ${status}).`;
  if (typeof detail !== "string") return fallback;
  const first = detail.split("\n")[0]?.trim() ?? "";
  const looksInternal =
    /Traceback|File "|\/[a-z]+\/[a-z]+\/|[A-Za-z]+Error:|line \d+|Exception|site-packages/i.test(
      first,
    ) ||
    first.length === 0 ||
    first.length > 240;
  return looksInternal ? fallback : first;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the reconciliation API at ${API_BASE_URL}. Make sure the FastAPI backend is running.`,
      0,
    );
  }

  if (!res.ok) {
    let detail: unknown;
    try {
      const body = (await res.json()) as { detail?: unknown; message?: unknown };
      detail = body?.detail ?? body?.message;
      if (Array.isArray(detail)) {
        detail = (detail as Array<{ msg?: string }>).map((d) => d?.msg).filter(Boolean)[0];
      }
    } catch {
      detail = undefined;
    }
    throw new ApiError(sanitize(detail, res.status), res.status);
  }

  return (await res.json()) as T;
}

type Rec = Record<string, unknown>;
const asRec = (v: unknown): Rec => (v && typeof v === "object" ? (v as Rec) : {});
const num = (v: unknown): number | undefined => (typeof v === "number" ? v : undefined);

/** Normalizes the run payload, tolerating flat or nested summary shapes. */
function normalizeRun(raw: unknown): RunResponse {
  const root = asRec(raw);
  const summarySrc = asRec(root["summary"] ?? root["metrics"] ?? root);

  const summary: ReconSummary = {
    bank_records: num(summarySrc["bank_records"]),
    ledger_records: num(summarySrc["ledger_records"]),
    total_source_records: num(summarySrc["total_source_records"]),
    total_results: num(summarySrc["total_results"]),
    match_rate: num(summarySrc["match_rate"]),
    exception_count: num(summarySrc["exception_count"]),
    reconciliation_runtime_seconds: num(summarySrc["reconciliation_runtime_seconds"]),
    intelligence_runtime_seconds: num(summarySrc["intelligence_runtime_seconds"]),
    total_runtime_seconds: num(summarySrc["total_runtime_seconds"]),
    throughput_records_per_second: num(summarySrc["throughput_records_per_second"]),
  };

  const statusSrc = asRec(root["status_counts"] ?? summarySrc["status_counts"]);
  const prioritySrc = asRec(root["priority_counts"] ?? summarySrc["priority_counts"]);

  const results = Array.isArray(root["results"]) ? (root["results"] as ReconRow[]) : undefined;

  return {
    run_id: String(root["run_id"] ?? root["id"] ?? ""),
    summary,
    status_counts: statusSrc as StatusCounts,
    priority_counts: prioritySrc as PriorityCounts,
    results,
  };
}

function normalizePage(raw: unknown, limit: number, offset: number): ExceptionsPage {
  if (Array.isArray(raw)) {
    return { items: raw as ReconRow[], total: raw.length, limit, offset };
  }
  const root = asRec(raw);
  const items = (root["items"] ??
    root["exceptions"] ??
    root["results"] ??
    root["data"] ??
    []) as ReconRow[];
  const total =
    num(root["total"]) ??
    num(root["total_matching"]) ??
    num(root["count"]) ??
    num(root["total_count"]);
  return {
    items: Array.isArray(items) ? items : [],
    total: total ?? (Array.isArray(items) ? items.length : 0),
    limit: num(root["limit"]) ?? limit,
    offset: num(root["offset"]) ?? offset,
  };
}

export function checkHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/api/health");
}

export async function runReconciliation(bankFile: File, ledgerFile: File): Promise<RunResponse> {
  const form = new FormData();
  form.append("bank_file", bankFile);
  form.append("ledger_file", ledgerFile);
  const raw = await request<unknown>("/api/reconcile", { method: "POST", body: form });
  return normalizeRun(raw);
}

/**
 * Runs the reconciliation engine on the dataset bundled with the backend.
 * The frontend never reads dataset files (or the ground truth) itself — this is a
 * single isolated call to the backend demo endpoint, which executes the same
 * pipeline as the upload workflow and returns real, freshly computed results.
 */
export const DEMO_ENDPOINT = "/api/reconcile/demo";

export async function runDemoReconciliation(): Promise<RunResponse> {
  const raw = await request<unknown>(DEMO_ENDPOINT, { method: "POST" });
  return normalizeRun(raw);
}

/**
 * Offline benchmark metrics, if (and only if) the backend exposes them.
 * Returns null when the endpoint is not available — nothing is ever fabricated.
 */
export const BENCHMARK_ENDPOINT = "/api/benchmark";

export async function getBenchmark(): Promise<BenchmarkReport | null> {
  try {
    const raw = await request<unknown>(BENCHMARK_ENDPOINT);
    const root = asRec(raw);
    const src = asRec(root["benchmark"] ?? root["metrics"] ?? root);
    const perClassSrc = asRec(src["per_class"] ?? src["per_class_metrics"] ?? src["classes"]);
    const per_class = Object.entries(perClassSrc).map(([label, v]) => {
      const m = asRec(v);
      return {
        label,
        precision: num(m["precision"]),
        recall: num(m["recall"]),
        f1: num(m["f1"]) ?? num(m["f1_score"]),
        support: num(m["support"]),
      };
    });
    return {
      evaluated_cases: num(src["evaluated_cases"]) ?? num(src["total_cases"]),
      correct_cases: num(src["correct_cases"]),
      incorrect_cases: num(src["incorrect_cases"]),
      accuracy: num(src["accuracy"]),
      macro_f1: num(src["macro_f1"]) ?? num(src["macro_f1_score"]),
      weighted_f1: num(src["weighted_f1"]) ?? num(src["weighted_f1_score"]),
      match_resolution: num(src["match_resolution"]),
      benchmark_throughput_records_per_second: num(src["benchmark_throughput_records_per_second"]),
      per_class,
    };
  } catch {
    return null;
  }
}

export async function getRun(runId: string): Promise<RunResponse> {
  return normalizeRun(await request<unknown>(`/api/reconcile/${encodeURIComponent(runId)}`));
}

export interface ExceptionFilters {
  status?: string;
  priority?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export async function getExceptions(
  runId: string,
  filters: ExceptionFilters = {},
): Promise<ExceptionsPage> {
  const limit = filters.limit ?? 25;
  const offset = filters.offset ?? 0;
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "ALL") params.set("status", filters.status);
  if (filters.priority && filters.priority !== "ALL") params.set("priority", filters.priority);
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  params.set("limit", String(limit));
  params.set("offset", String(offset));

  const raw = await request<unknown>(
    `/api/reconcile/${encodeURIComponent(runId)}/exceptions?${params.toString()}`,
  );
  return normalizePage(raw, limit, offset);
}

export async function getExceptionDetail(runId: string, bankTxnId: string): Promise<ReconRow> {
  const raw = await request<unknown>(
    `/api/reconcile/${encodeURIComponent(runId)}/exceptions/${encodeURIComponent(bankTxnId)}`,
  );
  const root = asRec(raw);
  const inner = root["exception"] ?? root["detail"] ?? root["result"] ?? raw;
  return asRec(inner) as ReconRow;
}
