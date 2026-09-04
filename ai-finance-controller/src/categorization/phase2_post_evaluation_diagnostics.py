"""Post-evaluation analysis that never alters Phase 2 benchmark artifacts."""

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from src.categorization.evaluate import evaluate_predictions


def _metrics(frame: pd.DataFrame, prediction_column: str, labels: list[str]) -> Dict[str, Any]:
    """Return metrics only for rows known to have a valid prediction."""
    return evaluate_predictions(frame["category"], frame[prediction_column], labels=labels)


def _provider_message_summary(message: Any) -> Any:
    """Normalize varying retry times while retaining the provider's cause."""
    if not isinstance(message, str):
        return message
    if "RESOURCE_EXHAUSTED" in message and "Quota exceeded" in message:
        return "429 RESOURCE_EXHAUSTED: free-tier generate_content requests-per-minute quota exceeded."
    return re.sub(r"Please retry in [^.'\\]+[s.]?", "", message)[:500]


def analyze_phase2_results(
    predictions_path: str | Path = "evaluation/phase2_predictions.csv",
    metrics_path: str | Path = "evaluation/phase2_hybrid_metrics.json",
    output_path: str | Path = "evaluation/phase2_post_evaluation_diagnostics.json",
) -> Dict[str, Any]:
    """Separate valid Gemini performance from quota-failed fallback attempts."""
    predictions = pd.read_csv(predictions_path)
    source_metrics = json.loads(Path(metrics_path).read_text(encoding="utf-8"))
    required = {
        "challenge_group", "category", "final_prediction", "source", "fallback_used",
        "gemini_attempted", "gemini_category", "fallback_error",
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Predictions artifact is missing required columns: {sorted(missing)}")

    labels = list(source_metrics["ml_only_metrics"]["classes"])
    fallback_attempts = predictions.loc[predictions["gemini_attempted"].fillna(False)].copy()
    failures = fallback_attempts.loc[fallback_attempts["fallback_error"].notna()].copy()
    successes = fallback_attempts.loc[
        fallback_attempts["source"].eq("gemini") & fallback_attempts["fallback_error"].isna()
    ].copy()
    valid_hybrid_rows = predictions.loc[~(predictions["fallback_used"].fillna(False) & predictions["fallback_error"].notna())].copy()

    # Failed fallbacks are intentionally not treated as ML or Gemini outcomes:
    # their denominator remains in the overall benchmark and their numerator is
    # zero, making the failure-inclusive score explicit.
    valid_correct = int((valid_hybrid_rows["category"] == valid_hybrid_rows["final_prediction"]).sum())
    failure_inclusive_accuracy = valid_correct / len(predictions)

    group_results: Dict[str, Any] = {}
    for group, group_rows in predictions.groupby("challenge_group"):
        group_successes = successes.loc[successes["challenge_group"].eq(group)]
        group_failures = failures.loc[failures["challenge_group"].eq(group)]
        group_valid = valid_hybrid_rows.loc[valid_hybrid_rows["challenge_group"].eq(group)]
        group_valid_correct = int((group_valid["category"] == group_valid["final_prediction"]).sum())
        group_results[group] = {
            "rows": int(len(group_rows)),
            "gemini_successful_responses": int(len(group_successes)),
            "gemini_failures": int(len(group_failures)),
            "gemini_accuracy_on_successes": (
                float((group_successes["category"] == group_successes["gemini_category"]).mean())
                if not group_successes.empty else None
            ),
            "hybrid_accuracy_excluding_gemini_failures": (
                float((group_valid["category"] == group_valid["final_prediction"]).mean())
                if not group_valid.empty else None
            ),
            "hybrid_accuracy_failure_inclusive": group_valid_correct / len(group_rows),
        }

    diagnostic_columns = [
        column for column in (
            "fallback_error", "gemini_exception_type", "gemini_http_status_code", "gemini_provider_message"
        ) if column in failures.columns
    ]
    summarized_failures = failures.copy()
    if "gemini_provider_message" in summarized_failures:
        summarized_failures["gemini_provider_message"] = summarized_failures["gemini_provider_message"].apply(
            _provider_message_summary
        )
    failure_breakdown = (
        summarized_failures.groupby(diagnostic_columns, dropna=False).size().reset_index(name="count").to_dict("records")
        if not summarized_failures.empty else []
    )

    report = {
        "source_artifacts": {"predictions": str(predictions_path), "metrics": str(metrics_path)},
        "benchmark_rows": int(len(predictions)),
        "selected_threshold": source_metrics["selected_threshold"],
        "gemini_fallback_calls": int(len(fallback_attempts)),
        "gemini_successful_responses": int(len(successes)),
        "gemini_failed_responses": int(len(failures)),
        "gemini_metrics_on_successful_responses_only": _metrics(successes, "gemini_category", labels),
        "gemini_accuracy_by_group_on_successful_responses_only": group_results,
        "gemini_failure_count_by_group": {
            group: values["gemini_failures"] for group, values in group_results.items()
        },
        "hybrid_metrics_excluding_gemini_failed_rows": _metrics(valid_hybrid_rows, "final_prediction", labels),
        "hybrid_accuracy_failure_inclusive": {
            "accuracy": failure_inclusive_accuracy,
            "valid_correct_predictions": valid_correct,
            "failed_fallbacks_counted_as_incorrect": int(len(failures)),
            "denominator": int(len(predictions)),
        },
        "per_group": group_results,
        "failure_diagnostics": failure_breakdown,
    }
    Path(output_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze completed Phase 2 artifacts without rerunning Gemini")
    parser.add_argument("--predictions", default="evaluation/phase2_predictions.csv")
    parser.add_argument("--metrics", default="evaluation/phase2_hybrid_metrics.json")
    parser.add_argument("--output", default="evaluation/phase2_post_evaluation_diagnostics.json")
    args = parser.parse_args()
    print(json.dumps(analyze_phase2_results(args.predictions, args.metrics, args.output), indent=2))


if __name__ == "__main__":
    main()
