"""Deterministic normalization utilities and similarity metrics for reconciliation.

All normalization rules are deterministic and fully documented.
"""

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional


# ==============================================================================
# CANONICAL MERCHANT ALIAS MAPPINGS
# ==============================================================================
# Maps known merchant variant strings to their canonical business entity.
# This prevents trivial channel/branding differences from failing matches.
CANONICAL_MERCHANT_MAP = {
    # Food delivery
    "SWIGGY": "SWIGGY",
    "SWIGGY*BLR": "SWIGGY",
    "SWIGGY BLR": "SWIGGY",
    "SWIGGY INDIA": "SWIGGY",
    "ZOMATO": "ZOMATO",
    "ZOMATO*BANGALORE": "ZOMATO",
    "ZOMATO BANGALORE": "ZOMATO",
    "ZOMATO LTD": "ZOMATO",
    "DOMINOS": "DOMINOS",
    "DOMINO'S PIZZA": "DOMINOS",
    "DOMINOS PIZZA": "DOMINOS",
    "DOMINOS INDIA": "DOMINOS",

    # E-commerce & Retail
    "FLIPKART": "FLIPKART",
    "FLIPKART PAY": "FLIPKART",
    "FLIPKART INTERNET": "FLIPKART",
    "AMAZON": "AMAZON",
    "AMAZON PAY": "AMAZON",
    "AMAZON INDIA": "AMAZON",
    "MYNTRA": "MYNTRA",
    "MYNTRA PAY": "MYNTRA",
    "MYNTRA DESIGNS": "MYNTRA",
    "NYKAA": "NYKAA",
    "NYKAA.COM": "NYKAA",
    "NYKAA COM": "NYKAA",
    "NYKAA E-RETAIL": "NYKAA",
    "NYKAA E RETAIL": "NYKAA",
    "CROMA": "CROMA",
    "CROMA RETAIL": "CROMA",
    "CROMA ELECTRONICS": "CROMA",
    "DECATHLON": "DECATHLON",
    "DECATHLON INDIA": "DECATHLON",
    "DECATHLON SPORTS": "DECATHLON",
    "RELIANCE RETAIL": "RELIANCE",
    "RELIANCE RETAIL LTD": "RELIANCE",
    "RELIANCE DIGITAL": "RELIANCE",
    "METRO INDIA": "METRO",
    "METRO CASH & CARRY": "METRO",
    "METRO CASH AND CARRY": "METRO",
    "METRO RETAIL": "METRO",

    # Grocery & Essentials
    "BIGBASKET": "BIGBASKET",
    "BIGBASKET INDIA": "BIGBASKET",
    "BIG BASKET": "BIGBASKET",
    "APOLLO": "APOLLO",
    "APOLLO PHARMACY": "APOLLO",
    "APOLLO PHARMACY LTD": "APOLLO",

    # Travel & Mobility
    "UBER": "UBER",
    "UBER INDIA": "UBER",
    "UBER TECHNOLOGIES": "UBER",
    "OLA": "OLA",
    "OLA CABS": "OLA",
    "OLA MOBILITY": "OLA",
    "IRCTC": "IRCTC",
    "IRCTC RAIL": "IRCTC",
    "IRCTC E-TICKETING": "IRCTC",
    "IRCTC E TICKETING": "IRCTC",

    # Entertainment & Services
    "BOOKMYSHOW": "BOOKMYSHOW",
    "BOOKMYSHOW.COM": "BOOKMYSHOW",
    "BOOKMYSHOW COM": "BOOKMYSHOW",
    "BMS": "BOOKMYSHOW",
    "URBAN COMPANY": "URBAN COMPANY",
    "URBAN COMPANY INDIA": "URBAN COMPANY",
    "URBANCLAP": "URBAN COMPANY",

    # Gateway / Settlements
    "RAZORPAY SETTLEMENT": "RAZORPAY SETTLEMENT",
}


def normalize_merchant(name: Optional[str]) -> str:
    """Normalize a merchant string deterministically.

    Normalization Rules:
    1. Handle null/empty input by returning empty string.
    2. Convert to uppercase.
    3. Replace harmful punctuation/separators (*, ., ,, ', ", _, -, /, \\, &, +) with spaces.
    4. Collapse multiple consecutive whitespace characters into a single space and trim edges.
    5. Check against the canonical merchant mapping to resolve known brand aliases.

    Example:
        >>> normalize_merchant(" Swiggy*BLR ")
        'SWIGGY'
        >>> normalize_merchant("BMS")
        'BOOKMYSHOW'
        >>> normalize_merchant("Domino's Pizza")
        'DOMINOS'
    """
    if not name or not isinstance(name, str):
        return ""

    # Step 1: Uppercase & trim
    text = name.strip().upper()

    # Step 2: Check canonical map directly before punctuation stripping
    if text in CANONICAL_MERCHANT_MAP:
        return CANONICAL_MERCHANT_MAP[text]

    # Step 3: Remove punctuation and separators
    cleaned = re.sub(r"[^\w\s]", " ", text)

    # Step 4: Collapse whitespace
    collapsed = " ".join(cleaned.split())

    # Step 5: Check canonical map on collapsed text
    if collapsed in CANONICAL_MERCHANT_MAP:
        return CANONICAL_MERCHANT_MAP[collapsed]

    # Fallback to cleaned collapsed text
    return collapsed


def normalize_reference(ref: Optional[str]) -> str:
    """Normalize a payment/invoice reference string deterministically.

    Normalization Rules:
    1. Handle null/empty input by returning empty string.
    2. Convert to uppercase.
    3. Remove harmless separators such as '-', '_', spaces, slashes, and tabs.
    4. Retain all meaningful alphanumeric content without truncating digits or prefixes.
    5. Avoid destructive over-normalization (distinct IDs like UPI123 and UPI124 remain distinct).

    Example:
        >>> normalize_reference("UPI-156805")
        'UPI156805'
        >>> normalize_reference(" UPI 449836 ")
        'UPI449836'
        >>> normalize_reference("SYNTH-INV-000001")
        'SYNTHINV000001'
    """
    if not ref or not isinstance(ref, str):
        return ""

    # Step 1: Uppercase & trim
    text = ref.strip().upper()

    # Step 2: Remove harmless separators: hyphens, underscores, slashes, whitespace
    cleaned = re.sub(r"[\s\-_/\\,.:;]", "", text)

    return cleaned


def compute_reference_similarity(ref1: Optional[str], ref2: Optional[str]) -> float:
    """Compute deterministic similarity between two reference strings.

    Formula:
    - If either reference is empty, similarity is 0.0.
    - If normalized references are identical, similarity is 1.0.
    - Otherwise, compute the Levenshtein-based SequenceMatcher ratio.

    Returns:
        float: Similarity score between 0.0 and 1.0.
    """
    n1 = normalize_reference(ref1)
    n2 = normalize_reference(ref2)

    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0

    return SequenceMatcher(None, n1, n2).ratio()


def compute_merchant_similarity(m1: Optional[str], m2: Optional[str]) -> float:
    """Compute deterministic similarity between two merchant names.

    Formula:
    - If either merchant is empty, similarity is 0.0.
    - If normalized canonical merchants are identical, similarity is 1.0.
    - Otherwise, compute token Jaccard similarity and SequenceMatcher ratio,
      taking the maximum for robust string overlap.

    Returns:
        float: Similarity score between 0.0 and 1.0.
    """
    n1 = normalize_merchant(m1)
    n2 = normalize_merchant(m2)

    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0

    # Token-level overlap
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    jaccard = len(tokens1 & tokens2) / max(len(tokens1 | tokens2), 1)

    seq_ratio = SequenceMatcher(None, n1, n2).ratio()
    return max(jaccard, seq_ratio)


def compute_amount_similarity(amt1: float, amt2: float) -> float:
    """Compute deterministic similarity between two monetary amounts.

    Formula:
        Similarity = 1.0 - min(1.0, abs(amt1 - amt2) / max(amt1, amt2, 1e-6))

    Returns:
        float: Similarity score between 0.0 (large difference) and 1.0 (exact match).
    """
    if amt1 <= 0.0 and amt2 <= 0.0:
        return 1.0
    max_amt = max(abs(amt1), abs(amt2), 1e-6)
    diff = abs(amt1 - amt2)
    return max(0.0, 1.0 - (diff / max_amt))


def compute_timestamp_proximity(t1: datetime, t2: datetime, max_window_seconds: float = 604800.0) -> float:
    """Compute deterministic proximity between two timestamps.

    Formula:
        Proximity = max(0.0, 1.0 - abs(t1 - t2 in seconds) / max_window_seconds)

    Args:
        t1: First datetime.
        t2: Second datetime.
        max_window_seconds: Maximum window considered (default 7 days = 604,800 seconds).

    Returns:
        float: Proximity score between 0.0 (at or outside window) and 1.0 (identical time).
    """
    delta_seconds = abs((t1 - t2).total_seconds())
    if delta_seconds >= max_window_seconds:
        return 0.0
    return 1.0 - (delta_seconds / max_window_seconds)
