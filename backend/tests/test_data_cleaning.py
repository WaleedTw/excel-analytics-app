import pandas as pd

from app.data_cleaning import clean_dataset, parse_numeric_value
from app.excel_service import infer_columns, profile_quality


def test_currency_text_is_typed_and_structural_summary_is_excluded():
    source = pd.DataFrame({
        "Product ID": [1001, 1002, "Total Summary"],
        "Category": ["Electronics", "Electronics", None],
        "Product Name": ["Android Smartphone", "27-inch Monitor", None],
        "Unit Price (USD)": ["$1,200.00", "$950.00", "$1,075.00 (Avg)"],
        "Quantity Sold": [12, 8, "20"],
        "Total Sales (USD)": ["$14,400.00", "$7,600.00", "$22,000.00"],
    })
    source_copy = source.copy(deep=True)
    source_profiles = infer_columns(source)

    cleaned, audit = clean_dataset(source, source_profiles)
    cleaned_profiles = infer_columns(cleaned)
    quality = profile_quality(cleaned, cleaned_profiles)
    roles = {profile.name: profile.semantic_role for profile in cleaned_profiles}

    pd.testing.assert_frame_equal(source, source_copy)
    assert roles["Product ID"] == "identifier"
    assert roles["Unit Price (USD)"] == "measure"
    assert roles["Total Sales (USD)"] == "measure"
    assert len(cleaned) == 2
    assert cleaned["Unit Price (USD)"].mean() == 1075
    assert cleaned["Quantity Sold"].sum() == 20
    assert cleaned["Total Sales (USD)"].sum() == 22000
    assert audit.excluded_summary_rows == [4]
    assert audit.numeric_conversions == 4
    assert audit.invalid_numeric_cells == 0
    assert quality.invalid_values == 0


def test_numeric_parser_supports_arabic_digits_and_accounting_negatives():
    assert parse_numeric_value("١٬٢٣٤٫٥٠ ر.س") == 1234.5
    assert parse_numeric_value("($2,500.00)") == -2500
    assert parse_numeric_value("=1+1") is None
    assert parse_numeric_value("12abc") is None


def test_safe_row_formulas_are_calculated_and_empty_columns_are_excluded():
    source = pd.DataFrame({
        "المنتج": ["أ", "ب", "الإجمالي العام"],
        "الكمية": [2, 3, "=SUM(B2:B3)"],
        "سعر الوحدة": [10, 20, None],
        "إجمالي المبلغ": ["=B2*C2", "=B3*C3", "=SUM(D2:D3)"],
        "ملاحظات فارغة": [None, None, None],
    })
    profiles = infer_columns(source)

    cleaned, audit = clean_dataset(source, profiles)

    assert cleaned["إجمالي المبلغ"].tolist() == [20.0, 60.0]
    assert "ملاحظات فارغة" not in cleaned.columns
    assert audit.excluded_summary_rows == [4]
    assert audit.excluded_empty_columns == ["ملاحظات فارغة"]
    assert audit.formula_calculations == 2


def test_formula_evaluator_rejects_cross_row_and_function_formulas():
    source = pd.DataFrame({
        "الكمية": [2, 3],
        "سعر الوحدة": [10, 20],
        "إجمالي المبلغ": ["=A3*B3", "=SUM(A2:B2)"],
    })

    cleaned, audit = clean_dataset(source, infer_columns(source))

    assert cleaned["إجمالي المبلغ"].isna().all()
    assert audit.formula_calculations == 0
    assert audit.invalid_numeric_cells == 2


def test_missing_sales_and_sequential_identifier_are_repaired_with_source_rows():
    source = pd.DataFrame({
        "Product ID": [1001, 1002, 1003, 1004, 1005, 1006, 1007, None, 1009],
        "Product Name": [f"Product {index}" for index in range(1, 10)],
        "Unit Price": [100, 200, 300, 180, 250, 350, 310, 450, 90],
        "Quantity Sold": [1, 2, 3, 15, 5, 6, 7, 22, 9],
        "Total Sales": [100, 400, 900, None, 1250, 2100, 2170, 9900, 810],
    })

    cleaned, audit = clean_dataset(source, infer_columns(source))

    assert cleaned.loc[3, "Total Sales"] == 2700
    assert cleaned.loc[7, "Product ID"] == 1008
    assert audit.missing_values_before == {"Product ID": 1, "Total Sales": 1}
    assert audit.missing_locations == {"Product ID": [9], "Total Sales": [5]}
    assert audit.remaining_missing_values == {}
    assert {(action["column"], action["strategy"]) for action in audit.imputation_actions} == {
        ("Product ID", "sequential"),
        ("Total Sales", "derived"),
    }


def test_fallback_imputation_is_role_aware_and_ambiguous_values_are_retained():
    source = pd.DataFrame({
        "Revenue (SAR)": [100.0, None, 300.0],
        "Score": [1.0, None, 100.0],
        "Category": ["A", None, "B"],
        "Order Date": ["2025-01-01", None, "2025-01-03"],
        "Reference ID": ["A-10", None, "B-99"],
    })
    profiles = [
        {"name": "Revenue (SAR)", "semantic_role": "measure"},
        {"name": "Score", "semantic_role": "measure"},
        {"name": "Category", "semantic_role": "dimension"},
        {"name": "Order Date", "semantic_role": "date"},
        {"name": "Reference ID", "semantic_role": "identifier"},
    ]

    cleaned, audit = clean_dataset(source, profiles)

    assert cleaned.loc[1, "Revenue (SAR)"] == 200
    assert cleaned.loc[1, "Score"] == 50.5
    assert cleaned.loc[1, "Category"] == "غير محدد"
    assert pd.isna(cleaned.loc[1, "Order Date"])
    assert pd.isna(cleaned.loc[1, "Reference ID"])
    strategies = {action["column"]: action["strategy"] for action in audit.imputation_actions}
    assert strategies == {
        "Revenue (SAR)": "mean",
        "Score": "median",
        "Category": "label",
        "Order Date": "retained",
        "Reference ID": "retained",
    }
    assert audit.remaining_missing_values == {"Order Date": 1, "Reference ID": 1}


def test_only_exact_duplicate_rows_are_removed_and_audited():
    source = pd.DataFrame({
        "Category": ["A", "A", "A"],
        "Amount": [10, 10, 11],
    })

    cleaned, audit = clean_dataset(source, infer_columns(source))

    assert cleaned.to_dict(orient="records") == [
        {"Category": "A", "Amount": 10.0},
        {"Category": "A", "Amount": 11.0},
    ]
    assert audit.removed_duplicate_rows == [3]


def test_manual_missing_values_are_applied_by_excel_row_and_audited():
    source = pd.DataFrame({
        "Product ID": [1001, None, 1003],
        "Unit Price": [100, 200, 300],
        "Quantity Sold": [1, 2, 3],
        "Total Sales": [100, None, 900],
    })
    overrides = [
        {"column": "Product ID", "source_row": 3, "value": "1002"},
        {"column": "Total Sales", "source_row": 3, "value": "400"},
    ]

    cleaned, audit = clean_dataset(source, infer_columns(source), "manual", overrides)

    assert cleaned.loc[1, "Product ID"] == "1002"
    assert cleaned.loc[1, "Total Sales"] == 400
    assert audit.missing_value_mode == "manual"
    assert audit.output_source_rows == [2, 3, 4]
    assert audit.remaining_missing_values == {}
    assert all(action["strategy"] == "manual" for action in audit.imputation_actions)


def test_manual_mode_retains_cells_the_user_did_not_fill():
    source = pd.DataFrame({"Category": ["A", None], "Amount": [10, None]})
    profiles = [
        {"name": "Category", "semantic_role": "dimension"},
        {"name": "Amount", "semantic_role": "measure"},
    ]

    cleaned, audit = clean_dataset(source, profiles, "manual", [])

    assert cleaned.iloc[1].isna().all()
    assert audit.remaining_missing_values == {"Category": 1, "Amount": 1}
    assert all(action["strategy"] == "retained" for action in audit.imputation_actions)