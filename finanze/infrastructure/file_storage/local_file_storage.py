import uuid
from pathlib import Path

from application.ports.file_storage_port import FileStoragePort
from domain.file_upload import FileUpload


class LocalFileStorage(FileStoragePort):
    def __init__(self, upload_dir: Path, static_url_prefix: str):
        self.upload_dir = upload_dir
        self.static_url_prefix = static_url_prefix
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def save(self, file: FileUpload, folder: str) -> str:
        if not file.filename:
            raise ValueError("No filename provided")

        folder_path = self.upload_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
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
