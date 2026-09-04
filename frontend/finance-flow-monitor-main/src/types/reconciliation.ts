export const STATUSES = [
  "MATCH",
  "AMOUNT_MISMATCH",
  "DUPLICATE",
  "AMBIGUOUS",
  "UNMATCHED_BANK",
  "UNMATCHED_LEDGER",
] as const;

export type ReconStatus = (typeof STATUSES)[number];

export const PRIORITIES = ["HIGH", "MEDIUM", "LOW"] as const;
export type Priority = (typeof PRIORITIES)[number];

export interface ReconSummary {
  bank_records?: number | undefined;
  ledger_records?: number | undefined;
  total_source_records?: number | undefined;
  total_results?: number | undefined;
  match_rate?: number | undefined;
  exception_count?: number | undefined;
  reconciliation_runtime_seconds?: number | undefined;
  intelligence_runtime_seconds?: number | undefined;
  total_runtime_seconds?: number | undefined;
  throughput_records_per_second?: number | undefined;
}

export type StatusCounts = Partial<Record<ReconStatus, number>>;
export type PriorityCounts = Partial<Record<Priority, number>>;

/** A reconciliation result row (exception or match), as returned by the backend. */
export interface ReconRow {
  bank_txn_id?: string | null;
  ledger_id?: string | null;
  predicted_status?: string | null;
  match_confidence?: number | null;
  match_method?: string | null;
  reason?: string | null;
  amount_difference?: number | null;
  timestamp_difference?: number | null;
  merchant_similarity?: number | null;
  reference_similarity?: number | null;

  /* supporting intelligence */
  category?: string | null;
  categorization_confidence?: number | null;
  categorization_source?: string | null;
  anomaly_flag?: boolean | string | null;
  anomaly_score?: number | null;
  anomaly_status?: string | null;
  anomaly_reason?: string | null;
  priority?: string | null;
  priority_reasons?: string[] | string | null;

  /* record detail (names vary slightly by backend build; all optional) */
  bank_merchant?: string | null;
  bank_reference?: string | null;
  bank_amount?: number | null;
  bank_direction?: string | null;
  bank_timestamp?: string | null;
  ledger_merchant?: string | null;
  ledger_reference?: string | null;
  ledger_amount?: number | null;
  ledger_direction?: string | null;
  ledger_timestamp?: string | null;

  merchant?: string | null;
  reference?: string | null;
  amount?: number | null;
  direction?: string | null;
  timestamp?: string | null;

  [key: string]: unknown;
}

export interface RunResponse {
  run_id: string;
  summary: ReconSummary;
  status_counts: StatusCounts;
  priority_counts: PriorityCounts;
  results?: ReconRow[] | undefined;
}

export interface ExceptionsPage {
  items: ReconRow[];
  total: number;
  limit: number;
  offset: number;
}

export interface HealthResponse {
  status?: string;
  [key: string]: unknown;
}

export interface BenchmarkClassMetrics {
  label: string;
  precision?: number | undefined;
  recall?: number | undefined;
  f1?: number | undefined;
  support?: number | undefined;
}

/** Offline evaluation artifact metrics — never produced by a live run. */
export interface BenchmarkReport {
  evaluated_cases?: number | undefined;
  correct_cases?: number | undefined;
  incorrect_cases?: number | undefined;
  accuracy?: number | undefined;
  macro_f1?: number | undefined;
  weighted_f1?: number | undefined;
  match_resolution?: number | undefined;
  benchmark_throughput_records_per_second?: number | undefined;
  per_class: BenchmarkClassMetrics[];
}

/** Which workflow produced the current run. */
export type RunSource = "demo" | "upload";
