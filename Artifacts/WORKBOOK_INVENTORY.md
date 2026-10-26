# Workbook Inventory and Verification

This inventory was verified against the repository's actual fixture set in `Initial provided Info/Test_files` and the existing backend test references.

## Available workbooks

1. `sample_bordereaux_master.xlsx`
2. `test_control_zero_issues.xlsx`
3. `test_std_01_structural.xlsx`
4. `test_std_02_formats.xlsx`
5. `test_std_03_multisheet.xlsx`
6. `test_map_01_exact_fuzzy.xlsx`
7. `test_map_02_semantic.xlsx`
8. `test_map_03_arithmetic_passthrough.xlsx`
9. `test_mcr_01_core_deduction.xlsx`
10. `test_mcr_02_basis_alignment.xlsx`
11. `test_mcr_03_traps.xlsx`
12. `test_mcr_04_signs_totals_ambiguity.xlsx`
13. `test_integration_realistic.xlsx`

## Status

All 13 expected workbooks are present in the repository and are exercised by existing backend tests.

## Typical workbook roles

- `test_std_01_structural.xlsx`: structural and header-row detection
- `test_std_02_formats.xlsx`: format normalization and sign preservation
- `test_std_03_multisheet.xlsx`: multi-sheet selection and sheet filtering
- `test_map_01_exact_fuzzy.xlsx`: exact + fuzzy mapping
- `test_map_02_semantic.xlsx`: semantic mapping, aliasing, ambiguous resolution
- `test_map_03_arithmetic_passthrough.xlsx`: ambiguity-safe passthrough, no financial inference
- `test_mcr_01_core_deduction.xlsx`: ingestion and mapping stress for downstream financial scenarios
- `test_mcr_02_basis_alignment.xlsx`: basis/percentage-preservation validation
- `test_mcr_03_traps.xlsx`: misleading columns and safe unresolved mappings
- `test_mcr_04_signs_totals_ambiguity.xlsx`: sign/zero/total ambiguity handling
- `test_integration_realistic.xlsx`: end-to-end happy path

## Test evidence

The repo currently includes integration and unit tests that target these fixtures, including:

- `backend/tests/integration/test_answer_keys.py` - every workbook above, end to end through the HTTP API, driven by the workbook's own "Treaty Figures" and "Answer Key" sheets (generic per-file check plus focused mapping / cleaning / structure / FX / trap / totals checks). Rows where the app deliberately does not reproduce the key are listed in its `KNOWN_GAPS` with the reason.
- `backend/tests/integration/test_workbooks.py` - pipeline-wide invariants for all workbooks
- `backend/tests/integration/test_sample_master.py`, `test_realistic_answer_key.py` - the two workbooks with their own detailed answer-key tests
- `backend/tests/unit/ingestion/test_ingestion_service.py`
- `backend/tests/integration/test_happy_path.py`
- `backend/tests/unit/mapping/test_mapping_service.py`
- `backend/tests/unit/mapping/test_money_resolution.py`

Total / subtotal / footer rows (e.g. `test_std_01_structural`, `test_mcr_04_signs_totals_ambiguity`) are set aside during cleaning and cross-checked against the data rows (MCR-F1/F2/F3) during financial checks; they never reach the processed file.

These tests validate the ingestion and standardization pipeline without introducing MCR or downstream financial calculations beyond the first-iteration scope.
