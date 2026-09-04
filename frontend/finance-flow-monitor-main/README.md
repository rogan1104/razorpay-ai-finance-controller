# Finance Flow Monitor

Build the frontend for my project: "AI Finance Controller".

IMPORTANT:

This is a FRONTEND task only.

Do NOT build or modify a backend.

Do NOT create a database.

Do NOT create new ML models.

Do NOT retrain or replace any existing ML models.

Do NOT implement reconciliation logic in the frontend.

Do NOT generate fake AI results or fake statistics.

A FastAPI backend already exists and will be running locally at:

http://127.0.0.1:8000

Your frontend must consume the real API.

==================================================

PROJECT PURPOSE

==================================================

This is a Track 04 finance operations project focused primarily on:

FINANCIAL TRANSACTION RECONCILIATION

The core workflow is:

Bank Transactions

        +

Merchant Ledger

        ↓

Deterministic Reconciliation Engine

        ↓

MATCH / EXCEPTIONS / UNMATCHED

        ↓

Exception Investigation

        ↓

Supporting ML Intelligence

The reconciliation loop is the MAIN STORY.

The existing ML models are supporting intelligence, not the centerpiece.

The application should feel like a real finance operations/reconciliation

platform rather than an AI chatbot or generic analytics dashboard.

==================================================

TECHNOLOGY

==================================================

Build the frontend using:

- React

- TypeScript

- modern CSS

- clean component architecture

Use a professional component structure.

Do not introduce unnecessary libraries.

The frontend must communicate with the existing FastAPI backend using HTTP.

Backend base URL:

http://127.0.0.1:8000

Make the API base URL configurable through an environment variable.

For example:

VITE_API_BASE_URL=http://127.0.0.1:8000

==================================================

DESIGN DIRECTION

==================================================

Create a LIGHT, PREMIUM FINANCE OPERATIONS UI.

Color direction:

- white

- warm off-white

- very light gray

- soft blue

- pale mint/green

- soft peach/coral

- muted yellow

IMPORTANT:

DO NOT USE LAVENDER OR PURPLE.

No purple gradients.

No lavender cards.

No violet accents.

Avoid dark mode.

Avoid neon colors.

Avoid excessive gradients.

Avoid excessive glassmorphism.

Avoid making it look like a generic SaaS template.

The design should feel:

modern

clean

trustworthy

analytical

professional

finance-focused

operations-focused

Use pastel colors as subtle accents rather than painting the entire interface

in pastel colors.

Use plenty of whitespace.

Use rounded cards, but avoid excessive pill-shaped UI everywhere.

Typography should be clean and highly readable.

==================================================

APPLICATION LAYOUT

==================================================

Create:

- left sidebar navigation

- top header

- main dashboard content

Sidebar:

AI Finance Controller

Navigation:

Overview

Reconciliation

Exceptions

Transactions

Keep navigation simple.

The primary active section should be Reconciliation.

==================================================

TOP HEADER

==================================================

Header should contain:

AI Finance Controller

Subtitle:

Reconciliation & Exception Intelligence

On the right:

System status indicator

Example:

● API Connected

This must be based on:

GET /api/health

Do not hardcode the connected state.

==================================================

OVERVIEW DASHBOARD

==================================================

Create a polished overview dashboard.

Show KPI cards:

1. Bank Records

2. Ledger Records

3. Match Rate

4. Exceptions

5. Processing Throughput

These must come from the FastAPI response.

Do NOT hardcode benchmark numbers.

Display appropriate formatting:

Match Rate:

65.47%

Throughput:

2,559 records/sec

etc.

Below the KPI cards show:

Reconciliation Status Breakdown

with:

MATCH

AMOUNT_MISMATCH

DUPLICATE

AMBIGUOUS

UNMATCHED_BANK

UNMATCHED_LEDGER

Use subtle semantic colors:

MATCH → soft green

AMOUNT_MISMATCH → soft peach/orange

DUPLICATE → soft yellow

AMBIGUOUS → soft blue

UNMATCHED_BANK → soft coral

UNMATCHED_LEDGER → muted gray/blue

Do not use purple.

==================================================

RECONCILIATION PAGE

==================================================

This is the main page.

Create a clear upload area.

Two separate upload cards:

--------------------------------

BANK TRANSACTIONS

--------------------------------

Upload:

bank_transactions.csv

--------------------------------

MERCHANT LEDGER

--------------------------------

Upload:

merchant_ledger.csv

Show:

- selected filename

- file size

- upload state

- remove/reset button

Then provide a prominent:

RUN RECONCILIATION

button.

The button must call:

POST /api/reconcile

using multipart form data:

bank_file

ledger_file

Do not simulate the request.

==================================================

PROCESSING STATE

==================================================

When reconciliation is running, show a professional processing state.

Example:

Reconciling transactions...

Step indicators:

✓ Validating files

✓ Matching transactions

● Enriching exceptions

○ Preparing results

Do not pretend a step is complete when it isn't.

Use the actual request lifecycle where possible.

Disable duplicate submissions while processing.

==================================================

RECONCILIATION RESULTS

==================================================

After the API returns successfully, show:

Reconciliation Complete

Then show:

- Bank records

- Ledger records

- Total source records

- Match rate

- Exception count

- Throughput

- Runtime

Use the API response.

Do not calculate or invent alternative benchmark numbers in the frontend.

==================================================

STATUS BREAKDOWN

==================================================

Show a visual breakdown of:

MATCH

AMOUNT_MISMATCH

DUPLICATE

AMBIGUOUS

UNMATCHED_BANK

UNMATCHED_LEDGER

Each should display:

status name

count

percentage of results

Use a clean horizontal bar or compact chart.

Keep it readable and professional.

==================================================

EXCEPTION WORKSPACE

==================================================

Create a dedicated Exceptions page.

This is one of the most important parts of the application.

At the top:

Exceptions Requiring Review

Show:

Total Exceptions

Then filters:

Status

Priority

Search

Status options:

All

MATCH

AMOUNT_MISMATCH

DUPLICATE

AMBIGUOUS

UNMATCHED_BANK

UNMATCHED_LEDGER

Priority:

All

HIGH

MEDIUM

LOW

Search should support:

Bank transaction ID

Ledger ID

Merchant

Reference

The API supports:

GET /api/reconcile/{run_id}/exceptions

with:

status

priority

search

limit

offset

Use these API parameters rather than downloading everything unnecessarily.

==================================================

EXCEPTION TABLE

==================================================

Create a professional data table.

Columns:

Status

Priority

Bank Transaction

Ledger Record

Amount Difference

Confidence

Match Method

Reason

Make the table:

- sortable where appropriate

- filterable

- paginated

- responsive

Do not render thousands of rows at once.

Use server-side pagination through:

limit

offset

when appropriate.

==================================================

EXCEPTION DETAIL

==================================================

When the user clicks an exception, open a large side panel or detail view.

Use:

GET /api/reconcile/{run_id}/exceptions/{bank_txn_id}

Display:

--------------------------------

EXCEPTION SUMMARY

--------------------------------

Status

Priority

Confidence

Match Method

--------------------------------

BANK TRANSACTION

--------------------------------

Transaction ID

Merchant

Reference

Amount

Direction

Timestamp

--------------------------------

MERCHANT LEDGER

--------------------------------

Ledger ID

Merchant

Reference

Amount

Direction

Timestamp

--------------------------------

MATCHING SIGNALS

--------------------------------

Amount Difference

Timestamp Difference

Merchant Similarity

Reference Similarity

--------------------------------

WHY THIS WAS FLAGGED

--------------------------------

Display the exact:

reason

returned by the backend.

Do NOT rewrite or generate the explanation in the frontend.

The backend's explanation is authoritative.

==================================================

SUPPORTING ML INTELLIGENCE

==================================================

Inside the exception detail panel, add a section titled:

Supporting Intelligence

This should clearly be secondary to reconciliation.

Display when available:

Category

Categorization Confidence

Categorization Source

Anomaly Status

Anomaly Flag

Anomaly Score

Anomaly Reason

Priority

Priority Reasons

Add a subtle informational note:

"ML signals support exception review and do not determine reconciliation status."

This distinction is VERY important.

If anomaly analysis is unavailable, show the backend-provided explanation.

For example:

"Anomaly analysis unavailable"

Do not fabricate an anomaly score.

==================================================

TRANSACTION VIEW

==================================================

Create a clean Transactions page showing reconciliation results.

Allow users to search/filter by:

Transaction ID

Merchant

Reference

Status

Category

Show useful transaction information without overwhelming the screen.

==================================================

EMPTY STATES

==================================================

Create polished empty states for:

- no files uploaded

- only bank file selected

- only ledger file selected

- no reconciliation run yet

- no exceptions

- no search results

Example:

"No reconciliation run yet"

"Upload your bank transactions and merchant ledger to begin."

==================================================

ERROR STATES

==================================================

Handle backend errors gracefully.

Examples:

Invalid CSV

Missing required columns

Empty file

API unavailable

Unknown run

Server error

Show human-readable messages.

Never show:

Python traceback

filesystem paths

internal exceptions

API keys

environment variables

Provide a Retry action where appropriate.

==================================================

API INTEGRATION

==================================================

Create a dedicated API service layer.

For example:

src/api/

with functions:

checkHealth()

runReconciliation(bankFile, ledgerFile)

getRun(runId)

getExceptions(runId, filters)

getExceptionDetail(runId, bankTxnId)

Use the real endpoints:

GET /api/health

POST /api/reconcile

GET /api/reconcile/{run_id}

GET /api/reconcile/{run_id}/exceptions

GET /api/reconcile/{run_id}/exceptions/{bank_txn_id}

Do not duplicate backend logic.

==================================================

IMPORTANT RESPONSE FIELDS

==================================================

The backend reconciliation result contains fields such as:

bank_txn_id

ledger_id

predicted_status

match_confidence

match_method

reason

amount_difference

timestamp_difference

merchant_similarity

reference_similarity

Supporting intelligence may contain:

category

categorization_confidence

categorization_source

anomaly_flag

anomaly_score

anomaly_status

anomaly_reason

priority

priority_reasons

Summary contains:

bank_records

ledger_records

total_source_records

total_results

match_rate

exception_count

reconciliation_runtime_seconds

intelligence_runtime_seconds

total_runtime_seconds

throughput_records_per_second

Status counts:

MATCH

AMOUNT_MISMATCH

DUPLICATE

AMBIGUOUS

UNMATCHED_BANK

UNMATCHED_LEDGER

Priority counts:

HIGH

MEDIUM

LOW

Use the actual backend fields.

Do not rename their semantic meaning.

==================================================

NO FAKE DATA

==================================================

During development, you may use a clearly separated mock API mode only if

necessary to construct the UI.

However:

- never present mock numbers as real

- never mix mock data with live data

- clearly label mock mode

- default to the real FastAPI backend

Once connected, the application must display only real backend results.

==================================================

NO AI CHATBOT

==================================================

Do NOT add:

AI chat

"Ask AI"

fake AI explanations

fake anomaly detection

fake fraud detection

AI-generated financial advice

This project is about measurable reconciliation and exception handling.

==================================================

DEMO EXPERIENCE

==================================================

Optimize the application for a project demonstration.

The ideal flow is:

1. Open dashboard

2. API shows Connected

3. Go to Reconciliation

4. Upload bank_transactions.csv

5. Upload merchant_ledger.csv

6. Click Run Reconciliation

7. Show processing state

8. Show Match Rate

9. Show Exceptions

10. Open Exceptions

11. Filter HIGH priority

12. Click an exception

13. Show bank and ledger records side-by-side

14. Show exact reconciliation reason

15. Show supporting ML intelligence

The reviewer should understand the project within 30 seconds.

==================================================

RESPONSIVENESS

==================================================

Desktop/laptop is the primary target.

Also support tablet widths.

Do not sacrifice the desktop data-table experience.

==================================================

ACCESSIBILITY

==================================================

Use:

semantic HTML

accessible buttons

keyboard navigation

visible focus states

proper form labels

ARIA labels where useful

sufficient color contrast

Do not rely on color alone to communicate status.

==================================================

CODE QUALITY

==================================================

Use reusable components.

Suggested structure:

src/

  components/

    Layout

    Sidebar

    Header

    MetricCard

    StatusBreakdown

    FileUpload

    ReconciliationTable

    ExceptionDetail

    Filters

    IntelligencePanel

  pages/

    Dashboard

    Reconciliation

    Exceptions

    Transactions

  api/

    client

  types/

    reconciliation

  App

You may adjust the structure if needed.

Avoid one giant component.

==================================================

IMPORTANT BACKEND BOUNDARY

==================================================

The FastAPI backend is already implemented.

DO NOT modify it.

Do not create another backend.

Do not replace FastAPI with Supabase.

Do not add Firebase.

Do not create a database.

Do not move reconciliation logic into React.

The React application is simply the presentation and interaction layer over

the existing FastAPI API.

==================================================

FINAL DELIVERABLE

==================================================

Build the complete polished frontend.

At the end provide:

1. Files created/modified

2. Main components

3. API endpoints integrated

4. Environment variable required

5. How to run the frontend

6. Any dependencies added

7. Any assumptions made

8. Confirmation that no backend or ML logic was modified

Most importantly:

The final UI must look like a serious financial reconciliation operations

application, not a generic AI dashboard.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
