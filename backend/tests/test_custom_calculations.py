import pandas as pd
import pytest

from app.custom_calculations import CustomCalculationError, execute_custom_calculation
from app.schemas import CustomCalculationRequest


COLUMNS = [
    {"name": "الإيرادات", "semantic_role": "measure"},
    {"name": "الربح", "semantic_role": "measure"},
    {"name": "الشركة", "semantic_role": "dimension"},
]


def test_natural_language_margin_is_verified_with_two_engines():
    frame = pd.DataFrame({"الشركة": ["أ", "ب"], "الإيرادات": [1000, 500], "الربح": [200, 100]})
    result = execute_custom_calculation(
        CustomCalculationRequest(instruction="هامش الربح = الربح ÷ الإيرادات × 100"),
        frame,
        COLUMNS,
    )

    assert result.name == "هامش الربح"
    assert result.value == pytest.approx(20)
    assert result.format == "percent"
    assert result.source_columns == ["الإيرادات", "الربح"] or result.source_columns == ["الربح", "الإيرادات"]
    assert "DuckDB" in result.verification and "Pandas" in result.verification


def test_custom_calculation_rejects_code_and_function_calls():
    frame = pd.DataFrame({"الإيرادات": [100], "الربح": [20]})
    with pytest.raises(CustomCalculationError):
        execute_custom_calculation(
            CustomCalculationRequest(instruction="خطر = __import__('os')"),
            frame,
            COLUMNS,
        )


def test_custom_calculation_rejects_zero_denominator():
    frame = pd.DataFrame({"الإيرادات": [0], "الربح": [20]})
    with pytest.raises(CustomCalculationError, match="المقام"):
        execute_custom_calculation(
            CustomCalculationRequest(instruction="هامش الربح = الربح ÷ الإيرادات × 100"),
            frame,
            COLUMNS,
        )