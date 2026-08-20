import re
from typing import Any

import duckdb
import pandas as pd

from app.schemas import (
    ChartSeries, ChartSpec, DashboardSpec, FilterSpec, InsightSpec,
    KpiSpec, QualityReport, ResultValue, TableSpec,
)


TEMPORAL_NAMES = {
    "year", "quarter", "month", "week", "السنة", "السنه", "العام",
    "الربع", "الشهر", "الأسبوع", "الاسبوع",
}
PERCENTAGE_NAMES = {"percentage", "percent", "rate", "margin", "النسبة", "نسبة"}
CURRENCY_NAMES = {
    "revenue", "sales", "cost", "profit", "amount", "value",
    "إيراد", "ايراد", "تكلفة", "ربح", "مبيعات", "قيمة",
}


def _quoted(column: str) -> str:
    return '"' + column.replace('"', '""') + '"'


def _words(column: str) -> set[str]:
    return set(re.sub(r"[_\-]+", " ", column.strip().lower()).split())


def _contains(column: str, terms: set[str]) -> bool:
    lower = column.strip().lower()
    return lower in terms or bool(_words(column) & terms) or any(term in lower for term in terms if len(term) > 3)


def _is_percentage(column: str) -> bool:
    return _contains(column, PERCENTAGE_NAMES)


def _format_for(column: str) -> str:
    if _is_percentage(column):
        return "percent"
    if _contains(column, CURRENCY_NAMES):
        return "currency"
    return "number"


def _aggregate(column: str) -> tuple[str, str, str]:
    if _is_percentage(column):
        return "AVG", "average", "متوسط"
    return "SUM", "sum", "إجمالي"


def _ordered_names(available: list[str], preferred: list[str] | None) -> list[str]:
    preferred = preferred or []
    safe_preferred = [name for name in preferred if name in available]
    return safe_preferred + [name for name in available if name not in safe_preferred]


def _clean_frame(frame: pd.DataFrame, columns: list[dict[str, Any]]) -> pd.DataFrame:
    cleaned = frame.copy()
    for profile in columns:
        name = profile["name"]
        if profile["semantic_role"] == "measure":
            cleaned[name] = pd.to_numeric(cleaned[name], errors="coerce")
        elif profile["semantic_role"] == "date":
            cleaned[name] = pd.to_datetime(cleaned[name], errors="coerce")
    return cleaned


def execute_deterministic_analysis(
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
    quality: QualityReport,
    analysis_plan: dict[str, Any] | None = None,
) -> tuple[dict[str, ResultValue], list[ChartSpec], list[KpiSpec], list[FilterSpec], TableSpec]:
    """Execute verified calculations while letting the validated agent plan set priorities."""
    frame = _clean_frame(frame, columns)
    connection = duckdb.connect(database=":memory:")
    connection.register("dataset", frame)
    registry: dict[str, ResultValue] = {}

    def register(key: str, value: Any, operation: str, source: list[str], query: str) -> str:
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float):
            value = round(value, 2)
        registry[key] = ResultValue(value=value, operation=operation, source_columns=source, query=query)
        return key

    row_query = "SELECT COUNT(*) FROM dataset"
    row_count = int(connection.execute(row_query).fetchone()[0])
    register("rows.total", row_count, "count", [], row_query)
    register("quality.score", quality.score, "quality_profile", [], "Python quality profiler")
    register("quality.missing", quality.missing_cells, "missing_count", [], "Python quality profiler")
    register("quality.duplicates", quality.duplicate_rows, "duplicate_count", [], "Python quality profiler")
    register("quality.invalid", quality.invalid_values, "invalid_count", [], "Python quality profiler")
    register("quality.outliers", quality.outlier_count, "outlier_count", [], "Python quality profiler")

    available_measures = [c["name"] for c in columns if c["semantic_role"] == "measure"]
    available_dimensions = [c["name"] for c in columns if c["semantic_role"] == "dimension"]
    available_dates = [c["name"] for c in columns if c["semantic_role"] == "date"]
    plan = analysis_plan or {}
    measures = _ordered_names(available_measures, plan.get("measures"))
    dimensions = _ordered_names(available_dimensions, plan.get("dimensions"))
    dates = _ordered_names(available_dates, plan.get("dates"))

    # جودة البيانات وعدد السجلات لهما أقسام مستقلة في الواجهة، لذلك لا
    # نكررهما داخل مؤشرات الأداء التنفيذية.
    kpis: list[KpiSpec] = []
    for measure in measures[:4]:
        sql_aggregate, operation, label_prefix = _aggregate(measure)
        query = f"SELECT COALESCE({sql_aggregate}({_quoted(measure)}), 0) FROM dataset"
        value = connection.execute(query).fetchone()[0]
        result_key = f"sum.{measure}" if operation == "sum" else f"metric.{operation}.{measure}"
        key = register(result_key, float(value or 0), operation, [measure], query)
        kpis.append(KpiSpec(
            id=f"metric-{measure}", label=f"{label_prefix} {measure}", result_ref=key,
            format=_format_for(measure), tone="neutral",
        ))

    # أكمل الصف إلى أربعة مؤشرات مفيدة عند توفر مقياس رقمي، من دون اختراع بيانات.
    extra_operations = [("AVG", "average", "متوسط"), ("MAX", "max", "أعلى"), ("MIN", "min", "أدنى")]
    for measure in measures:
        primary_operation = _aggregate(measure)[1]
        for sql_aggregate, operation, label_prefix in extra_operations:
            if len(kpis) >= 4:
                break
            if operation == primary_operation:
                continue
            query = f"SELECT COALESCE({sql_aggregate}({_quoted(measure)}), 0) FROM dataset"
            value = connection.execute(query).fetchone()[0]
            key = register(f"metric.{operation}.{measure}", float(value or 0), operation, [measure], query)
            kpis.append(KpiSpec(
                id=f"{operation}-{measure}", label=f"{label_prefix} {measure}", result_ref=key,
                format=_format_for(measure), tone="positive" if operation == "average" else "neutral",
            ))
        if len(kpis) >= 4:
            break

    # ضمان أربعة مؤشرات تنفيذية عند وجود مقياس رقمي واحد على الأقل.
    # لا تُنشأ أرقام جديدة؛ كل بطاقة مرتبطة باستعلام DuckDB مسجل.
    if measures and len(kpis) < 4:
        fallback_operations = [
            ("SUM", "sum", "إجمالي"),
            ("AVG", "average", "متوسط"),
            ("MAX", "max", "أعلى"),
            ("MIN", "min", "أدنى"),
        ]
        existing_ids = {kpi.id for kpi in kpis}
        for measure in measures:
            for sql_aggregate, operation, label_prefix in fallback_operations:
                kpi_id = f"{operation}-{measure}"
                if kpi_id in existing_ids:
                    continue
                query = f"SELECT COALESCE({sql_aggregate}({_quoted(measure)}), 0) FROM dataset"
                value = connection.execute(query).fetchone()[0]
                key = register(
                    f"metric.fallback.{operation}.{measure}", float(value or 0),
                    operation, [measure], query,
                )
                kpis.append(KpiSpec(
                    id=kpi_id, label=f"{label_prefix} {measure}", result_ref=key,
                    format=_format_for(measure), tone="neutral",
                ))
                existing_ids.add(kpi_id)
                if len(kpis) >= 4:
                    break
            if len(kpis) >= 4:
                break

    charts: list[ChartSpec] = []
    category_rows: list[tuple[Any, ...]] = []
    category_dimension = next((name for name in dimensions if not _contains(name, TEMPORAL_NAMES)), None)
    chart_measures = measures[:2]

    if category_dimension and chart_measures:
        aggregate_parts = [f"{_aggregate(measure)[0]}({_quoted(measure)})" for measure in chart_measures]
        query = (
            f"SELECT CAST({_quoted(category_dimension)} AS VARCHAR), {', '.join(aggregate_parts)} "
            f"FROM dataset WHERE {_quoted(category_dimension)} IS NOT NULL "
            "GROUP BY 1 ORDER BY 2 DESC LIMIT 8"
        )
        category_rows = connection.execute(query).fetchall()
        category_refs: list[list[str]] = [[] for _ in chart_measures]
        category_series: list[ChartSeries] = []
        for measure_index, measure in enumerate(chart_measures):
            values = [float(row[measure_index + 1] or 0) for row in category_rows]
            operation = _aggregate(measure)[1]
            for row_index, value in enumerate(values):
                category_refs[measure_index].append(register(
                    f"chart.category.{measure_index}.{row_index}", value,
                    f"group_{operation}", [category_dimension, measure], query,
                ))
            category_series.append(ChartSeries(name=measure, values=values))

        categories = [str(row[0]) for row in category_rows]
        charts.append(ChartSpec(
            id="category-bar", title=f"مقارنة الأداء حسب {category_dimension}", type="bar",
            categories=categories, series=category_series,
            result_refs=[ref for refs in category_refs for ref in refs],
            x_label=category_dimension, y_label="القيمة",
        ))
        primary_measure = chart_measures[0]
        charts.append(ChartSpec(
            id="category-donut", title=f"حصة {primary_measure} حسب {category_dimension}", type="donut",
            categories=categories[:6],
            series=[ChartSeries(name=primary_measure, values=category_series[0].values[:6])],
            result_refs=category_refs[0][:6],
            x_label=category_dimension, y_label=primary_measure,
        ))

    temporal_dimensions = [name for name in dimensions if _contains(name, TEMPORAL_NAMES)]
    if chart_measures and (dates or temporal_dimensions):
        time_columns = dates[:1] if dates else temporal_dimensions[:2]
        if dates:
            date_column = dates[0]
            period_expr = f"strftime({_quoted(date_column)}, '%Y-%m')"
            select_dimensions = f"{period_expr} AS period"
            group_order = "1"
            category_builder = lambda row: str(row[0])
        else:
            select_dimensions = ", ".join(f"CAST({_quoted(name)} AS VARCHAR)" for name in time_columns)
            group_order = ", ".join(str(index + 1) for index in range(len(time_columns)))
            category_builder = lambda row: " · ".join(str(value) for value in row[:len(time_columns)])

        aggregate_parts = [f"{_aggregate(measure)[0]}({_quoted(measure)})" for measure in chart_measures]
        not_null = " AND ".join(f"{_quoted(name)} IS NOT NULL" for name in time_columns)
        query = (
            f"SELECT {select_dimensions}, {', '.join(aggregate_parts)} FROM dataset "
            f"WHERE {not_null} GROUP BY {group_order} ORDER BY {group_order} LIMIT 24"
        )
        trend_rows = connection.execute(query).fetchall()
        offset = len(time_columns)
        trend_series: list[ChartSeries] = []
        trend_refs_by_measure: list[list[str]] = []
        for measure_index, measure in enumerate(chart_measures):
            values = [float(row[offset + measure_index] or 0) for row in trend_rows]
            operation = _aggregate(measure)[1]
            refs: list[str] = []
            for row_index, value in enumerate(values):
                refs.append(register(
                    f"chart.trend.{measure_index}.{row_index}", value,
                    f"period_{operation}", [*time_columns, measure], query,
                ))
            trend_series.append(ChartSeries(name=measure, values=values))
            trend_refs_by_measure.append(refs)
        charts.append(ChartSpec(
            id="time-line", title=f"تطور الأداء حسب {' و'.join(time_columns)}", type="line",
            categories=[category_builder(row) for row in trend_rows], series=[trend_series[0]],
            result_refs=trend_refs_by_measure[0], x_label=time_columns[0], y_label=trend_series[0].name,
        ))
    if measures:
        measure = measures[0]
        query = f"SELECT MIN({_quoted(measure)}), AVG({_quoted(measure)}), MAX({_quoted(measure)}) FROM dataset"
        minimum, average, maximum = connection.execute(query).fetchone()
        distribution_values = [float(minimum or 0), float(average or 0), float(maximum or 0)]
        refs = [
            register(f"dist.{measure}.min", distribution_values[0], "min", [measure], query),
            register(f"dist.{measure}.avg", distribution_values[1], "average", [measure], query),
            register(f"dist.{measure}.max", distribution_values[2], "max", [measure], query),
        ]
        charts.append(ChartSpec(
            id="distribution", title=f"نطاق {measure}", type="bar",
            categories=["الأدنى", "المتوسط", "الأعلى"],
            series=[ChartSeries(name=measure, values=distribution_values)],
            result_refs=refs, y_label=measure,
        ))

    if not charts:
        charts.append(ChartSpec(
            id="quality-overview", title="ملخص جودة البيانات", type="bar",
            categories=["درجة الجودة", "الخلايا المفقودة", "الصفوف المكررة"],
            series=[ChartSeries(name="القيمة", values=[quality.score, quality.missing_cells, quality.duplicate_rows])],
            result_refs=["quality.score", "quality.missing", "quality.duplicates"],
        ))

    strategy_ids = {
        "trend": "time-line", "category_comparison": "category-bar",
        "share": "category-donut", "distribution": "distribution",
    }
    desired = [strategy_ids[item] for item in plan.get("chart_strategy", []) if item in strategy_ids]
    original_order = {chart.id: index for index, chart in enumerate(charts)}
    charts.sort(key=lambda chart: desired.index(chart.id) if chart.id in desired else len(desired) + original_order[chart.id])

    filters = []
    for dimension in dimensions[:3]:
        values = [str(value) for value in frame[dimension].dropna().astype(str).unique()[:30]]
        filters.append(FilterSpec(column=dimension, label=dimension, values=values))

    preview = frame.copy()
    for column in preview.columns:
        if pd.api.types.is_datetime64_any_dtype(preview[column]):
            preview[column] = preview[column].dt.strftime("%Y-%m-%d")
    rows = []
    for raw_row in preview.to_dict(orient="records"):
        row: dict[str, Any] = {}
        for key, value in raw_row.items():
            if pd.isna(value):
                row[str(key)] = None
            elif hasattr(value, "item"):
                row[str(key)] = value.item()
            else:
                row[str(key)] = value
        rows.append(row)
    table = TableSpec(
        id="source-preview", title="تفاصيل البيانات",
        columns=[str(column) for column in preview.columns], rows=rows,
    )
    connection.close()
    return registry, charts[:6], kpis[:4], filters, table


def assert_numeric_provenance(texts: list[str], registry: dict[str, ResultValue]) -> None:
    known = {str(value.value).replace(",", "") for value in registry.values() if isinstance(value.value, (int, float))}
    for text in texts:
        # Content between guillemets is a source label (for example «2025-Q1»),
        # not a calculated numeric claim. Validate calculated prose only.
        prose = re.sub(r"«[^»]*»", "", text)
        for raw in re.findall(r"(?<![\w.])-?\d+(?:[,.]\d+)?(?![\w.])", prose):
            normalized = raw.replace(",", "")
            if normalized not in known:
                raise ValueError(f"نتيجة رقمية غير موثقة: {raw}")


def build_dashboard(
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
    quality: QualityReport,
    sheet_name: str,
    analysis_plan: dict[str, Any] | None = None,
) -> DashboardSpec:
    registry, charts, kpis, filters, table = execute_deterministic_analysis(
        frame, columns, quality, analysis_plan,
    )
    total = registry["rows.total"].value
    quality_score = registry["quality.score"].value

    def register_derived(
        key: str,
        value: float,
        operation: str,
        source_columns: list[str],
        query: str,
    ) -> tuple[float, str]:
        verified = round(float(value), 2)
        registry[key] = ResultValue(
            value=verified,
            operation=operation,
            source_columns=source_columns,
            query=query,
        )
        return verified, key

    completeness, completeness_ref = register_derived(
        "quality.completeness",
        (1 - quality.missing_rate) * 100,
        "completeness_rate",
        [],
        "Python quality profiler: (1 - missing_rate) * 100",
    )
    insights = [
        InsightSpec(
            title="نطاق التحليل",
            text=f"استند التحليل إلى {total} سجلًا من ورقة العمل المحددة.",
            result_refs=["rows.total"],
        ),
        InsightSpec(
            title="موثوقية النتائج",
            text=f"بلغت درجة جودة البيانات {quality_score} بعد فحص الاكتمال والتكرار وصحة الأنواع.",
            result_refs=["quality.score"],
        ),
        InsightSpec(
            title="اكتمال البيانات",
            text=(
                f"تم رصد {quality.missing_cells} خلية ناقصة، وينبغي مراجعتها قبل القرارات الحساسة."
                if quality.missing_cells else
                "لم يتم رصد خلايا ناقصة في نطاق التحليل."
            ),
            result_refs=["quality.missing"],
        ),
        InsightSpec(
            title="اتساق السجلات",
            text=f"أظهر الفحص {quality.duplicate_rows} صفًا مكررًا داخل الورقة.",
            result_refs=["quality.duplicates"],
        ),
        InsightSpec(
            title="نسبة اكتمال البيانات",
            text=f"بلغت نسبة اكتمال نطاق التحليل {completeness}% بعد احتساب الخلايا الناقصة.",
            result_refs=[completeness_ref],
        ),
        InsightSpec(
            title="سلامة الأنواع",
            text=f"رصد فحص الأنواع {quality.invalid_values} قيمة غير صالحة تحتاج إلى مراجعة.",
            result_refs=["quality.invalid"],
        ),
        InsightSpec(
            title="القيم الشاذة",
            text=f"اكتشف التحليل {quality.outlier_count} قيمة شاذة ضمن المقاييس الرقمية.",
            result_refs=["quality.outliers"],
        ),
    ]
    category_chart = next((chart for chart in charts if chart.id == "category-bar" and chart.categories), None)
    if category_chart and category_chart.series:
        top_value = category_chart.series[0].values[0]
        top_ref = category_chart.result_refs[0]
        insights.append(InsightSpec(
            title="الفئة الأعلى أداءً",
            text=f"تتصدر «{category_chart.categories[0]}» في {category_chart.series[0].name} بقيمة {top_value}.",
            result_refs=[top_ref],
        ))
        if len(category_chart.categories) > 1:
            second_value = category_chart.series[0].values[1]
            second_ref = category_chart.result_refs[1]
            insights.append(InsightSpec(
                title="الفئة الثانية أداءً",
                text=(
                    f"تأتي «{category_chart.categories[1]}» ثانية في {category_chart.series[0].name} "
                    f"بقيمة {second_value}."
                ),
                result_refs=[second_ref],
            ))
            lead_margin, lead_margin_ref = register_derived(
                "category.primary.lead_margin", top_value - second_value,
                "leader_runner_up_gap", [category_chart.x_label, category_chart.series[0].name],
                "Derived from verified category aggregation: leader - runner-up",
            )
            insights.append(InsightSpec(
                title="فارق الصدارة",
                text=(f"تتفوق «{category_chart.categories[0]}» على «{category_chart.categories[1]}» "
                      f"في {category_chart.series[0].name} بفارق {lead_margin}."),
                result_refs=[lead_margin_ref, top_ref, second_ref],
            ))
            last_index = len(category_chart.categories) - 1
            bottom_value = category_chart.series[0].values[last_index]
            bottom_ref = category_chart.result_refs[last_index]
            insights.append(InsightSpec(
                title="الفئة الأقل أداءً",
                text=(
                    f"تظهر «{category_chart.categories[last_index]}» في نهاية المقارنة "
                    f"لمقياس {category_chart.series[0].name} بقيمة {bottom_value}."
                ),
                result_refs=[bottom_ref],
            ))
            gap, gap_ref = register_derived(
                "category.primary.gap",
                top_value - bottom_value,
                "top_bottom_gap",
                [category_chart.x_label, category_chart.series[0].name],
                "Derived from verified category aggregation: top - bottom",
            )
            insights.append(InsightSpec(
                title="فجوة الأداء بين الفئات",
                text=(
                    f"تبلغ الفجوة بين الفئة الأعلى والأدنى في {category_chart.series[0].name} "
                    f"مقدار {gap}."
                ),
                result_refs=[gap_ref, top_ref, bottom_ref],
            ))

        category_total = sum(category_chart.series[0].values)
        if category_total > 0 and top_value >= 0:
            share, share_ref = register_derived(
                "category.primary.top_share",
                top_value / category_total * 100,
                "top_category_share",
                [category_chart.x_label, category_chart.series[0].name],
                "Derived from verified category aggregation: top / displayed total * 100",
            )
            insights.append(InsightSpec(
                title="تركيز الأداء",
                text=(
                    f"تمثل «{category_chart.categories[0]}» نسبة {share}% من إجمالي "
                    f"{category_chart.series[0].name} بين الفئات المعروضة."
                ),
                result_refs=[share_ref, top_ref],
            ))

        if len(category_chart.series) > 1:
            secondary = category_chart.series[1]
            secondary_top_index = max(range(len(secondary.values)), key=secondary.values.__getitem__)
            secondary_low_index = min(range(len(secondary.values)), key=secondary.values.__getitem__)
            secondary_offset = len(category_chart.categories)
            insights.extend([
                InsightSpec(
                    title="متصدر المقياس الثاني",
                    text=(f"تتصدر «{category_chart.categories[secondary_top_index]}» في {secondary.name} "
                          f"بقيمة {secondary.values[secondary_top_index]}."),
                    result_refs=[category_chart.result_refs[secondary_offset + secondary_top_index]],
                ),
                InsightSpec(
                    title="أدنى فئة في المقياس الثاني",
                    text=(f"تسجل «{category_chart.categories[secondary_low_index]}» أدنى قيمة في {secondary.name}: "
                          f"{secondary.values[secondary_low_index]}."),
                    result_refs=[category_chart.result_refs[secondary_offset + secondary_low_index]],
                ),
            ])

    trend_chart = next((chart for chart in charts if chart.id == "time-line" and chart.categories), None)
    if trend_chart and trend_chart.series and trend_chart.series[0].values:
        values = trend_chart.series[0].values
        peak_index = max(range(len(values)), key=values.__getitem__)
        low_index = min(range(len(values)), key=values.__getitem__)
        insights.extend([
            InsightSpec(
                title="ذروة الأداء عبر الزمن",
                text=(
                    f"سجلت الفترة «{trend_chart.categories[peak_index]}» أعلى "
                    f"قيمة لمقياس {trend_chart.series[0].name}: {values[peak_index]}."
                ),
                result_refs=[trend_chart.result_refs[peak_index]],
            ),
            InsightSpec(
                title="الفترة الأضعف",
                text=(
                    f"كانت الفترة «{trend_chart.categories[low_index]}» الأدنى "
                    f"لمقياس {trend_chart.series[0].name} بقيمة {values[low_index]}."
                ),
                result_refs=[trend_chart.result_refs[low_index]],
            ),
        ])
        change, change_ref = register_derived(
            "trend.primary.change",
            values[-1] - values[0],
            "period_change",
            [trend_chart.x_label, trend_chart.series[0].name],
            "Derived from verified trend aggregation: last period - first period",
        )
        average, average_ref = register_derived(
            "trend.primary.average",
            sum(values) / len(values),
            "period_average",
            [trend_chart.x_label, trend_chart.series[0].name],
            "Derived from verified trend aggregation: mean of displayed periods",
        )
        insights.extend([
            InsightSpec(
                title="التغير بين أول وآخر فترة",
                text=(
                    f"تغير {trend_chart.series[0].name} بمقدار {change} بين أول فترة "
                    f"«{trend_chart.categories[0]}» وآخر فترة «{trend_chart.categories[-1]}» المعروضتين."
                ),
                result_refs=[
                    change_ref,
                    trend_chart.result_refs[0],
                    trend_chart.result_refs[len(values) - 1],
                ],
            ),
            InsightSpec(
                title="متوسط الأداء الزمني",
                text=f"بلغ متوسط {trend_chart.series[0].name} عبر الفترات المعروضة {average}.",
                result_refs=[average_ref],
            ),
        ])
        if values[0] != 0:
            change_rate, change_rate_ref = register_derived(
                "trend.primary.change_rate", (values[-1] - values[0]) / abs(values[0]) * 100,
                "period_change_rate", [trend_chart.x_label, trend_chart.series[0].name],
                "Derived from verified trend aggregation: (last - first) / abs(first) * 100",
            )
            insights.append(InsightSpec(
                title="نسبة التغير الزمني",
                text=(f"بلغت نسبة التغير في {trend_chart.series[0].name} بين أول وآخر فترة {change_rate}%."),
                result_refs=[change_rate_ref, trend_chart.result_refs[0], trend_chart.result_refs[len(values) - 1]],
            ))
        periods_above_average, periods_above_average_ref = register_derived(
            "trend.primary.periods_above_average", sum(1 for value in values if value > average),
            "periods_above_average", [trend_chart.x_label, trend_chart.series[0].name],
            "Derived from verified trend aggregation: count(period value > displayed average)",
        )
        insights.append(InsightSpec(
            title="الفترات فوق المتوسط",
            text=(f"تجاوزت {periods_above_average} فترة متوسط {trend_chart.series[0].name} ضمن النطاق الزمني المعروض."),
            result_refs=[periods_above_average_ref, average_ref],
        ))
        distance_from_peak, distance_from_peak_ref = register_derived(
            "trend.primary.distance_from_peak", values[peak_index] - values[-1],
            "last_period_distance_from_peak", [trend_chart.x_label, trend_chart.series[0].name],
            "Derived from verified trend aggregation: peak - last period",
        )
        insights.append(InsightSpec(
            title="المسافة عن الذروة",
            text=(f"تفصل آخر فترة معروضة عن ذروة {trend_chart.series[0].name} قيمة {distance_from_peak}."),
            result_refs=[distance_from_peak_ref, trend_chart.result_refs[peak_index], trend_chart.result_refs[len(values) - 1]],
        ))

    distribution_chart = next((chart for chart in charts if chart.id == "distribution"), None)
    if distribution_chart and distribution_chart.series:
        values = distribution_chart.series[0].values
        insights.append(InsightSpec(
            title="نطاق القيم",
            text=(
                f"يتراوح {distribution_chart.series[0].name} بين {values[0]} و{values[2]}، "
                f"فيما يبلغ المتوسط {values[1]}."
            ),
            result_refs=distribution_chart.result_refs[:3],
        ))
        spread, spread_ref = register_derived(
            "distribution.primary.spread",
            values[2] - values[0],
            "range_spread",
            [distribution_chart.series[0].name],
            "Derived from verified distribution: maximum - minimum",
        )
        insights.append(InsightSpec(
            title="اتساع نطاق القيم",
            text=f"يبلغ الفرق بين أعلى وأدنى قيمة في {distribution_chart.series[0].name} مقدار {spread}.",
            result_refs=[spread_ref, distribution_chart.result_refs[0], distribution_chart.result_refs[2]],
        ))
        if values[1] != 0:
            relative_spread, relative_spread_ref = register_derived(
                "distribution.primary.relative_spread", spread / abs(values[1]) * 100,
                "relative_range_spread", [distribution_chart.series[0].name],
                "Derived from verified distribution: spread / abs(average) * 100",
            )
            insights.append(InsightSpec(
                title="النطاق مقارنة بالمتوسط",
                text=(f"يعادل نطاق {distribution_chart.series[0].name} نسبة {relative_spread}% من متوسطه."),
                result_refs=[relative_spread_ref, spread_ref, distribution_chart.result_refs[1]],
            ))
    # أكمل قائمة الرؤى إلى 25 قراءة موثقة من السجل الحسابي نفسه.
    # الأولوية لقراءات المؤشرات ثم نقاط الرسوم، مع منع تكرار العناوين.
    insight_titles = {insight.title for insight in insights}

    def add_verified_insight(title: str, text: str, refs: list[str]) -> None:
        if len(insights) >= 25 or title in insight_titles or not refs:
            return
        insights.append(InsightSpec(title=title, text=text, result_refs=refs))
        insight_titles.add(title)

    for kpi in kpis:
        result = registry[kpi.result_ref]
        add_verified_insight(
            f"قراءة تنفيذية: {kpi.label}",
            f"بلغ {kpi.label} قيمة {result.value} ضمن نطاق البيانات المحللة.",
            [kpi.result_ref],
        )

    for chart in charts:
        category_count = len(chart.categories)
        for series_index, series in enumerate(chart.series):
            for category_index, category in enumerate(chart.categories):
                ref_index = series_index * category_count + category_index
                if ref_index >= len(chart.result_refs) or category_index >= len(series.values):
                    continue
                result_ref = chart.result_refs[ref_index]
                add_verified_insight(
                    f"{chart.title}: {category} — {series.name}",
                    f"سجلت «{category}» في {series.name} قيمة {series.values[category_index]}.",
                    [result_ref],
                )
                if len(insights) >= 25:
                    break
            if len(insights) >= 25:
                break
        if len(insights) >= 25:
            break

    for result_ref, result in registry.items():
        add_verified_insight(
            f"قراءة موثقة رقم {len(insights) + 1}",
            f"سجل الحساب الموثق للعملية «{result.operation}» قيمة {result.value}.",
            [result_ref],
        )
        if len(insights) >= 25:
            break

    insights = insights[:25]
    assert_numeric_provenance([insight.text for insight in insights], registry)
    warnings = quality.notes if quality.score < 90 else []
    agent_description = (
        "اختار الوكيل الدلالي منظور التحليل، ثم نُفذت جميع الأرقام برمجيًا وتحققت مراجعها."
        if analysis_plan else
        "نُفذت جميع الأرقام برمجيًا وتحققت مراجعها قبل العرض."
    )
    return DashboardSpec(
        title=f"تحليل {sheet_name}", description=agent_description,
        kpis=kpis, charts=charts, tables=[table], filters=filters,
        computed_results=registry,
        value_formats={"currency": "SAR", "locale": "en-US"},
        layout=["agent", "kpis", "charts", "quality", "table", "insights"],
        warnings=warnings, quality_notes=quality.notes,
        executive_summary=(
            "تعرض هذه اللوحة الصورة التنفيذية للبيانات: حجمها، مستوى موثوقيتها، "
            "أبرز الفئات، واتجاه الأداء. مرّر على أي رسم لقراءة القيم الدقيقة."
        ),
        detailed_insights=insights,
        dimensions=[c["name"] for c in columns if c["semantic_role"] in {"dimension", "date"}],
        measures=[c["name"] for c in columns if c["semantic_role"] == "measure"],
    )