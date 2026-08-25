"""Presentation contract and numeric-provenance agent."""

from typing import Any

from pydantic import ValidationError

from app.analytics import assert_numeric_provenance
from app.schemas import DashboardSpec


class DashboardAgent:
    name = "dashboard_agent"
    label = "إيجنت الداشبورد والرؤى"
    responsibility = "التحقق من DashboardSpec وربط كل ادعاء رقمي بنتيجة محسوبة قبل العرض."

    def validate(self, candidate: DashboardSpec | dict[str, Any]) -> DashboardSpec:
        dashboard = DashboardSpec.model_validate(candidate)
        assert_numeric_provenance(
            [insight.text for insight in dashboard.detailed_insights],
            dashboard.computed_results,
        )
        return dashboard

    def finalize(self, candidate: DashboardSpec | dict[str, Any]) -> dict[str, Any]:
        return self.validate(candidate).model_dump(mode="json")

    def audit(self, status: str, summary: str, artifacts: list[str]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "label": self.label,
            "responsibility": self.responsibility,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
        }


__all__ = ["DashboardAgent", "ValidationError"]