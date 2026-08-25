from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from langgraph.types import Command

from app.agents import CleaningAgent
from app.config import DEFAULT_MAX_ITERATIONS, UPLOAD_DIR
from app.agent import answer_analysis_question
from app.custom_calculations import execute_custom_calculation
from app.data_loader import file_path_for, read_dataset
from app.graph import build_analysis_graph
from app.i18n import Locale, translate_error
from app.question_agent import QuestionUnderstandingError, answer_data_question
from app.schemas import (
    AnalysisAnswer,
    AnalysisQuestion,
    AnalysisResponse,
    AnalysisStart,
    ClarificationAnswer,
    CustomCalculationRequest,
    CustomCalculationResponse,
)
from app.storage import delete_file_record, get_file_record


TERMINAL_STATUSES = {"completed", "completed_with_fallback", "failed"}


class AnalysisService:
    def __init__(self, graph=None) -> None:
        self.graph = graph or build_analysis_graph()
        self.cleaning_agent = CleaningAgent()
        self.runs: dict[str, AnalysisResponse] = {}
        self.analysis_files: dict[str, str] = {}
        self.analysis_datasets: dict[str, dict[str, Any]] = {}
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="bayyinah-analysis")
        self.lock = RLock()

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
            cleaning_audit=result.get("cleaning_audit"),
            agent_runs=result.get("agent_runs", []), trace=result.get("trace", []), error=result.get("error") or None,
        )
        with self.lock:
            self.runs[analysis_id] = response
        return response

    def _build_state(self, request: AnalysisStart, analysis_id: str) -> dict[str, Any]:
        record = get_file_record(request.file_id)
        if not record:
            raise KeyError(request.file_id)
        if request.sheet_name not in [sheet["name"] for sheet in record["sheets"]]:
            raise ValueError("ورقة العمل غير موجودة في الملف.")
        self.analysis_files[analysis_id] = request.file_id
        return {
            "analysis_id": analysis_id, "file_id": request.file_id,
            "file_path": str(file_path_for(request.file_id)), "original_name": record["original_name"],
            "mime_type": record["mime_type"], "file_size": record["size_bytes"],
            "sheet_name": request.sheet_name, "column_mapping": request.column_mapping,
            "missing_value_mode": request.missing_value_mode,
            "missing_value_overrides": [item.model_dump() for item in request.missing_value_overrides],
            "iteration": 0, "max_iterations": request.max_iterations or DEFAULT_MAX_ITERATIONS,
            "status": "running", "stage": "queued", "progress": 0, "trace": [],
        }

    def _delete_source_file(self, analysis_id: str) -> None:
        file_id = self.analysis_files.pop(analysis_id, None)
        if not file_id:
            return
        for suffix in (".xlsx", ".csv"):
            (UPLOAD_DIR / f"{file_id}{suffix}").unlink(missing_ok=True)
        delete_file_record(file_id)

    def _cache_analysis_dataset(self, analysis_id: str, state: dict[str, Any]) -> None:
        """Keep a queryable copy in memory, then allow the source workbook to be deleted."""
        if state.get("status") not in {"completed", "completed_with_fallback"}:
            return
        path = Path(state["file_path"])
        source_frame = read_dataset(path, state["sheet_name"])
        cleaning = self.cleaning_agent.run(
            source_frame,
            state.get("column_mapping", {}),
            state.get("missing_value_mode", "recommended"),
            state.get("missing_value_overrides", []),
        )
        context = {
            "frame": cleaning.frame,
            "columns": [column.model_dump() for column in cleaning.columns],
            "cleaning_audit": cleaning.audit.model_dump(),
        }
        with self.lock:
            self.analysis_datasets[analysis_id] = context

    def _run_stream(self, analysis_id: str, graph_input: Any) -> None:
        final: AnalysisResponse | None = None
        try:
            for result in self.graph.stream(
                graph_input,
                config=self._config(analysis_id),
                stream_mode="values",
            ):
                if result.get("status") in {"completed", "completed_with_fallback"}:
                    try:
                        self._cache_analysis_dataset(analysis_id, result)
                    except Exception:
                        # تبقى لوحة النتائج صالحة حتى لو تعذر إنشاء سياق الأسئلة المؤقت.
                        pass
                final = self._response(analysis_id, result)
        except Exception as exc:
            final = self._response(analysis_id, {
                "status": "failed", "stage": "background_failure", "progress": 100,
                "trace": ["تعذر إكمال مهمة التحليل الخلفية."], "error": str(exc),
            })
        finally:
            if final and final.status in TERMINAL_STATUSES:
                try:
                    self._delete_source_file(analysis_id)
                except Exception:
                    # لا نُسقط نتيجة التحليل إذا تعذر تنظيف الملف؛ سيُنظف عند إعادة تشغيل الخدمة.
                    pass

    def start_background(self, request: AnalysisStart) -> AnalysisResponse:
        analysis_id = uuid4().hex
        state = self._build_state(request, analysis_id)
        queued = AnalysisResponse(
            analysis_id=analysis_id, status="queued", stage="queued", progress=0,
            ambiguity=None, analysis_plan=None, dashboard=None, quality=None, trace=[], error=None,
        )
        with self.lock:
            self.runs[analysis_id] = queued
        self.executor.submit(self._run_stream, analysis_id, state)
        return queued

    def resume_background(self, analysis_id: str, answer: ClarificationAnswer) -> AnalysisResponse:
        with self.lock:
            current = self.runs.get(analysis_id)
        if not current:
            raise KeyError(analysis_id)
        if current.status != "waiting_for_clarification":
            raise ValueError("التحليل لا ينتظر توضيحًا.")
        running = current.model_copy(update={
            "status": "running", "stage": "resume_queued",
            "progress": max(current.progress, 43), "ambiguity": None,
        })
        with self.lock:
            self.runs[analysis_id] = running
        self.executor.submit(
            self._run_stream,
            analysis_id,
            Command(resume=answer.model_dump()),
        )
        return running

    def start(self, request: AnalysisStart) -> AnalysisResponse:
        analysis_id = uuid4().hex
        state = self._build_state(request, analysis_id)
        result = self.graph.invoke(state, config=self._config(analysis_id))
        if result.get("status") in TERMINAL_STATUSES:
            try:
                self._cache_analysis_dataset(analysis_id, result)
            except Exception:
                pass
        response = self._response(analysis_id, result)
        if response.status in TERMINAL_STATUSES:
            try:
                self._delete_source_file(analysis_id)
            except Exception:
                pass
        return response

    def resume(self, analysis_id: str, answer: ClarificationAnswer) -> AnalysisResponse:
        current = self.runs.get(analysis_id)
        if not current: raise KeyError(analysis_id)
        if current.status != "waiting_for_clarification": raise ValueError("التحليل لا ينتظر توضيحًا.")
        result = self.graph.invoke(Command(resume=answer.model_dump()), config=self._config(analysis_id))
        if result.get("status") in TERMINAL_STATUSES:
            try:
                self._cache_analysis_dataset(analysis_id, result)
            except Exception:
                pass
        response = self._response(analysis_id, result)
        if response.status in TERMINAL_STATUSES:
            try:
                self._delete_source_file(analysis_id)
            except Exception:
                pass
        return response

    def get(self, analysis_id: str) -> AnalysisResponse:
        with self.lock:
            current = self.runs.get(analysis_id)
        if not current:
            raise KeyError(analysis_id)
        return current

    def ask(self, analysis_id: str, request: AnalysisQuestion, locale: Locale = "ar") -> AnalysisAnswer:
        current = self.get(analysis_id)
        if current.status not in {"completed", "completed_with_fallback"} or not current.dashboard:
            raise ValueError("لا يمكن طرح سؤال قبل اكتمال التحليل.")
        with self.lock:
            context = self.analysis_datasets.get(analysis_id)
        if context:
            try:
                answer = answer_data_question(
                    request.question,
                    context["frame"],
                    context["columns"],
                    current.dashboard,
                    context.get("cleaning_audit"),
                    locale,
                )
                return AnalysisAnswer.model_validate(answer)
            except QuestionUnderstandingError as exc:
                return AnalysisAnswer(
                    answer=translate_error(str(exc), locale) if locale == "en" else str(exc),
                    sources=["Verified query agent" if locale == "en" else "وكيل الاستعلامات الآمنة"],
                )
        return AnalysisAnswer.model_validate(answer_analysis_question(request.question, current.dashboard, locale))

    def calculate(
        self,
        analysis_id: str,
        request: CustomCalculationRequest,
    ) -> CustomCalculationResponse:
        current = self.get(analysis_id)
        if current.status not in {"completed", "completed_with_fallback"}:
            raise ValueError("لا يمكن إنشاء حساب مخصص قبل اكتمال التحليل.")
        with self.lock:
            context = self.analysis_datasets.get(analysis_id)
        if not context:
            raise ValueError("انتهت جلسة البيانات المؤقتة؛ نفّذ تحليلًا جديدًا لإنشاء الحساب.")
        return execute_custom_calculation(
            request,
            context["frame"],
            context["columns"],
        )