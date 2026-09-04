# AI-Powered Finance Controller

## Phase 1: Transaction categorization

Phase 1 categorizes a transaction using **only** its `transaction_description`.
It is a deliberately simple, reproducible baseline: TF-IDF (unigrams and
bigrams) followed by Logistic Regression. It does not use merchant, amount,
timestamp, payment method, customer history, review flags, or any other column.

The saved sklearn Pipeline owns text preprocessing, so the same logic is used
at fitting and when an independently loaded model receives raw text.

## Current implementation

- `clean_text()` lowercases and normalizes delimiters while retaining letters,
  numbers, merchant identifiers, city codes, and other useful tokens.
- `train_test_split(..., stratify=y, random_state=42)` creates a 75/25 split.
- TF-IDF is fitted only on training data inside the sklearn Pipeline.
- `predict_proba()` supplies the reported confidence (a model probability, not
  a separately calibrated reliability guarantee).
- The trained artifact is saved to `models/categorization_pipeline.joblib`.
- Metrics, classification report, confusion matrix, and duplicate analysis are
  saved to `evaluation/phase1_metrics.json`.

## Actual dataset inspection

The supplied `data/raw/transactions_v2.csv` is preserved as raw input and has:

- 12,000 rows and 15 columns; no missing values.
- No duplicate `transaction_id` values.
- 9 categories: Entertainment 1,413; Utilities 1,353; Education 1,353;
  Salary 1,346; Healthcare 1,337; Shopping 1,337; Food 1,312; Transport
  1,304; Rent 1,245.
- 28 unique merchants and 7,028 unique descriptions.
- 5,244 rows whose description appears more than once (4,972 repeated rows
  beyond the first occurrence).

## Actual Phase 1 evaluation

Run on `transactions_v2.csv` with test size 0.25 and random state 42:

- Accuracy: **1.0000**
- Macro precision: **1.0000**
- Macro recall: **1.0000**
- Macro F1: **1.0000**
- Weighted F1: **1.0000**

The 3,000-row test-set confusion matrix is diagonal: Education 338,
Entertainment 353, Food 328, Healthcare 334, Rent 312, Salary 337, Shopping
334, Transport 326, and Utilities 338 were all classified correctly. The full
classification report and matrix are in `evaluation/phase1_metrics.json`.

### Duplicate / leakage context

Duplicates were not removed. The random split has 213 exact descriptions in
both train and test. In total, **1,291 of 3,000 test rows (43.03%)** have a
description already seen in training. This overlap can inflate the perfect
score; it should not be interpreted as evidence of performance on entirely new
merchant-description patterns.

## Description-grouped benchmark

The grouped benchmark uses `GroupShuffleSplit` with the exact
`transaction_description` as the group and random state 42. It keeps every
occurrence of a description on one side of the split: 9,429 training rows and
2,571 test rows, with **zero** train/test description overlap.

On this grouped split, both evaluated text-only approaches scored 1.0000 for
accuracy, macro precision, macro recall, macro F1, and weighted F1:

- **Keyword baseline:** static, transparent mapping for merchant/keyword text
  such as `swiggy -> Food` and `uber -> Transport`; it has an explicit
  `Unknown` fallback.
- **TF-IDF + Logistic Regression:** the same Phase 1 pipeline used for the
  random benchmark.

Both full classification reports have per-class precision/recall/F1 of 1.00;
the 2,571-row matrices are diagonal (Education 161, Entertainment 174, Food
292, Healthcare 355, Rent 253, Salary 273, Shopping 304, Transport 338, and
Utilities 421). There are no grouped-holdout errors to list. The complete,
separate result—including rules, reports, matrices, and error analysis—is in
`evaluation/phase1_grouped_metrics.json`.

The grouped split is a better measure than the random benchmark because it
prevents memorizing an exact repeated description. It still does not establish
robustness to entirely new merchant families: this dataset's held-out
descriptions continue to use strongly category-specific merchant tokens, which
also lets the simple rule baseline achieve a perfect score.

## Controlled challenge benchmark

The evaluation-only challenge benchmark is generated with seed 42 and is saved
to `data/evaluation/phase1_challenge_dataset.csv`. It has 324 balanced rows:
three groups of 108 rows, with 12 examples for every category in each group.
It is **never used to train or tune the model**.

- **Known merchant + noisy description:** known merchant names appear in new
  bank-statement-style formats (UPI/POS prefixes, references, city codes,
  casing, spacing, and suffixes).
- **Unseen merchant:** synthetic merchant tokens absent from the raw dataset;
  their labels span the existing categories equally.
- **Ambiguous description:** generic payment text with no merchant/category
  clue; labels are balanced so there is no predictable wording-to-label rule.

Actual challenge results for the existing saved model:

- Known noisy merchants: accuracy 0.6389; macro F1 0.5874. Confidence median
  0.5414; 38.89%, 52.78%, 55.56%, and 55.56% of predictions fall below 0.50,
  0.60, 0.70, and 0.80 respectively.
- Unseen merchants: accuracy 0.1111; macro F1 0.0819. Confidence median
  0.2591; 50.93%, 75.00%, 100.00%, and 100.00% fall below the same thresholds.
- Ambiguous text: accuracy 0.0926; macro F1 0.0463. Confidence median 0.2308;
  73.15%, 73.15%, 100.00%, and 100.00% fall below those thresholds.

The full metrics, classification reports, confusion matrices, and confidence
distributions are saved separately in `evaluation/phase1_challenge_metrics.json`.
These results demonstrate why the perfect random and grouped benchmarks should
not be treated as robust generalization evidence.

## Phase 2: confidence-gated Gemini fallback

Phase 2 keeps the local TF-IDF + Logistic Regression pipeline as the first
decision point. A transaction is sent to Gemini only when local confidence is
below the chosen threshold; high-confidence transactions remain local. This
reduces latency, API usage, and cost while retaining a useful fallback for the
novel and ambiguous cases exposed by the challenge benchmark.

The Gemini integration is isolated in `src/llm/gemini_fallback.py`. It reads
`GEMINI_API_KEY` only from the process environment, requests JSON structured
output, checks category/confidence/reason fields against the model's actual
allowed categories, and returns a safe error state instead of crashing if the
provider is unavailable. API keys are never stored in code, tests, or artifacts.

The frozen challenge-set threshold analysis selected **0.70**: it is the lowest
tested threshold that routes 100% of the unseen-merchant and ambiguous groups
to the fallback. On the 324-row frozen set, this leaves 14.81% local ML
coverage and would route 276 rows (85.19%) to Gemini. The lower 0.50 threshold
would route 176 rows (54.32%), but would retain some novel/ambiguous cases
locally. These are routing measurements, not hybrid-quality claims.

Hybrid metrics are intentionally not reported until a controlled live Gemini
smoke test succeeds and actual API responses are evaluated. The frozen
challenge dataset is never used to retrain or tune the local model.

## Usage

Install dependencies:

```bash
pip install -r requirements.txt
```

Retrain with the actual Phase 1 dataset:

```bash
python -m src.categorization.train --data data/raw/transactions_v2.csv --model models/categorization_pipeline.joblib --evaluation-output evaluation/phase1_metrics.json
```

Run the grouped comparison without overwriting the random-split results:

```bash
python -m src.categorization.grouped_evaluate --data data/raw/transactions_v2.csv --output evaluation/phase1_grouped_metrics.json --random-state 42
```

Run the evaluation-only challenge benchmark (it loads the existing saved model
and does not retrain it):

```bash
python -m src.categorization.challenge_evaluate --data data/raw/transactions_v2.csv --model models/categorization_pipeline.joblib --dataset-output data/evaluation/phase1_challenge_dataset.csv --metrics-output evaluation/phase1_challenge_metrics.json --seed 42
```

After a successful Gemini smoke test, run the hybrid evaluation:

```bash
python -m src.categorization.phase2_evaluate --challenge data/evaluation/phase1_challenge_dataset.csv --model models/categorization_pipeline.joblib --metrics-output evaluation/phase2_hybrid_metrics.json --predictions-output evaluation/phase2_predictions.csv
```

Predict one transaction:

```bash
python -m src.categorization.predict "SWIGGY*BLR0091 BANGALORE"
```

Or use Python:

```python
from src.categorization.predict import TransactionClassifier

classifier = TransactionClassifier("models/categorization_pipeline.joblib")
print(classifier.predict("UBER INDIA"))
```

Run tests (the explicit base temp directory avoids restricted system-temp
folders in some Windows environments):

```bash
pytest -q --basetemp=.pytest_tmp
```

## Fast-API Backend (AI Finance Controller API)

The deterministic reconciliation engine and supporting ML intelligence pipeline are exposed through a production-ready FastAPI backend.

### Running Locally

Start the development server with Uvicorn:

```bash
uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

### API Endpoints & Documentation

- **Swagger UI Interactive Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON Schema**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

#### Key Endpoints:
1. `GET /api/health` — Checks API health and reports availability of ML models.
2. `POST /api/reconcile` — Upload `bank_file` and `ledger_file` CSVs as multipart form data. Executes deterministic reconciliation and ML enrichment, returning run metadata, status counts, priority distributions, and line-item results.
3. `GET /api/reconcile/{run_id}` — Retrieves previously executed reconciliation run summary and results.
4. `GET /api/reconcile/{run_id}/exceptions` — Retrieves paginated exceptions filterable by `status`, `priority` (`HIGH`, `MEDIUM`, `LOW`), and keyword `search`.
5. `GET /api/reconcile/{run_id}/exceptions/{bank_txn_id}` — Retrieves deep audit analysis and raw transaction payloads for a specific transaction ID.

## Legacy helper scripts

`create_v2.py`, `populate.py`, `populate_data.py`, `write_csv.py`,
`write_dataset.py`, and `run_v2_analysis.py` are retained for traceability.
They are one-off or incomplete dataset-generation/analysis helpers and are not
part of the supported training path above; do not run them against the raw
dataset.
