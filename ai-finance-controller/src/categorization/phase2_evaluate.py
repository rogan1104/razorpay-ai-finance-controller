"""Threshold analysis and challenge evaluation for the hybrid classifier."""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

from src.categorization.evaluate import evaluate_predictions
from src.categorization.hybrid import HybridTransactionClassifier


CANDIDATE_THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.90)


def analyze_thresholds(challenge: pd.DataFrame, classifier: HybridTransactionClassifier) -> List[Dict[str, Any]]:
    """Compute routing and ML-only quality for candidates without calling Gemini."""
    probabilities = classifier.pipeline.predict_proba(challenge["transaction_description"])
    best_indices = probabilities.argmax(axis=1)
    challenge = challenge.copy()
    challenge["ml_prediction"] = [str(classifier.pipeline.classes_[index]) for index in best_indices]
    challenge["ml_confidence"] = probabilities.max(axis=1)
    labels = classifier.allowed_categories
    analyses = []
    for threshold in CANDIDATE_THRESHOLDS:
        fallback = challenge["ml_confidence"] < threshold
        per_group = {
            group: {
                "rows": int(len(subset)),
                "ml_coverage_pct": float((~fallback.loc[subset.index]).mean() * 100),
                "gemini_fallback_rate_pct": float(fallback.loc[subset.index].mean() * 100),
            }
            for group, subset in challenge.groupby("challenge_group")
        }
        covered = challenge.loc[~fallback]
        analyses.append(
            {
                "threshold": threshold,
                "ml_coverage_pct": float((~fallback).mean() * 100),
                "gemini_fallback_rate_pct": float(fallback.mean() * 100),
                "gemini_calls": int(fallback.sum()),
                "low_confidence_cases": int(fallback.sum()),
                "ml_only_metrics_on_covered_rows": (
                    evaluate_predictions(covered["category"], covered["ml_prediction"], labels=labels)
                    if not covered.empty
                    else None
                ),
                "per_group": per_group,
            }
        )
    return analyses


def select_threshold(analyses: Iterable[Dict[str, Any]]) -> float:
    """Choose the lowest threshold that routes all unseen and ambiguous cases."""
    for analysis in analyses:
        per_group = analysis["per_group"]
        if (
            per_group["unseen_merchant"]["gemini_fallback_rate_pct"] == 100.0
            and per_group["ambiguous_description"]["gemini_fallback_rate_pct"] == 100.0
        ):
            return float(analysis["threshold"])
    return float(list(analyses)[-1]["threshold"])


def run_hybrid_evaluation(
    challenge_path: str | Path = "data/evaluation/phase1_challenge_dataset.csv",
    model_path: str | Path = "models/categorization_pipeline.joblib",
    metrics_output_path: str | Path = "evaluation/phase2_hybrid_metrics.json",
    predictions_output_path: str | Path = "evaluation/phase2_predictions.csv",
) -> Dict[str, Any]:
    """Evaluate a fixed model and call Gemini only for selected low-confidence rows."""
    challenge = pd.read_csv(challenge_path)
    classifier = HybridTransactionClassifier(model_path=model_path)
    analyses = analyze_thresholds(challenge, classifier)
    threshold = select_threshold(analyses)
    predictions = [classifier.predict(description, threshold) for description in challenge["transaction_description"]]
    # Keep the frozen challenge label in ``category`` and give the hybrid
    # result an unambiguous name. Using two ``category`` columns turns pandas
    # selection into a two-column DataFrame rather than 324 predictions.
    prediction_frame = pd.DataFrame(predictions).rename(
        columns={"category": "final_prediction", "confidence": "final_confidence"}
    )
    results_frame = pd.concat([challenge.reset_index(drop=True), prediction_frame], axis=1)
    labels = classifier.allowed_categories

    ml_metrics = evaluate_predictions(challenge["category"], results_frame["ml_category"], labels=labels)
    hybrid_metrics = evaluate_predictions(challenge["category"], results_frame["final_prediction"], labels=labels)
    per_group = {}
    for group, subset in results_frame.groupby("challenge_group"):
        per_group[group] = {
            "rows": int(len(subset)),
            "ml_only_metrics": evaluate_predictions(subset["category"], subset["ml_category"], labels=labels),
            "hybrid_metrics": evaluate_predictions(subset["category"], subset["final_prediction"], labels=labels),
            "ml_coverage_pct": float((~subset["fallback_used"]).mean() * 100),
            "gemini_fallback_rate_pct": float(subset["fallback_used"].mean() * 100),
            "gemini_calls": int(subset["gemini_attempted"].sum()),
            "gemini_request_attempts": int(subset["gemini_request_attempts"].sum()),
            "gemini_failures": int(subset["fallback_error"].notna().sum()),
        }

    results = {
        "status": "complete",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "challenge_dataset": str(challenge_path),
        "model_path": str(model_path),
        "selected_threshold": threshold,
        "threshold_analysis": analyses,
        "ml_only_metrics": ml_metrics,
        "hybrid_metrics": hybrid_metrics,
        "ml_coverage_pct": float((~results_frame["fallback_used"]).mean() * 100),
        "gemini_fallback_rate_pct": float(results_frame["fallback_used"].mean() * 100),
        "gemini_api_calls": int(results_frame["gemini_attempted"].sum()),
        "gemini_request_attempts": int(results_frame["gemini_request_attempts"].sum()),
        "gemini_failures": int(results_frame["fallback_error"].notna().sum()),
        "per_group": per_group,
    }
    Path(predictions_output_path).parent.mkdir(parents=True, exist_ok=True)
    results_frame.to_csv(predictions_output_path, index=False)
    Path(metrics_output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(metrics_output_path).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the Phase 2 hybrid categorizer")
    parser.add_argument("--challenge", default="data/evaluation/phase1_challenge_dataset.csv")
    parser.add_argument("--model", default="models/categorization_pipeline.joblib")
    parser.add_argument("--metrics-output", default="evaluation/phase2_hybrid_metrics.json")
    parser.add_argument("--predictions-output", default="evaluation/phase2_predictions.csv")
    args = parser.parse_args()
    results = run_hybrid_evaluation(args.challenge, args.model, args.metrics_output, args.predictions_output)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
