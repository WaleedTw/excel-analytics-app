"""Deterministic, auditable preparation of tabular data for analysis.

The source workbook is never changed. Only an in-memory working copy is
normalized, structural summary rows and exact duplicates are removed, typed
values are recovered, and missing values are repaired through explicit,
auditable policies. Ambiguous dates, identifiers and outliers are retained for
review rather than silently fabricated or discarded.
"""

from __future__ import annotations

import math
import operator
import re
from dataclasses import dataclass
from datetime import date, datetime
from numbers import Real
from typing import Any

import pandas as pd
from openpyxl.utils.cell import column_index_from_string


ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
MISSING_TOKENS = {
    "", "-", "—", "–", "n/a", "na", "null", "none", "nan",
    "غير متوفر", "غير متاح", "لا يوجد",
}
SUMMARY_LABEL = re.compile(
    r"^(?:grand\s+total|sub\s*total|subtotal|total(?:\s+summary)?|summary|"
    r"الإجمالي(?:\s+العام)?|الاجمالي(?:\s+العام)?|المجموع|ملخص(?:\s+الإجمالي)?)$",
    re.IGNORECASE,
)
CURRENCY_TOKENS = re.compile(
    r"(?:USD|US\$|SAR|S\.A\.R|AED|EUR|GBP|KWD|QAR|BHD|OMR|"
    r"دولار|ريال(?:\s+سعودي)?|درهم(?:\s+إماراتي)?|دينار|ر\.س|د\.إ)",
    re.IGNORECASE,
)
CURRENCY_SYMBOLS = re.compile(r"[$€£¥﷼]")
NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
ROW_ARITHMETIC_FORMULA = re.compile(
    r"^\s*=\s*\$?([A-Z]{1,3})\$?(\d+)\s*([+\-*/])\s*"
    r"\$?([A-Z]{1,3})\$?(\d+)\s*$",
    re.IGNORECASE,
)
ARITHMETIC_OPERATORS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
}
MONETARY_COLUMN_TERMS = {
    "amount", "revenue", "sales", "price", "cost", "profit", "income",
    "المبلغ", "الإيراد", "الايراد", "المبيعات", "السعر", "التكلفة", "الربح",
    "sar", "usd", "aed", "ريال", "دولار", "درهم", "ر.س", "$", "﷼",
}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def parse_numeric_value(value: Any) -> float | None:
    """Parse a numeric/currency cell without evaluating formulas or code."""
    if _is_missing(value):
        return None
    if isinstance(value, bool | datetime | date):
        return None
    if isinstance(value, Real):
        return float(value)
    if not isinstance(value, str):
        return None

    text = value.strip().translate(ARABIC_DIGITS)
    if text.casefold() in MISSING_TOKENS or text.startswith(("=", "@")):
        return None
    text = text.replace("\u00a0", "").replace("\u202f", "")
    text = CURRENCY_TOKENS.sub("", text)
    text = CURRENCY_SYMBOLS.sub("", text)
    text = text.replace("%", "").replace("٪", "")
    text = text.replace("٬", "").replace(",", "").replace("٫", ".")
    text = re.sub(r"\s+", "", text)

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    if not NUMBER_PATTERN.fullmatch(text):
        return None
    number = float(text)
    return -abs(number) if negative else number


def coerce_numeric_series(series: pd.Series) -> tuple[pd.Series, int, int]:
    """Return typed numbers plus counts of converted and invalid source cells."""
    parsed = series.map(parse_numeric_value)
    numeric = pd.to_numeric(parsed, errors="coerce")
    source_present = series.map(lambda value: not _is_missing(value))
    converted = int(sum(
        present and not isinstance(value, Real) and not _is_missing(number)
        for value, number, present in zip(series.tolist(), numeric.tolist(), source_present.tolist(), strict=True)
    ))
    invalid = int((source_present & numeric.isna()).sum())
    return numeric, converted, invalid


def is_numeric_like(series: pd.Series, threshold: float = 0.8) -> bool:
    """Detect text columns that are predominantly safe numeric representations."""
    present = series[series.map(lambda value: not _is_missing(value))]
    if present.empty:
        return False
    numeric, _, _ = coerce_numeric_series(present)
    return bool(numeric.notna().sum() / len(present) >= threshold)


def _profile_value(profile: Any, key: str) -> Any:
    if isinstance(profile, dict):
        return profile.get(key)
    return getattr(profile, key)


def _is_monetary_column(name: str) -> bool:
    normalized = name.casefold().replace("_", " ")
    return any(term in normalized for term in MONETARY_COLUMN_TERMS)


def _evaluate_row_formula(
    formula: Any,
    frame: pd.DataFrame,
    position: int,
    excel_row: int,
) -> float | None:
    """Evaluate only a two-cell arithmetic formula scoped to its own row.

    This deliberately rejects ranges, functions, cross-sheet references,
    names, external links, and references to any other row.
    """
    if not isinstance(formula, str):
        return None
    match = ROW_ARITHMETIC_FORMULA.fullmatch(formula)
    if not match:
        return None
    left_column, left_row, symbol, right_column, right_row = match.groups()
    if int(left_row) != excel_row or int(right_row) != excel_row:
        return None
    left_index = column_index_from_string(left_column.upper()) - 1
    right_index = column_index_from_string(right_column.upper()) - 1
    if left_index >= len(frame.columns) or right_index >= len(frame.columns):
        return None
    left = parse_numeric_value(frame.iat[position, left_index])
    right = parse_numeric_value(frame.iat[position, right_index])
    if left is None or right is None or (symbol == "/" and right == 0):
        return None
    result = ARITHMETIC_OPERATORS[symbol](left, right)
    return float(result) if pd.notna(result) else None


def _find_profile_column(profiles: list[Any], role: str, terms: tuple[str, ...]) -> str | None:
    for profile in profiles:
        name = str(_profile_value(profile, "name"))
        normalized = name.casefold().replace("_", " ")
        if _profile_value(profile, "semantic_role") == role and any(term in normalized for term in terms):
            return name
    return None


def _source_rows(mask: pd.Series, retained_excel_rows: list[int]) -> list[int]:
    return [retained_excel_rows[position] for position, selected in enumerate(mask.tolist()) if bool(selected)]


def _repair_derived_sales(
    frame: pd.DataFrame,
    profiles: list[Any],
    retained_excel_rows: list[int],
) -> list[dict[str, Any]]:
    """Repair the common quantity × unit-price relationship when all inputs exist."""
    quantity = _find_profile_column(profiles, "measure", ("quantity", "qty", "كمية", "الكمية"))
    unit_price = _find_profile_column(profiles, "measure", ("unit price", "unit_price", "سعر الوحدة"))
    total = _find_profile_column(
        profiles,
        "measure",
        ("total sales", "total amount", "sales amount", "إجمالي المبلغ", "اجمالي المبلغ"),
    )
    if not quantity or not unit_price or not total or any(name not in frame.columns for name in (quantity, unit_price, total)):
        return []

    actions: list[dict[str, Any]] = []
    quantity_values = pd.to_numeric(frame[quantity], errors="coerce")
    price_values = pd.to_numeric(frame[unit_price], errors="coerce")
    total_values = pd.to_numeric(frame[total], errors="coerce")

    missing_total = total_values.isna() & quantity_values.notna() & price_values.notna()
    if missing_total.any():
        frame.loc[missing_total, total] = quantity_values[missing_total] * price_values[missing_total]
        actions.append({
            "column": total,
            "count": int(missing_total.sum()),
            "strategy": "derived",
            "fill_value": f"{quantity} × {unit_price}",
            "source_rows": _source_rows(missing_total, retained_excel_rows),
            "explanation": "أُعيد بناء الإجمالي من الكمية مضروبة في سعر الوحدة بدل استخدام قيمة تقديرية.",
        })

    total_values = pd.to_numeric(frame[total], errors="coerce")
    missing_price = price_values.isna() & total_values.notna() & quantity_values.notna() & quantity_values.ne(0)
    if missing_price.any():
        frame.loc[missing_price, unit_price] = total_values[missing_price] / quantity_values[missing_price]
        actions.append({
            "column": unit_price,
            "count": int(missing_price.sum()),
            "strategy": "derived",
            "fill_value": f"{total} ÷ {quantity}",
            "source_rows": _source_rows(missing_price, retained_excel_rows),
            "explanation": "أُعيد بناء سعر الوحدة من الإجمالي مقسومًا على الكمية.",
        })

    price_values = pd.to_numeric(frame[unit_price], errors="coerce")
    candidate_quantity = total_values / price_values.replace(0, pd.NA)
    integral_quantity = candidate_quantity.map(lambda value: pd.notna(value) and math.isclose(float(value), round(float(value)), abs_tol=1e-9))
    missing_quantity = quantity_values.isna() & total_values.notna() & price_values.notna() & integral_quantity
    if missing_quantity.any():
        frame.loc[missing_quantity, quantity] = candidate_quantity[missing_quantity].round()
        actions.append({
            "column": quantity,
            "count": int(missing_quantity.sum()),
            "strategy": "derived",
            "fill_value": f"{total} ÷ {unit_price}",
            "source_rows": _source_rows(missing_quantity, retained_excel_rows),
            "explanation": "أُعيد بناء الكمية من الإجمالي وسعر الوحدة بعد التحقق من أن الناتج عدد صحيح.",
        })
    return actions


def _repair_sequential_identifier(series: pd.Series) -> tuple[pd.Series, int, str | None]:
    """Fill gaps only when at least 85% of known identifiers prove a +1 sequence."""
    repaired = series.astype("object").copy()
    missing_positions = [position for position, value in enumerate(repaired.tolist()) if _is_missing(value)]
    if not missing_positions:
        return repaired, 0, None

    numeric_known: list[tuple[int, int]] = []
    text_known: list[tuple[int, str, int, int]] = []
    for position, value in enumerate(repaired.tolist()):
        if _is_missing(value):
            continue
        parsed = parse_numeric_value(value)
        if parsed is not None and math.isclose(parsed, round(parsed), abs_tol=1e-9):
            numeric_known.append((position, int(round(parsed))))
            continue
        match = re.fullmatch(r"(.*?)(\d+)", str(value).strip())
        if match:
            text_known.append((position, match.group(1), int(match.group(2)), len(match.group(2))))

    if len(numeric_known) >= 3:
        offsets = [value - position for position, value in numeric_known]
        base = max(set(offsets), key=offsets.count)
        if offsets.count(base) / len(offsets) >= 0.85:
            for position in missing_positions:
                repaired.iat[position] = base + position
            return repaired, len(missing_positions), "تسلسل رقمي بزيادة 1"

    if len(text_known) >= 3:
        prefix = max({item[1] for item in text_known}, key=lambda item: sum(value[1] == item for value in text_known))
        matching = [item for item in text_known if item[1] == prefix]
        offsets = [number - position for position, _, number, _ in matching]
        base = max(set(offsets), key=offsets.count)
        width = max(set(item[3] for item in matching), key=lambda item: sum(value[3] == item for value in matching))
        if len(matching) / len(text_known) >= 0.85 and offsets.count(base) / len(matching) >= 0.85:
            for position in missing_positions:
                repaired.iat[position] = f"{prefix}{base + position:0{width}d}"
            return repaired, len(missing_positions), f"تسلسل {prefix}… بزيادة 1"
    return repaired, 0, None


def _normalize_text_cells(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    cleaned = frame.copy()
    changed = 0
    for column in cleaned.columns:
        if not pd.api.types.is_object_dtype(cleaned[column]) and not pd.api.types.is_string_dtype(cleaned[column]):
            continue

        def normalize(value: Any) -> Any:
            nonlocal changed
            if _is_missing(value):
                return pd.NA
            if not isinstance(value, str):
                return value
            normalized = value.replace("\u00a0", " ").strip()
            if normalized != value:
                changed += 1
            return pd.NA if normalized.casefold() in MISSING_TOKENS else normalized

        cleaned[column] = cleaned[column].map(normalize)
    return cleaned, changed


def _summary_row_positions(frame: pd.DataFrame, profiles: list[Any]) -> list[int]:
    roles = {str(_profile_value(profile, "name")): _profile_value(profile, "semantic_role") for profile in profiles}
    descriptor_columns = [
        str(column) for column in frame.columns
        if roles.get(str(column)) not in {"measure", "date"}
    ]
    measure_columns = [str(column) for column in frame.columns if roles.get(str(column)) == "measure"]
    positions: list[int] = []

    for position, (_, row) in enumerate(frame.iterrows()):
        present = [(index, str(column), value) for index, (column, value) in enumerate(row.items()) if not _is_missing(value)]
        if not present:
            continue
        first_index, first_column, first_value = present[0]
        label = " ".join(str(first_value).strip().split())
        if first_index > 1 or not SUMMARY_LABEL.fullmatch(label):
            continue
        descriptor_missing = any(
            column != first_column and _is_missing(row[column])
            for column in descriptor_columns
        )
        has_measure = any(not _is_missing(row[column]) for column in measure_columns)
        if descriptor_missing or has_measure:
            positions.append(position)
    return positions


@dataclass(frozen=True)
class DataCleaningAudit:
    input_rows: int
    output_rows: int
    excluded_summary_rows: list[int]
    numeric_conversions: int
    date_conversions: int
    normalized_text_cells: int
    invalid_numeric_cells: int
    invalid_date_cells: int
    excluded_empty_columns: list[str]
    formula_calculations: int
    missing_value_mode: str
    missing_values_before: dict[str, int]
    missing_locations: dict[str, list[int]]
    output_source_rows: list[int]
    remaining_missing_values: dict[str, int]
    imputation_actions: list[dict[str, Any]]
    removed_duplicate_rows: list[int]

    def summary(self) -> str:
        changes: list[str] = []
        if self.numeric_conversions:
            changes.append(f"تحويل {self.numeric_conversions} قيمة رقمية/مالية من نص إلى رقم")
        if self.date_conversions:
            changes.append(f"تحويل {self.date_conversions} قيمة إلى تاريخ")
        if self.excluded_summary_rows:
            changes.append(f"استبعاد {len(self.excluded_summary_rows)} صف إجمالي بنيوي")
        if self.removed_duplicate_rows:
            changes.append(f"إزالة {len(self.removed_duplicate_rows)} صف مكرر مطابق")
        if self.excluded_empty_columns:
            changes.append(f"استبعاد {len(self.excluded_empty_columns)} عامود فارغ بالكامل")
        if self.formula_calculations:
            changes.append(f"احتساب {self.formula_calculations} صيغة صفية آمنة")
        missing_total = sum(self.missing_values_before.values())
        imputed_total = sum(
            int(action["count"])
            for action in self.imputation_actions
            if action["strategy"] != "retained"
        )
        if missing_total:
            changes.append(f"رصد {missing_total} قيمة ناقصة في {len(self.missing_values_before)} عامود")
        if imputed_total:
            changes.append(f"معالجة {imputed_total} قيمة ناقصة بسياسة موثقة")
        if self.normalized_text_cells:
            changes.append(f"توحيد {self.normalized_text_cells} خلية نصية")
        if not changes:
            return "فُحصت نسخة التحليل ولم تتطلب تحويلات آمنة؛ لم يُعدّل الملف الأصلي."
        return "تم تنظيف نسخة التحليل عبر " + "، و".join(changes) + "؛ لم يُعدّل الملف الأصلي."

    def model_dump(self) -> dict[str, Any]:
        return {
            "input_rows": self.input_rows,
            "output_rows": self.output_rows,
            "excluded_summary_rows": self.excluded_summary_rows,
            "numeric_conversions": self.numeric_conversions,
            "date_conversions": self.date_conversions,
            "normalized_text_cells": self.normalized_text_cells,
            "invalid_numeric_cells": self.invalid_numeric_cells,
            "invalid_date_cells": self.invalid_date_cells,
            "excluded_empty_columns": self.excluded_empty_columns,
            "formula_calculations": self.formula_calculations,
            "missing_value_mode": self.missing_value_mode,
            "missing_values_before": self.missing_values_before,
            "missing_locations": self.missing_locations,
            "output_source_rows": self.output_source_rows,
            "remaining_missing_values": self.remaining_missing_values,
            "imputation_actions": self.imputation_actions,
            "removed_duplicate_rows": self.removed_duplicate_rows,
            "policy": (
                "طُبقت القيم التي أدخلها المستخدم يدويًا فقط، وبقيت أي خلية لم يحددها للمراجعة."
                if self.missing_value_mode == "manual" else
                "تُستخدم العلاقات الحسابية المثبتة أولًا، ثم تُستكمل المعرّفات ذات التسلسل المؤكد. "
                "تُعوّض المقاييس المالية بالمتوسط، والمقاييس العددية الأخرى بالوسيط، وتُوسم الأبعاد "
                "الناقصة بغير محدد. تُزال الصفوف المتطابقة فقط؛ ولا تُختلق التواريخ أو المعرّفات "
                "غير المؤكدة ولا تُحذف القيم الشاذة تلقائيًا."
            ),
        }


def _apply_manual_overrides(
    frame: pd.DataFrame,
    profiles: list[Any],
    retained_excel_rows: list[int],
    overrides: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    roles = {str(_profile_value(profile, "name")): _profile_value(profile, "semantic_role") for profile in profiles}
    row_positions = {source_row: position for position, source_row in enumerate(retained_excel_rows)}
    actions: list[dict[str, Any]] = []
    for override in overrides:
        column = str(override.get("column", ""))
        source_row = int(override.get("source_row", 0))
        if column not in frame.columns or source_row not in row_positions:
            raise ValueError(f"تعذر تطبيق القيمة اليدوية على {column} في صف Excel {source_row}.")
        position = row_positions[source_row]
        if not _is_missing(frame.at[position, column]):
            raise ValueError(f"الخلية {column} في صف Excel {source_row} ليست ناقصة ولا تحتاج إلى استبدال.")
        raw_value = override.get("value")
        role = roles.get(column)
        if role == "measure":
            value = parse_numeric_value(raw_value)
            if value is None:
                raise ValueError(f"أدخل رقمًا صالحًا للعامود {column} في صف Excel {source_row}.")
        elif role == "date":
            value = pd.to_datetime(raw_value, errors="coerce")
            if pd.isna(value):
                raise ValueError(f"أدخل تاريخًا صالحًا للعامود {column} في صف Excel {source_row}.")
        else:
            frame[column] = frame[column].astype("object")
            value = str(raw_value).strip()
            if not value:
                raise ValueError(f"القيمة اليدوية للعامود {column} في صف Excel {source_row} لا يمكن أن تكون فارغة.")
        frame.at[position, column] = value
        actions.append({
            "column": column,
            "count": 1,
            "strategy": "manual",
            "fill_value": value.isoformat() if isinstance(value, pd.Timestamp) else value,
            "source_rows": [source_row],
            "explanation": "استخدمت بيّنة القيمة التي أدخلها المستخدم يدويًا قبل بدء التحليل.",
        })
    return actions


def clean_dataset(
    frame: pd.DataFrame,
    profiles: list[Any],
    missing_value_mode: str = "recommended",
    missing_value_overrides: list[dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, DataCleaningAudit]:
    """Create a conservative typed working copy and its complete audit record."""
    cleaned, normalized_text_cells = _normalize_text_cells(frame)
    summary_positions = _summary_row_positions(cleaned, profiles)
    source_row_numbers = [position + 2 for position in summary_positions]
    retained_excel_rows = [position + 2 for position in range(len(cleaned))]
    if summary_positions:
        keep = [position for position in range(len(cleaned)) if position not in set(summary_positions)]
        cleaned = cleaned.iloc[keep].reset_index(drop=True)
        retained_excel_rows = [retained_excel_rows[position] for position in keep]

    excluded_empty_columns = [str(column) for column in cleaned.columns if cleaned[column].isna().all()]
    if excluded_empty_columns:
        cleaned = cleaned.drop(columns=excluded_empty_columns)

    numeric_conversions = 0
    invalid_numeric_cells = 0
    date_conversions = 0
    invalid_date_cells = 0
    formula_calculations = 0
    for profile in profiles:
        name = str(_profile_value(profile, "name"))
        role = _profile_value(profile, "semantic_role")
        if name not in cleaned.columns:
            continue
        if role == "measure":
            cleaned[name] = cleaned[name].astype("object")
            for position, excel_row in enumerate(retained_excel_rows):
                calculated = _evaluate_row_formula(cleaned.iat[position, cleaned.columns.get_loc(name)], cleaned, position, excel_row)
                if calculated is not None:
                    cleaned.iat[position, cleaned.columns.get_loc(name)] = calculated
                    formula_calculations += 1
            numeric, converted, invalid = coerce_numeric_series(cleaned[name])
            cleaned[name] = numeric
            numeric_conversions += converted
            invalid_numeric_cells += invalid
        elif role == "date":
            source = cleaned[name]
            parsed = pd.to_datetime(source, errors="coerce")
            source_present = source.map(lambda value: not _is_missing(value))
            invalid_date_cells += int((source_present & parsed.isna()).sum())
            date_conversions += int(sum(
                present and not isinstance(value, datetime | date) and not _is_missing(parsed_value)
                for value, parsed_value, present in zip(source.tolist(), parsed.tolist(), source_present.tolist(), strict=True)
            ))
            cleaned[name] = parsed

    duplicate_positions = [position for position, duplicate in enumerate(cleaned.duplicated(keep="first").tolist()) if duplicate]
    removed_duplicate_rows = [retained_excel_rows[position] for position in duplicate_positions]
    if duplicate_positions:
        duplicate_set = set(duplicate_positions)
        keep = [position for position in range(len(cleaned)) if position not in duplicate_set]
        cleaned = cleaned.iloc[keep].reset_index(drop=True)
        retained_excel_rows = [retained_excel_rows[position] for position in keep]

    missing_values_before = {
        str(column): int(cleaned[column].isna().sum())
        for column in cleaned.columns
        if cleaned[column].isna().any()
    }
    missing_locations = {
        str(column): _source_rows(cleaned[column].isna(), retained_excel_rows)
        for column in cleaned.columns
        if cleaned[column].isna().any()
    }
    imputation_actions: list[dict[str, Any]] = []
    if missing_value_mode == "manual":
        imputation_actions.extend(_apply_manual_overrides(
            cleaned,
            profiles,
            retained_excel_rows,
            missing_value_overrides or [],
        ))
    elif missing_value_mode == "recommended":
        imputation_actions.extend(_repair_derived_sales(cleaned, profiles, retained_excel_rows))
    else:
        raise ValueError("طريقة معالجة القيم الناقصة غير مدعومة.")

    for profile in profiles if missing_value_mode == "recommended" else []:
        name = str(_profile_value(profile, "name"))
        role = _profile_value(profile, "semantic_role")
        if role != "identifier" or name not in cleaned.columns or not cleaned[name].isna().any():
            continue
        repaired, repaired_count, sequence = _repair_sequential_identifier(cleaned[name])
        if repaired_count:
            cleaned[name] = repaired
            imputation_actions.append({
                "column": name,
                "count": repaired_count,
                "strategy": "sequential",
                "fill_value": sequence,
                "source_rows": missing_locations.get(name, []),
                "explanation": "أُكمل المعرّف من النمط التصاعدي المثبت في الصفوف المجاورة دون تغيير المعرّفات الموجودة.",
            })

    for profile in profiles if missing_value_mode == "recommended" else []:
        name = str(_profile_value(profile, "name"))
        role = _profile_value(profile, "semantic_role")
        if name not in cleaned.columns:
            continue
        missing_count = int(cleaned[name].isna().sum())
        if not missing_count:
            continue
        strategy = "retained"
        fill_value: float | str | None = None
        explanation = "أُبقيت للمراجعة لأن تعويضها تلقائيًا قد يختلق قيمة غير صحيحة."
        if role == "measure":
            valid = pd.to_numeric(cleaned[name], errors="coerce").dropna()
            if not valid.empty:
                strategy = "mean" if _is_monetary_column(name) else "median"
                fill_value = float(valid.mean() if strategy == "mean" else valid.median())
                cleaned[name] = cleaned[name].fillna(fill_value)
                explanation = (
                    "عُوّضت بمتوسط القيم الصحيحة في العامود المالي."
                    if strategy == "mean" else
                    "عُوّضت بوسيط القيم الصحيحة للحد من أثر القيم الشاذة."
                )
        elif role == "dimension":
            strategy = "label"
            fill_value = "غير محدد"
            cleaned[name] = cleaned[name].fillna(fill_value)
            explanation = "وُسمت بغير محدد بدل اختلاق فئة أو اسم غير موجود."
        imputation_actions.append({
            "column": name,
            "count": missing_count,
            "strategy": strategy,
            "fill_value": fill_value,
            "source_rows": _source_rows(cleaned[name].isna(), retained_excel_rows) if strategy == "retained" else missing_locations.get(name, []),
            "explanation": explanation,
        })

    if missing_value_mode == "manual":
        for profile in profiles:
            name = str(_profile_value(profile, "name"))
            if name not in cleaned.columns:
                continue
            missing_count = int(cleaned[name].isna().sum())
            if not missing_count:
                continue
            imputation_actions.append({
                "column": name,
                "count": missing_count,
                "strategy": "retained",
                "fill_value": None,
                "source_rows": _source_rows(cleaned[name].isna(), retained_excel_rows),
                "explanation": "لم يُدخل المستخدم قيمة لهذه الخلية؛ أُبقيت ناقصة للمراجعة ولم تُختلق قيمة بديلة.",
            })

    remaining_missing_values = {
        str(column): int(cleaned[column].isna().sum())
        for column in cleaned.columns
        if cleaned[column].isna().any()
    }

    audit = DataCleaningAudit(
        input_rows=len(frame),
        output_rows=len(cleaned),
        excluded_summary_rows=source_row_numbers,
        numeric_conversions=numeric_conversions,
        date_conversions=date_conversions,
        normalized_text_cells=normalized_text_cells,
        invalid_numeric_cells=invalid_numeric_cells,
        invalid_date_cells=invalid_date_cells,
        excluded_empty_columns=excluded_empty_columns,
        formula_calculations=formula_calculations,
        missing_value_mode=missing_value_mode,
        missing_values_before=missing_values_before,
        missing_locations=missing_locations,
        output_source_rows=retained_excel_rows,
        remaining_missing_values=remaining_missing_values,
        imputation_actions=imputation_actions,
        removed_duplicate_rows=removed_duplicate_rows,
    )
    return cleaned, audit


__all__ = [
    "DataCleaningAudit",
    "clean_dataset",
    "coerce_numeric_series",
    "is_numeric_like",
    "parse_numeric_value",
]