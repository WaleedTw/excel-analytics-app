"""Safe natural-language custom calculations over verified numeric columns.

The instruction is converted into a tiny arithmetic language. No Python eval,
SQL fragments, function calls, attributes, or arbitrary identifiers are ever
accepted. Column aggregates are independently reconciled with DuckDB and
pandas before the final expression is evaluated.
"""

from __future__ import annotations

import ast
import math
import operator
import re
from dataclasses import dataclass
from typing import Any

import duckdb
import pandas as pd

from app.schemas import CustomCalculationRequest, CustomCalculationResponse


class CustomCalculationError(ValueError):
    pass


@dataclass(frozen=True)
class CalculationPlan:
    name: str
    expression: str
    token_expression: str
    tokens: dict[str, str]


_BIN_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def _clean_name(text: str) -> str:
    cleaned = re.sub(r"^(?:احسب|أنشئ|انشئ|أضف|اضف|calculate|create)\s+", "", text.strip(), flags=re.I)
    return cleaned.strip(" :-=")[:100] or "حساب مخصص"


def _replace_operator_words(text: str) -> str:
    replacements = (
        (r"\bمقسوم(?:ة)?\s+على\b|\bdivided\s+by\b", "/"),
        (r"\bمضروب(?:ة)?\s+في\b|\bmultiplied\s+by\b", "*"),
        (r"\bناقص\b|\bminus\b", "-"),
        (r"\bزائد\b|\bplus\b", "+"),
    )
    normalized = text.replace("÷", "/").replace("×", "*").replace("−", "-").replace("–", "-")
    for pattern, value in replacements:
        normalized = re.sub(pattern, value, normalized, flags=re.I)
    return normalized


def _mentioned_columns(text: str, columns: list[str]) -> list[str]:
    lowered = text.casefold()
    return [column for column in sorted(columns, key=len, reverse=True) if column.casefold() in lowered]


def _derive_expression(instruction: str, columns: list[str]) -> tuple[str, str]:
    if "=" in instruction:
        name, expression = instruction.split("=", 1)
        return _clean_name(name), _replace_operator_words(expression.strip())
    equals = re.split(r"\s+(?:يساوي|equals)\s+", instruction, maxsplit=1, flags=re.I)
    if len(equals) == 2:
        return _clean_name(equals[0]), _replace_operator_words(equals[1])

    mentioned = _mentioned_columns(instruction, columns)
    if len(mentioned) < 2:
        raise CustomCalculationError(
            "اكتب الحساب بصيغة واضحة، مثل: هامش الربح = الربح ÷ الإيرادات × 100."
        )
    normalized = _replace_operator_words(instruction)
    if "/" in normalized:
        expression = f"{mentioned[0]} / {mentioned[1]}"
    elif "-" in normalized:
        expression = f"{mentioned[0]} - {mentioned[1]}"
    elif "+" in normalized:
        expression = f"{mentioned[0]} + {mentioned[1]}"
    elif "*" in normalized:
        expression = f"{mentioned[0]} * {mentioned[1]}"
    else:
        raise CustomCalculationError("لم أتعرف على العملية الحسابية المطلوبة.")
    if re.search(r"نسبة|مئوية|percent|percentage|%", instruction, flags=re.I) and "/" in expression:
        expression += " * 100"
    return _clean_name(instruction.split(mentioned[0], 1)[0]), expression


def create_calculation_plan(instruction: str, numeric_columns: list[str]) -> CalculationPlan:
    name, expression = _derive_expression(instruction, numeric_columns)
    tokens: dict[str, str] = {}
    token_expression = expression
    for index, column in enumerate(sorted(numeric_columns, key=len, reverse=True)):
        if column.casefold() not in token_expression.casefold():
            continue
        token = f"c{index}"
        token_expression, count = re.subn(re.escape(column), token, token_expression, flags=re.I)
        if count:
            tokens[token] = column
    if not tokens:
        raise CustomCalculationError("لم أجد أي عامود رقمي معروف داخل صيغة الحساب.")
    token_expression = token_expression.replace("%", " / 100")
    tree = _parse_expression(token_expression, set(tokens))
    del tree
    return CalculationPlan(name=name, expression=expression, token_expression=token_expression, tokens=tokens)


def _parse_expression(expression: str, allowed_names: set[str]) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise CustomCalculationError("صيغة الحساب غير مكتملة أو غير مفهومة.") from exc
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression | ast.Load | ast.Constant | ast.BinOp):
            continue
        if isinstance(node, ast.Name) and node.id in allowed_names:
            continue
        if isinstance(node, tuple(_BIN_OPS)):
            continue
        raise CustomCalculationError("تحتوي الصيغة على عملية غير مسموحة. المتاح: + و- و× و÷ فقط.")
    return tree


def _evaluate(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant) and isinstance(node.value, int | float):
        return float(node.value)
    if isinstance(node, ast.Name) and node.id in values:
        return float(values[node.id])
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _evaluate(node.left, values)
        right = _evaluate(node.right, values)
        if isinstance(node.op, ast.Div) and math.isclose(right, 0.0, abs_tol=1e-12):
            raise CustomCalculationError("لا يمكن تنفيذ الحساب لأن المقام يساوي صفرًا.")
        result = _BIN_OPS[type(node.op)](left, right)
        if not math.isfinite(result):
            raise CustomCalculationError("نتيجة الحساب ليست رقمًا محدودًا صالحًا للعرض.")
        return float(result)
    raise CustomCalculationError("تعذر تنفيذ صيغة الحساب الآمنة.")


def _quoted(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def execute_custom_calculation(
    request: CustomCalculationRequest,
    frame: pd.DataFrame,
    columns: list[dict[str, Any]],
) -> CustomCalculationResponse:
    numeric_columns = [
        item["name"] for item in columns
        if item.get("semantic_role") == "measure" and item.get("name") in frame.columns
    ]
    if not numeric_columns:
        raise CustomCalculationError("لا توجد مقاييس رقمية تسمح بإنشاء حساب مخصص.")
    plan = create_calculation_plan(request.instruction, numeric_columns)
    source_columns = list(dict.fromkeys(plan.tokens.values()))
    prepared = frame.copy()
    for column in source_columns:
        prepared[column] = pd.to_numeric(prepared[column], errors="coerce")

    select = ", ".join(f"COALESCE(SUM({_quoted(column)}), 0) AS {_quoted(token)}" for token, column in plan.tokens.items())
    query = f"SELECT {select} FROM dataset"
    connection = duckdb.connect(database=":memory:")
    connection.register("dataset", prepared)
    try:
        duck_values = connection.execute(query).fetchone()
    finally:
        connection.close()
    duck_totals = {token: float(value or 0) for token, value in zip(plan.tokens, duck_values, strict=True)}
    pandas_totals = {
        token: float(pd.to_numeric(prepared[column], errors="coerce").sum())
        for token, column in plan.tokens.items()
    }
    for token in plan.tokens:
        if not math.isclose(duck_totals[token], pandas_totals[token], rel_tol=1e-9, abs_tol=1e-6):
            raise CustomCalculationError("فشل التحقق المستقل من أحد عواميد الحساب.")

    tree = _parse_expression(plan.token_expression, set(plan.tokens))
    duck_result = _evaluate(tree, duck_totals)
    pandas_result = _evaluate(tree, pandas_totals)
    if not math.isclose(duck_result, pandas_result, rel_tol=1e-9, abs_tol=1e-6):
        raise CustomCalculationError("فشل التحقق المزدوج من نتيجة الحساب المخصص.")
    is_percent = bool(re.search(r"نسبة|هامش|مئوية|percent|margin|\*\s*100", request.instruction, flags=re.I))
    return CustomCalculationResponse(
        name=plan.name,
        expression=plan.expression,
        value=round(duck_result, 6),
        format="percent" if is_percent else "decimal",
        source_columns=source_columns,
        verification="تمت مطابقة النتيجة مستقلًا بين DuckDB وPandas.",
        query=query,
    )


__all__ = [
    "CalculationPlan",
    "CustomCalculationError",
    "create_calculation_plan",
    "execute_custom_calculation",
]