from fastapi.testclient import TestClient

from app.main import app
from app.service import AnalysisService


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
        assert analysis.json()["status"] == "completed"
        assert analysis.json()["analysis_plan"]["mode"] == "mock"
        assert len(analysis.json()["dashboard"]["charts"]) >= 4
        restored = AnalysisService().get(analysis.json()["analysis_id"])
        assert restored.status == "completed"
        assert restored.dashboard is not None
