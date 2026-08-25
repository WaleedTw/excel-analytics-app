from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SheetInfo(BaseModel):
    name: str
    rows: int = Field(ge=0)
    columns: int = Field(ge=0)
    has_data: bool


class WorkbookInfo(BaseModel):
    file_id: str
    original_name: str
    safe_name: str
    size_bytes: int
    mime_type: str
    sheets: list[SheetInfo]
    created_at: datetime


class ColumnProfile(BaseModel):
    name: str
    inferred_type: Literal["date", "number", "category", "text", "unknown"]
    semantic_role: Literal["date", "dimension", "measure", "identifier", "unknown"]
    null_count: int
    unique_count: int
    sample_values: list[Any] = Field(default_factory=list)
    ambiguous: bool = False
    reason: str = ""


class QualityReport(BaseModel):
    row_count: int
    column_count: int
    missing_cells: int
    missing_rate: float = Field(ge=0, le=1)
    duplicate_rows: int
    invalid_values: int
    outlier_count: int
    formula_like_cells: int
    score: int = Field(ge=0, le=100)
    notes: list[str] = Field(default_factory=list)


class AnalysisPlanContent(BaseModel):
    objective: str = Field(min_length=10, max_length=500)
    measures: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    chart_strategy: list[Literal["trend", "category_comparison", "share", "distribution"]] = Field(min_length=1)
    privacy: str = Field(min_length=10, max_length=500)


class AnalysisPlan(AnalysisPlanContent):
    mode: Literal["mock", "ollama", "groq"]
    model: str


class ResultValue(BaseModel):
    value: int | float | str
    operation: str
    source_columns: list[str]
    query: str


class KpiSpec(BaseModel):
    id: str
    label: str
    result_ref: str
    format: Literal["number", "currency", "percent", "decimal"]
    tone: Literal["primary", "positive", "neutral", "warning"] = "neutral"


class ChartSeries(BaseModel):
    name: str
    values: list[float]


class ChartSpec(BaseModel):
    id: str
    title: str
    type: Literal["line", "bar", "stacked_bar", "area", "donut", "scatter", "histogram", "heatmap", "boxplot"]
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    result_refs: list[str] = Field(min_length=1)
    x_label: str = ""
    y_label: str = ""


class TableSpec(BaseModel):
    id: str
    title: str
    columns: list[str]
    rows: list[dict[str, Any]]


class FilterSpec(BaseModel):
    column: str
    label: str
    values: list[str]


class InsightSpec(BaseModel):
    title: str
    text: str
    result_refs: list[str] = Field(default_factory=list)


class DashboardSpec(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3)
    description: str = Field(min_length=10)
    kpis: list[KpiSpec] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(min_length=1)
    tables: list[TableSpec] = Field(min_length=1)
    filters: list[FilterSpec] = Field(default_factory=list)
    computed_results: dict[str, ResultValue] = Field(min_length=1)
    value_formats: dict[str, str] = Field(default_factory=dict)
    layout: list[str] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    quality_notes: list[str] = Field(default_factory=list)
    executive_summary: str = Field(min_length=10)
    detailed_insights: list[InsightSpec] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    measures: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def all_numeric_claims_are_referenced(self) -> "DashboardSpec":
        known = set(self.computed_results)
        refs = [k.result_ref for k in self.kpis]
        refs += [ref for chart in self.charts for ref in chart.result_refs]
        refs += [ref for insight in self.detailed_insights for ref in insight.result_refs]
        missing = sorted(set(refs) - known)
        if missing:
            raise ValueError(f"مراجع نتائج غير موثقة: {', '.join(missing)}")
        return self


class MissingValueOverride(BaseModel):
    column: str = Field(min_length=1)
    source_row: int = Field(ge=2)
    value: str | int | float


class AnalysisStart(BaseModel):
    file_id: str
    sheet_name: str
    max_iterations: int = Field(default=3, ge=1, le=5)
    column_mapping: dict[str, str] = Field(default_factory=dict)
    missing_value_mode: Literal["recommended", "manual"] = "recommended"
    missing_value_overrides: list[MissingValueOverride] = Field(default_factory=list)


class ClarificationAnswer(BaseModel):
    mappings: dict[str, str] = Field(min_length=1)


class AnalysisQuestion(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class AnalysisAnswer(BaseModel):
    answer: str = Field(min_length=2)
    sources: list[str] = Field(default_factory=list)


class AgentExecution(BaseModel):
    agent: Literal["cleaning_agent", "analysis_agent", "dashboard_agent"]
    label: str
    responsibility: str
    status: Literal["completed", "failed"]
    summary: str
    artifacts: list[str] = Field(default_factory=list)


class CleaningImputation(BaseModel):
    column: str = Field(min_length=1)
    count: int = Field(ge=1)
    strategy: Literal["derived", "sequential", "mean", "median", "label", "manual", "retained"]
    fill_value: float | str | None = None
    source_rows: list[int] = Field(default_factory=list)
    explanation: str = Field(min_length=10)


class CleaningAudit(BaseModel):
    input_rows: int = Field(ge=0)
    output_rows: int = Field(ge=0)
    excluded_summary_rows: list[int] = Field(default_factory=list)
    numeric_conversions: int = Field(ge=0)
    date_conversions: int = Field(ge=0)
    normalized_text_cells: int = Field(ge=0)
    invalid_numeric_cells: int = Field(ge=0)
    invalid_date_cells: int = Field(ge=0)
    excluded_empty_columns: list[str] = Field(default_factory=list)
    formula_calculations: int = Field(default=0, ge=0)
    missing_value_mode: Literal["recommended", "manual"] = "recommended"
    missing_values_before: dict[str, int] = Field(default_factory=dict)
    missing_locations: dict[str, list[int]] = Field(default_factory=dict)
    output_source_rows: list[int] = Field(default_factory=list)
    remaining_missing_values: dict[str, int] = Field(default_factory=dict)
    imputation_actions: list[CleaningImputation] = Field(default_factory=list)
    removed_duplicate_rows: list[int] = Field(default_factory=list)
    policy: str = Field(min_length=10)

    @model_validator(mode="after")
    def output_cannot_exceed_input(self) -> "CleaningAudit":
        if self.output_rows > self.input_rows:
            raise ValueError("عدد صفوف نسخة التحليل لا يمكن أن يتجاوز صفوف المصدر أثناء التنظيف.")
        return self


class CustomCalculationRequest(BaseModel):
    instruction: str = Field(min_length=5, max_length=500)


class CustomCalculationResponse(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    expression: str
    value: float
    format: Literal["percent", "decimal"]
    source_columns: list[str] = Field(min_length=1)
    verification: str
    query: str


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: Literal["queued", "running", "waiting_for_clarification", "completed", "completed_with_fallback", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    ambiguity: dict[str, Any] | None = None
    analysis_plan: AnalysisPlan | None = None
    dashboard: DashboardSpec | None = None
    quality: QualityReport | None = None
    cleaning_audit: CleaningAudit | None = None
    agent_runs: list[AgentExecution] = Field(default_factory=list)
    trace: list[str] = Field(default_factory=list)
    error: str | None = None


class PreviewResponse(BaseModel):
    file_id: str
    sheet_name: str
    columns: list[ColumnProfile]
    rows: list[dict[str, Any]]
    total_rows: int
    cleaning_audit: CleaningAudit | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    service: Literal["bayyinah-backend"] = "bayyinah-backend"
    mode: Literal["mock", "ollama", "groq"]
    model: str
    llm_ready: bool
    detail: str
    database: Literal["sqlite", "postgresql"]
    jobs: Literal["inline", "background", "celery"]