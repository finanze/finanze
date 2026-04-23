import base64
import uuid
from pathlib import Path
from typing import Optional

import js

from application.ports.file_storage_port import FileStoragePort
from domain.file_upload import FileUpload

STATIC_URL_PREFIX = "/static"


class MobileFileStorage(FileStoragePort):
    def __init__(self):
        pass

    async def save(
        self,
        file: FileUpload,
        folder: str,
        keep_name: bool = False,
        existing_url: Optional[str] = None,
    ) -> str:
        if not file.filename:
            raise ValueError("No filename provided")

        await js.jsBridge.filesystem.createDirectory(folder)

        if existing_url:
            existing_path = existing_url.replace(STATIC_URL_PREFIX + "/", "")
            unique_filename = Path(existing_path).name
        elif not keep_name:
            file_extension = Path(file.filename).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
        else:
            unique_filename = file.filename

        data = file.data.read()
        data_b64 = base64.b64encode(data).decode("ascii")

        file_path = f"{folder}/{unique_filename}"
        await js.jsBridge.filesystem.writeFile(file_path, data_b64, True)
        return file_path

    async def delete(self, file_path: str):
        await js.jsBridge.filesystem.deleteFile(file_path)

    def get_url(self, file_path: str) -> str:
        return f"{STATIC_URL_PREFIX}/{file_path}"

    async def delete_by_url(self, file_url: str) -> bool:
        file_path = file_url.replace(STATIC_URL_PREFIX + "/", "")
        return await js.jsBridge.filesystem.deleteFile(file_path)

    async def save_from_url(
        self, file_url: str, folder: str, filename: Optional[str] = None
    ) -> str:
        return file_url
