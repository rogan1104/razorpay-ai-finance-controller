"""Controlled robustness challenge for the fixed Phase 1 categorization model."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable

import joblib
import numpy as np
import pandas as pd

from src.categorization.evaluate import evaluate_predictions


CHALLENGE_GROUPS = (
    "known_merchant_noisy_description",
    "unseen_merchant",
    "ambiguous_description",
)
CITY_CODES = ("BLR", "MUM", "DEL", "HYD", "PUN", "KOL", "AHM", "CHN")
UNSEEN_MERCHANTS = {
    "Education": "VENDORAQUILA",
    "Entertainment": "VENDORBIRCH",
    "Food": "VENDORCYPRESS",
    "Healthcare": "VENDORDRIFT",
    "Rent": "VENDORELM",
    "Salary": "VENDORFABLE",
    "Shopping": "VENDORGROVE",
    "Transport": "VENDORHARBOR",
    "Utilities": "VENDORIVORY",
}
AMBIGUOUS_TEMPLATES = (
    "UPI PAYMENT {reference}",
    "POS PURCHASE {reference}",
    "ONLINE TXN {reference}",
    "PAYMENT REF {reference}",
)


def _merchant_token(merchant: str) -> str:
    """Convert a known merchant name into a bank-statement-style token."""
    return "".join(character for character in str(merchant).upper() if character.isalnum())


def generate_challenge_dataset(
    raw_data_path: str | Path,
    seed: int = 42,
    samples_per_category: int = 12,
) -> pd.DataFrame:
    """Create a balanced, evaluation-only challenge set without changing raw data."""
    if samples_per_category < 1:
        raise ValueError("samples_per_category must be at least 1")

    raw = pd.read_csv(raw_data_path)
    required_columns = {"category", "merchant"}
    missing = required_columns - set(raw.columns)
    if missing:
        raise ValueError(f"Raw data is missing required columns: {sorted(missing)}")

    categories = sorted(raw["category"].dropna().astype(str).unique())
    if set(categories) != set(UNSEEN_MERCHANTS):
        raise ValueError("Unseen-merchant mapping must cover exactly the raw dataset categories.")

    source_merchants = {value.lower() for value in raw["merchant"].dropna().astype(str)}
    if any(name.lower() in source_merchants for name in UNSEEN_MERCHANTS.values()):
        raise ValueError("An unseen challenge merchant occurs in the raw dataset.")

    rng = np.random.default_rng(seed)
    rows = []
    for category in categories:
        known_merchants = raw.loc[raw["category"].eq(category), "merchant"].dropna().astype(str).unique()
        for index in range(samples_per_category):
            reference = str(int(rng.integers(100000, 999999)))
            city = str(rng.choice(CITY_CODES))
            known = _merchant_token(str(rng.choice(known_merchants)))
            unseen = UNSEEN_MERCHANTS[category]

            known_templates = (
                f"UPI-{known}-{reference}",
                f" {known.lower()}  {city}  txn {reference} ",
                f"POS/{known}/{city}/{reference}",
                f"{known} INDIA PVT LTD PAYREF{reference}",
            )
            unseen_templates = (
                f"UPI-{unseen}-{reference}",
                f"{unseen.lower()}  {city}  txn {reference}",
                f"POS/{unseen}/{city}/{reference}",
                f"{unseen} PAYMENT REF {reference}",
            )
            ambiguous = str(rng.choice(AMBIGUOUS_TEMPLATES)).format(reference=reference)
            rows.extend(
                [
                    {
                        "challenge_group": "known_merchant_noisy_description",
                        "transaction_description": known_templates[index % len(known_templates)],
                        "category": category,
                    },
                    {
                        "challenge_group": "unseen_merchant",
                        "transaction_description": unseen_templates[index % len(unseen_templates)],
                        "category": category,
                    },
                    {
                        "challenge_group": "ambiguous_description",
                        "transaction_description": ambiguous,
                        "category": category,
                    },
                ]
            )
    return pd.DataFrame(rows)


def confidence_summary(confidences: Iterable[float]) -> Dict[str, Any]:
    """Summarize confidence and the requested low-confidence rates."""
    values = np.asarray(list(confidences), dtype=float)
    return {
        "min": float(values.min()),
        "p10": float(np.percentile(values, 10)),
        "median": float(np.median(values)),
        "mean": float(values.mean()),
        "p90": float(np.percentile(values, 90)),
        "max": float(values.max()),
        "below_confidence_threshold_pct": {
            str(threshold): float((values < threshold).mean() * 100)
            for threshold in (0.50, 0.60, 0.70, 0.80)
        },
    }


def run_challenge_evaluation(
    data_path: str | Path = "data/raw/transactions_v2.csv",
    model_path: str | Path = "models/categorization_pipeline.joblib",
    dataset_output_path: str | Path = "data/evaluation/phase1_challenge_dataset.csv",
    metrics_output_path: str | Path = "evaluation/phase1_challenge_metrics.json",
    seed: int = 42,
    samples_per_category: int = 12,
) -> Dict[str, Any]:
    """Generate the challenge set and evaluate an already-trained model only."""
    model_file = Path(model_path)
    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")

    challenge = generate_challenge_dataset(data_path, seed, samples_per_category)
    dataset_destination = Path(dataset_output_path)
    dataset_destination.parent.mkdir(parents=True, exist_ok=True)
    challenge.to_csv(dataset_destination, index=False)

    pipeline = joblib.load(model_file)
    labels = sorted(challenge["category"].unique())
    group_results: Dict[str, Any] = {}
    for group in CHALLENGE_GROUPS:
        subset = challenge.loc[challenge["challenge_group"].eq(group)]
        predictions = pipeline.predict(subset["transaction_description"])
        confidences = pipeline.predict_proba(subset["transaction_description"]).max(axis=1)
        group_results[group] = {
            "rows": len(subset),
            "category_distribution": subset["category"].value_counts().sort_index().to_dict(),
            "metrics": evaluate_predictions(subset["category"], predictions, labels=labels),
            "confidence_distribution": confidence_summary(confidences),
        }

    results = {
        "benchmark": {
            "seed": seed,
            "samples_per_category_per_group": samples_per_category,
            "total_rows": len(challenge),
            "training_used": False,
            "model_path": str(model_file),
            "groups": list(CHALLENGE_GROUPS),
        },
        "groups": group_results,
    }
    metrics_destination = Path(metrics_output_path)
    metrics_destination.parent.mkdir(parents=True, exist_ok=True)
    metrics_destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Challenge dataset saved to: {dataset_destination.resolve()}")
    print(f"Challenge metrics saved to: {metrics_destination.resolve()}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation-only Phase 1 challenge benchmark")
    parser.add_argument("--data", default="data/raw/transactions_v2.csv")
    parser.add_argument("--model", default="models/categorization_pipeline.joblib")
    parser.add_argument("--dataset-output", default="data/evaluation/phase1_challenge_dataset.csv")
    parser.add_argument("--metrics-output", default="evaluation/phase1_challenge_metrics.json")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--samples-per-category", type=int, default=12)
    args = parser.parse_args()
    run_challenge_evaluation(
        args.data,
        args.model,
        args.dataset_output,
        args.metrics_output,
        args.seed,
        args.samples_per_category,
    )


if __name__ == "__main__":
    main()
