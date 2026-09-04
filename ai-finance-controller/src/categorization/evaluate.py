"""Model evaluation module for transaction categorization."""

from typing import Any, Dict, Iterable, Optional
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def evaluate_predictions(
    y_test: pd.Series,
    y_pred: Iterable[str],
    labels: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Compute serializable classification metrics from predictions."""
    y_pred = list(y_pred)
    classes = list(labels) if labels is not None else sorted(set(y_test) | set(y_pred))

    acc = accuracy_score(y_test, y_pred)
    macro_precision = precision_score(y_test, y_pred, average="macro", labels=classes, zero_division=0)
    macro_recall = recall_score(y_test, y_pred, average="macro", labels=classes, zero_division=0)
    macro_f1 = f1_score(y_test, y_pred, average="macro", labels=classes, zero_division=0)
    weighted_f1 = f1_score(y_test, y_pred, average="weighted", labels=classes, zero_division=0)

    report_str = classification_report(y_test, y_pred, labels=classes, zero_division=0)
    report_dict = classification_report(y_test, y_pred, labels=classes, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, y_pred, labels=classes)
    cm_df = pd.DataFrame(cm, index=classes, columns=classes)

    metrics = {
        "accuracy": float(acc),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "weighted_f1": float(weighted_f1),
        "classification_report_str": report_str,
        "classification_report_dict": report_dict,
        "confusion_matrix": cm.tolist(),
        "classes": classes,
        "total_test_samples": len(y_test),
    }

    # Print clean summary
    print("\n" + "=" * 60)
    print("           MODEL EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Total Test Samples: {len(y_test)}")
    print(f"Accuracy:           {acc:.4f}")
    print(f"Macro Precision:    {macro_precision:.4f}")
    print(f"Macro Recall:       {macro_recall:.4f}")
    print(f"Macro-F1 Score:     {macro_f1:.4f}  (Primary metric for class balance)")
    print(f"Weighted F1:        {weighted_f1:.4f}")
    print("\n--- Detailed Classification Report ---")
    print(report_str)
    print("--- Confusion Matrix ---")
    print(cm_df.to_string())
    print("=" * 60 + "\n")

    return metrics


def evaluate_model(pipeline: Any, X_test: pd.Series, y_test: pd.Series) -> Dict[str, Any]:
    """Evaluate a trained categorization pipeline on test data."""
    return evaluate_predictions(y_test, pipeline.predict(X_test), labels=pipeline.classes_)
