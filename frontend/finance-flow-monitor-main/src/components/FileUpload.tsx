import { useId, useRef, useState } from "react";
import { Button } from "@/components/ui-kit";
import { fmtFileSize } from "@/lib/format";
import { cn } from "@/lib/utils";

export function FileUpload({
  title,
  expectedName,
  file,
  onSelect,
  onClear,
  disabled,
  accent = "sky",
}: {
  title: string;
  expectedName: string;
  file: File | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
  accent?: "sky" | "mint";
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  function accept(candidate: File | undefined) {
    if (!candidate) return;
    if (!/\.csv$/i.test(candidate.name)) {
      setLocalError("Only .csv files are accepted.");
      return;
    }
    if (candidate.size === 0) {
      setLocalError("That file is empty. Select a CSV with data rows.");
      return;
    }
    setLocalError(null);
    onSelect(candidate);
  }

  return (
    <div className="card-surface flex flex-col p-5">
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={cn(
            "h-2.5 w-2.5 rounded-sm",
            accent === "sky" ? "bg-sky" : "bg-mint",
          )}
        />
        <h3 className="text-xs font-semibold uppercase tracking-wider text-foreground">{title}</h3>
      </div>

      {file ? (
        <div className="mt-4 rounded-lg border border-border bg-surface p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
              <p className="num mt-1 text-xs text-muted-foreground">
                {fmtFileSize(file.size)} · ready to submit
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                if (inputRef.current) inputRef.current.value = "";
                onClear();
              }}
              disabled={disabled}
              aria-label={`Remove ${file.name}`}
            >
              Remove
            </Button>
          </div>
        </div>
      ) : (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (!disabled) accept(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "mt-4 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
            dragging ? "border-primary bg-primary-soft" : "border-border-strong bg-surface",
          )}
        >
          <p className="text-sm text-muted-foreground">
            Drop <span className="num text-foreground">{expectedName}</span> here
          </p>
          <label htmlFor={inputId} className="sr-only">
            {title} CSV file
          </label>
          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            disabled={disabled}
            onChange={(e) => accept(e.target.files?.[0] ?? undefined)}
          />
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            disabled={disabled}
            onClick={() => inputRef.current?.click()}
          >
            Choose file
          </Button>
        </div>
      )}

      {localError ? (
        <p role="alert" className="mt-3 text-xs font-medium text-destructive">
          {localError}
        </p>
      ) : (
        <p className="mt-3 text-xs text-muted-foreground">
          Expected file: <span className="num">{expectedName}</span>
        </p>
      )}
    </div>
  );
}
