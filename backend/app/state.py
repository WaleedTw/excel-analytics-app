import operator
from typing import Annotated, Any, TypedDict


class AnalysisState(TypedDict, total=False):
    analysis_id: str
    file_id: str
    file_path: str
    original_name: str
    mime_type: str
    file_size: int
    sheet_name: str
    workbook_info: dict[str, Any]
    table_info: dict[str, Any]
    columns: list[dict[str, Any]]
    ambiguous_columns: list[dict[str, Any]]
    column_mapping: dict[str, str]
    missing_value_mode: str
    missing_value_overrides: list[dict[str, Any]]
    quality: dict[str, Any]
    cleaning_audit: dict[str, Any]
    analysis_plan: dict[str, Any]
    computed_results: dict[str, Any]
    dashboard: dict[str, Any]
    status: str
    stage: str
    progress: int
    error: str
    iteration: int
    max_iterations: int
    validation_errors: list[str]
    agent_runs: Annotated[list[dict[str, Any]], operator.add]
    trace: Annotated[list[str], operator.add]