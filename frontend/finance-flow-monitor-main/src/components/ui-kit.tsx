import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({
  children,
  className,
  as: As = "section",
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
}) {
  return <As className={cn("card-surface p-5", className)}>{children}</As>;
}

export function SectionHeading({
  title,
  subtitle,
  action,
  level = 2,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  level?: 1 | 2 | 3;
}) {
  const H = `h${level}` as "h1" | "h2" | "h3";
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <H
          className={cn(
            "font-semibold text-foreground",
            level === 1 ? "text-2xl" : "text-base tracking-tight",
          )}
        >
          {title}
        </H>
        {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
      </div>
      {action}
    </div>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-55",
        size === "sm" && "px-3 py-1.5 text-xs",
        size === "md" && "px-4 py-2 text-sm",
        size === "lg" && "px-6 py-3 text-sm",
        variant === "primary" && "bg-primary text-primary-foreground hover:bg-primary/90",
        variant === "outline" &&
          "border border-border-strong bg-card text-foreground hover:bg-muted",
        variant === "ghost" && "text-muted-foreground hover:bg-muted hover:text-foreground",
        variant === "danger" && "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        className,
      )}
    />
  );
}

export function Chip({
  children,
  className,
  glyph,
}: {
  children: ReactNode;
  className?: string;
  glyph?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-semibold tracking-wide",
        className,
      )}
    >
      {glyph ? <span aria-hidden="true">{glyph}</span> : null}
      {children}
    </span>
  );
}

export function Field({
  label,
  htmlFor,
  children,
  className,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label
        htmlFor={htmlFor}
        className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

export const controlClass =
  "h-9 rounded-lg border border-border bg-card px-3 text-sm text-foreground outline-none transition-colors hover:border-border-strong";

export function EmptyState({
  title,
  description,
  glyph = "◇",
  action,
}: {
  title: string;
  description?: string | undefined;
  glyph?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border-strong bg-surface px-6 py-14 text-center">
      <span
        aria-hidden="true"
        className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-card text-lg text-muted-foreground shadow-sm"
      >
        {glyph}
      </span>
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {description ? (
        <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  title = "Something went wrong",
}: {
  message: string;
  onRetry?: (() => void) | undefined;
  title?: string;
}) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-destructive/25 bg-destructive-soft px-5 py-4"
    >
      <p className="text-sm font-semibold text-destructive">{title}</p>
      <p className="mt-1 text-sm text-foreground/80">{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} />;
}

export function DataRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border py-2 last:border-0">
      <dt className="text-xs uppercase tracking-wider text-muted-foreground">{label}</dt>
      <dd className="num text-sm text-foreground">{value}</dd>
    </div>
  );
}
