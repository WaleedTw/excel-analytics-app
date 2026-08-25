"""Semantic planning and deterministic analysis agent."""

from collections.abc import Callable
from typing import Any

import pandas as pd

from app.agent import create_analysis_plan
from app.analytics import build_dashboard
from app.schemas import DashboardSpec, QualityReport

DashboardBuilder = Callable[
    [pd.DataFrame, list[dict[str, Any]], QualityReport, str, dict[str, Any] | None],
    DashboardSpec | dict[str, Any],
]
PlanBuilder = Callable[[list[dict[str, Any]], dict[str, Any]], dict[str, Any]]


class AnalysisAgent:
    name = "analysis_agent"
    label = "إيجنت التحليل والحسابات"
    responsibility = "إنشاء الخطة الدلالية وتنفيذ جميع الحسابات برمجيًا مع سجل مصدر لكل رقم."

    def __init__(
        self,
        dashboard_builder: DashboardBuilder = build_dashboard,
        plan_builder: PlanBuilder = create_analysis_plan,
    ) -> None:
        self.dashboard_builder = dashboard_builder
        self.plan_builder = plan_builder

    def plan(self, columns: list[dict[str, Any]], quality: dict[str, Any]) -> dict[str, Any]:
        return self.plan_builder(columns, quality)

    def execute(
        self,
        frame: pd.DataFrame,
        columns: list[dict[str, Any]],
        quality: QualityReport,
        dataset_name: str,
        plan: dict[str, Any] | None,
    ) -> DashboardSpec | dict[str, Any]:
        return self.dashboard_builder(frame, columns, quality, dataset_name, plan)

    def audit(self, status: str, summary: str, artifacts: list[str]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "label": self.label,
            "responsibility": self.responsibility,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
        }