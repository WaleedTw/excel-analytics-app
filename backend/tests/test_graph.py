from app.analytics import build_dashboard
from app.agent import LLMProviderError
import app.graph as graph_module
from app.graph import build_analysis_graph
from app.schemas import AnalysisStart, ClarificationAnswer
from app.service import AnalysisService


def test_clean_file_routes_to_dashboard(sales_record):
    service = AnalysisService()
    result = service.start(AnalysisStart(file_id=sales_record.file_id, sheet_name="المبيعات"))
    assert result.status == "completed"
    assert result.dashboard is not None
    assert result.progress == 100
    assert any("DashboardSpec" in item for item in result.trace)


def test_hitl_interrupt_and_resume(messy_record):
    service = AnalysisService()
    paused = service.start(AnalysisStart(file_id=messy_record.file_id, sheet_name="بيانات مختلطة"))
    assert paused.status == "waiting_for_clarification"
    assert paused.ambiguity["kind"] == "column_clarification"
    names = [column["name"] for column in paused.ambiguity["columns"]]
    assert "رمز_س" in names

    mappings = {name: "dimension" for name in names}
    completed = service.resume(paused.analysis_id, ClarificationAnswer(mappings=mappings))
    assert completed.status == "completed"
    assert completed.dashboard is not None
    assert any("استؤنف" in item for item in completed.trace)


def test_max_iteration_limit_and_fallback(sales_record):
    def invalid_dashboard(*_args, **_kwargs):
        return {"title": "غير صالح"}

    service = AnalysisService(graph=build_analysis_graph(dashboard_builder=invalid_dashboard))
    result = service.start(AnalysisStart(file_id=sales_record.file_id, sheet_name="المبيعات", max_iterations=2))
    assert result.status == "completed_with_fallback"
    attempts = [item for item in result.trace if "الحسابات البرمجية بالمحاولة" in item]
    assert len(attempts) == 2
    assert result.dashboard is not None


def test_llm_failure_stops_safely(monkeypatch, sales_record):
    def unavailable(*_args, **_kwargs):
        raise LLMProviderError("Ollama غير جاهز للاختبار.")

    monkeypatch.setattr(graph_module, "llm_analysis_plan", unavailable)
    service = AnalysisService(graph=build_analysis_graph())
    result = service.start(AnalysisStart(file_id=sales_record.file_id, sheet_name="المبيعات"))

    assert result.status == "failed"
    assert result.dashboard is None
    assert "Ollama غير جاهز" in result.error
    assert any("أوقف النظام" in item for item in result.trace)
