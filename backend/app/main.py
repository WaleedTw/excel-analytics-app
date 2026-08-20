from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agent import get_llm_status
from app.config import CORS_ORIGIN_REGEX, FRONTEND_ORIGINS
from app.excel_service import FileValidationError, preview_sheet, register_sample, store_upload
from app.logging_config import configure_logging
from app.schemas import (
    AnalysisAnswer, AnalysisQuestion, AnalysisResponse, AnalysisStart, ClarificationAnswer, HealthResponse,
    PreviewResponse, WorkbookInfo,
)
from app.service import AnalysisService
from app.storage import get_file_record, initialize_database, purge_previous_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    initialize_database()
    purge_previous_data()
    yield


app = FastAPI(title="بيّنة API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type"],
)
service = AnalysisService()


@app.get("/api/v1/health", response_model=HealthResponse)
def health() -> HealthResponse:
    llm = get_llm_status()
    return HealthResponse(
        status="ok" if llm["ready"] else "degraded",
        mode=llm["mode"], model=llm["model"], llm_ready=llm["ready"], detail=llm["detail"],
        database="sqlite", jobs="background",
    )


@app.post("/api/v1/files", response_model=WorkbookInfo)
async def upload_file(file: UploadFile = File(...)) -> WorkbookInfo:
    try: return await store_upload(file)
    except FileValidationError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/samples/{kind}", response_model=WorkbookInfo)
def load_sample(kind: str) -> WorkbookInfo:
    try: return register_sample(kind)
    except FileValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/files/{file_id}", response_model=WorkbookInfo)
def get_file(file_id: str) -> WorkbookInfo:
    record = get_file_record(file_id)
    if not record: raise HTTPException(status_code=404, detail="الملف غير موجود.")
    return WorkbookInfo.model_validate(record)


@app.get("/api/v1/files/{file_id}/preview", response_model=PreviewResponse)
def preview(file_id: str, sheet: str) -> PreviewResponse:
    try: return preview_sheet(file_id, sheet)
    except FileValidationError as exc: raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/analyses", response_model=AnalysisResponse)
def start_analysis(request: AnalysisStart) -> AnalysisResponse:
    try: return service.start_background(request)
    except KeyError as exc: raise HTTPException(status_code=404, detail="الملف غير موجود.") from exc
    except ValueError as exc: raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/analyses/{analysis_id}/resume", response_model=AnalysisResponse)
def resume_analysis(analysis_id: str, answer: ClarificationAnswer) -> AnalysisResponse:
    try: return service.resume_background(analysis_id, answer)
    except KeyError as exc: raise HTTPException(status_code=404, detail="التحليل غير موجود.") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str) -> AnalysisResponse:
    try: return service.get(analysis_id)
    except KeyError as exc: raise HTTPException(status_code=404, detail="التحليل غير موجود.") from exc


@app.post("/api/v1/analyses/{analysis_id}/ask", response_model=AnalysisAnswer)
def ask_analysis(analysis_id: str, request: AnalysisQuestion) -> AnalysisAnswer:
    try: return service.ask(analysis_id, request)
    except KeyError as exc: raise HTTPException(status_code=404, detail="التحليل غير موجود.") from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=str(exc)) from exc
