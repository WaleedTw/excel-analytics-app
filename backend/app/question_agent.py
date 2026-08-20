"""Verified, read-only question agent for completed workbook analyses.

The agent converts common Arabic business questions into a constrained query
plan.  The plan is validated against inferred columns and actual dimension
values before DuckDB receives it.  User text is never executed as SQL.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Literal

import duckdb
import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from app.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT_SECONDS, LLM_PROVIDER
from app.schemas import DashboardSpec


class QuestionUnderstandingError(ValueError):
    """Raised when a safe, verified answer cannot be produced."""


Operation = Literal["aggregate", "ranking", "comparison", "growth"]
Aggregation = Literal["sum", "average", "min", "max"]


@dataclass(frozen=True)
class SafeFilter:
    column: str
    values: tuple[Any, ...]


@dataclass(frozen=True)
class SafeQueryPlan:
    operation: Operation
    measure: str
    aggregation: Aggregation
    filters: tuple[SafeFilter, ...] = ()
    group_by: str | None = None
    order: Literal["asc", "desc"] | None = None
    limit: int = 10
    time_column: str | None = None


@dataclass
class QueryResult:
    rows: list[dict[str, Any]]
    matched_rows: int
    query: str
    parameters: list[Any] = field(default_factory=list)


class IntentFilter(BaseModel):
    column: str
    values: list[str | int | float] = Field(default_factory=list)


class QuestionIntent(BaseModel):
    """Semantic query plan produced before any calculation is allowed."""

    answerable: bool
    reason: str = ""
    operation: Operation | None = None
    measure: str | None = None
    aggregation: Aggregation = "sum"
    filters: list[IntentFilter] = Field(default_factory=list)
    group_by: str | None = None
    order: Literal["asc", "desc"] | None = None
    limit: int = Field(default=10, ge=1, le=20)
    time_column: str | None = None
    unresolved_terms: list[str] = Field(default_factory=list)


QUESTION_SYSTEM_PROMPT = """أنت مخطط استعلامات بيانات، ولست آلة حاسبة.
حوّل سؤال المستخدم إلى JSON مطابق للمخطط المرفق، اعتمادًا حصريًا على الأعمدة والقيم المتاحة.
قواعد إلزامية:
1. كل اسم شركة أو فئة أو سنة أو ربع يذكره المستخدم يجب أن يظهر في filters.
2. استخدم اسم العمود والقيمة كما وردا حرفيًا في available_values، حتى لو كتب المستخدم ترجمة أو تهجئة عربية.
3. إذا ذكر المستخدم اسمًا أو شرطًا غير موجود، ضعه في unresolved_terms واجعل answerable=false.
4. لا تتجاهل أي كيان مذكور ولا تحوّل السؤال المقيد إلى إجمالي جميع الصفوف.
5. لا تحسب النتيجة ولا تكتب SQL. اختر فقط العملية والمقياس والفلاتر والتجميع.
6. إذا كان السؤال غامضًا أو لا تكفي البيانات للإجابة، اجعل answerable=false واشرح السبب بإيجاز.
العمليات المسموحة: aggregate, ranking, comparison, growth.
التجميعات المسموحة: sum, average, min, max.
أعد JSON فقط."""


ARABIC_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670]")
VALUE_ALIASES = {
    "jarir": ("جرير",),
    "nahdi": ("النهدي", "نهدي"),
    "al othaim": ("العثيم", "الاثيم", "othaim"),
    "saco": ("ساكو",),
    "alsaif gallery": ("السيف غاليري", "السيف", "السايف"),
    "cenomi retail": ("سينومي ريتيل", "سينومي", "سنومي"),
}
QUARTER_WORDS = {
    1: ("q1", "الربع الاول", "ربع اول", "الربع 1"),
    2: ("q2", "الربع الثاني", "ربع ثاني", "الربع 2"),
    3: ("q3", "الربع الثالث", "ربع ثالث", "الربع 3"),
    4: ("q4", "الربع الرابع", "ربع رابع", "الربع 4"),
}


def _normalize(value: Any) -> str:
    text = ARABIC_DIACRITICS.sub("", str(value).strip().lower())
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ة": "ه"}))
    return " ".join(re.sub(r"[^\w\u0600-\u06ff]+", " ", text).split())


def _profile_names(columns: list[dict[str, Any]], role: str) -> list[str]:
    return [str(column["name"]) for column in columns if column.get("semantic_role") == role]


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(_normalize(term) in text for term in terms)


def _find_column(names: list[str], terms: tuple[str, ...]) -> str | None:
    scored: list[tuple[int, int, str]] = []
    for index, name in enumerate(names):
        normalized = _normalize(name)
        score = sum(1 for term in terms if _normalize(term) in normalized)
        if score:
            scored.append((score, -index, name))
    return max(scored, default=(0, 0, ""))[2] or None


def _select_measure(question: str, measures: list[str]) -> str:
    if not measures:
        raise QuestionUnderstandingError("لا يوجد مقياس رقمي يمكن استخدامه للإجابة.")
    q = _normalize(question)
    wants_ecommerce = _contains_any(q, ("الكتروني", "ecom", "e com", "e commerce", "online"))
    wants_growth = _contains_any(q, ("نمو", "تغير", "تطور", "growth", "change"))
    wants_percentage = _contains_any(q, ("نسبه", "percentage", "percent", "rate")) and not wants_growth
    wants_revenue = _contains_any(q, ("ايراد", "مبيعات", "revenue", "sales"))

    best: tuple[int, int, str] | None = None
    for index, name in enumerate(measures):
        normalized = _normalize(name)
        is_ecommerce = _contains_any(normalized, ("ecom", "e com", "e commerce", "الكتروني", "online"))
        is_percentage = _contains_any(normalized, ("percentage", "percent", "rate", "نسبه"))
        is_revenue = _contains_any(normalized, ("revenue", "sales", "ايراد", "مبيعات"))
        is_total = _contains_any(normalized, ("total", "اجمالي"))
        score = 0
        score += 10 if wants_ecommerce and is_ecommerce else 0
        score -= 8 if not wants_ecommerce and is_ecommerce else 0
        score += 6 if wants_percentage and is_percentage else 0
        score -= 6 if wants_growth and is_percentage else 0
        score += 4 if wants_revenue and is_revenue else 0
        score += 3 if wants_revenue and not wants_ecommerce and is_total else 0
        score += 2 if wants_growth and is_revenue else 0
        candidate = (score, -index, name)
        if best is None or candidate > best:
            best = candidate
    return best[2] if best else measures[0]


def _actual_values(frame: pd.DataFrame, column: str) -> list[Any]:
    values: list[Any] = []
    for value in frame[column].dropna().unique().tolist():
        values.append(value.item() if hasattr(value, "item") else value)
    return values


def _semantic_catalog(frame: pd.DataFrame, columns: list[dict[str, Any]]) -> dict[str, Any]:
    """Expose schema and bounded dimension dictionaries, never measure rows."""
    dimensions = _profile_names(columns, "dimension")
    dates = _profile_names(columns, "date")
    return {
        "measures": _profile_names(columns, "measure"),
        "dimensions": dimensions,
        "dates": dates,
        "available_values": {
            name: [str(value) for value in _actual_values(frame, name)[:80]]
            for name in dict.fromkeys(dimensions + dates)
            if name in frame.columns
        },
    }


def _groq_question_intent(
    question: str,
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
) -> QuestionIntent:
    if not GROQ_API_KEY:
        raise QuestionUnderstandingError("خدمة فهم السؤال غير مضبوطة.")
    try:
        from groq import Groq
    except ImportError as exc:
        raise QuestionUnderstandingError("تعذر تحميل خدمة فهم السؤال.") from exc

    payload = {
        "question": question,
        **_semantic_catalog(frame, columns),
        "output_schema": QuestionIntent.model_json_schema(),
    }
    try:
        response = Groq(
            api_key=GROQ_API_KEY,
            timeout=GROQ_TIMEOUT_SECONDS,
            max_retries=2,
        ).chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_completion_tokens=700,
        )
        content = response.choices[0].message.content
        if not content:
            raise QuestionUnderstandingError("لم أتمكن من فهم السؤال بدرجة كافية للإجابة.")
        return QuestionIntent.model_validate_json(content)
    except QuestionUnderstandingError:
        raise
    except (ValidationError, ValueError, TypeError) as exc:
        raise QuestionUnderstandingError("لم أتمكن من تحويل السؤال إلى استعلام آمن وواضح.") from exc
    except Exception as exc:
        raise QuestionUnderstandingError("تعذر تشغيل خدمة فهم السؤال الآن. أعد المحاولة لاحقًا.") from exc


def _resolve_column_name(requested: str | None, allowed: list[str]) -> str | None:
    if requested is None:
        return None
    normalized = _normalize(requested)
    return next((name for name in allowed if _normalize(name) == normalized), None)


def _resolve_intent_value(requested: Any, actual_values: list[Any]) -> Any | None:
    normalized = _normalize(requested)
    for actual in actual_values:
        if _normalize(actual) == normalized:
            return actual
        try:
            if float(actual) == float(requested):
                return actual
        except (TypeError, ValueError):
            pass
    for canonical, aliases in VALUE_ALIASES.items():
        names = {_normalize(canonical), *(_normalize(alias) for alias in aliases)}
        if normalized in names:
            return next((actual for actual in actual_values if _normalize(actual) == _normalize(canonical)), None)
    return None


def _validated_intent_plan(
    intent: QuestionIntent,
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
) -> SafeQueryPlan:
    if not intent.answerable or intent.unresolved_terms:
        missing = "، ".join(f"«{term}»" for term in intent.unresolved_terms)
        detail = intent.reason.strip() or (f"لم أجد {missing} في البيانات." if missing else "السؤال يحتاج إلى تفاصيل إضافية.")
        raise QuestionUnderstandingError(f"لا توجد معلومات كافية للإجابة بدقة. {detail}")

    measures = _profile_names(columns, "measure")
    dimensions = _profile_names(columns, "dimension")
    dates = _profile_names(columns, "date")
    allowed_filters = list(dict.fromkeys(dimensions + dates))
    measure = _resolve_column_name(intent.measure, measures)
    if not intent.operation or not measure:
        raise QuestionUnderstandingError("لا توجد معلومات كافية لتحديد المقياس المطلوب من السؤال.")

    safe_filters: list[SafeFilter] = []
    for requested_filter in intent.filters:
        column = _resolve_column_name(requested_filter.column, allowed_filters)
        if not column:
            raise QuestionUnderstandingError(f"العمود «{requested_filter.column}» غير موجود في البيانات.")
        actual_values = _actual_values(frame, column)
        resolved_values: list[Any] = []
        missing_values: list[str] = []
        for requested_value in requested_filter.values:
            resolved = _resolve_intent_value(requested_value, actual_values)
            if resolved is None:
                missing_values.append(str(requested_value))
            elif resolved not in resolved_values:
                resolved_values.append(resolved)
        if missing_values:
            available = "، ".join(str(value) for value in actual_values[:20])
            missing = "، ".join(f"«{value}»" for value in missing_values)
            raise QuestionUnderstandingError(
                f"لا توجد معلومات كافية للإجابة بدقة. {missing} غير موجود في عمود {column}. القيم المتاحة: {available}."
            )
        if not resolved_values:
            raise QuestionUnderstandingError(f"لم يحدد السؤال قيمة واضحة لعمود {column}.")
        safe_filters.append(SafeFilter(column, tuple(resolved_values)))

    group_by = _resolve_column_name(intent.group_by, allowed_filters)
    time_column = _resolve_column_name(intent.time_column, allowed_filters)
    if intent.operation in {"ranking", "comparison"} and not group_by:
        raise QuestionUnderstandingError("لا توجد معلومات كافية لتحديد بُعد المقارنة أو الترتيب.")
    if intent.operation == "growth" and not time_column:
        raise QuestionUnderstandingError("لا توجد معلومات كافية لتحديد البعد الزمني المطلوب لحساب النمو.")
    return SafeQueryPlan(
        operation=intent.operation,
        measure=measure,
        aggregation=intent.aggregation,
        filters=tuple(safe_filters),
        group_by=group_by,
        order=intent.order or ("desc" if intent.operation in {"ranking", "comparison"} else None),
        limit=intent.limit,
        time_column=time_column,
    )


def _mentioned_dimension_values(question: str, frame: pd.DataFrame, column: str) -> list[Any]:
    q = _normalize(question)
    matches: list[Any] = []
    for value in _actual_values(frame, column):
        normalized = _normalize(value)
        aliases = VALUE_ALIASES.get(normalized, ())
        if (normalized and normalized in q) or any(_normalize(alias) in q for alias in aliases):
            matches.append(value)
    return matches


def _missing_known_company(question: str, frame: pd.DataFrame, column: str) -> str | None:
    """Return a mentioned known company alias when it is absent from the dataset."""
    q = _normalize(question)
    actual = {_normalize(value) for value in _actual_values(frame, column)}
    for canonical, aliases in VALUE_ALIASES.items():
        mentioned = next((alias for alias in aliases if _normalize(alias) in q), None)
        if not mentioned and _normalize(canonical) in q:
            mentioned = canonical
        if mentioned and _normalize(canonical) not in actual:
            return mentioned
    return None


def _unmapped_company_tail(question: str, company_values: list[Any]) -> str | None:
    """Refuse an unknown company phrase instead of silently removing it."""
    q = _normalize(question)
    if any(_normalize(value) in q for value in company_values):
        return None
    match = re.search(
        r"(?:ايرادات|ايراد|مبيعات|revenue|sales)\s+(.+?)(?=\s+(?:في|عام|سنه|خلال|للربع)\b|$)",
        q,
    )
    if not match:
        return None
    candidate = match.group(1).strip().replace("؟", "").replace("?", "")
    ignored = {
        "الاجماليه", "اجماليه", "الاجمالي", "اجمالي", "الالكترونيه", "الكترونيه",
        "الكل", "كل", "الشركات", "الشركه", "حسب", "كم", "هي",
    }
    remaining = [
        word for word in candidate.split()
        if word not in ignored and not re.fullmatch(r"20\d{2}", word)
    ]
    return " ".join(remaining) or None


def _resolve_year(question: str, frame: pd.DataFrame, column: str | None) -> Any | None:
    if not column:
        return None
    match = re.search(r"(?<!\d)(20\d{2})(?!\d)", question)
    if not match:
        return None
    year = int(match.group(1))
    for value in _actual_values(frame, column):
        try:
            if int(float(value)) == year:
                return value
        except (TypeError, ValueError):
            continue
    raise QuestionUnderstandingError(f"السنة {year} غير موجودة في البيانات.")


def _resolve_quarter(question: str, frame: pd.DataFrame, column: str | None) -> Any | None:
    if not column:
        return None
    q = _normalize(question)
    requested = next((number for number, terms in QUARTER_WORDS.items() if any(_normalize(term) in q for term in terms)), None)
    if requested is None:
        return None
    candidates = _actual_values(frame, column)
    for value in candidates:
        normalized = _normalize(value)
        if normalized in {f"q{requested}", str(requested), f"ربع {requested}"}:
            return value
    raise QuestionUnderstandingError(f"الربع Q{requested} غير موجود في البيانات.")


def create_safe_query_plan(question: str, frame: pd.DataFrame, columns: list[dict[str, Any]]) -> SafeQueryPlan:
    q = _normalize(question)
    measures = _profile_names(columns, "measure")
    dimensions = _profile_names(columns, "dimension")
    dates = _profile_names(columns, "date")
    measure = _select_measure(question, measures)
    company_column = _find_column(dimensions, ("company", "شركه", "brand"))
    year_column = _find_column(dimensions + dates, ("year", "سنه", "عام"))
    quarter_column = _find_column(dimensions, ("quarter", "ربع"))

    filters: list[SafeFilter] = []
    year = _resolve_year(question, frame, year_column)
    if year_column and year is not None:
        filters.append(SafeFilter(year_column, (year,)))
    quarter = _resolve_quarter(question, frame, quarter_column)
    if quarter_column and quarter is not None:
        filters.append(SafeFilter(quarter_column, (quarter,)))
    company_values = _mentioned_dimension_values(question, frame, company_column) if company_column else []
    if company_column and not company_values:
        missing_company = _missing_known_company(question, frame, company_column)
        if missing_company:
            available = "، ".join(str(value) for value in _actual_values(frame, company_column))
            raise QuestionUnderstandingError(
                f"الشركة «{missing_company}» غير موجودة في البيانات. الشركات المتاحة: {available}."
            )
        unmapped_company = _unmapped_company_tail(question, _actual_values(frame, company_column))
        if unmapped_company:
            available = "، ".join(str(value) for value in _actual_values(frame, company_column))
            raise QuestionUnderstandingError(
                f"لا توجد معلومات كافية للإجابة بدقة. لم أجد «{unmapped_company}» في البيانات. "
                f"الشركات المتاحة: {available}."
            )

    is_comparison = _contains_any(q, ("قارن", "مقارنه", "مقابل", "compare")) or len(company_values) > 1
    is_growth = _contains_any(q, ("نمو", "تغير", "تطور", "growth"))
    is_top = _contains_any(q, ("اعلي", "اكبر", "افضل", "الاكثر", "top", "highest"))
    is_bottom = _contains_any(q, ("اقل", "ادني", "اضعف", "الاقل", "bottom", "lowest"))

    aggregation: Aggregation = "average" if _contains_any(_normalize(measure), ("percentage", "percent", "rate", "نسبه")) else "sum"
    if _contains_any(q, ("متوسط", "average")):
        aggregation = "average"
    elif _contains_any(q, ("اقصي قيمه", "maximum")):
        aggregation = "max"
    elif _contains_any(q, ("ادني قيمه", "minimum")):
        aggregation = "min"

    if is_comparison:
        if not company_column or len(company_values) < 2:
            raise QuestionUnderstandingError("حدد فئتين واضحتين على الأقل لإجراء المقارنة.")
        filters.append(SafeFilter(company_column, tuple(company_values)))
        return SafeQueryPlan("comparison", measure, aggregation, tuple(filters), company_column, "desc", 10)

    if is_growth:
        time_column = year_column or (dates[0] if dates else None) or quarter_column
        if not time_column:
            raise QuestionUnderstandingError("لا يوجد عمود زمني يسمح بحساب نسبة النمو.")
        if company_column and company_values:
            filters.append(SafeFilter(company_column, (company_values[0],)))
        return SafeQueryPlan("growth", measure, aggregation, tuple(filters), time_column=time_column)

    if is_top or is_bottom:
        if _contains_any(q, ("شركه", "company")) and company_column:
            group_by = company_column
        elif _contains_any(q, ("ربع", "quarter")) and quarter_column:
            group_by = quarter_column
        else:
            group_by = next((name for name in dimensions if name not in {year_column, quarter_column}), None) or quarter_column
        if not group_by:
            raise QuestionUnderstandingError("لم أجد بُعدًا تصنيفيًا مناسبًا للترتيب.")
        if company_column and company_values and group_by != company_column:
            filters.append(SafeFilter(company_column, (company_values[0],)))
        return SafeQueryPlan("ranking", measure, aggregation, tuple(filters), group_by, "asc" if is_bottom else "desc", 1)

    if company_column and company_values:
        filters.append(SafeFilter(company_column, (company_values[0],)))
    return SafeQueryPlan("aggregate", measure, aggregation, tuple(filters))


def create_agent_query_plan(question: str, frame: pd.DataFrame, columns: list[dict[str, Any]]) -> SafeQueryPlan:
    """Understand semantically, validate locally, and only then allow calculation."""
    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        intent = _groq_question_intent(question, frame, columns)
        plan = _validated_intent_plan(intent, frame, columns)
        _validate_question_coverage(question, plan, frame, columns)
        return plan
    return create_safe_query_plan(question, frame, columns)


def _validate_question_coverage(
    question: str,
    plan: SafeQueryPlan,
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
) -> None:
    """Prove that the semantic plan did not drop explicit question constraints."""
    dimensions = _profile_names(columns, "dimension")
    dates = _profile_names(columns, "date")
    company_column = _find_column(dimensions, ("company", "شركه", "brand"))
    year_column = _find_column(dimensions + dates, ("year", "سنه", "عام"))
    quarter_column = _find_column(dimensions, ("quarter", "ربع"))
    plan_filters = {item.column: set(item.values) for item in plan.filters}

    if company_column:
        mentioned = set(_mentioned_dimension_values(question, frame, company_column))
        covered = plan_filters.get(company_column, set())
        missing = mentioned - covered
        if missing:
            names = "، ".join(f"«{value}»" for value in missing)
            raise QuestionUnderstandingError(f"لا توجد معلومات كافية للإجابة بدقة؛ لم تُفسر الشركات المذكورة: {names}.")
        unknown = _unmapped_company_tail(question, _actual_values(frame, company_column))
        if not mentioned and unknown:
            available = "، ".join(str(value) for value in _actual_values(frame, company_column))
            raise QuestionUnderstandingError(
                f"لا توجد معلومات كافية للإجابة بدقة. لم أجد «{unknown}» في البيانات. الشركات المتاحة: {available}."
            )

    requested_year = _resolve_year(question, frame, year_column)
    if year_column and requested_year is not None and requested_year not in plan_filters.get(year_column, set()):
        raise QuestionUnderstandingError(f"لا توجد معلومات كافية للإجابة بدقة؛ لم تُفسر السنة {requested_year}.")
    requested_quarter = _resolve_quarter(question, frame, quarter_column)
    if quarter_column and requested_quarter is not None and requested_quarter not in plan_filters.get(quarter_column, set()):
        raise QuestionUnderstandingError(f"لا توجد معلومات كافية للإجابة بدقة؛ لم يُفسر الربع {requested_quarter}.")


def _quoted(identifier: str, allowed: set[str]) -> str:
    if identifier not in allowed:
        raise QuestionUnderstandingError("رفض النظام عمودًا غير موجود في البيانات.")
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _where_clause(filters: tuple[SafeFilter, ...], allowed: set[str]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    parameters: list[Any] = []
    for item in filters:
        column = _quoted(item.column, allowed)
        if not item.values:
            continue
        placeholders = ", ".join("?" for _ in item.values)
        clauses.append(f"{column} IN ({placeholders})")
        parameters.extend(item.values)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), parameters


def _aggregate_sql(aggregation: Aggregation) -> str:
    return {"sum": "SUM", "average": "AVG", "min": "MIN", "max": "MAX"}[aggregation]


def execute_safe_plan(plan: SafeQueryPlan, frame: pd.DataFrame) -> QueryResult:
    allowed = {str(column) for column in frame.columns}
    measure = _quoted(plan.measure, allowed)
    aggregate = _aggregate_sql(plan.aggregation)
    prepared = frame.copy()
    prepared[plan.measure] = pd.to_numeric(prepared[plan.measure], errors="coerce")
    where, parameters = _where_clause(plan.filters, allowed)
    connection = duckdb.connect(database=":memory:")
    connection.register("dataset", prepared)
    try:
        if plan.operation == "aggregate":
            query = f"SELECT COALESCE({aggregate}({measure}), 0), COUNT({measure}) FROM dataset{where}"
            value, count = connection.execute(query, parameters).fetchone()
            rows = [{"value": float(value or 0)}]
            matched_rows = int(count or 0)
        else:
            group_name = plan.time_column if plan.operation == "growth" else plan.group_by
            if not group_name:
                raise QuestionUnderstandingError("خطة السؤال لا تحتوي على بُعد للتجميع.")
            group = _quoted(group_name, allowed)
            order_sql = group if plan.operation == "growth" else f"2 {plan.order.upper()}"
            limit_sql = "" if plan.operation == "growth" else f" LIMIT {max(1, min(plan.limit, 20))}"
            query = (
                f"SELECT CAST({group} AS VARCHAR), COALESCE({aggregate}({measure}), 0), COUNT({measure}) "
                f"FROM dataset{where} GROUP BY {group} ORDER BY {order_sql}{limit_sql}"
            )
            raw_rows = connection.execute(query, parameters).fetchall()
            rows = [{"label": str(label), "value": float(value or 0), "rows": int(count or 0)} for label, value, count in raw_rows]
            matched_rows = sum(int(row["rows"]) for row in rows)
    finally:
        connection.close()
    if matched_rows <= 0 or not rows:
        raise QuestionUnderstandingError("لا توجد صفوف مطابقة للشروط المذكورة في السؤال.")
    _verify_plan_result(plan, frame, rows)
    return QueryResult(rows=rows, matched_rows=matched_rows, query=query, parameters=list(parameters))


def _filtered_frame(frame: pd.DataFrame, filters: tuple[SafeFilter, ...]) -> pd.DataFrame:
    filtered = frame
    for item in filters:
        filtered = filtered[filtered[item.column].isin(item.values)]
    return filtered


def _pandas_aggregate(series: pd.Series, aggregation: Aggregation) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return 0.0
    return float({"sum": numeric.sum, "average": numeric.mean, "min": numeric.min, "max": numeric.max}[aggregation]())


def _verify_plan_result(plan: SafeQueryPlan, frame: pd.DataFrame, rows: list[dict[str, Any]]) -> None:
    filtered = _filtered_frame(frame, plan.filters)
    if plan.operation == "aggregate":
        expected = _pandas_aggregate(filtered[plan.measure], plan.aggregation)
        if not math.isclose(expected, float(rows[0]["value"]), rel_tol=1e-9, abs_tol=1e-6):
            raise QuestionUnderstandingError("فشل التحقق المستقل من نتيجة السؤال.")
        return
    group_name = plan.time_column if plan.operation == "growth" else plan.group_by
    if not group_name:
        raise QuestionUnderstandingError("تعذر التحقق من بُعد التجميع.")
    for row in rows:
        group = filtered[filtered[group_name].astype(str) == str(row["label"])]
        expected = _pandas_aggregate(group[plan.measure], plan.aggregation)
        if not math.isclose(expected, float(row["value"]), rel_tol=1e-9, abs_tol=1e-6):
            raise QuestionUnderstandingError("فشل التحقق المستقل من إحدى النتائج المجمعة.")


def _format_number(value: float, measure: str, percent: bool = False) -> str:
    if percent:
        return f"{value:,.2f}%"
    normalized = _normalize(measure)
    suffix = " ريال" if _contains_any(normalized, ("revenue", "sales", "ايراد", "مبيعات", "sar")) else ""
    absolute = abs(value)
    if absolute >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.2f} مليار{suffix}"
    if absolute >= 1_000_000:
        return f"{value / 1_000_000:,.2f} مليون{suffix}"
    return f"{value:,.2f}{suffix}"


def _filter_description(filters: tuple[SafeFilter, ...]) -> str:
    parts = [f"{item.column}={', '.join(str(value) for value in item.values)}" for item in filters]
    return "، ".join(parts) if parts else "جميع الصفوف"


def answer_data_question(
    question: str,
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
    dashboard: DashboardSpec,
) -> dict[str, Any]:
    del dashboard  # The verified dataset is the numeric source for this tool.
    plan = create_agent_query_plan(question, frame, columns)
    result = execute_safe_plan(plan, frame)
    aggregation_label = {"sum": "إجمالي", "average": "متوسط", "min": "أدنى", "max": "أعلى"}[plan.aggregation]
    filters = _filter_description(plan.filters)

    if plan.operation == "aggregate":
        value = _format_number(result.rows[0]["value"], plan.measure)
        answer = f"بلغ {aggregation_label} {plan.measure} وفق الشروط ({filters}) مقدار {value}."
    elif plan.operation == "ranking":
        row = result.rows[0]
        value = _format_number(row["value"], plan.measure)
        direction = "الأعلى" if plan.order == "desc" else "الأقل"
        answer = f"{direction} حسب {plan.group_by} هو «{row['label']}» بقيمة {value} لمقياس {plan.measure} وفق الشروط ({filters})."
    elif plan.operation == "comparison":
        if len(result.rows) < 2:
            raise QuestionUnderstandingError("لا تتوفر نتيجتان مكتملتان لإجراء المقارنة.")
        details = " مقابل ".join(f"«{row['label']}»: {_format_number(row['value'], plan.measure)}" for row in result.rows)
        leader, runner = result.rows[0], result.rows[1]
        difference = leader["value"] - runner["value"]
        answer = f"المقارنة وفق الشروط ({filters}): {details}. الأعلى «{leader['label']}» بفارق {_format_number(difference, plan.measure)}."
    else:
        if len(result.rows) < 2:
            raise QuestionUnderstandingError("تحتاج نسبة النمو إلى فترتين على الأقل.")
        first, last = result.rows[0], result.rows[-1]
        if math.isclose(first["value"], 0.0, abs_tol=1e-12):
            raise QuestionUnderstandingError("لا يمكن حساب نسبة النمو لأن قيمة الفترة الأولى تساوي صفرًا.")
        growth = (last["value"] - first["value"]) / abs(first["value"]) * 100
        direction = "نموًا" if growth >= 0 else "انخفاضًا"
        answer = (
            f"سجل {plan.measure} {direction} بنسبة {_format_number(growth, plan.measure, percent=True)} "
            f"من «{first['label']}» ({_format_number(first['value'], plan.measure)}) إلى «{last['label']}» "
            f"({_format_number(last['value'], plan.measure)}) وفق الشروط ({filters})."
        )

    sources = [
        f"حساب موثق: {aggregation_label} {plan.measure}",
        f"الفلاتر: {filters}",
        "تحقق مزدوج: DuckDB وPandas",
    ]
    return {"answer": answer, "sources": sources}
