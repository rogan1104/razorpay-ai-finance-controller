import { Field, controlClass } from "@/components/ui-kit";
import { ALL_STATUSES } from "@/lib/status";
import { PRIORITIES } from "@/types/reconciliation";
import { cn } from "@/lib/utils";

export interface FilterValues {
  status: string;
  priority: string;
  search: string;
}

export function Filters({
  value,
  onChange,
  searchPlaceholder = "Search bank txn ID, ledger ID, merchant or reference",
  extra,
}: {
  value: FilterValues;
  onChange: (next: FilterValues) => void;
  searchPlaceholder?: string;
  extra?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Field label="Status" htmlFor="filter-status">
        <select
          id="filter-status"
          className={cn(controlClass, "min-w-[11rem]")}
          value={value.status}
          onChange={(e) => onChange({ ...value, status: e.target.value })}
        >
          <option value="ALL">All statuses</option>
          {ALL_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Priority" htmlFor="filter-priority">
        <select
          id="filter-priority"
          className={cn(controlClass, "min-w-[8rem]")}
          value={value.priority}
          onChange={(e) => onChange({ ...value, priority: e.target.value })}
        >
          <option value="ALL">All priorities</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </Field>

      <Field label="Search" htmlFor="filter-search" className="min-w-[18rem] flex-1">
        <input
          id="filter-search"
          type="search"
          className={cn(controlClass, "w-full")}
          placeholder={searchPlaceholder}
          value={value.search}
          onChange={(e) => onChange({ ...value, search: e.target.value })}
        />
      </Field>

      {extra}
    </div>
  );
}
