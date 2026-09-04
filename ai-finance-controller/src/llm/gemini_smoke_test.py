"""Small, controlled live Gemini check to run before bulk hybrid evaluation."""

import json
import argparse
from typing import Any, Dict, Iterable, Optional

from src.llm.gemini_fallback import classify_with_gemini


SMOKE_DESCRIPTIONS = (
    "SWIGGY*BLR0091 BANGALORE",
    "AMAZON PAY",
    "BESCOM ELECTRICITY BILL",
    "UPI PAYMENT 829173",
)


def run_gemini_smoke_test(
    allowed_categories: Iterable[str], client: Optional[Any] = None
) -> Dict[str, Any]:
    """Make at most four controlled requests and return validation outcomes."""
    results = [
        {
            "transaction_description": description,
            "result": classify_with_gemini(description, allowed_categories, client=client),
        }
        for description in SMOKE_DESCRIPTIONS
    ]
    return {
        "requests_attempted": len(results),
        "successful_responses": sum(result["result"].get("ok", False) for result in results),
        "results": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the controlled Gemini smoke test")
    parser.add_argument("--model", default="models/categorization_pipeline.joblib")
    args = parser.parse_args()
    import joblib

    pipeline = joblib.load(args.model)
    print(json.dumps(run_gemini_smoke_test(pipeline.classes_), indent=2))
