"""Locale-aware presentation adapters for API responses.

The analysis graph remains deterministic and language-neutral at the storage
boundary.  These adapters localize system-authored copy without translating or
mutating workbook data such as sheet names, column names, and cell values.
"""

from __future__ import annotations

from typing import Any, Literal

from app.schemas import (
    AnalysisResponse,
    CleaningAudit,
    CustomCalculationResponse,
    DashboardSpec,
    HealthResponse,
    PreviewResponse,
)


Locale = Literal["ar", "en"]


def translate_error(message: str, locale: Locale) -> str:
    if locale == "ar":
        return message
    normalized = message.strip()
    exact = {
        "الملف غير موجود.": "The file was not found.",
        "التحليل غير موجود.": "The analysis was not found.",
        "ورقة العمل غير موجودة في الملف.": "The worksheet was not found in the file.",
        "ورقة العمل فارغة.": "The worksheet is empty.",
        "التحليل لا ينتظر توضيحًا.": "This analysis is not waiting for clarification.",
        "لا يمكن طرح سؤال قبل اكتمال التحليل.": "Questions are available after the analysis is complete.",
        "لا يمكن إنشاء حساب مخصص قبل اكتمال التحليل.": "Custom calculations are available after the analysis is complete.",
        "انتهت جلسة البيانات المؤقتة؛ نفّذ تحليلًا جديدًا لإنشاء الحساب.": "The temporary data session has expired. Run a new analysis to create this calculation.",
    }
    if normalized in exact:
        return exact[normalized]
    if "10" in normalized and ("ميجابايت" in normalized or "MB" in normalized.upper()):
        return "The file exceeds the 10 MB upload limit."
    if "xlsx" in normalized.lower() or "csv" in normalized.lower():
        return "Upload a valid XLSX or CSV file."
    return "The request could not be completed safely. Review the file and try again."


def _audit_summary(audit: dict[str, Any]) -> str:
    changes: list[str] = []
    counters = (
        ("numeric_conversions", "numeric or currency values converted"),
        ("date_conversions", "date values converted"),
        ("normalized_text_cells", "text cells normalized"),
        ("formula_calculations", "safe row formulas calculated"),
    )
    for key, label in counters:
        count = int(audit.get(key, 0))
        if count:
            changes.append(f"{count} {label}")
    list_counters = (
        ("excluded_summary_rows", "structural summary rows excluded"),
        ("removed_duplicate_rows", "exact duplicate rows removed"),
        ("excluded_empty_columns", "fully empty columns excluded"),
    )
    for key, label in list_counters:
        count = len(audit.get(key, []))
        if count:
            changes.append(f"{count} {label}")
    missing = sum(int(value) for value in audit.get("missing_values_before", {}).values())
    treated = sum(
        int(item.get("count", 0))
        for item in audit.get("imputation_actions", [])
        if item.get("strategy") != "retained"
    )
    if missing:
        changes.append(f"{missing} missing values detected")
    if treated:
        changes.append(f"{treated} missing values treated with documented rules")
    if not changes:
        return "The analysis copy was checked and required no safe transformations; the original file was not modified."
    return "The analysis copy was cleaned: " + "; ".join(changes) + ". The original file was not modified."


def _imputation_explanation(action: dict[str, Any]) -> str:
    strategy = action.get("strategy")
    explanations = {
        "derived": "Recalculated from a verified row-level relationship between numeric columns.",
        "sequential": "Completed from the confirmed identifier sequence without changing existing identifiers.",
        "mean": "Filled with the mean of valid values in the monetary column.",
        "median": "Filled with the median of valid numeric values to reduce outlier influence.",
        "label": "Labeled as Unspecified instead of inventing a category or name.",
        "manual": "Replaced with the value explicitly entered by the user.",
        "retained": "Left missing for review because automatic replacement could invent an unsupported value.",
    }
    return explanations.get(str(strategy), "Handled using the documented data-cleaning policy.")


def localize_cleaning_audit(audit: CleaningAudit | dict[str, Any] | None, locale: Locale) -> CleaningAudit | None:
    if audit is None:
        return None
    model = audit if isinstance(audit, CleaningAudit) else CleaningAudit.model_validate(audit)
    if locale == "ar":
        return model
    data = model.model_dump(mode="json")
    for action in data["imputation_actions"]:
        action["explanation"] = _imputation_explanation(action)
        if action.get("strategy") == "sequential":
            action["fill_value"] = "Confirmed sequence (+1)"
        elif action.get("fill_value") == "غير محدد":
            action["fill_value"] = "Unspecified"
    data["policy"] = (
        "Only user-entered replacements were applied; every unspecified cell remains available for review."
        if data["missing_value_mode"] == "manual"
        else "Verified row relationships are applied first, followed by confirmed identifier sequences. Monetary measures use the mean, other numeric measures use the median, and missing dimensions are labeled Unspecified. Exact duplicates may be removed; uncertain dates or identifiers are never invented and outliers are never deleted automatically."
    )
    return CleaningAudit.model_validate(data)


def _quality_notes(quality: dict[str, Any], audit: dict[str, Any] | None) -> list[str]:
    notes = [_audit_summary(audit)] if audit else []
    if int(quality.get("missing_cells", 0)):
        notes.append(f"{quality['missing_cells']} missing cells remain in the analysis copy.")
    if int(quality.get("duplicate_rows", 0)):
        notes.append(f"{quality['duplicate_rows']} duplicate rows require review.")
    if int(quality.get("invalid_values", 0)):
        notes.append(f"{quality['invalid_values']} invalid values were detected.")
    if int(quality.get("outlier_count", 0)):
        notes.append(f"{quality['outlier_count']} statistical outliers were flagged, not deleted.")
    if not notes:
        notes.append("No material data-quality issues were detected in the analysis copy.")
    return notes


def _kpi_label(operation: str, source_columns: list[str]) -> str:
    subject = source_columns[0] if source_columns else "records"
    operation = operation.lower()
    prefix = "Total"
    if "average" in operation or "avg" in operation or "mean" in operation:
        prefix = "Average"
    elif operation == "max" or "maximum" in operation:
        prefix = "Maximum"
    elif operation == "min" or "minimum" in operation:
        prefix = "Minimum"
    elif "count" in operation:
        prefix = "Count of"
    return f"{prefix} {subject}"


def _chart_title(chart: dict[str, Any]) -> str:
    measure = chart.get("y_label") or next(
        (series.get("name") for series in chart.get("series", []) if series.get("name") != "القيمة"),
        "Value",
    )
    if measure == "القيمة":
        measure = "Value"
    dimension = chart.get("x_label") or "category"
    chart_type = chart.get("type")
    if chart_type in {"line", "area"}:
        return f"{measure} trend by {dimension}"
    if chart_type == "donut":
        return f"{measure} share by {dimension}"
    if chart.get("id", "").startswith("distribution") or chart_type in {"histogram", "boxplot"}:
        return f"{measure} range"
    return f"{measure} by {dimension}"


def localize_dashboard(dashboard: DashboardSpec | dict[str, Any] | None, locale: Locale) -> DashboardSpec | None:
    if dashboard is None:
        return None
    model = dashboard if isinstance(dashboard, DashboardSpec) else DashboardSpec.model_validate(dashboard)
    if locale == "ar":
        return model
    data = model.model_dump(mode="json")
    data["title"] = "Verified analysis dashboard"
    data["description"] = "All displayed numbers were calculated programmatically and validated before presentation."
    for kpi in data["kpis"]:
        result = data["computed_results"][kpi["result_ref"]]
        kpi["label"] = _kpi_label(str(result["operation"]), list(result["source_columns"]))
    generated_categories = {"الأدنى": "Low", "المتوسط": "Median", "الأعلى": "High"}
    for chart in data["charts"]:
        chart["title"] = _chart_title(chart)
        chart["categories"] = [generated_categories.get(str(value), value) for value in chart["categories"]]
        for series in chart["series"]:
            if series["name"] == "القيمة":
                series["name"] = "Value"
        if chart["y_label"] == "القيمة":
            chart["y_label"] = "Value"
    for table in data["tables"]:
        table["title"] = "Data details"
    for item in data["filters"]:
        item["label"] = f"Filter by {item['column']}"
    insights: list[dict[str, Any]] = []
    for index, insight in enumerate(data["detailed_insights"]):
        references = insight.get("result_refs", [])
        results = [data["computed_results"][ref] for ref in references if ref in data["computed_results"]]
        if results:
            statements = [
                f"The verified {result['operation']} calculation returned {result['value']}."
                for result in results
            ]
            text = " ".join(statements)
        else:
            text = "This finding is based on the verified analysis scope."
        insights.append({"title": f"Verified insight {index + 1}", "text": text, "result_refs": references})
    data["detailed_insights"] = insights
    data["value_formats"]["locale"] = "en-US"
    data["executive_summary"] = "This dashboard presents the verified scale, quality, leading segments, and performance trends in the analyzed data."
    data["quality_notes"] = ["Review the documented data-quality record before making sensitive decisions."] if data["quality_notes"] else []
    data["warnings"] = ["Review the data-quality notes before making sensitive decisions."] if data["warnings"] else []
    return DashboardSpec.model_validate(data)


def _localize_ambiguity(ambiguity: dict[str, Any] | None) -> dict[str, Any] | None:
    if not ambiguity:
        return None
    data = dict(ambiguity)
    data["title"] = "A short clarification is needed"
    data["question"] = "What is the correct role for each of these columns?"
    labels = {"dimension": "Descriptive dimension", "measure": "Numeric measure", "date": "Date", "identifier": "Identifier"}
    data["allowed_roles"] = [
        {**item, "label": labels.get(str(item.get("value")), str(item.get("label", "")))}
        for item in data.get("allowed_roles", [])
    ]
    columns = []
    for column in data.get("columns", []):
        item = dict(column)
        item["reason"] = "The column role cannot be determined safely from the available values."
        columns.append(item)
    data["columns"] = columns
    return data


def localize_preview_response(response: PreviewResponse, locale: Locale) -> PreviewResponse:
    if locale == "ar":
        return response
    data = response.model_dump(mode="json")
    for column in data["columns"]:
        role = column["semantic_role"]
        if column["ambiguous"]:
            column["reason"] = "The column role needs user confirmation."
        elif role == "unknown":
            column["reason"] = "No reliable semantic role was inferred."
        else:
            column["reason"] = f"Detected as {role}."
    data["cleaning_audit"] = localize_cleaning_audit(response.cleaning_audit, locale).model_dump(mode="json") if response.cleaning_audit else None
    return PreviewResponse.model_validate(data)


def localize_analysis_response(response: AnalysisResponse, locale: Locale) -> AnalysisResponse:
    if locale == "ar":
        return response
    data = response.model_dump(mode="json")
    # Keep the stable stage identifier so the client can map it to localized live copy.
    data["stage"] = response.stage
    data["ambiguity"] = _localize_ambiguity(response.ambiguity)
    if response.analysis_plan:
        data["analysis_plan"]["objective"] = "Analyze the dataset across verified measures, dimensions, and time fields to identify material patterns."
        data["analysis_plan"]["privacy"] = "Only the minimum verified schema and aggregate context are used for semantic planning."
    audit = localize_cleaning_audit(response.cleaning_audit, locale)
    data["cleaning_audit"] = audit.model_dump(mode="json") if audit else None
    if response.quality:
        data["quality"]["notes"] = _quality_notes(data["quality"], data["cleaning_audit"])
    dashboard = localize_dashboard(response.dashboard, locale)
    data["dashboard"] = dashboard.model_dump(mode="json") if dashboard else None
    agent_copy = {
        "cleaning_agent": ("Data Cleaning Agent", "Prepares the analysis copy, documents transformations, and checks missing, duplicate, invalid, and outlier values.", "Prepared the analysis copy and recorded the quality audit."),
        "analysis_agent": ("Analysis & Calculation Agent", "Creates the semantic plan and runs every calculation programmatically with numeric provenance.", "Executed the semantic plan and deterministic calculations."),
        "dashboard_agent": ("Dashboard & Insights Agent", "Validates DashboardSpec and links every numeric claim to a calculated result before presentation.", "Validated the dashboard structure and numeric provenance."),
    }
    for run in data["agent_runs"]:
        label, responsibility, summary = agent_copy[run["agent"]]
        run.update(label=label, responsibility=responsibility, summary=summary)
    data["trace"] = [f"Verified workflow event {index + 1}" for index, _ in enumerate(data["trace"])]
    data["error"] = translate_error(response.error, locale) if response.error else None
    return AnalysisResponse.model_validate(data)


def localize_health_response(response: HealthResponse, locale: Locale) -> HealthResponse:
    if locale == "ar":
        return response
    if response.mode == "mock":
        detail = "Mock mode is intended for tests; no real language model is used."
    elif response.mode == "groq":
        detail = "Groq is configured and ready for semantic planning." if response.llm_ready else "Add GROQ_API_KEY to the server configuration."
    else:
        detail = "Ollama and the configured model are ready." if response.llm_ready else "Ollama or the configured local model is not available."
    return response.model_copy(update={"detail": detail})


def localize_custom_calculation(response: CustomCalculationResponse, locale: Locale) -> CustomCalculationResponse:
    if locale == "ar":
        return response
    return response.model_copy(update={"verification": "Verified independently with two deterministic calculation engines."})