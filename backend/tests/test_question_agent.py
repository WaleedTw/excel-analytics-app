import pandas as pd
import pytest
import app.question_agent as question_agent

from app.question_agent import (
    QuestionIntent,
    QuestionUnderstandingError,
    answer_data_question,
    create_agent_query_plan,
    create_safe_query_plan,
    execute_safe_plan,
)
from app.schemas import AnalysisQuestion, AnalysisResponse, ChartSeries, ChartSpec, DashboardSpec, ResultValue, TableSpec
from app.service import AnalysisService


def business_frame():
    return pd.DataFrame([
        ["Jarir", 2022, "Q1", 2_280_000_000, 524_400_000],
        ["Jarir", 2022, "Q2", 2_100_000_000, 462_000_000],
        ["Jarir", 2022, "Q3", 2_610_000_000, 652_500_000],
        ["Jarir", 2022, "Q4", 2_400_000_000, 521_100_000],
        ["Jarir", 2024, "Q1", 2_650_000_000, 848_000_000],
        ["Jarir", 2024, "Q2", 2_400_000_000, 744_000_000],
        ["Jarir", 2024, "Q3", 3_120_000_000, 1_150_000_000],
        ["Jarir", 2024, "Q4", 2_610_000_000, 858_000_000],
        ["Nahdi", 2024, "Q1", 2_480_000_000, 620_000_000],
        ["Nahdi", 2024, "Q2", 2_550_000_000, 643_000_000],
        ["Nahdi", 2024, "Q3", 2_490_000_000, 650_000_000],
        ["Nahdi", 2024, "Q4", 2_560_000_000, 687_000_000],
        ["SACO", 2022, "Q1", 305_200_000, 15_260_000],
        ["SACO", 2022, "Q2", 321_400_000, 16_070_000],
        ["SACO", 2022, "Q3", 272_100_000, 13_605_000],
        ["SACO", 2022, "Q4", 260_400_000, 13_020_000],
    ], columns=["Company", "Year", "Quarter", "Total Revenue (SAR)", "E-com Revenue (SAR)"])


COLUMNS = [
    {"name": "Company", "semantic_role": "dimension"},
    {"name": "Year", "semantic_role": "dimension"},
    {"name": "Quarter", "semantic_role": "dimension"},
    {"name": "Total Revenue (SAR)", "semantic_role": "measure"},
    {"name": "E-com Revenue (SAR)", "semantic_role": "measure"},
]


def dashboard():
    result = ResultValue(value=1, operation="count", source_columns=[], query="SELECT 1")
    return DashboardSpec(
        title="اختبار", description="لوحة اختبار موثقة للأسئلة.", charts=[ChartSpec(
            id="test", title="اختبار", type="bar", categories=["A"],
            series=[ChartSeries(name="Total Revenue (SAR)", values=[1])],
            result_refs=["known"],
        )], tables=[TableSpec(id="test", title="اختبار", columns=[], rows=[])],
        computed_results={"known": result}, layout=["charts"],
        executive_summary="ملخص تنفيذي صالح للاختبار.",
    )


def ask(question: str):
    return answer_data_question(question, business_frame(), COLUMNS, dashboard())


def test_jarir_revenue_in_2022_is_computed_from_four_quarters():
    answer = ask("كم إيرادات جرير في 2022؟")
    assert "9.39 مليار ريال" in answer["answer"]
    assert "الشركات" in answer["answer"]
    assert "Jarir" in answer["answer"]


def test_top_company_in_third_quarter():
    answer = ask("ما أعلى شركة في الربع الثالث؟")
    assert "Jarir" in answer["answer"]
    assert "Q3" in answer["answer"]


def test_compare_jarir_and_nahdi_in_2024():
    answer = ask("قارن جرير والنهدي عام 2024.")
    assert "Jarir" in answer["answer"]
    assert "Nahdi" in answer["answer"]
    assert "2024" in answer["answer"]


def test_generic_company_dimension_is_not_mistaken_for_an_unknown_company():
    plan = create_safe_query_plan(
        "قارن Total Revenue حسب Company",
        business_frame(),
        COLUMNS,
    )

    assert plan.operation == "comparison"
    assert plan.group_by == "Company"
    assert plan.filters == ()


@pytest.mark.parametrize("question", [
    "قارن إجمالي الإيرادات بين الشركات",
    "قارن إجمالي الإيرادات عبر الشركات",
    "Compare total revenue between companies",
])
def test_comparison_connectors_are_not_mistaken_for_company_names(question):
    plan = create_safe_query_plan(question, business_frame(), COLUMNS)

    assert plan.operation == "comparison"
    assert plan.group_by == "Company"
    assert plan.measure == "Total Revenue (SAR)"
    assert plan.filters == ()


def test_compare_all_companies_returns_verified_results():
    result = ask("قارن إجمالي الإيرادات بين الشركات")

    assert "مقارنة إجمالي الإيرادات حسب الشركات" in result["answer"]
    assert all(company in result["answer"] for company in ("Jarir", "Nahdi", "SACO"))


def test_currency_suffix_is_not_mistaken_for_an_unknown_company():
    plan = create_safe_query_plan(
        "ما أعلى 3 Company حسب Total Revenue (SAR)؟",
        business_frame(),
        COLUMNS,
    )

    assert plan.operation == "ranking"
    assert plan.group_by == "Company"
    assert plan.measure == "Total Revenue (SAR)"
    assert plan.limit == 3


def test_verified_planner_recovers_when_semantic_service_mistakes_currency_for_entity(monkeypatch):
    monkeypatch.setattr(question_agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(question_agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        question_agent,
        "_groq_question_intent",
        lambda *_args, **_kwargs: QuestionIntent(
            answerable=False,
            reason="SAR was treated as an unknown company.",
            unresolved_terms=["SAR"],
        ),
    )

    plan = create_agent_query_plan(
        "ما أعلى 3 Company حسب Total Revenue (SAR)؟",
        business_frame(),
        COLUMNS,
    )

    assert plan.operation == "ranking"
    assert plan.group_by == "Company"
    assert plan.measure == "Total Revenue (SAR)"
    assert plan.limit == 3


def test_verified_planner_recovers_when_semantic_service_mistakes_between_for_entity(monkeypatch):
    monkeypatch.setattr(question_agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(question_agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(
        question_agent,
        "_groq_question_intent",
        lambda *_args, **_kwargs: QuestionIntent(
            answerable=False,
            reason="The comparison connector was treated as an unknown company.",
            unresolved_terms=["بين"],
        ),
    )

    plan = create_agent_query_plan(
        "قارن إجمالي الإيرادات بين الشركات",
        business_frame(),
        COLUMNS,
    )

    assert plan.operation == "comparison"
    assert plan.group_by == "Company"
    assert plan.measure == "Total Revenue (SAR)"
    assert plan.filters == ()


def test_ecommerce_growth_uses_first_and_last_year():
    plan = create_safe_query_plan("كم نسبة نمو المبيعات الإلكترونية؟", business_frame(), COLUMNS)
    assert plan.operation == "growth"
    assert plan.measure == "E-com Revenue (SAR)"
    result = execute_safe_plan(plan, business_frame())
    assert result.rows[0]["label"] == "2022"
    assert result.rows[-1]["label"] == "2024"


def test_lowest_quarter_for_saco():
    answer = ask("ما أقل ربع أداءً لدى ساكو؟")
    assert "Q4" in answer["answer"]
    assert "SACO" in answer["answer"]


def test_every_verified_answer_reports_duckdb_and_pandas_check():
    answer = ask("كم إيرادات جرير في 2022؟")
    assert any("DuckDB + Pandas" in source for source in answer["sources"])


def test_top_three_request_returns_three_verified_ranked_items():
    answer = ask("ما أعلى 3 شركات حسب إجمالي الإيرادات؟")
    assert "1." in answer["answer"]
    assert "2." in answer["answer"]
    assert "3." in answer["answer"]
    assert all(company in answer["answer"] for company in ("Jarir", "Nahdi", "SACO"))


def test_cleaning_question_explains_columns_rows_and_actions():
    audit = {
        "missing_values_before": {"Product ID": 1, "Total Sales": 1},
        "missing_locations": {"Product ID": [9], "Total Sales": [5]},
        "remaining_missing_values": {},
        "excluded_summary_rows": [62],
        "imputation_actions": [
            {
                "column": "Product ID", "count": 1, "strategy": "sequential",
                "fill_value": "تسلسل رقمي بزيادة 1", "source_rows": [9],
                "explanation": "أُكمل المعرّف من النمط التصاعدي المثبت.",
            },
            {
                "column": "Total Sales", "count": 1, "strategy": "derived",
                "fill_value": "Quantity Sold × Unit Price", "source_rows": [5],
                "explanation": "أُعيد بناء الإجمالي من الكمية مضروبة في سعر الوحدة.",
            },
        ],
    }

    result = answer_data_question(
        "ما القيم الناقصة وكيف عولجت؟",
        business_frame(),
        COLUMNS,
        dashboard(),
        audit,
    )

    assert "Product ID" in result["answer"]
    assert "Total Sales" in result["answer"]
    assert "صفوف Excel 9" in result["answer"]
    assert "صفوف Excel 5" in result["answer"]
    assert "لم تبقَ قيم ناقصة" in result["answer"]


def test_unknown_company_is_not_silently_replaced_with_all_rows():
    with pytest.raises(QuestionUnderstandingError, match="العثيم.*غير موجودة"):
        ask("كم إيرادات العثيم؟")


def test_any_unknown_company_is_not_silently_replaced_with_all_rows():
    with pytest.raises(QuestionUnderstandingError, match="التويجري.*الشركات المتاحة"):
        ask("كم إيرادات التويجري؟")


def test_semantic_agent_maps_question_before_calculation(monkeypatch):
    intent = QuestionIntent(
        answerable=True,
        operation="aggregate",
        measure="Total Revenue (SAR)",
        filters=[
            {"column": "Company", "values": ["Jarir"]},
            {"column": "Year", "values": [2022]},
        ],
    )
    monkeypatch.setattr(question_agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(question_agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(question_agent, "_groq_question_intent", lambda *_args: intent)

    plan = create_agent_query_plan("كم إيرادات جرير في 2022؟", business_frame(), COLUMNS)

    assert plan.measure == "Total Revenue (SAR)"
    assert plan.filters[0].values == ("Jarir",)
    assert plan.filters[1].values == (2022,)


def test_semantic_agent_cannot_drop_an_unknown_entity(monkeypatch):
    intent = QuestionIntent(
        answerable=True,
        operation="aggregate",
        measure="Total Revenue (SAR)",
        filters=[],
    )
    monkeypatch.setattr(question_agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(question_agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(question_agent, "_groq_question_intent", lambda *_args: intent)

    with pytest.raises(QuestionUnderstandingError, match="التويجري"):
        create_agent_query_plan("كم إيرادات التويجري؟", business_frame(), COLUMNS)


def test_semantic_agent_says_when_information_is_insufficient(monkeypatch):
    intent = QuestionIntent(
        answerable=False,
        reason="اسم الشركة غير موجود في القيم المتاحة.",
        unresolved_terms=["التويجري"],
    )
    monkeypatch.setattr(question_agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(question_agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(question_agent, "_groq_question_intent", lambda *_args: intent)

    with pytest.raises(QuestionUnderstandingError, match="لا توجد معلومات كافية"):
        create_agent_query_plan("كم إيرادات التويجري؟", business_frame(), COLUMNS)


def test_analysis_service_routes_completed_questions_to_verified_dataset_agent():
    service = AnalysisService(graph=object())
    analysis_id = "verified-analysis"
    service.runs[analysis_id] = AnalysisResponse(
        analysis_id=analysis_id,
        status="completed",
        stage="done",
        progress=100,
        dashboard=dashboard(),
        trace=[],
    )
    service.analysis_datasets[analysis_id] = {"frame": business_frame(), "columns": COLUMNS}

    answer = service.ask(analysis_id, AnalysisQuestion(question="كم إيرادات جرير في 2022؟"))

    assert "9.39 مليار ريال" in answer.answer
    assert any("DuckDB + Pandas" in source for source in answer.sources)