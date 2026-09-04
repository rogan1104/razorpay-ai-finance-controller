"""Unit tests for transaction categorization ML pipeline."""

from pathlib import Path
import pytest
import pandas as pd

from src.categorization.preprocess import clean_text, load_data
from src.categorization.train import build_pipeline, train_and_save_pipeline
from src.categorization.predict import TransactionClassifier, predict_transaction
from src.categorization.grouped_evaluate import predict_with_rules
from src.categorization.challenge_evaluate import generate_challenge_dataset


def test_clean_text_standard():
    """Verify lowercase conversion, punctuation normalization, and whitespace stripping."""
    raw = "  SWIGGY*BLR0091   BANGALORE-560038  "
    expected = "swiggy blr0091 bangalore 560038"
    assert clean_text(raw) == expected


def test_clean_text_special_delimiters():
    """Verify delimiter replacement keeps meaningful tokens separated."""
    raw = "UBER_INDIA/MUMBAI#TRIP@123"
    cleaned = clean_text(raw)
    assert "uber" in cleaned
    assert "india" in cleaned
    assert "mumbai" in cleaned
    assert "trip" in cleaned
    assert "123" in cleaned


def test_clean_text_missing_and_empty():
    """Verify graceful handling of None, NaN, and whitespace."""
    assert clean_text(None) == ""
    assert clean_text(float("nan")) == ""
    assert clean_text("   ") == ""
    assert clean_text("") == ""


def test_load_data_valid(tmp_path: Path):
    """Verify loading and validating a proper CSV."""
    csv_file = tmp_path / "valid.csv"
    csv_file.write_text(
        "transaction_description,category\n"
        "SWIGGY ORDER,Food & Dining\n"
        "UBER TRIP,Travel\n"
        ",Utilities\n"  # empty description should be kept as empty string
        "ZOMATO,\n"  # missing category should be dropped
    )
    df = load_data(csv_file)
    assert len(df) == 3
    assert list(df.columns) == ["transaction_description", "category"]
    assert df.iloc[0]["transaction_description"] == "SWIGGY ORDER"
    assert df.iloc[0]["category"] == "Food & Dining"


def test_load_data_missing_columns(tmp_path: Path):
    """Verify ValueError is raised when required columns are absent."""
    csv_file = tmp_path / "invalid.csv"
    csv_file.write_text("desc,label\nSWIGGY,Food\n")
    with pytest.raises(ValueError, match="missing required column"):
        load_data(csv_file)


def test_load_data_missing_file():
    """Verify FileNotFoundError when file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_data("non_existent_file.csv")


def test_train_and_save_pipeline_lifecycle(tmp_path: Path):
    """Verify end-to-end training, saving, loading, and evaluation lifecycle."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "transaction_description,category\n"
        "SWIGGY FOOD,Food\n"
        "ZOMATO DINNER,Food\n"
        "DOMINOS PIZZA,Food\n"
        "UBER RIDE,Travel\n"
        "OLA CABS,Travel\n"
        "RAPIDO BIKE,Travel\n"
        "BESCOM POWER,Utilities\n"
        "TATAPOWER ELECTRIC,Utilities\n"
        "AIRTEL BILL,Utilities\n"
    )
    model_path = tmp_path / "model.joblib"

    pipeline, metrics = train_and_save_pipeline(
        data_path=csv_file,
        model_save_path=model_path,
        test_size=0.33,
        random_state=42,
        stratify=True,
    )

    assert model_path.exists()
    assert "accuracy" in metrics
    assert "macro_f1" in metrics
    assert isinstance(metrics["macro_f1"], float)

    # Raw input is accepted by the saved sklearn Pipeline: it owns the same
    # clean_text preprocessing used while fitting TF-IDF.
    assert pipeline.named_steps["tfidf"].preprocessor is clean_text
    assert pipeline.predict(["SWIGGY*BLR0091"])[0] == "Food"

    # Test loading saved model
    classifier = TransactionClassifier(model_path=model_path)
    res = classifier.predict("SWIGGY BLR RESTAURANT")
    assert isinstance(res, dict)
    assert "predicted_category" in res
    assert "confidence" in res
    assert 0.0 <= res["confidence"] <= 1.0


def test_prediction_output_format(tmp_path: Path):
    """Verify the exact dictionary structure and data types of prediction outputs."""
    csv_file = tmp_path / "dummy.csv"
    csv_file.write_text(
        "transaction_description,category\n"
        "SWIGGY 1,Food\n"
        "SWIGGY 2,Food\n"
        "UBER 1,Travel\n"
        "UBER 2,Travel\n"
    )
    model_path = tmp_path / "dummy_model.joblib"
    train_and_save_pipeline(csv_file, model_path, test_size=0.5, random_state=42, stratify=True)

    classifier = TransactionClassifier(model_path=model_path)
    pred = classifier.predict("SWIGGY ORDER")

    assert "transaction" in pred
    assert "predicted_category" in pred
    assert "confidence" in pred
    assert isinstance(pred["transaction"], str)
    assert isinstance(pred["predicted_category"], str)
    assert isinstance(pred["confidence"], float)
    assert 0.0 <= pred["confidence"] <= 1.0


def test_prediction_empty_and_none_input(tmp_path: Path):
    """Verify prediction behavior on empty string, None, and whitespace."""
    csv_file = tmp_path / "dummy.csv"
    csv_file.write_text(
        "transaction_description,category\n"
        "A1,ClassA\n"
        "A2,ClassA\n"
        "B1,ClassB\n"
        "B2,ClassB\n"
    )
    model_path = tmp_path / "dummy_model.joblib"
    train_and_save_pipeline(csv_file, model_path, test_size=0.5, random_state=42, stratify=True)

    classifier = TransactionClassifier(model_path=model_path)

    for empty_input in ["", None, "     ", "\n\t"]:
        res = classifier.predict(empty_input)
        assert res["predicted_category"] == "Unknown"
        assert res["confidence"] == 0.0


def test_model_not_found():
    """Verify FileNotFoundError when loading non-existent model file."""
    with pytest.raises(FileNotFoundError, match="Model file not found"):
        TransactionClassifier(model_path="non_existent_model.joblib")


def test_keyword_baseline_uses_text_only_rules():
    """Verify representative static text rules and the explicit unknown fallback."""
    assert predict_with_rules(["SWIGGY*BLR0091", "UBER INDIA", "unrecognized text"]) == [
        "Food",
        "Transport",
        "Unknown",
    ]


def test_challenge_dataset_is_balanced_and_seeded(tmp_path: Path):
    """Challenge generation is deterministic, balanced, and leaves raw input separate."""
    raw = tmp_path / "raw.csv"
    raw.write_text(
        "merchant,category\n"
        "Swiggy,Food\n"
        "Uber,Transport\n"
        "Netflix,Entertainment\n"
        "Airtel,Utilities\n"
        "Udemy,Education\n"
        "Apollo,Healthcare\n"
        "Landlord,Rent\n"
        "Employer,Salary\n"
        "Amazon,Shopping\n"
    )
    first = generate_challenge_dataset(raw, seed=7, samples_per_category=2)
    second = generate_challenge_dataset(raw, seed=7, samples_per_category=2)
    assert first.equals(second)
    assert set(first["challenge_group"]) == {
        "known_merchant_noisy_description", "unseen_merchant", "ambiguous_description"
    }
    assert first.groupby(["challenge_group", "category"]).size().eq(2).all()
    assert not first["transaction_description"].str.contains("Swiggy", case=False).all()
