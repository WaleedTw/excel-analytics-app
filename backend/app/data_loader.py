"""Unified, security-conscious ingestion for Excel and CSV datasets.

The loader is deliberately not an agent: it is deterministic infrastructure
that normalizes supported files into the same pandas/DataFrame contract before
the three analysis agents run.
"""

from __future__ import annotations

import csv
import mimetypes
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi import UploadFile

from app.data_cleaning import clean_dataset
from app.config import MAX_COLUMNS, MAX_FILE_SIZE, MAX_ROWS, SAMPLE_DIR, UPLOAD_DIR
from app.excel_service import (
    ALLOWED_MIME_TYPES as EXCEL_MIME_TYPES,
    SAFE_NAME,
    FileValidationError,
    infer_columns,
    inspect_xlsx,
    profile_quality,
    read_sheet,
)
from app.schemas import PreviewResponse, SheetInfo, WorkbookInfo
from app.storage import get_file_record, save_file_record

CSV_SHEET_NAME = "Data"
SUPPORTED_EXTENSIONS = {".xlsx", ".csv"}
CSV_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
}
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1256")
CSV_DELIMITERS = (",", ";", "\t", "|")


def _path_is_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _decode_csv_sample(content: bytes) -> tuple[str, str]:
    if b"\x00" in content[:8192]:
        raise FileValidationError("ملف CSV يحتوي على بيانات ثنائية غير مسموحة.")
    for encoding in CSV_ENCODINGS:
        try:
            return content.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise FileValidationError("تعذر قراءة ترميز CSV. استخدم UTF-8 أو Windows-1256.")


def _csv_options(content: bytes) -> tuple[str, str]:
    text, encoding = _decode_csv_sample(content[:65536])
    sample = text[:32768]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="".join(CSV_DELIMITERS)).delimiter
    except csv.Error:
        delimiter = ","
    return encoding, delimiter


def _read_csv(path: Path) -> pd.DataFrame:
    if not (_path_is_inside(path, UPLOAD_DIR) or _path_is_inside(path, SAMPLE_DIR)):
        raise FileValidationError("مسار الملف خارج نطاق المشروع الآمن.")
    content = path.read_bytes()
    encoding, delimiter = _csv_options(content)
    try:
        frame = pd.read_csv(
            path,
            encoding=encoding,
            sep=delimiter,
            engine="python",
            nrows=MAX_ROWS + 1,
            on_bad_lines="error",
        )
    except (pd.errors.ParserError, UnicodeError, ValueError) as exc:
        raise FileValidationError("ملف CSV تالف أو لا يحتوي بنية جدول صالحة.") from exc
    if len(frame) > MAX_ROWS or len(frame.columns) > MAX_COLUMNS:
        raise FileValidationError("حجم ملف CSV يتجاوز حدود الصفوف أو العواميد الآمنة.")
    if frame.empty or not len(frame.columns):
        raise FileValidationError("لا يحتوي ملف CSV على بيانات قابلة للتحليل.")
    frame.columns = [str(column).strip() or f"عامود_{index + 1}" for index, column in enumerate(frame.columns)]
    object_columns = frame.select_dtypes(include=["object", "string"]).columns
    if len(object_columns):
        frame[object_columns] = frame[object_columns].replace(r"^\s*$", pd.NA, regex=True)
    return frame


def inspect_data_file(path: Path, original_name: str, mime_type: str, file_id: str) -> WorkbookInfo:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return inspect_xlsx(path, original_name, mime_type, file_id)
    if suffix != ".csv":
        raise FileValidationError("الامتداد المدعوم هو XLSX أو CSV فقط.")
    frame = _read_csv(path)
    return WorkbookInfo(
        file_id=file_id,
        original_name=original_name,
        safe_name=path.name,
        size_bytes=path.stat().st_size,
        mime_type=mime_type,
        sheets=[SheetInfo(name=CSV_SHEET_NAME, rows=len(frame) + 1, columns=len(frame.columns), has_data=True)],
        created_at=datetime.now(timezone.utc),
    )


async def store_upload(upload: UploadFile) -> WorkbookInfo:
    original = Path(upload.filename or "").name
    if original != (upload.filename or "") or not original or not SAFE_NAME.match(original):
        raise FileValidationError("اسم الملف غير آمن.")
    suffix = Path(original).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise FileValidationError("الامتداد المدعوم هو XLSX أو CSV فقط.")
    mime_type = upload.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream"
    allowed_mimes = EXCEL_MIME_TYPES if suffix == ".xlsx" else CSV_MIME_TYPES
    if mime_type not in allowed_mimes:
        raise FileValidationError("نوع MIME للملف غير مدعوم.")
    content = await upload.read(MAX_FILE_SIZE + 1)
    if not content:
        raise FileValidationError("الملف فارغ.")
    if len(content) > MAX_FILE_SIZE:
        raise FileValidationError("حجم الملف يتجاوز الحد المسموح.")
    if suffix == ".xlsx" and content[:2] != b"PK":
        raise FileValidationError("توقيع الملف لا يطابق ملف Excel حديثًا.")
    if suffix == ".csv":
        _csv_options(content)

    file_id = uuid4().hex
    safe_path = UPLOAD_DIR / f"{file_id}{suffix}"
    safe_path.write_bytes(content)
    try:
        info = inspect_data_file(safe_path, original, mime_type, file_id)
    except Exception:
        safe_path.unlink(missing_ok=True)
        raise
    save_file_record(info.model_dump())
    return info


def register_sample(kind: str) -> WorkbookInfo:
    filenames = {"sales": "مبيعات_عربية_مرتبة.xlsx", "messy": "بيانات_غير_مرتبة.xlsx"}
    if kind not in filenames:
        raise FileValidationError("ملف التجربة غير معروف.")
    source = SAMPLE_DIR / filenames[kind]
    if not source.exists():
        raise FileValidationError("ملف التجربة غير متاح.")
    file_id = uuid4().hex
    target = UPLOAD_DIR / f"{file_id}.xlsx"
    shutil.copy2(source, target)
    info = inspect_data_file(
        target,
        filenames[kind],
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        file_id,
    )
    save_file_record(info.model_dump())
    return info


def file_path_for(file_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", file_id):
        raise FileValidationError("معرف الملف غير صالح.")
    record = get_file_record(file_id)
    if not record:
        raise FileValidationError("الملف غير موجود.")
    suffix = Path(record["safe_name"]).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise FileValidationError("نوع الملف المسجل غير مدعوم.")
    path = UPLOAD_DIR / f"{file_id}{suffix}"
    if not path.exists() or not _path_is_inside(path, UPLOAD_DIR):
        raise FileValidationError("الملف غير موجود.")
    return path


def read_dataset(path: Path, sheet_name: str) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        if sheet_name != CSV_SHEET_NAME:
            raise FileValidationError("مجموعة بيانات CSV لا تحتوي ورقة بهذا الاسم.")
        return _read_csv(path)
    return read_sheet(path, sheet_name)


def preview_dataset(file_id: str, sheet_name: str, mapping: dict[str, str] | None = None) -> PreviewResponse:
    source_frame = read_dataset(file_path_for(file_id), sheet_name)
    source_profiles = infer_columns(source_frame, mapping)
    frame, cleaning_audit = clean_dataset(source_frame, source_profiles)
    rows = []
    # The preview is the user's review surface, so return every cleaned data row.
    # The frontend keeps the table in a bounded, scrollable region with a sticky
    # header instead of silently hiding records after an arbitrary row limit.
    for row in frame.to_dict(orient="records"):
        normalized: dict[str, object] = {}
        for key, value in row.items():
            if pd.isna(value):
                normalized[str(key)] = None
            elif isinstance(value, (pd.Timestamp, datetime)):
                normalized[str(key)] = value.isoformat()
            elif hasattr(value, "item"):
                normalized[str(key)] = value.item()
            else:
                normalized[str(key)] = value
        rows.append(normalized)
    return PreviewResponse(
        file_id=file_id,
        sheet_name=sheet_name,
        columns=infer_columns(frame, mapping),
        rows=rows,
        total_rows=len(frame),
        cleaning_audit=cleaning_audit.model_dump(),
    )


__all__ = [
    "FileValidationError",
    "file_path_for",
    "infer_columns",
    "inspect_data_file",
    "preview_dataset",
    "profile_quality",
    "read_dataset",
    "register_sample",
    "store_upload",
]