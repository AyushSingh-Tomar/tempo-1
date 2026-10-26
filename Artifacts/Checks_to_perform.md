## First define the two datasets

### For your use case

| Dataset | Role |
| --- | --- |
| Subledger | Source of truth / expected financial or transactional record |
| Claimsmapping | Data that should correspond to the subledger |
| Reconciliation output | Matched records + mismatches + explanation/category |

### The goal should not simply be

"Do both files have the same rows?"

### It should be

For every relevant subledger record, can we find the corresponding Claimsmapping record, and if found, do the important attributes and amounts agree? If they don't, can we explain why?

This distinction is important because two datasets can have identical row counts while containing different records.

---

## Recommended reconciliation framework

### I would divide your checks into three layers

Layer A — Python / deterministic checks

Things that can be calculated exactly and repeatedly.

Layer B — AI-assisted checks

Things where AI can identify patterns, infer likely causes, map inconsistent representations, and prioritize exceptions.

Layer C — Human investigation

Things requiring business knowledge or confirmation of whether a difference is actually legitimate.

And before those, there should be a pre-reconciliation normalization layer.

---

## PRE-CHECK — Normalize both datasets

This is extremely important because otherwise you can get false mismatches.

### For both Claimsmapping and Subledger

Standardize
Column names
Leading/trailing spaces
Case
Date formats
Decimal precision
Currency representation
Null/blank representation
Boolean representation
Numeric/string types
Leading zeros
Special characters
Encoding
Duplicate whitespace
Date/time/timezone

### For example

Subledger:
CLAIM_ID = "CLM00123"

Claimsmapping:
claim_id = " clm00123 "

### A naïve comparison says

---

# MISMATCH

### A normalized comparison should say

---

# MATCH

Hash-based reconciliation also needs normalization because whitespace, case, dates and decimal precision can otherwise create false differences.

---

## PYTHON-AUTOMATABLE CHECKS

These are the checks I would make into your core reconciliation Python script.

1. File / dataset-level checks
1. File existence

### Check

Is Claimsmapping file present?
Is Subledger file present?
Correct file version?
Correct reporting period?
Correct filename/date?
---

## File size

### Compare

file size
number of rows
number of columns

A sudden unexpected file-size change can indicate an incomplete extract.

---

## Schema reconciliation

### Compare

Column name
Data type
Nullable
Expected/actual format

### Example

| Field | Subledger | Claimsmapping | Result |
| --- | --- | --- | --- |
| claim_id | string | string | PASS |
| claim_date | date | string | WARNING |
| amount | decimal | float | WARNING |
| status | string | string | PASS |

### Also identify

Columns only in Subledger
SUBLEDGER ONLY
Columns only in Claimsmapping
CLAIMSMAPPING ONLY
Same business field with different names

### For example

CLAIM_ID
claim_number
claim_no
claim_reference

This is where AI becomes useful later.

---

## Row-count reconciliation

### The simplest check

len(subledger)
len(claimsmapping)

### Example

| Subledger | = 4511 |
| --- | --- |
| Claimsmapping | = 4498 |
| Difference | = 13 |

But do not stop here.

Row-count reconciliation is only the first-level completeness check.

---

## Row counts by important dimensions

This is much more powerful.

### Instead of

4511 vs 4498

### calculate

Year
Quarter
Month
Business unit
Claim type
Product
Region
Status
Account
etc.

### Example

| Quarter | Subledger | Claimsmapping | Difference |
| --- | --- | --- | --- |
| Q1 | 1100 | 1100 | 0 |
| Q2 | 1150 | 1148 | -2 |
| Q3 | 1200 | 1192 | -8 |
| Q4 | 1061 | 1058 | -3 |

### Now you know

The problem is concentrated in Q3.

This is one of the most useful diagnostic checks.

---

## Distinct-key reconciliation

### Suppose your key is

Claim_ID

### Check

subledger["claim_id"].nunique()
claimsmapping["claim_id"].nunique()

### Also compare

COUNT(*)
vs
COUNT(DISTINCT claim_id)

This catches duplicates that simple row counts won't reveal. Distinct business-key counts are a standard source-to-target reconciliation check.

---

## Duplicate checks

Check duplicates in both datasets.

### For example

subledger[subledger["claim_id"].duplicated(keep=False)]

### and

claimsmapping[claimsmapping["claim_id"].duplicated(keep=False)]

### But there is an important question

Is Claim_ID actually supposed to be unique?

### Sometimes the real key is

Claim_ID + Claim_Line

For claims data, composite keys such as claim_id + claim_line_number are commonly required because one claim can contain multiple lines.

### So your script should test several possible keys

claim_id
claim_id + line_number
claim_id + transaction_date
claim_id + account

depending on the business definition.

---

## Missing records

This is one of your most important checks.

### Find

Present in Subledger but absent in Claimsmapping
SUBLEDGER ONLY

These are potentially missing Claimsmapping records.

### And

Present in Claimsmapping but absent in Subledger
CLAIMSMAPPING ONLY

These are potentially extra/unexpected records.

### Conceptually

Subledger
```
 ↓
```
---

# FULL OUTER JOIN
```
 ↓
```
┌───────────────┬───────────────┐
│ Missing       │ Extra         │
│ Claimsmapping │ Claimsmapping │
└───────────────┴───────────────┘

A full key-level comparison is much more informative than simply reporting that the counts differ.

---

## Field-level comparison

For records where the key exists in both datasets, compare fields.

### Example

| Claim ID | Field | Subledger | Claimmapping | Result |
| --- | --- | --- | --- | --- |
| 1001 | Amount | 5000 | 5000 | MATCH |
| 1002 | Amount | 7000 | 7200 | MISMATCH |
| 1003 | Status | Paid | PAID | FORMAT MATCH |
| 1004 | Date | 2026-01-15 | 2026-01-16 | MISMATCH |

This should be done programmatically.

---

## Numeric reconciliation

### For financial/transactional fields

SUM
MIN
MAX
AVG
MEDIAN
COUNT

Compare between datasets.

### For example

Total claim amount

| Subledger | ₹25,430,000 |
| --- | --- |
| Claimsmapping | ₹25,410,000 |
| Difference | ₹20,000 |

### Then break it down

By year
By quarter
By month
By claim type
By account
By status

Control totals are particularly important for financial reconciliation.

---

## Absolute difference / variance

### For every matching key

variance = subledger_amount - claimsmapping_amount

### Then classify

0              → MATCH
0.01–1         → ROUNDING
small variance → POSSIBLE ROUNDING
large variance → INVESTIGATE

For money, don't blindly use floating-point equality.

Use an agreed business precision.

---

## Debit / credit checks

### If applicable to your subledger

Total Debit
Total Credit
Net Balance

Compare both sides.

### Also check

Debit + Credit relationship

and whether the resulting balance agrees.

General ledger/subledger reconciliation commonly checks whether detailed subledger balances agree with corresponding ledger balances for the same period.

---

## Date reconciliation

### Compare

MIN(date)
MAX(date)
COUNT by date
COUNT by month
COUNT by quarter

### Look for

Missing dates
Future dates
Unexpected old dates
Different fiscal periods
Month-end differences
Year-end differences
Off-by-one-day errors
Time-zone shifts

Date-boundary checks are a standard migration/reconciliation technique because they can expose truncated or shifted history even when totals appear reasonable.

---

## Null checks

### For every important column

NULL count
NULL %
Blank count
Blank %

### Example

| Field | Subledger NULL % | Claimmapping NULL % |
| --- | --- | --- |
| Claim ID | 0% | 0% |
| Amount | 0.1% | 1.8% |
| Status | 0% | 4.2% |

A sudden increase in nulls is a strong indicator of extraction/mapping/transformation problems.

---

## Null vs blank vs zero

Very important.

### These are not necessarily equivalent

NULL
""
" "
0
"0"

Your Python checks should explicitly distinguish them.

---

## Data type checks

### Examples

Amount → numeric?
Claim ID → string?
Date → valid date?
Status → string?

### Potential problems

1000.50
"1000.50"
"1,000.50"
"$1,000.50"

They may represent the same value but require normalization.

---

## Domain/value checks

### For categorical columns

Status
Claim Type
Transaction Type
Region
Product
Account
Currency

### Find

unique values in Subledger
unique values in Claimmapping

Then compare.

### Example

Subledger:
Paid
Pending
Rejected
Cancelled

Claimmapping:
PAID
PENDING
REJECTED
CANCEL

### AI can later determine that

CANCEL ≈ Cancelled

but Python should first report the raw difference.

---

## Referential integrity

### If Claimmapping contains

claim_id
customer_id
account_id
product_id

check whether those IDs exist in their corresponding master data.

This catches orphan records.

Referential-integrity checks are a standard data-quality control.

---

## Distribution checks

Compare distributions.

### For example

Amount distribution
Claim status distribution
Claims by region
Claims by month
Claims by account

### Example

### Subledger

| Paid | 72% |
| --- | --- |
| Pending | 18% |
| Rejected | 10% |

### Claimmapping

| Paid | 72% |
| --- | --- |
| Pending | 17% |
| Rejected | 6% |
| Unknown | 5% |

This immediately indicates something suspicious even if total records match.

---

## Hash-based comparison

For critical records, create a normalized row hash.

### Conceptually

claim_id
- date
- amount
- status
- account
- ...
  ↓
  normalized string
  ↓
  SHA256

Then compare hashes.

This is useful when aggregate totals match but individual records may have changed. Hash comparison is a recognized reconciliation technique.

---

## PYTHON CHECKS — SUMMARY

### I would make your Python reconciliation engine perform

Level 1 — Structural
File existence
File metadata
Row count
Column count
Schema
Data types
Column presence
Column naming
Level 2 — Completeness
Row counts
Distinct keys
Missing keys
Extra keys
Partition completeness
Date completeness
Level 3 — Integrity
Duplicate keys
Nulls
Blank values
Referential integrity
Invalid data types
Invalid categorical values
Level 4 — Value reconciliation
SUM
MIN
MAX
AVG
Count
Control totals
Amount variance
Date variance
Field-by-field comparison
Hash comparison
Level 5 — Distribution
Counts by month
Counts by quarter
Counts by year
Counts by status
Counts by account
Counts by claim type
Numeric distributions
---

## WHERE AI BECOMES USEFUL

This is where I would not replace Python with AI.

Python should produce the facts.

AI should interpret the facts.

### For example

### Python

1,204 records matched
37 records missing
22 records extra
18 amount mismatches
9 date mismatches
14 status mismatches

AI then investigates the pattern.

---

## AI CHECK #1 — Semantic column mapping

This is particularly useful when Claimsmapping and Subledger have different column names.

### Example

SUBLEDGER:
CLAIM_NUMBER

CLAIMSMAPPING:
CLM_REF

### AI can inspect

Column names
Sample values
Data types
Value distributions
Relationships

### and suggest

CLAIM_NUMBER ↔ CLM_REF

### Similarly

TOTAL_AMT ↔ CLAIM_AMOUNT
TXN_DT ↔ TRANSACTION_DATE
ACCT_NO ↔ ACCOUNT_NUMBER

But human approval should be required before using an AI-generated mapping for financial reconciliation.

---

## AI CHECK #2 — Identify equivalent values

### Example

Subledger:
Paid
Cancelled
Pending

Claimsmapping:
PAID
CANCEL
PEND

### AI can propose

| PAID | → Paid |
| --- | --- |
| CANCEL | → Cancelled |
| PEND | → Pending |

This is especially useful when source systems use different code sets.

---

## AI CHECK #3 — Explain mismatches

This is probably the most valuable AI feature.

### Suppose

Claim ID: 10052

Subledger:
Amount = 10,000
Date = 15-Aug
Status = Paid

Claimmapping:
Amount = 10,000
Date = 16-Aug
Status = Paid

### AI could classify

Likely category:
Date transformation / posting-date difference

Evidence:
Amount and status match.
Only transaction date differs by one day.

### Possible causes
- posting date vs transaction date
- timezone conversion
- business-day processing
- late posting

Notice that AI should say possible cause, not pretend it knows the root cause.

---

## AI CHECK #4 — Pattern detection across mismatches

### Suppose you have

500 mismatches

### AI can group them

Group A — 220 records
Amount differs by exactly 0.01

Group B — 150 records
Date differs by exactly 1 day

Group C — 80 records
Status "CANCEL" vs "CANCELLED"

Group D — 50 records
Account mapping missing

This is much more useful than giving an analyst 500 rows in Excel.

---

## AI CHECK #5 — Detect systematic transformation errors

This is especially important.

### Imagine

Subledger amount:
100
200
300
400

Claimsmapping:
90
180
270
360

### AI may notice

Claimsmapping ≈ Subledger × 0.90

### That could suggest

fee deduction
tax
currency conversion
incorrect percentage
transformation rule

Python can detect the numerical relationship; AI can help describe the likely transformation.

---

## AI CHECK #6 — Detect field shifts

### A particularly nasty Excel/CSV problem is

Column A → Column B
Column B → Column C

### AI can examine samples and recognize

Column X looks like dates
but is currently mapped to Amount.

This can catch mapping errors that basic schema validation won't.

---

## AI CHECK #7 — Detect inconsistent business rules

### Example

### Subledger

Status = Paid
Amount = 0

### Claimmapping

Status = Paid
Amount = 5000

### AI can flag

"This combination may violate the expected business relationship between status and amount."

This requires business rules/context, so it is much better suited to AI-assisted analysis than pure structural validation.

---

## AI CHECK #8 — Detect suspicious clusters

### AI can group mismatches by

year
month
quarter
account
claim type
region
status
amount range
source system

### For example

"Most mismatches occur in 2024 Q3 and are associated with Account X."

That dramatically reduces investigation time.

---

## AI CHECK #9 — Fuzzy matching

This is useful when IDs are not perfectly aligned.

### Example

Subledger:
ABC-000123

Claimmapping:
ABC123

### or

ABC Hospital Pvt Ltd

ABC HOSPITAL PVT. LTD.

AI/fuzzy matching can identify likely matches.

But do not allow fuzzy matching to silently declare financial records reconciled.

### Instead

Exact match
Probable match
Possible match
No match

and send probable/possible matches to human review.

---

## AI CHECK #10 — Root-cause classification

I'd have AI classify every exception into categories such as:

1. Missing record
2. Extra record
3. Duplicate
4. Wrong mapping
5. Amount mismatch
6. Date mismatch
7. Status mismatch
8. Code mismatch
9. Formatting mismatch
10. Rounding
11. Timing difference
12. Transformation difference
13. Master-data mismatch
14. Source-data issue
15. Unknown

This creates an extremely useful reconciliation report.

---

## HUMAN CHECKS

This is the part that should not be completely automated.

### The human's job is primarily to answer

Is this difference actually wrong, or is it an expected business difference?

---

## Human Check #1 — Understand the business definition

### Before investigating individual records, ask

What does each dataset actually represent?

### For example

Subledger = accounting posting date

Claimsmapping = operational transaction date

Then a date mismatch may be perfectly valid.

### Similarly

Subledger = gross amount
Claimsmapping = net amount

Then amount mismatches are expected.

This is why source-to-target reconciliation must account for intentional filters, aggregation, deduplication and transformations.

---

## Human Check #2 — Confirm the reconciliation key

### Ask

What uniquely identifies a transaction?

### Possibilities

Claim ID
Claim ID + Line Number
Claim ID + Account
Claim ID + Date
Claim ID + Transaction ID

A huge percentage of reconciliation problems come from using the wrong key.

38. Human Check #3 — Check whether one-to-many relationships exist

### Example

Subledger
Claim 1001 → ₹10,000
Claimsmapping
Claim 1001 → ₹4,000
Claim 1001 → ₹6,000

That's not necessarily a mismatch.

### It could be

1 Subledger transaction
```
    ↓
```
2 Claimmapping lines

Your reconciliation logic needs to aggregate before comparing.

---

## Human Check #4 — Check timing

Some mismatches are simply timing differences.

### Example

Subledger:
31 Dec

Claimsmapping:
01 Jan

### Potential reasons

Cutoff
Posting delay
Batch processing
Late-arriving data
Different extraction time

Late-arriving records are a recognized reconciliation issue and need an explicit policy rather than being automatically treated as errors.

---

## Human Check #5 — Check adjustments

### Look for

Original transaction
Adjustment
Reversal
Correction
Refund
Write-off
Chargeback

### For example

| Field | Value |
| --- | --- |
| Original | +10,000 |
| Adjustment | -500 |
| Final | 9,500 |

One system may contain the original + adjustment while another contains only the final value.

That creates an apparent mismatch even though both systems are internally correct.

---

## Human Check #6 — Check business mapping rules

### For example

Account A → Claim Type X
Account B → Claim Type Y

If Claimsmapping uses a mapping table, check whether the mapping changed.

### Potential causes

New account introduced
Old account retired
Mapping table outdated
Wrong mapping version
Manual override
Incorrect lookup
---

## Human Check #7 — Check source-system changes

### Ask

Did anything change around the date when mismatches started?

### Examples

New application release
New ETL pipeline
New source file
New column
New account
New business rule
New mapping table
New vendor
New data format

A sudden mismatch beginning on one specific date is a very strong clue.

---

## Human Check #8 — Check historical records

### Compare

2023
2024
2025
2026

### If

2023 → 99.8% match
2024 → 99.7%
2025 → 99.8%
2026 → 91%

then you should investigate what changed in 2026 rather than manually examining thousands of records.

44. Human Check #9 — Trace an individual mismatch to the source

### For important exceptions, trace

Subledger
↓
Original source
↓
Transformation
↓
Claimsmapping
↓
Final output

This gives you the actual root cause rather than just saying:

"Amount doesn't match."

45. Human Check #10 — Determine whether mismatch is acceptable

### Every exception should ultimately become

---

# VALID DIFFERENCE

or

---

# TRUE DATA ERROR

### For example

| Difference | Possible result |
| --- | --- |
| Date +1 day | Valid timing difference |
| Amount ₹0.01 | Valid rounding |
| Status casing | Formatting issue |
| Missing claim | True issue |
| Duplicate claim | True issue |
| Account mismatch | Mapping issue |
| New claim in source | Timing issue |
| Reversal | Valid business adjustment |
| Unknown | Needs investigation |
---

## WHY CLAIMSMAPPING MAY NOT MATCH SUBLEDGER

Here's the practical root-cause library I would keep.

1. Data extraction problems
Missing source records
Partial file
Wrong reporting period
Failed extraction
Truncated file
Wrong source system
Incorrect filters
Late-arriving records
B. Mapping problems
Wrong column mapped
Wrong source column
Mapping table outdated
Mapping rule changed
Mapping code missing
New code not mapped
Incorrect account mapping
Incorrect claim-type mapping
C. Duplicate problems
Duplicate source records
Duplicate load
Duplicate claim lines
Incorrect join
Many-to-many join
Retry/reprocessing created duplicates
D. Transformation problems
Incorrect calculation
Wrong formula
Wrong sign
Wrong percentage
Tax incorrectly included/excluded
Currency conversion
Rounding
Decimal precision
Unit conversion
Aggregation error
E. Timing problems
Different extraction times
Posting delay
Late-arriving data
Month-end cutoff
Fiscal-year difference
Time-zone conversion
Backdated transaction
Future-dated transaction
F. Business-process differences
Adjustment
Reversal
Refund
Chargeback
Write-off
Cancellation
Partial payment
Partial settlement
Manual journal entry

Subledger/ledger reconciliations specifically need to distinguish genuinely unreconciled items from entries that exist on one side for legitimate reasons, such as manual postings.

G. Formatting differences
Upper/lowercase
Leading zeros
Spaces
Special characters
Different date format
Decimal formatting
Currency symbols
NULL vs blank
NULL vs zero
H. Master-data problems
Customer ID changed
Account ID changed
Product ID changed
Claim ID changed
Entity renamed
Old code retired
New code introduced

Master-data inconsistencies are a common cause of claims reconciliation problems because the same entity can appear under different codes/names across systems.

---

## The reconciliation architecture I'd recommend for you

Given the work you're already doing with Python/CSV/SAS/Excel, I'd build this:

```
            ┌─────────────────┐
            │    SUBLEDGER    │
            │  Source of Truth│
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │  NORMALIZATION   │
            │                 │
            │ dates            │
            │ strings          │
            │ amounts          │
            │ nulls            │
            │ codes            │
            └────────┬────────┘
                     │
                     │
            ┌────────▼────────┐
            │   CLAIMSMAPPING  │
            │                  │
            └────────┬─────────┘
                     │
                     ▼
         ┌────────────────────────┐
         │ PYTHON RECONCILIATION │
         └───────────┬────────────┘
                     │
   ┌─────────────────┼──────────────────┐
   ▼                 ▼                  ▼
```
Completeness       Accuracy           Integrity
```
   │                 │                  │
   ▼                 ▼                  ▼
```
| missing keys | amount diff | duplicates |
| --- | --- | --- |
| extra keys | field diff | nulls |
| row counts | date diff | invalid values |
| partitions | hash diff | referential |
```
   │                 │                  │
   └─────────────────┼──────────────────┘
                     ▼
             EXCEPTION TABLE
                     │
                     ▼
              ┌─────────────┐
              │     AI      │
              │             │
              │ clustering  │
              │ explanation │
              │ patterns    │
              │ fuzzy match │
              │ root cause  │
              └──────┬──────┘
                     │
                     ▼
              HUMAN REVIEW
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   Valid difference         True issue
         │                       │
         ▼                       ▼
   Document reason        Correct source/
                          mapping/process
```
---

## The final reconciliation output

### I would not make your Python script simply print

PASS
FAIL

Instead, generate an Exception/Recon Report.

Summary
Metric	Result
Subledger rows	4,511
Claimsmapping rows	4,498
Row difference	-13
Matching keys	4,470
Missing Claimsmapping	41
Extra Claimsmapping	28
Amount mismatches	18
Date mismatches	9
Status mismatches	14
Duplicate keys	3
Null critical keys	0

### Then

Exception detail
Claim ID	Exception	Subledger	Claimmapping	Variance	AI category	Human status
10001	Amount	10,000	9,500	-500	Adjustment?	Review
10002	Date	15-Aug	16-Aug	1 day	Timing	Valid
10003	Missing	Exists	—	—	Missing record	Review
10004	Status	Paid	PAID	—	Formatting	Valid
10005	Duplicate	1	2	—	Duplicate	Review

This becomes much more useful to your senior/data analysts than a simple "data doesn't match" report.

---

## One important design principle

### I'd strongly recommend separating three concepts

---

## Technical mismatch

The values are different.

### Example

10000 != 9500
---

## Business-valid difference

The values are different, but they are supposed to be different because of a documented rule.

### Example

Gross amount vs net amount
---

## Data defect

The values are different and there is no legitimate business explanation.

### Example

Wrong account mapping

This separation is critical. A reconciliation is not successful merely because numbers match, and a mismatch is not automatically an error. Good reconciliation explicitly accounts for intentional exclusions, transformations, merges and legitimate differences.

---

## My recommended priority for your actual project

Since you're currently working with Claimsmapping + Subledger, I would implement the checks in this order:

Phase 1 — Python

### Must have

Schema comparison
Row count
Distinct key count
Duplicate key detection
Missing keys
Extra keys
Field-level comparison
Amount/control-total reconciliation
Date reconciliation
Null checks
Data-type checks
Categorical/value checks
Counts by year/quarter/month
Amount totals by year/quarter/month
Hash comparison for matched records
Phase 2 — AI

Then give AI only the exception dataset, rather than blindly giving it millions of raw rows.

### Have AI

Identify semantic column mappings
Identify equivalent codes
Group similar mismatches
Identify systematic patterns
Suggest likely root causes
Detect timing patterns
Detect transformation patterns
Identify possible duplicates
Fuzzy-match questionable records
Produce a human-readable explanation
Phase 3 — Human

### Human validates

What is the actual business key?
Are the two datasets at the same granularity?
Are amounts gross/net?
Are dates transaction/posting dates?
Are adjustments/reversals involved?
Are there intentional exclusions?
Did mapping rules change?
Did the source system change?
Is the mismatch acceptable?
What corrective action is required?