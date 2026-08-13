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
    kpis: list[KpiSpec] = Field(min_length=1)
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


class AnalysisStart(BaseModel):
    file_id: str
    sheet_name: str
    max_iterations: int = Field(default=3, ge=1, le=5)
    column_mapping: dict[str, str] = Field(default_factory=dict)


class ClarificationAnswer(BaseModel):
    mappings: dict[str, str] = Field(min_length=1)


class AnalysisResponse(BaseModel):
    analysis_id: str
    status: Literal["waiting_for_clarification", "completed", "completed_with_fallback", "failed"]
    stage: str
    progress: int = Field(ge=0, le=100)
    ambiguity: dict[str, Any] | None = None
    analysis_plan: AnalysisPlan | None = None
    dashboard: DashboardSpec | None = None
    quality: QualityReport | None = None
    trace: list[str] = Field(default_factory=list)
    error: str | None = None


class PreviewResponse(BaseModel):
    file_id: str
    sheet_name: str
    columns: list[ColumnProfile]
    rows: list[dict[str, Any]]
    total_rows: int


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    service: Literal["bayyinah-backend"] = "bayyinah-backend"
    mode: Literal["mock", "ollama", "groq"]
    model: str
    llm_ready: bool
    detail: str
    database: Literal["sqlite", "postgresql"]
    jobs: Literal["inline", "celery"]
