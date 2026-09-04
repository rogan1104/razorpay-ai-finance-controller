"""Transaction text preprocessing and data loading utilities."""

import os
import re
from pathlib import Path
from typing import Any, Union

import pandas as pd


def clean_text(text: Any) -> str:
    """Preprocess transaction description text.

    Steps applied:
    - Handle null/non-string values safely.
    - Convert to lowercase.
    - Normalize punctuation/delimiters (e.g. *, -, /, _) to spaces to preserve
      merchant tokens.
    - Remove non-alphanumeric noise while retaining letters and numbers.
    - Collapse and strip extra whitespace.

    Args:
        text: Raw transaction description.

    Returns:
        Cleaned text string.
    """
    if text is None or pd.isna(text):
        return ""

    if not isinstance(text, str):
        text = str(text)

    # Convert to lowercase
    text = text.lower()

    # Replace delimiters that often connect merchant codes with spaces
    text = re.sub(r"[\*\/\\_\-\|@#:;,.]+", " ", text)

    # Remove non-alphanumeric characters (keep basic alphanumeric words & spaces)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse multiple whitespaces and strip leading/trailing spaces
    text = re.sub(r"\s+", " ", text).strip()

    return text


def load_data(
    filepath: Union[str, Path],
    description_col: str = "transaction_description",
    category_col: str = "category",
) -> pd.DataFrame:
    """Load and validate transaction dataset from CSV file.

    Expects a dataset with transaction descriptions and corresponding categories.
    No specific merchants or categories are hard-coded.

    Args:
        filepath: Path to the CSV file.
        description_col: Name of the transaction description column.
        category_col: Name of the category label column.

    Returns:
        Preprocessed pandas DataFrame with [description_col, category_col].

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If required columns are missing or dataset is empty.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found at: {filepath}")

    df = pd.read_csv(filepath)

    required_cols = {description_col, category_col}
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Dataset is missing required column(s): {missing_cols}. "
            f"Expected columns: ['{description_col}', '{category_col}']"
        )

    # Safely handle missing values
    # Drop rows without category label as they cannot be used for training/evaluation
    df = df.dropna(subset=[category_col]).copy()
    df[category_col] = df[category_col].astype(str).str.strip()
    df = df[df[category_col] != ""]

    if df.empty:
        raise ValueError(f"No valid labeled samples found in {filepath}")

    # Handle missing descriptions safely
    df[description_col] = df[description_col].fillna("").astype(str)

    return df[[description_col, category_col]].reset_index(drop=True)
