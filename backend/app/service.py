from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app.config import DEFAULT_MAX_ITERATIONS
from app.excel_service import file_path_for
from app.graph import build_analysis_graph
from app.schemas import AnalysisResponse, AnalysisStart, ClarificationAnswer
from app.storage import get_analysis_record, get_file_record


class AnalysisService:
    def __init__(self, graph=None) -> None:
        self.graph = graph or build_analysis_graph()
        self.runs: dict[str, AnalysisResponse] = {}

    @staticmethod
    def _config(analysis_id: str) -> dict[str, dict[str, str]]:
        return {"configurable": {"thread_id": analysis_id}}

    @staticmethod
    def _interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
        values = result.get("__interrupt__")
        if not values: return None
        first = values[0]
        return first.value if hasattr(first, "value") else first

    def _response(self, analysis_id: str, result: dict[str, Any]) -> AnalysisResponse:
        ambiguity = self._interrupt(result)
        status = "waiting_for_clarification" if ambiguity else result.get("status", "failed")
        response = AnalysisResponse(
            analysis_id=analysis_id, status=status, stage=result.get("stage", "unknown"),
            progress=result.get("progress", 0), ambiguity=ambiguity, dashboard=result.get("dashboard"),
            analysis_plan=result.get("analysis_plan"), quality=result.get("quality"),
            trace=result.get("trace", []), error=result.get("error") or None,
        )
        self.runs[analysis_id] = response
        return response

    def start(self, request: AnalysisStart) -> AnalysisResponse:
        record = get_file_record(request.file_id)
        if not record: raise KeyError(request.file_id)
        if request.sheet_name not in [sheet["name"] for sheet in record["sheets"]]:
            raise ValueError("ورقة العمل غير موجودة في الملف.")
        analysis_id = uuid4().hex
        state = {
            "analysis_id": analysis_id, "file_id": request.file_id,
            "file_path": str(file_path_for(request.file_id)), "original_name": record["original_name"],
            "mime_type": record["mime_type"], "file_size": record["size_bytes"],
            "sheet_name": request.sheet_name, "column_mapping": request.column_mapping,
            "iteration": 0, "max_iterations": request.max_iterations or DEFAULT_MAX_ITERATIONS,
            "status": "running", "stage": "queued", "progress": 0, "trace": [],
        }
        return self._response(analysis_id, self.graph.invoke(state, config=self._config(analysis_id)))

    def resume(self, analysis_id: str, answer: ClarificationAnswer) -> AnalysisResponse:
        current = self.runs.get(analysis_id)
        if not current: raise KeyError(analysis_id)
        if current.status != "waiting_for_clarification": raise ValueError("التحليل لا ينتظر توضيحًا.")
        result = self.graph.invoke(Command(resume=answer.model_dump()), config=self._config(analysis_id))
        return self._response(analysis_id, result)

    def get(self, analysis_id: str) -> AnalysisResponse:
        if analysis_id in self.runs:
            return self.runs[analysis_id]
        saved = get_analysis_record(analysis_id)
        if not saved:
            raise KeyError(analysis_id)
        response = AnalysisResponse(
            analysis_id=saved["id"], status=saved["status"], stage="saved",
            progress=100, ambiguity=None, analysis_plan=saved.get("analysis_plan"), dashboard=saved["dashboard"],
            quality=saved["quality"], trace=saved["trace"], error=None,
        )
        self.runs[analysis_id] = response
        return response
