"""Deterministic cleaning agent for the in-memory analysis copy."""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.data_cleaning import DataCleaningAudit, clean_dataset
from app.data_loader import infer_columns, profile_quality
from app.schemas import ColumnProfile, QualityReport


@dataclass(frozen=True)
class CleaningResult:
    frame: pd.DataFrame
    columns: list[ColumnProfile]
    quality: QualityReport
    audit: DataCleaningAudit


class CleaningAgent:
    name = "cleaning_agent"
    label = "إيجنت تنظيف البيانات"
    responsibility = "تنظيف نسخة التحليل، وتوثيق التحويلات، وفحص النواقص والتكرار والقيم غير الصالحة والشاذة."

    def inspect_columns(
        self,
        frame: pd.DataFrame,
        mapping: dict[str, str] | None = None,
    ) -> list[ColumnProfile]:
        return infer_columns(frame, mapping)

    def run(
        self,
        frame: pd.DataFrame,
        mapping: dict[str, str] | None = None,
        missing_value_mode: str = "recommended",
        missing_value_overrides: list[dict[str, Any]] | None = None,
    ) -> CleaningResult:
        source_columns = self.inspect_columns(frame, mapping)
        cleaned_frame, audit = clean_dataset(
            frame,
            source_columns,
            missing_value_mode,
            missing_value_overrides,
        )
        cleaned_columns = self.inspect_columns(cleaned_frame, mapping)
        quality = profile_quality(cleaned_frame, cleaned_columns)
        quality = quality.model_copy(update={"notes": [audit.summary(), *quality.notes]})
        return CleaningResult(
            frame=cleaned_frame,
            columns=cleaned_columns,
            quality=quality,
            audit=audit,
        )

    def audit(self, status: str, summary: str, artifacts: list[str]) -> dict[str, Any]:
        return {
            "agent": self.name,
            "label": self.label,
            "responsibility": self.responsibility,
            "status": status,
            "summary": summary,
            "artifacts": artifacts,
        }