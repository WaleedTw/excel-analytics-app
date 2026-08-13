from pathlib import Path

import pandas as pd

from app.config import SAMPLE_DIR
from app.excel_service import infer_columns, inspect_xlsx, preview_sheet, profile_quality, read_sheet


def test_reads_excel_and_detects_sheets(sales_record):
    assert [sheet.name for sheet in sales_record.sheets] == ["المبيعات", "تدقيق الحسابات"]
    assert sales_record.sheets[0].rows == 121
    assert sales_record.sheets[0].columns == 10


def test_preview_and_semantic_inference(sales_record):
    preview = preview_sheet(sales_record.file_id, "المبيعات")
    roles = {column.name: column.semantic_role for column in preview.columns}
    assert roles["التاريخ"] == "date"
    assert roles["الإيرادات"] == "measure"
    assert roles["المدينة"] == "dimension"
    assert len(preview.rows) == 50


def test_messy_quality_profile_detects_issues(messy_record):
    path = Path(SAMPLE_DIR) / "بيانات_غير_مرتبة.xlsx"
    frame = read_sheet(path, "بيانات مختلطة")
    columns = infer_columns(frame)
    quality = profile_quality(frame, columns)
    assert quality.missing_cells >= 3
    assert quality.duplicate_rows >= 1
    assert quality.invalid_values >= 2
    assert quality.outlier_count >= 1
    assert quality.score < 100


def test_ambiguous_column_is_detected(messy_record):
    preview = preview_sheet(messy_record.file_id, "بيانات مختلطة")
    ambiguous = [column.name for column in preview.columns if column.ambiguous]
    assert "رمز_س" in ambiguous


def test_business_time_columns_are_not_mistaken_for_measures():
    frame = pd.DataFrame({
        "Company": ["Jarir", "SACO"],
        "Year": [2022, 2023],
        "Quarter": ["Q1", "Q2"],
        "Total_Revenue": [1000, 1200],
        "Ecom_Percentage": [0.2, 0.3],
    })
    roles = {column.name: column.semantic_role for column in infer_columns(frame)}

    assert roles["Company"] == "dimension"
    assert roles["Year"] == "dimension"
    assert roles["Quarter"] == "dimension"
    assert roles["Total_Revenue"] == "measure"
    assert roles["Ecom_Percentage"] == "measure"


def test_whitespace_only_cells_are_counted_as_missing(tmp_path):
    path = tmp_path / "spaces.xlsx"
    pd.DataFrame({"Company": ["Jarir", "   ", "SACO"], "Sales": [10, 20, 30]}).to_excel(path, index=False)
    frame = read_sheet(path, "Sheet1")
    profiles = infer_columns(frame)
    company = next(profile for profile in profiles if profile.name == "Company")

    assert company.null_count == 1
    assert company.unique_count == 2
