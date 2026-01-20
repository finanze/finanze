from typing import Optional
from application.ports.file_storage_port import FileStoragePort


class MobileFileStorage(FileStoragePort):
    def __init__(self):
        pass

    def save(self, file_path: str, content: bytes) -> str:
        return file_path

    def delete(self, file_path: str):
        pass

    def get_url(self, file_path: str) -> str:
        return file_path

    def delete_by_url(self, file_url: str) -> bool:
        return True

    def save_from_url(
        self, file_url: str, folder: str, filename: Optional[str] = None
    ) -> str:
        return file_url
