import uuid
from pathlib import Path
from typing import Optional

from application.ports.file_storage_port import FileStoragePort
from domain.file_upload import FileUpload


class LocalFileStorage(FileStoragePort):
    def __init__(self, upload_dir: Path, static_url_prefix: str):
        self.upload_dir = upload_dir
        self.static_url_prefix = static_url_prefix
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file: FileUpload, folder: str, keep_name: bool = False) -> str:
        if not file.filename:
            raise ValueError("No filename provided")

        folder_path = self.upload_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        if not keep_name:
            file_extension = Path(file.filename).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
        else:
            unique_filename = file.filename

        file_path = folder_path / unique_filename

        try:
            with open(file_path, "wb") as f:
                while True:
                    chunk = file.data.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            raise ValueError(f"Failed to save file: {str(e)}")

        return f"{folder}/{unique_filename}"

    def save_from_url(
        self, file_url: str, folder: str, filename: Optional[str] = None
    ) -> str:
        import requests

        response = requests.get(file_url, stream=True)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch file from URL: {file_url}")

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        content_length = int(response.headers.get("Content-Length", 0))

        if not filename:
            filename = file_url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4()}"

        file_upload = FileUpload(
            filename=filename,
            content_type=content_type,
            content_length=content_length,
            data=response.raw,
        )

        return self.save(file_upload, folder, keep_name=True)

    def delete(self, file_path: str) -> bool:
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False

    def get_url(self, file_path: str) -> str:
        return f"{self.static_url_prefix}/{file_path}"

    def delete_by_url(self, file_url: str) -> bool:
        file_path = Path(file_url.replace(self.static_url_prefix + "/", ""))
        return self.delete(str(file_path))
