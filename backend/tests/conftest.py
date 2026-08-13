import os
import shutil
from pathlib import Path

import pytest

os.environ.setdefault("LLM_PROVIDER", "mock")

from app.config import SAMPLE_DIR, UPLOAD_DIR
from app.excel_service import inspect_xlsx
from app.storage import initialize_database, save_file_record


@pytest.fixture(scope="session", autouse=True)
def database():
    initialize_database()


@pytest.fixture()
def sales_record():
    source = SAMPLE_DIR / "مبيعات_عربية_مرتبة.xlsx"
    file_id = "a" * 32
    target = UPLOAD_DIR / f"{file_id}.xlsx"
    shutil.copy2(source, target)
    record = inspect_xlsx(target, source.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", file_id)
    save_file_record(record.model_dump())
    return record


@pytest.fixture()
def messy_record():
    source = SAMPLE_DIR / "بيانات_غير_مرتبة.xlsx"
    file_id = "b" * 32
    target = UPLOAD_DIR / f"{file_id}.xlsx"
    shutil.copy2(source, target)
    record = inspect_xlsx(target, source.name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", file_id)
    save_file_record(record.model_dump())
    return record
