from app.i18n import localize_analysis_response, localize_preview_response
from app.schemas import (
    AnalysisResponse, ChartSeries, ChartSpec, ColumnProfile, DashboardSpec,
    InsightSpec, KpiSpec, PreviewResponse, QualityReport, ResultValue, TableSpec,
)


def has_arabic(value: str) -> bool:
    return any("\u0600" <= character <= "\u06ff" for character in value)


def test_english_analysis_localizes_system_copy_but_preserves_workbook_data():
    result = ResultValue(value=42, operation="sum", source_columns=["Revenue"], query="SELECT 42")
    dashboard = DashboardSpec(
        title="تحليل المبيعات",
        description="وصف عربي موثق للوحة.",
        kpis=[KpiSpec(id="revenue", label="إجمالي الإيراد", result_ref="known", format="currency")],
        charts=[ChartSpec(
            id="distribution-revenue", title="نطاق الإيراد", type="bar",
            categories=["الأدنى", "المتوسط", "الأعلى"],
            series=[ChartSeries(name="القيمة", values=[1, 2, 3])],
            result_refs=["known"], y_label="القيمة",
        )],
        tables=[TableSpec(
            id="data", title="تفاصيل البيانات", columns=["اسم العميل", "Revenue"],
            rows=[{"اسم العميل": "أحمد", "Revenue": 42}],
        )],
        computed_results={"known": result}, layout=["kpis", "charts", "table"],
        executive_summary="ملخص تنفيذي عربي صالح للاختبار.",
        detailed_insights=[InsightSpec(title="رؤية", text="بلغت القيمة 42.", result_refs=["known"])],
    )
    response = AnalysisResponse(
        analysis_id="analysis", status="completed", stage="save_analysis", progress=100,
        dashboard=dashboard,
        quality=QualityReport(
            row_count=1, column_count=2, missing_cells=0, missing_rate=0,
            duplicate_rows=0, invalid_values=0, outlier_count=0,
            formula_like_cells=0, score=100, notes=["ملاحظة عربية"],
        ),
    )

    localized = localize_analysis_response(response, "en")
    system_copy = [
        localized.dashboard.title,
        localized.dashboard.description,
        localized.dashboard.executive_summary,
        *[item.label for item in localized.dashboard.kpis],
        *[item.title for item in localized.dashboard.charts],
        *[item.title + item.text for item in localized.dashboard.detailed_insights],
        *localized.quality.notes,
    ]

    assert not any(has_arabic(item) for item in system_copy)
    assert localized.stage == "save_analysis"
    assert localized.dashboard.tables[0].rows[0]["اسم العميل"] == "أحمد"


def test_english_preview_localizes_profile_reason_only():
    preview = PreviewResponse(
        file_id="file", sheet_name="المبيعات", total_rows=1,
        columns=[ColumnProfile(
            name="اسم العميل", inferred_type="text", semantic_role="unknown",
            null_count=0, unique_count=1, sample_values=["أحمد"],
            ambiguous=True, reason="سبب عربي",
        )],
        rows=[{"اسم العميل": "أحمد"}],
    )

    localized = localize_preview_response(preview, "en")

    assert not has_arabic(localized.columns[0].reason)
    assert localized.sheet_name == "المبيعات"
    assert localized.rows[0]["اسم العميل"] == "أحمد"