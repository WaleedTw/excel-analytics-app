from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from app.agent import LLMProviderError, create_analysis_plan as llm_analysis_plan
from app.agents import AnalysisAgent, CleaningAgent, DashboardAgent
from app.analytics import assert_numeric_provenance, build_dashboard
from app.config import MAX_FILE_SIZE, UPLOAD_DIR
from app.data_loader import FileValidationError, inspect_data_file, read_dataset
from app.schemas import DashboardSpec, QualityReport
from app.state import AnalysisState

DashboardBuilder = Callable[[Any, list[dict[str, Any]], QualityReport, str, dict[str, Any] | None], DashboardSpec | dict[str, Any]]


def _trace(owner: str, message: str) -> str:
    return f"{owner} — {message}"


def build_analysis_graph(
    dashboard_builder: DashboardBuilder = build_dashboard,
    checkpointer: InMemorySaver | None = None,
):
    cleaning_agent = CleaningAgent()
    analysis_agent = AnalysisAgent(dashboard_builder, llm_analysis_plan)
    dashboard_agent = DashboardAgent()

    def validate_file(state: AnalysisState) -> dict[str, Any]:
        path = Path(state["file_path"])
        try:
            path.resolve().relative_to(UPLOAD_DIR.resolve())
            if path.suffix.lower() not in {".xlsx", ".csv"} or not path.exists() or path.stat().st_size > MAX_FILE_SIZE:
                raise FileValidationError("الملف لا يطابق سياسة الرفع الآمن.")
        except (ValueError, OSError, FileValidationError) as exc:
            return {"status": "failed", "error": str(exc), "stage": "validate_file", "progress": 4, "trace": [_trace("طبقة التهيئة الآمنة", "فشل التحقق الأمني من الملف.")]}
        return {"status": "running", "stage": "validate_file", "progress": 8, "trace": [_trace("طبقة التهيئة الآمنة", "اجتاز الملف فحوص الامتداد والحجم والمسار الآمن.")]}

    def inspect_workbook(state: AnalysisState) -> dict[str, Any]:
        try:
            info = inspect_data_file(Path(state["file_path"]), state["original_name"], state["mime_type"], state["file_id"])
        except FileValidationError as exc:
            return {"status": "failed", "error": str(exc), "stage": "inspect_workbook", "trace": [_trace("طبقة التهيئة الآمنة", "تعذر فحص بنية المصنف.")]}
        return {"workbook_info": info.model_dump(mode="json"), "stage": "inspect_workbook", "progress": 16, "trace": [_trace("طبقة التهيئة الآمنة", f"تم اكتشاف {len(info.sheets)} ورقة عمل.")]}

    def detect_tables(state: AnalysisState) -> dict[str, Any]:
        frame = read_dataset(Path(state["file_path"]), state["sheet_name"])
        if frame.empty or not len(frame.columns):
            return {"status": "failed", "error": "ورقة العمل فارغة.", "table_info": {"analyzable": False}, "stage": "detect_tables", "trace": [_trace("طبقة التهيئة الآمنة", "لم تُكتشف بيانات قابلة للتحليل.")]}
        return {"table_info": {"analyzable": True, "rows": len(frame), "columns": len(frame.columns)}, "stage": "detect_tables", "progress": 23, "trace": [_trace("طبقة التهيئة الآمنة", f"تم اكتشاف جدول يحوي {len(frame)} صفًا و{len(frame.columns)} عامودًا.")]}

    def infer_semantics(state: AnalysisState) -> dict[str, Any]:
        frame = read_dataset(Path(state["file_path"]), state["sheet_name"])
        columns = cleaning_agent.inspect_columns(frame, state.get("column_mapping", {}))
        return {"columns": [c.model_dump() for c in columns], "stage": "infer_semantics", "progress": 31, "trace": [_trace("إيجنت تنظيف البيانات", "اكتملت قراءة أنواع العواميد وأدوارها الدلالية.")]}

    def detect_ambiguities(state: AnalysisState) -> dict[str, Any]:
        ambiguous = [column for column in state["columns"] if column["ambiguous"]]
        return {"ambiguous_columns": ambiguous, "stage": "detect_ambiguities", "progress": 38, "trace": [_trace("إيجنت تنظيف البيانات", f"تم رصد {len(ambiguous)} عامود غامض.")]}

    def request_user_clarification(state: AnalysisState) -> dict[str, Any]:
        answer = interrupt({
            "kind": "column_clarification",
            "title": "نحتاج توضيحًا قصيرًا",
            "question": "ما الدور الصحيح للعواميد التالية؟",
            "columns": state["ambiguous_columns"],
            "allowed_roles": [
                {"value": "dimension", "label": "بُعد وصفي"},
                {"value": "measure", "label": "مقياس رقمي"},
                {"value": "date", "label": "تاريخ"},
                {"value": "identifier", "label": "معرّف"},
            ],
        })
        mapping = dict(state.get("column_mapping", {}))
        mapping.update(answer.get("mappings", {}))
        return {"column_mapping": mapping, "ambiguous_columns": [], "stage": "request_user_clarification", "progress": 43, "trace": [_trace("إيجنت تنظيف البيانات", "استؤنف التحليل بعد حفظ توضيح المستخدم.")]}

    def profile_dataset(state: AnalysisState) -> dict[str, Any]:
        frame = read_dataset(Path(state["file_path"]), state["sheet_name"])
        result = cleaning_agent.run(
            frame,
            state.get("column_mapping", {}),
            state.get("missing_value_mode", "recommended"),
            state.get("missing_value_overrides", []),
        )
        audit = cleaning_agent.audit(
            "completed",
            result.audit.summary(),
            ["cleaned_dataset", "cleaning_audit", "column_profiles", "quality_report"],
        )
        return {
            "columns": [column.model_dump() for column in result.columns],
            "quality": result.quality.model_dump(),
            "cleaning_audit": result.audit.model_dump(),
            "agent_runs": [audit],
            "stage": "profile_dataset",
            "progress": 53,
            "trace": [
                _trace(
                    "إيجنت تنظيف البيانات",
                    f"أكمل نسخة عمل من {result.audit.output_rows} صفًا وسجل تقرير الجودة بدرجة {result.quality.score}.",
                )
            ],
        }

    def create_analysis_plan(state: AnalysisState) -> dict[str, Any]:
        try:
            plan = analysis_agent.plan(state["columns"], state["quality"])
            return {"analysis_plan": plan, "stage": "create_analysis_plan", "progress": 62, "trace": [_trace("إيجنت التحليل والحسابات", "أُنشئت خطة التحليل الدلالية دون تفويض الحسابات للنموذج.")]}
        except LLMProviderError as exc:
            return {
                "status": "failed", "error": str(exc), "stage": "create_analysis_plan",
                "progress": 62, "trace": [_trace("إيجنت التحليل والحسابات", "أوقف التنفيذ لأن مزود النموذج غير جاهز أو أعاد خطة غير آمنة.")],
            }

    def execute_analysis(state: AnalysisState) -> dict[str, Any]:
        iteration = int(state.get("iteration", 0)) + 1
        try:
            source_frame = read_dataset(Path(state["file_path"]), state["sheet_name"])
            frame = cleaning_agent.run(
                source_frame,
                state.get("column_mapping", {}),
                state.get("missing_value_mode", "recommended"),
                state.get("missing_value_overrides", []),
            ).frame
            quality = QualityReport.model_validate(state["quality"])
            dashboard = analysis_agent.execute(frame, state["columns"], quality, state["sheet_name"], state.get("analysis_plan"))
            if isinstance(dashboard, DashboardSpec): dashboard = dashboard.model_dump(mode="json")
            audit = analysis_agent.audit(
                "completed",
                f"نُفذت الخطة والحسابات الحتمية في المحاولة {iteration}.",
                ["analysis_plan", "computed_results", "dashboard_candidate"],
            )
            return {"dashboard": dashboard, "iteration": iteration, "validation_errors": [], "agent_runs": [audit], "stage": "execute_analysis", "progress": 73, "trace": [_trace("إيجنت التحليل والحسابات", f"نفّذ العمليات البرمجية بالمحاولة {iteration}/{state['max_iterations']}.")]}
        except Exception as exc:
            return {"iteration": iteration, "validation_errors": [str(exc)], "stage": "execute_analysis", "trace": [_trace("إيجنت التحليل والحسابات", f"تعذر تنفيذ التحليل في المحاولة {iteration}.")]}

    def validate_results(state: AnalysisState) -> dict[str, Any]:
        if state.get("validation_errors"):
            return {"stage": "validate_results", "trace": [_trace("إيجنت الداشبورد والرؤى", "رُفضت النتائج قبل التحقق البنيوي.")]}
        try:
            dashboard = dashboard_agent.validate(state["dashboard"])
            audit = dashboard_agent.audit(
                "completed",
                f"تحقق من {len(dashboard.computed_results)} نتيجة و{len(dashboard.detailed_insights)} رؤية.",
                ["dashboard_spec", "numeric_provenance"],
            )
            return {"dashboard": dashboard.model_dump(mode="json"), "validation_errors": [], "agent_runs": [audit], "stage": "validate_results", "progress": 81, "trace": [_trace("إيجنت الداشبورد والرؤى", "تحقق من البنية ومصدر كل ادعاء رقمي.")]}
        except (ValidationError, ValueError) as exc:
            return {"validation_errors": [str(exc)], "stage": "validate_results", "trace": [_trace("إيجنت الداشبورد والرؤى", "فشل تحقق DashboardSpec أو توثيق الأرقام.")]}

    def generate_dashboard_spec(state: AnalysisState) -> dict[str, Any]:
        dashboard = dashboard_agent.finalize(state["dashboard"])
        return {"dashboard": dashboard, "stage": "generate_dashboard_spec", "progress": 88, "trace": [_trace("إيجنت الداشبورد والرؤى", "ثبّت مواصفة DashboardSpec المتحققة للواجهة.")]}

    def generate_insights(state: AnalysisState) -> dict[str, Any]:
        dashboard = dashboard_agent.validate(state["dashboard"])
        assert_numeric_provenance([i.text for i in dashboard.detailed_insights], dashboard.computed_results)
        return {"stage": "generate_insights", "progress": 94, "trace": [_trace("إيجنت الداشبورد والرؤى", "صاغ الرؤى العربية من نتائج محسوبة وموثقة فقط.")]}

    def save_analysis(state: AnalysisState) -> dict[str, Any]:
        return {
            "status": "completed", "stage": "save_analysis", "progress": 100,
            "trace": [_trace("إيجنت الداشبورد والرؤى", "أكمل إعداد النتيجة للجلسة الحالية دون الاحتفاظ بملف البيانات الخام.")],
        }

    def fallback_analysis(state: AnalysisState) -> dict[str, Any]:
        try:
            source_frame = read_dataset(Path(state["file_path"]), state["sheet_name"])
            frame = cleaning_agent.run(
                source_frame,
                state.get("column_mapping", {}),
                state.get("missing_value_mode", "recommended"),
                state.get("missing_value_overrides", []),
            ).frame
            dashboard = build_dashboard(
                frame, state["columns"], QualityReport.model_validate(state["quality"]),
                state["sheet_name"], state.get("analysis_plan"),
            )
            finalized = dashboard_agent.finalize(dashboard)
            audit = dashboard_agent.audit(
                "completed",
                "تحقق من لوحة fallback المحلية بعد استنفاد محاولات المسار الأساسي.",
                ["fallback_dashboard_spec", "numeric_provenance"],
            )
            update = {"dashboard": finalized, "agent_runs": [audit], "status": "completed_with_fallback", "stage": "fallback_analysis", "progress": 100, "trace": [_trace("إيجنت الداشبورد والرؤى", "اعتمد مسار التحليل المحلي المحافظ بعد بلوغ المحاولات حدها.")]}
            return update
        except Exception:
            return {"status": "failed", "stage": "fallback_analysis", "progress": 100, "error": "تعذر إنشاء لوحة آمنة بعد استنفاد المحاولات.", "trace": [_trace("إيجنت الداشبورد والرؤى", "فشل مسار التحليل الاحتياطي المحافظ.")]}

    def handle_failure(state: AnalysisState) -> dict[str, Any]:
        return {"status": "failed", "stage": "handle_failure", "progress": 100, "error": state.get("error", "تعذر إكمال التحليل."), "trace": [_trace("طبقة التهيئة الآمنة", "أوقفت المسار بأمان دون تنفيذ حسابات غير موثقة.")]}

    def after_file(state: AnalysisState) -> Literal["inspect_workbook", "handle_failure"]:
        return "handle_failure" if state.get("status") == "failed" else "inspect_workbook"

    def after_tables(state: AnalysisState) -> Literal["infer_semantics", "handle_failure"]:
        return "infer_semantics" if state.get("table_info", {}).get("analyzable") else "handle_failure"

    def after_ambiguity(state: AnalysisState) -> Literal["request_user_clarification", "profile_dataset"]:
        return "request_user_clarification" if state.get("ambiguous_columns") else "profile_dataset"

    def after_validation(state: AnalysisState) -> Literal["execute_analysis", "fallback_analysis", "generate_dashboard_spec"]:
        if not state.get("validation_errors"): return "generate_dashboard_spec"
        return "execute_analysis" if state["iteration"] < state["max_iterations"] else "fallback_analysis"

    def after_plan(state: AnalysisState) -> Literal["execute_analysis", "handle_failure"]:
        return "handle_failure" if state.get("status") == "failed" else "execute_analysis"

    graph = StateGraph(AnalysisState)
    nodes = {
        "validate_file": validate_file, "inspect_workbook": inspect_workbook, "detect_tables": detect_tables,
        "infer_semantics": infer_semantics, "detect_ambiguities": detect_ambiguities,
        "request_user_clarification": request_user_clarification, "profile_dataset": profile_dataset,
        "create_analysis_plan": create_analysis_plan, "execute_analysis": execute_analysis,
        "validate_results": validate_results, "generate_dashboard_spec": generate_dashboard_spec,
        "generate_insights": generate_insights, "save_analysis": save_analysis,
        "fallback_analysis": fallback_analysis, "handle_failure": handle_failure,
    }
    for name, node in nodes.items(): graph.add_node(name, node)
    graph.add_edge(START, "validate_file")
    graph.add_conditional_edges("validate_file", after_file, {"inspect_workbook": "inspect_workbook", "handle_failure": "handle_failure"})
    graph.add_edge("inspect_workbook", "detect_tables")
    graph.add_conditional_edges("detect_tables", after_tables, {"infer_semantics": "infer_semantics", "handle_failure": "handle_failure"})
    graph.add_edge("infer_semantics", "detect_ambiguities")
    graph.add_conditional_edges("detect_ambiguities", after_ambiguity, {"request_user_clarification": "request_user_clarification", "profile_dataset": "profile_dataset"})
    graph.add_edge("request_user_clarification", "profile_dataset")
    graph.add_edge("profile_dataset", "create_analysis_plan")
    graph.add_conditional_edges("create_analysis_plan", after_plan, {"execute_analysis": "execute_analysis", "handle_failure": "handle_failure"})
    graph.add_edge("execute_analysis", "validate_results")
    graph.add_conditional_edges("validate_results", after_validation, {"execute_analysis": "execute_analysis", "fallback_analysis": "fallback_analysis", "generate_dashboard_spec": "generate_dashboard_spec"})
    graph.add_edge("generate_dashboard_spec", "generate_insights")
    graph.add_edge("generate_insights", "save_analysis")
    graph.add_edge("save_analysis", END)
    graph.add_edge("fallback_analysis", END)
    graph.add_edge("handle_failure", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())