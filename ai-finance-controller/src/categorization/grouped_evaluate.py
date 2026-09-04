"""Description-grouped Phase 1 evaluation and transparent rule baseline."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from src.categorization.evaluate import evaluate_predictions
from src.categorization.preprocess import clean_text, load_data
from src.categorization.train import build_pipeline


# Static domain rules: descriptions are the only input. The labels are outputs,
# never features or values learned from the evaluation dataset.
KEYWORD_RULES = {
    "Transport": ("uber", "olacabs", "ola", "rapido", "indianoil", "delhimetro"),
    "Entertainment": ("netflix", "spotify", "bookmyshow"),
    "Utilities": ("airtel", "municipalwater", "jiofiber", "bescom"),
    "Food": ("swiggy", "zomato", "dominos", "starbucks", "localtiffins"),
    "Rent": ("landlord", "rent payment", " rent "),
    "Salary": ("employercorp", "salary", "payroll"),
    "Education": ("udemy", "coursera"),
    "Healthcare": ("practo", "apollo"),
    "Shopping": ("amazon", "flipkart", "myntra", "reliancetrends", "localkirana"),
}


def predict_with_rules(descriptions: Iterable[str]) -> List[str]:
    """Assign the first matching static rule or an explicit Unknown label."""
    predictions = []
    for description in descriptions:
        text = f" {clean_text(description)} "
        prediction = "Unknown"
        for category, keywords in KEYWORD_RULES.items():
            if any(keyword in text for keyword in keywords):
                prediction = category
                break
        predictions.append(prediction)
    return predictions


def analyze_errors(
    descriptions: Iterable[str], y_true: Iterable[str], y_pred: Iterable[str], limit: int = 10
) -> List[Dict[str, Any]]:
    """Return the largest off-diagonal error groups and representative examples."""
    errors: Dict[tuple[str, str], List[str]] = {}
    for description, actual, predicted in zip(descriptions, y_true, y_pred):
        if actual != predicted:
            errors.setdefault((str(actual), str(predicted)), []).append(str(description))
    return [
        {
            "actual": actual,
            "predicted": predicted,
            "count": len(examples),
            "examples": examples[:3],
        }
        for (actual, predicted), examples in sorted(
            errors.items(), key=lambda item: (-len(item[1]), item[0])
        )[:limit]
    ]


def run_grouped_evaluation(
    data_path: str | Path = "data/raw/transactions_v2.csv",
    output_path: str | Path = "evaluation/phase1_grouped_metrics.json",
    test_size: float = 0.25,
    random_state: int = 42,
) -> Dict[str, Any]:
    """Evaluate rules and TF-IDF + Logistic Regression on unseen descriptions."""
    df = load_data(data_path)
    descriptions = df["transaction_description"].fillna("").astype(str)
    labels = df["category"]

    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_indices, test_indices = next(splitter.split(descriptions, labels, groups=descriptions))
    X_train, X_test = descriptions.iloc[train_indices], descriptions.iloc[test_indices]
    y_train, y_test = labels.iloc[train_indices], labels.iloc[test_indices]

    train_groups, test_groups = set(X_train), set(X_test)
    overlap = train_groups & test_groups
    if overlap:
        raise RuntimeError("Description-grouped split unexpectedly contains overlap.")

    pipeline = build_pipeline()
    pipeline.fit(X_train, y_train)
    model_predictions = pipeline.predict(X_test)
    rule_predictions = predict_with_rules(X_test)
    metric_labels = sorted(set(labels) | set(rule_predictions))

    results = {
        "split": {
            "method": "GroupShuffleSplit grouped by exact transaction_description",
            "test_size_requested": test_size,
            "random_state": random_state,
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "train_unique_descriptions": len(train_groups),
            "test_unique_descriptions": len(test_groups),
            "train_test_description_overlap": len(overlap),
        },
        "keyword_rules": {category: list(keywords) for category, keywords in KEYWORD_RULES.items()},
        "keyword_baseline": evaluate_predictions(y_test, rule_predictions, labels=metric_labels),
        "tfidf_logistic_regression": evaluate_predictions(y_test, model_predictions, labels=sorted(set(labels))),
        "errors": {
            "keyword_baseline": analyze_errors(X_test, y_test, rule_predictions),
            "tfidf_logistic_regression": analyze_errors(X_test, y_test, model_predictions),
        },
        "manual_predictions": [
            {
                "transaction": text,
                "predicted_category": str(prediction),
                "confidence": round(float(confidence), 4),
            }
            for text, prediction, confidence in zip(
                ["SWIGGY*BLR0091 BANGALORE", "UBER INDIA", "AMAZON PAY", "BESCOM ELECTRICITY BILL"],
                pipeline.predict(["SWIGGY*BLR0091 BANGALORE", "UBER INDIA", "AMAZON PAY", "BESCOM ELECTRICITY BILL"]),
                pipeline.predict_proba(["SWIGGY*BLR0091 BANGALORE", "UBER INDIA", "AMAZON PAY", "BESCOM ELECTRICITY BILL"]).max(axis=1),
            )
        ],
    }

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"Grouped evaluation saved to: {destination.resolve()}")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 1 description-grouped evaluation")
    parser.add_argument("--data", default="data/raw/transactions_v2.csv")
    parser.add_argument("--output", default="evaluation/phase1_grouped_metrics.json")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    run_grouped_evaluation(args.data, args.output, args.test_size, args.random_state)


if __name__ == "__main__":
    main()
