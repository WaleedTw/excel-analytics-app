from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.agent import get_llm_status
from app.config import CORS_ORIGIN_REGEX, FRONTEND_ORIGINS
from app.custom_calculations import CustomCalculationError
from app.data_loader import FileValidationError, preview_dataset, register_sample, store_upload
from app.logging_config import configure_logging
from app.i18n import (
    Locale, localize_analysis_response, localize_custom_calculation,
    localize_health_response, localize_preview_response, translate_error,
)
from app.schemas import (
    AnalysisAnswer, AnalysisQuestion, AnalysisResponse, AnalysisStart, ClarificationAnswer, HealthResponse,
    CustomCalculationRequest, CustomCalculationResponse, PreviewResponse, WorkbookInfo,
)
from app.service import AnalysisService
from app.storage import get_file_record, initialize_database, purge_previous_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    initialize_database()
    purge_previous_data()
    yield


app = FastAPI(title="بيّنة API", version="2.0.0", lifespan=lifespan)
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
def health(locale: Locale = "ar") -> HealthResponse:
    llm = get_llm_status()
    response = HealthResponse(
        status="ok" if llm["ready"] else "degraded",
        mode=llm["mode"], model=llm["model"], llm_ready=llm["ready"], detail=llm["detail"],
        database="sqlite", jobs="background",
    )
    return localize_health_response(response, locale)


@app.post("/api/v1/files", response_model=WorkbookInfo)
async def upload_file(file: UploadFile = File(...), locale: Locale = "ar") -> WorkbookInfo:
    try: return await store_upload(file)
    except FileValidationError as exc: raise HTTPException(status_code=422, detail=translate_error(str(exc), locale)) from exc


@app.post("/api/v1/samples/{kind}", response_model=WorkbookInfo)
def load_sample(kind: str, locale: Locale = "ar") -> WorkbookInfo:
    try: return register_sample(kind)
    except FileValidationError as exc: raise HTTPException(status_code=404, detail=translate_error(str(exc), locale)) from exc


@app.get("/api/v1/files/{file_id}", response_model=WorkbookInfo)
def get_file(file_id: str, locale: Locale = "ar") -> WorkbookInfo:
    record = get_file_record(file_id)
    if not record: raise HTTPException(status_code=404, detail=translate_error("الملف غير موجود.", locale))
    return WorkbookInfo.model_validate(record)


@app.get("/api/v1/files/{file_id}/preview", response_model=PreviewResponse)
def preview(file_id: str, sheet: str, locale: Locale = "ar") -> PreviewResponse:
    try: return localize_preview_response(preview_dataset(file_id, sheet), locale)
    except FileValidationError as exc: raise HTTPException(status_code=404, detail=translate_error(str(exc), locale)) from exc


@app.post("/api/v1/analyses", response_model=AnalysisResponse)
def start_analysis(request: AnalysisStart, locale: Locale = "ar") -> AnalysisResponse:
    try: return localize_analysis_response(service.start_background(request), locale)
    except KeyError as exc: raise HTTPException(status_code=404, detail=translate_error("الملف غير موجود.", locale)) from exc
    except ValueError as exc: raise HTTPException(status_code=422, detail=translate_error(str(exc), locale)) from exc


@app.post("/api/v1/analyses/{analysis_id}/resume", response_model=AnalysisResponse)
def resume_analysis(analysis_id: str, answer: ClarificationAnswer, locale: Locale = "ar") -> AnalysisResponse:
    try: return localize_analysis_response(service.resume_background(analysis_id, answer), locale)
    except KeyError as exc: raise HTTPException(status_code=404, detail=translate_error("التحليل غير موجود.", locale)) from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=translate_error(str(exc), locale)) from exc


@app.get("/api/v1/analyses/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, locale: Locale = "ar") -> AnalysisResponse:
    try: return localize_analysis_response(service.get(analysis_id), locale)
    except KeyError as exc: raise HTTPException(status_code=404, detail=translate_error("التحليل غير موجود.", locale)) from exc


@app.post("/api/v1/analyses/{analysis_id}/ask", response_model=AnalysisAnswer)
def ask_analysis(analysis_id: str, request: AnalysisQuestion, locale: Locale = "ar") -> AnalysisAnswer:
    try: return service.ask(analysis_id, request, locale)
    except KeyError as exc: raise HTTPException(status_code=404, detail=translate_error("التحليل غير موجود.", locale)) from exc
    except ValueError as exc: raise HTTPException(status_code=409, detail=translate_error(str(exc), locale)) from exc


@app.post("/api/v1/analyses/{analysis_id}/calculations", response_model=CustomCalculationResponse)
def create_custom_calculation(
    analysis_id: str,
    request: CustomCalculationRequest,
    locale: Locale = "ar",
) -> CustomCalculationResponse:
    try:
        return localize_custom_calculation(service.calculate(analysis_id, request), locale)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=translate_error("التحليل غير موجود.", locale)) from exc
    except CustomCalculationError as exc:
        raise HTTPException(status_code=422, detail=translate_error(str(exc), locale)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=translate_error(str(exc), locale)) from exc