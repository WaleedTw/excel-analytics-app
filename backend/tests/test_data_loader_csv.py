from io import BytesIO
import asyncio

import pytest
from starlette.datastructures import UploadFile

from app.data_loader import CSV_SHEET_NAME, FileValidationError, preview_dataset, store_upload


def test_csv_upload_is_normalized_to_dataset_contract():
    content = "الشركة,الإيرادات,الربح\nجرير,1000,200\nالنهدي,900,180\n".encode("utf-8-sig")
    upload = UploadFile(filename="مبيعات.csv", file=BytesIO(content), headers={"content-type": "text/csv"})

    info = asyncio.run(store_upload(upload))
    preview = preview_dataset(info.file_id, CSV_SHEET_NAME)

    assert info.safe_name.endswith(".csv")
    assert [sheet.name for sheet in info.sheets] == [CSV_SHEET_NAME]
    assert preview.total_rows == 2
    assert {column.name: column.semantic_role for column in preview.columns}["الإيرادات"] == "measure"


def test_binary_content_cannot_be_disguised_as_csv():
    upload = UploadFile(
        filename="unsafe.csv",
        file=BytesIO(b"column\x00name,value\nA,1"),
        headers={"content-type": "text/csv"},
    )
    with pytest.raises(FileValidationError, match="ثنائية"):
        asyncio.run(store_upload(upload))