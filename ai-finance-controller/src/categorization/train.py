"""Training pipeline for transaction categorization model."""

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from src.categorization.evaluate import evaluate_model
from src.categorization.preprocess import clean_text, load_data


def build_pipeline() -> Pipeline:
    """Construct an end-to-end TF-IDF + Logistic Regression pipeline.

    Using an sklearn Pipeline guarantees that:
    1. There is no data leakage (vectorizer vocabulary and IDF weights are fit
       only on training folds/sets).
    2. Inference can be performed by feeding raw/preprocessed text directly.

    Returns:
        Configured Pipeline instance.
    """
    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),  # unigrams and bigrams
                    min_df=1,            # robust for small datasets, configurable
                    sublinear_tf=True,   # applies 1 + log(tf) scaling to dampen frequent terms
                    token_pattern=r"(?u)\b\w+\b",
                    preprocessor=clean_text,
                    lowercase=False,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    C=1.0,
                    max_iter=1000,
                    class_weight="balanced",  # handle category imbalance
                    random_state=42,
                    solver="lbfgs",
                ),
            ),
        ]
    )


def train_and_save_pipeline(
    data_path: str | Path,
    model_save_path: str | Path = "models/categorization_pipeline.joblib",
    test_size: float = 0.25,
    random_state: int = 42,
    stratify: bool = True,
    evaluation_save_path: str | Path = "evaluation/phase1_metrics.json",
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Load data, split, train pipeline, evaluate, and save serialized artifact.

    Args:
        data_path: Path to raw transaction CSV.
        model_save_path: Destination path for serialized joblib model.
        test_size: Fraction of samples reserved for testing.
        random_state: Seed for reproducible data split.
        stratify: Whether to preserve class distributions in train/test splits.

    Returns:
        Tuple of (trained Pipeline, evaluation metrics dictionary).
    """
    print(f"Loading data from: {data_path}")
    df = load_data(data_path)
    # Phase 1 deliberately uses only transaction_description as the model input.
    X = df["transaction_description"]
    y = df["category"]

    print(f"Loaded {len(df)} transactions across {y.nunique()} categories.")
    print("Class distribution:\n", y.value_counts().to_string())

    # Check if stratification is feasible given class counts
    min_class_count = y.value_counts().min()
    stratify_labels = y if (stratify and min_class_count >= 2) else None
    if stratify and min_class_count < 2:
        print("[Warning] Some classes have only 1 sample; proceeding without stratification.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify_labels,
    )

    print(f"\nDataset split: {len(X_train)} training samples, {len(X_test)} test samples.")

    # Keep duplicates in place, but quantify their impact on a random split.
    all_descriptions = X.fillna("").astype(str)
    train_descriptions = set(X_train.fillna("").astype(str))
    test_descriptions = set(X_test.fillna("").astype(str))
    overlap = train_descriptions & test_descriptions
    test_seen_in_train = X_test.fillna("").astype(str).isin(train_descriptions)
    duplicate_mask = all_descriptions.duplicated(keep=False)
    duplicate_analysis = {
        "duplicate_description_rows": int(duplicate_mask.sum()),
        "additional_duplicate_description_rows": int(all_descriptions.duplicated().sum()),
        "unique_descriptions": int(all_descriptions.nunique()),
        "train_unique_descriptions": len(train_descriptions),
        "test_unique_descriptions": len(test_descriptions),
        "train_test_description_overlap": len(overlap),
        "test_rows_with_description_seen_in_training": int(test_seen_in_train.sum()),
        "test_rows_with_description_seen_in_training_pct": float(test_seen_in_train.mean() * 100),
    }
    print("Description overlap analysis:", json.dumps(duplicate_analysis, indent=2))

    pipeline = build_pipeline()
    print("Fitting TF-IDF Vectorizer and Logistic Regression classifier on training set...")
    pipeline.fit(X_train, y_train)

    print("\nEvaluating model performance on unseen test split...")
    metrics = evaluate_model(pipeline, X_test, y_test)
    metrics["split"] = {
        "test_size": test_size,
        "random_state": random_state,
        "stratified": stratify_labels is not None,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }
    metrics["duplicate_leakage_analysis"] = duplicate_analysis

    evaluation_path = Path(evaluation_save_path)
    evaluation_path.parent.mkdir(parents=True, exist_ok=True)
    with evaluation_path.open("w", encoding="utf-8") as metrics_file:
        json.dump(metrics, metrics_file, indent=2)
    print(f"Evaluation metrics saved to: {evaluation_path.resolve()}")

    # Save model artifact
    save_path = Path(model_save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, save_path)
    print(f"Model successfully saved to: {save_path.resolve()}")

    return pipeline, metrics


def main() -> None:
    """CLI entrypoint for training."""
    parser = argparse.ArgumentParser(description="Train Transaction Categorization Model")
    parser.add_argument(
        "--data",
        type=str,
        default="data/raw/transactions_v2.csv",
        help="Path to training CSV file (default: data/raw/transactions_v2.csv)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="models/categorization_pipeline.joblib",
        help="Path to save trained model artifact (default: models/categorization_pipeline.joblib)",
    )
    parser.add_argument(
        "--evaluation-output",
        type=str,
        default="evaluation/phase1_metrics.json",
        help="Path to save machine-readable evaluation metrics JSON.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.25,
        help="Proportion of the dataset to include in the test split (default: 0.25)",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random state seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    train_and_save_pipeline(
        data_path=args.data,
        model_save_path=args.model,
        test_size=args.test_size,
        random_state=args.random_state,
        evaluation_save_path=args.evaluation_output,
    )


if __name__ == "__main__":
    main()
