import time

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["service"] == "bayyinah-backend"
        assert response.json()["mode"] == "mock"
        assert response.json()["llm_ready"] is True
        assert response.json()["model"] == "deterministic-test-double"


def test_full_sample_api_journey():
    with TestClient(app) as client:
        workbook = client.post("/api/v1/samples/sales").json()
        assert workbook["sheets"][0]["name"] == "المبيعات"
        preview = client.get(f"/api/v1/files/{workbook['file_id']}/preview", params={"sheet": "المبيعات"})
        assert preview.status_code == 200
        analysis = client.post("/api/v1/analyses", json={"file_id": workbook["file_id"], "sheet_name": "المبيعات", "max_iterations": 3})
        assert analysis.status_code == 200
        assert analysis.json()["status"] in {"queued", "running"}

        analysis_id = analysis.json()["analysis_id"]
        result = analysis.json()
        for _ in range(100):
            result = client.get(f"/api/v1/analyses/{analysis_id}").json()
            if result["status"] not in {"queued", "running"}:
                break
            time.sleep(0.02)

        assert result["status"] == "completed"
        assert result["analysis_plan"]["mode"] == "mock"
        assert len(result["dashboard"]["charts"]) >= 4
        assert all(kpi["id"] != "quality" for kpi in result["dashboard"]["kpis"])
        assert len(result["dashboard"]["kpis"]) == 4
        answer = client.post(f"/api/v1/analyses/{analysis_id}/ask", json={"question": "ما أبرز نتيجة؟"})
        assert answer.status_code == 200
        assert answer.json()["answer"]
        calculation = client.post(
            f"/api/v1/analyses/{analysis_id}/calculations",
            json={"instruction": "هامش الربح = الربح ÷ الإيرادات × 100"},
        )
        assert calculation.status_code == 200
        assert calculation.json()["format"] == "percent"
        assert "DuckDB" in calculation.json()["verification"]
        assert {run["agent"] for run in result["agent_runs"]} == {
            "cleaning_agent", "analysis_agent", "dashboard_agent",
        }
        assert result["cleaning_audit"]["output_rows"] <= result["cleaning_audit"]["input_rows"]
        assert result["cleaning_audit"]["policy"]
        assert client.get(f"/api/v1/files/{workbook['file_id']}").status_code == 404