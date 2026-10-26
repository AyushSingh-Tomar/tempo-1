import datetime as dt
import io
from decimal import Decimal as D

import openpyxl
import pytest

from bordereaux.core.exceptions import ValidationError
from bordereaux.reconciliation import expr as E
from bordereaux.reconciliation.combine import combine_tables
from bordereaux.reconciliation.encoding import decide_encoding
from bordereaux.reconciliation.engine import reconcile
from bordereaux.reconciliation.readers import list_sheets, read_csv, read_table, read_xlsx
from bordereaux.reconciliation.schema import build_schema_summary, infer_type, parse_date, slug

pytestmark = pytest.mark.unit


# --- encoding -------------------------------------------------------------------


def test_utf8_detected_and_rechecked_against_single_byte_reading():
    text = "Name,Amount\nCafé Müller,10\nNaïve Søn,20\n"
    d = decide_encoding(text.encode("utf-8"))
    assert d.chosen == "utf-8" and d.method == "DETECTED"
    assert d.differences, "the re-check shows what the rival reading would change"
    rival = next(c for c in d.candidates if c.encoding == "iso8859-1")
    assert rival.mojibake_pairs > 0


def test_cp1252_text_is_not_read_as_utf8():
    text = "Name,Note\nSmith,“quoted” €5\n"
    d = decide_encoding(text.encode("cp1252"))
    assert d.chosen == "cp1252"
    utf8 = next(c for c in d.candidates if c.encoding == "utf-8")
    assert not utf8.decodes_cleanly


def test_plain_ascii_all_encodings_agree():
    d = decide_encoding(b"a,b\n1,2\n")
    assert d.all_agree and not d.differences


def test_user_forced_encoding_is_validated_and_warned():
    d = decide_encoding("Café".encode("utf-8"), user_encoding="latin-1")
    assert d.chosen == "iso8859-1" and d.method == "USER" and d.warnings
    with pytest.raises(ValueError):
        decide_encoding(b"x", user_encoding="not-a-codec")


def test_candidate_dropdown_restricts_search():
    d = decide_encoding("Café".encode("cp1252"), candidates=["utf-8", "cp1252"])
    assert d.chosen == "cp1252" and {c.encoding for c in d.candidates} == {"utf-8", "cp1252"}


def test_bom_decides():
    assert decide_encoding(b"\xef\xbb\xbfa,b\n").chosen == "utf-8-sig"


# --- readers --------------------------------------------------------------------


def _xlsx(sheets: dict) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_csv_delimiter_sniffing_and_duplicate_headers():
    t = read_csv(b"A;B;A\n1;2;3\n", "utf-8")
    assert t.columns == ["A", "B", "A_2"] and t.rows[0]["_source_row"] == 2


def test_xlsx_sheets_and_header_row():
    content = _xlsx({"Notes": [["x"]], "Data": [["title"], ["Treaty", "Amt"], ["T1", 5]]})
    assert list_sheets("XLSX", content) == ["Notes", "Data"]
    t = read_xlsx(content, "Data", header_row=2)
    assert t.columns == ["Treaty", "Amt"] and t.rows == [{"Treaty": "T1", "Amt": 5, "_source_row": 3}]
    with pytest.raises(ValidationError):
        read_table("XLSX", content, "Missing", None)


def test_sas_reader_uses_pyreadstat(monkeypatch):
    import pyreadstat

    class Meta:
        column_names = ["TREATY", "AMT"]

    monkeypatch.setattr(
        pyreadstat,
        "read_sas7bdat",
        lambda path, **kw: ({"TREATY": ["T1", "T2"], "AMT": [1.5, float("nan")]}, Meta()),
    )
    t = read_table("SAS7BDAT", b"fake", "(whole file)", "utf-8")
    assert t.columns == ["TREATY", "AMT"] and t.rows[1]["AMT"] is None and t.rows[0]["AMT"] == 1.5


# --- schema / combine -----------------------------------------------------------


def test_infer_type_and_dates():
    assert infer_type(["1", "2"]) == "INTEGER" and infer_type(["1.5", "2"]) == "DECIMAL"
    assert infer_type(["2024-01-31", "31/01/2024"]) == "DATE" and infer_type(["a", "b"]) == "STRING"
    assert parse_date("03/04/2024", day_first=True)[0].isoformat() == "2024-04-03"
    assert parse_date("03/04/2024", day_first=False)[0].isoformat() == "2024-03-04"
    assert parse_date("31/01/2024")[1] is False and parse_date("03/04/2024")[1] is True
    assert slug("Gross Prem.") == "gross_prem"


def _tables():
    a = {
        "id": "a", "file": "q1.csv", "sheet": "(whole file)",
        "columns": ["Treaty ID", "Booking Date", "Gross Premium"],
        "rows": [
            {"Treaty ID": "T1", "Booking Date": "15/01/2024", "Gross Premium": "1,000.50", "_source_row": 2},
            {"Treaty ID": "T2", "Booking Date": "20/02/2024", "Gross Premium": "200", "_source_row": 3},
        ],
    }
    b = {
        "id": "b", "file": "q3.xlsx", "sheet": "Data",
        "columns": ["treaty_id", "booking_date", "gross_premium", "Extra Col"],
        "rows": [
            {"treaty_id": "T1", "booking_date": dt.datetime(2024, 8, 5), "gross_premium": 300, "Extra Col": "x", "_source_row": 2}
        ],
    }
    return [a, b]


def test_schema_summary_common_unique_partial():
    s = build_schema_summary(_tables())
    assert s["common_columns"] == ["booking_date", "gross_premium", "treaty_id"]
    assert s["unique_columns"] == [{"column": "extra_col", "table": "b"}]


def test_combine_normalises_dates_numbers_and_lists_periods():
    out = combine_tables(_tables())
    r = out["report"]
    assert [row["booking_date"] for row in out["rows"]] == ["2024-01-15", "2024-02-20", "2024-08-05"]
    assert out["rows"][0]["gross_premium"] == "1000.50"
    assert r["years"] == [2024] and [q["period"] for q in r["quarters"]] == ["2024-Q1", "2024-Q3"]
    assert r["period_column"] == "booking_date" and out["rows"][2]["_quarter"] == "Q3"
    assert {f["file"] for f in r["files"]} == {"q1.csv", "q3.xlsx"}
    assert out["rows"][2]["_source_file"] == "q3.xlsx"


def test_alias_merges_two_columns_into_one():
    t = _tables()
    t[1]["columns"][2] = "Gross Prem"
    t[1]["rows"][0]["Gross Prem"] = t[1]["rows"][0].pop("gross_premium")
    out = combine_tables(t, aliases={"gross_prem": "gross_premium"})
    assert "gross_prem" not in out["columns"] and out["rows"][2]["gross_premium"] == "300"


def test_ambiguous_dates_warn_and_respect_setting():
    t = [{"id": "a", "file": "f", "sheet": "s", "columns": ["d"], "rows": [{"d": f"0{i}/04/2024", "_source_row": i} for i in range(1, 6)]}]
    dayfirst = combine_tables(t, day_first=True)
    monthfirst = combine_tables(t, day_first=False)
    assert dayfirst["rows"][0]["d"] == "2024-04-01" and monthfirst["rows"][0]["d"] == "2024-01-04"
    assert any("ambiguous" in w for w in dayfirst["report"]["warnings"])


# --- expressions ----------------------------------------------------------------


def test_expression_parse_and_eval():
    ast = E.parse_expression("bordereaux.a + b.b * 2 - abs(-3)")
    assert {(r.side, r.column) for r in E.refs(ast)} == {("bordereaux", "a"), ("bordereaux", "b")}
    assert E.evaluate(ast, lambda c: {"a": D(10), "b": D(4)}[c]) == D(15)
    assert E.split_rule("bordereaux.a + bordereaux.b = subledger.c") == ("bordereaux.a + bordereaux.b", "=", "subledger.c")
    assert E.split_rule("b.a <= s.c")[1] == "<="
    for bad in ("", "bordereaux.a +", "foo.a + 1", "bordereaux.a ** 2", "__import__('os')"):
        with pytest.raises(ValidationError):
            E.parse_expression(bad)
    with pytest.raises(E.DivisionByZero):
        E.evaluate(E.parse_expression("1 / (b.a - b.a)"), lambda c: D(1))


# --- engine ---------------------------------------------------------------------

B = [
    {"treaty_id": "T1", "_period": "2024-Q1", "gross": "100", "tax": "10"},
    {"treaty_id": "T1", "_period": "2024-Q1", "gross": "50", "tax": "5"},
    {"treaty_id": "T2", "_period": "2024-Q1", "gross": "200", "tax": "20"},
    {"treaty_id": "T3", "_period": "2024-Q2", "gross": "10", "tax": "1"},
]
S = [
    {"treaty_ref": "t1", "_period": "2024-Q1", "total": "165"},
    {"treaty_ref": "T2", "_period": "2024-Q1", "total": "210"},
    {"treaty_ref": "T9", "_period": "2024-Q1", "total": "5"},
]
COLS = {"bordereaux": set(B[0]), "subledger": set(S[0])}
GROUP = [{"bordereaux": "treaty_id", "subledger": "treaty_ref"}]
RULE = [{"expression": "bordereaux.gross + bordereaux.tax = subledger.total"}]


def test_reconcile_groups_full_outer_join_and_statuses():
    res = reconcile(B, S, COLS, RULE, GROUP, None, {"absolute": "0.01"})
    rule = res["rules"][0]
    by = {g["labels"][0].upper(): g for g in rule["groups"]}
    assert by["T1"]["status"] == "MATCHED" and by["T1"]["bordereaux_value"] == "165.00"  # key match ignores case
    assert by["T2"]["status"] == "VARIANCE" and by["T2"]["variance"] == "10.00"
    assert by["T3"]["status"] == "ONLY_IN_BORDEREAUX" and by["T9"]["status"] == "ONLY_IN_SUBLEDGER"
    assert rule["counts"] == {"MATCHED": 1, "VARIANCE": 1, "ONLY_IN_BORDEREAUX": 1, "ONLY_IN_SUBLEDGER": 1}
    assert res["status"] == "UNRECONCILED"


def test_filters_apply_to_chosen_side_or_both():
    f = [{"side": "both", "column": "_period", "op": "in", "values": ["2024-Q1"]}]
    res = reconcile(B, S, COLS, RULE, GROUP, f, None)
    assert {g["labels"][0].upper() for g in res["rules"][0]["groups"]} == {"T1", "T2", "T9"}
    assert res["rows_in_scope"]["bordereaux"] == 3
    f = [{"side": "bordereaux", "column": "treaty_id", "op": "in", "values": ["t1"]}]
    res = reconcile(B, S, COLS, RULE, GROUP, f, None)
    assert res["rows_in_scope"] == {"bordereaux": 2, "subledger": 3, "bordereaux_total": 4, "subledger_total": 3}


def test_total_grain_and_offsetting_differences_flagged():
    b = [{"treaty_id": "A", "gross": "100", "tax": "0"}, {"treaty_id": "B", "gross": "-100", "tax": "0"}]
    s = [{"treaty_ref": "A", "total": "0"}, {"treaty_ref": "B", "total": "0"}]
    cols = {"bordereaux": set(b[0]), "subledger": set(s[0])}
    res = reconcile(b, s, cols, RULE, [], None, None)
    assert res["rules"][0]["status"] == "RECONCILED"
    res = reconcile(b, s, cols, RULE, GROUP, None, None)
    r = res["rules"][0]
    assert r["status"] == "UNRECONCILED" and r["offsetting_differences"] is True and r["totals"]["within_tolerance"]


def test_tolerance_percentage_or_absolute():
    res = reconcile(B, S, COLS, RULE, GROUP, None, {"absolute": "0", "percentage": "0.05"})
    by = {g["labels"][0].upper(): g["status"] for g in res["rules"][0]["groups"]}
    assert by["T2"] == "MATCHED"  # 10 / 210 = 4.8% <= 5%


def test_rule_validation():
    for expr in (
        "bordereaux.gross = bordereaux.tax",
        "subledger.total = subledger.total",
        "bordereaux.nope = subledger.total",
        "bordereaux.gross",
    ):
        with pytest.raises(ValidationError):
            reconcile(B, S, COLS, [{"expression": expr}], GROUP, None, None)
    res = reconcile(B, S, COLS, [{"expression": "subledger.total = bordereaux.gross + bordereaux.tax"}], GROUP, None, None)
    assert res["rules"][0]["bordereaux_expression"].startswith("(bordereaux.gross")
