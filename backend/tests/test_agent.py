import json
import sys
from types import SimpleNamespace

import pytest

from app import agent


COLUMNS = [
    {
        "name": "الإيرادات", "inferred_type": "number", "semantic_role": "measure",
        "null_count": 0, "unique_count": 3, "sample_values": ["سر-لا-ترسله"],
        "ambiguous": False, "reason": "",
    },
    {
        "name": "المدينة", "inferred_type": "category", "semantic_role": "dimension",
        "null_count": 0, "unique_count": 2, "sample_values": ["الرياض"],
        "ambiguous": False, "reason": "",
    },
]


def _response(measures=None):
    return json.dumps({
        "objective": "تحليل الأداء حسب المدينة بطريقة موثقة وآمنة.",
        "measures": measures or ["الإيرادات"],
        "dimensions": ["المدينة"],
        "dates": [],
        "chart_strategy": ["category_comparison", "share"],
        "privacy": "استُخدمت البيانات الوصفية فقط دون إرسال صفوف المصنف.",
    }, ensure_ascii=False)


def test_ollama_structured_plan_excludes_sample_values(monkeypatch):
    captured = {}

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def chat(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(message=SimpleNamespace(content=_response()))

    monkeypatch.setattr(agent, "LLM_PROVIDER", "ollama")
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=FakeClient))
    plan = agent.create_analysis_plan(COLUMNS, {"score": 95})

    assert plan["mode"] == "ollama"
    assert plan["measures"] == ["الإيرادات"]
    assert "سر-لا-ترسله" not in captured["messages"][1]["content"]
    assert captured["format"]["type"] == "object"


def test_ollama_plan_rejects_hallucinated_columns(monkeypatch):
    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def chat(self, **_kwargs):
            return SimpleNamespace(message=SimpleNamespace(content=_response(["عمود غير موجود"])))

    monkeypatch.setattr(agent, "LLM_PROVIDER", "ollama")
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(Client=FakeClient))

    with pytest.raises(agent.LLMProviderError, match="أعمدة غير مسموحة"):
        agent.create_analysis_plan(COLUMNS, {"score": 95})


def test_groq_plan_uses_json_mode_and_excludes_sample_values(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=_response()))]
            )

    class FakeGroq:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(agent, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(agent, "GROQ_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))

    plan = agent.create_analysis_plan(COLUMNS, {"score": 95})

    assert plan["mode"] == "groq"
    assert plan["model"] == "llama-3.3-70b-versatile"
    assert captured["response_format"] == {"type": "json_object"}
    assert "سر-لا-ترسله" not in captured["messages"][1]["content"]


def test_groq_requires_api_key(monkeypatch):
    monkeypatch.setattr(agent, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(agent, "GROQ_API_KEY", "")

    with pytest.raises(agent.LLMProviderError, match="GROQ_API_KEY"):
        agent.create_analysis_plan(COLUMNS, {"score": 95})
