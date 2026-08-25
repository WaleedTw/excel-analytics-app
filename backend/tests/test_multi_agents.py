from app.schemas import AnalysisStart
from app.service import AnalysisService


def test_completed_analysis_exposes_three_auditable_agent_boundaries(sales_record):
    service = AnalysisService()
    result = service.start(AnalysisStart(file_id=sales_record.file_id, sheet_name="المبيعات"))

    assert result.status == "completed"
    latest = {run.agent: run for run in result.agent_runs}
    assert set(latest) == {"cleaning_agent", "analysis_agent", "dashboard_agent"}
    assert all(run.status == "completed" for run in latest.values())
    assert "cleaned_dataset" in latest["cleaning_agent"].artifacts
    assert "cleaning_audit" in latest["cleaning_agent"].artifacts
    assert latest["dashboard_agent"].artifacts == ["dashboard_spec", "numeric_provenance"]