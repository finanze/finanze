import logging

import js
from pyodide.ffi import to_js

from domain.backup import BackupFileType
from domain.exception.exceptions import TooManyRequests
from infrastructure.cloud.backup.staging_registry import get_file_name
from infrastructure.client.cloud.backup.file_transfer_strategy import (
    FileTransferStrategy,
)


def _get_plugin():
    plugin = js.window.FileTransfer
    if plugin is None:
        raise RuntimeError("FileTransfer plugin not available")
    return plugin


class CapacitorFileTransferStrategy(FileTransferStrategy):
    TIMEOUT = 60000

    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def upload(
        self,
        url: str,
        method: str,
        payload: bytes,
        headers: dict[str, str],
        backup_type: BackupFileType,
    ) -> None:
        plugin = _get_plugin()

        file_name = get_file_name(backup_type, "compiled")
        self._log.info(f"Uploading file {file_name} to {url}")

        try:
            self._log.info(f"Starting native upload: {file_name}")
            options = {
                "url": url,
                "fileName": file_name,
                "method": method,
                "headers": headers,
                "timeout": self.TIMEOUT,
            }
            result = await plugin.upload(to_js(options, create_pyproxies=False))
            result_py = result.to_py() if hasattr(result, "to_py") else result

            if not result_py.get("success"):
                status = result_py.get("status", 0)
                if status == 429:
                    raise TooManyRequests()
                raise RuntimeError(f"Upload failed with status {status}")

            self._log.info(f"Upload successful: {file_name}")

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "TOO_MANY_REQUESTS" in error_msg:
                raise TooManyRequests() from e
            self._log.error(f"Upload failed: {e}")
            raise

    async def download(self, url: str, backup_type: BackupFileType) -> bytes:
        plugin = _get_plugin()

        file_name = get_file_name(backup_type, "imported")
        self._log.info(f"Downloading to {file_name} from {url}")

        try:
            self._log.info(f"Starting native download: {file_name}")
            options = {
                "url": url,
                "fileName": file_name,
                "timeout": self.TIMEOUT,
            }
            result = await plugin.download(to_js(options, create_pyproxies=False))
            result_py = result.to_py() if hasattr(result, "to_py") else result

            if not result_py.get("success"):
                status = result_py.get("status", 0)
                if status == 429:
                    raise TooManyRequests()
                raise RuntimeError(f"Download failed with status {status}")

            size = result_py.get("size", 0)
            self._log.info(f"Download successful: {file_name}, size={size}")
            return b""

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "TOO_MANY_REQUESTS" in error_msg:
                raise TooManyRequests() from e
            self._log.error(f"Download failed: {e}")
            raise
