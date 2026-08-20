import pytest
import pandas as pd

from app.analytics import assert_numeric_provenance, build_dashboard, execute_deterministic_analysis
from app.config import SAMPLE_DIR
from app.excel_service import infer_columns, profile_quality, read_sheet
from app.schemas import DashboardSpec, ResultValue


def sales_inputs():
    frame = read_sheet(SAMPLE_DIR / "مبيعات_عربية_مرتبة.xlsx", "المبيعات")
    columns = infer_columns(frame)
    quality = profile_quality(frame, columns)
    return frame, [column.model_dump() for column in columns], quality


def test_duckdb_calculations_reconcile():
    frame, columns, quality = sales_inputs()
    registry, charts, kpis, _, _ = execute_deterministic_analysis(frame, columns, quality)
    assert registry["rows.total"].value == len(frame)
    assert registry["sum.الإيرادات"].value == pytest.approx(frame["الإيرادات"].sum())
    assert len(charts) >= 4
    assert len(kpis) >= 3


def test_dashboard_pydantic_schema_is_valid():
    frame, columns, quality = sales_inputs()
    dashboard = build_dashboard(frame, columns, quality, "المبيعات")
    assert DashboardSpec.model_validate(dashboard)
    assert all(kpi.result_ref in dashboard.computed_results for kpi in dashboard.kpis)
    assert len(dashboard.tables[0].rows) == len(frame)
    assert len(dashboard.detailed_insights) >= 20
    assert "quality.completeness" in dashboard.computed_results
    assert dashboard.dimensions
    assert dashboard.measures
    assert dashboard.value_formats["locale"] == "en-US"


def test_unproven_numeric_claim_is_blocked():
    registry = {"known": ResultValue(value=42, operation="count", source_columns=[], query="SELECT 42")}
    with pytest.raises(ValueError, match="غير موثقة"):
        assert_numeric_provenance(["ظهرت نتيجة مقدارها 999"], registry)


def test_agent_plan_prioritizes_safe_measure_and_builds_business_charts():
    frame = pd.DataFrame({
        "Company": ["Jarir", "Jarir", "SACO", "SACO"],
        "Year": [2022, 2023, 2022, 2023],
        "Quarter": ["Q1", "Q1", "Q1", "Q1"],
        "Total_Revenue": [1000, 1200, 800, 900],
        "Ecom_Revenue": [200, 320, 120, 180],
    })
    profiles = infer_columns(frame)
    quality = profile_quality(frame, profiles)
    plan = {
        "measures": ["Ecom_Revenue", "Total_Revenue"],
        "dimensions": ["Company", "Year", "Quarter"],
        "dates": [],
        "chart_strategy": ["trend", "category_comparison", "share", "distribution"],
    }

    _, charts, kpis, _, _ = execute_deterministic_analysis(
        frame, [profile.model_dump() for profile in profiles], quality, plan,
    )

    assert charts[0].id == "time-line"
    assert charts[1].id == "category-bar"
    assert charts[1].series[0].name == "Ecom_Revenue"
    assert kpis[2].label == "إجمالي Ecom_Revenue"
