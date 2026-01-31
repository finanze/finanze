import base64
import logging

import js
from pyodide.ffi import to_js

from application.ports.backup_processor import BackupProcessor
from domain.backup import BackupProcessRequest, BackupProcessResult
from domain.exception.exceptions import (
    UnsupportedBackupProtocol,
    InvalidBackupCredentials,
)
from infrastructure.cloud.backup.staging_registry import get_file_name


def _get_plugin():
    plugin = js.window.BackupProcessor
    if plugin is None:
        raise RuntimeError("BackupProcessor plugin not available")
    return plugin


class CapacitorBackupProcessorAdapter(BackupProcessor):
    def __init__(self):
        self._log = logging.getLogger(__name__)

    async def compile(self, data: BackupProcessRequest) -> BackupProcessResult:
        plugin = _get_plugin()

        input_file = get_file_name(data.type, "exported")
        output_file = get_file_name(data.type, "compiled")

        try:
            options = {
                "inputFile": input_file,
                "outputFile": output_file,
                "password": data.password,
                "version": data.protocol,
            }
            result = await plugin.compile(to_js(options, create_pyproxies=False))
            result_py = result.to_py() if hasattr(result, "to_py") else result
            size = result_py.get("size", 0)
            self._log.info(f"Compiled {input_file} -> {output_file}, size={size}")
            return BackupProcessResult(payload=b"", size=size)
        except Exception as e:
            error_msg = str(e)
            if "INVALID_CREDENTIALS" in error_msg:
                raise InvalidBackupCredentials() from e
            if "UNSUPPORTED_PROTOCOL" in error_msg:
                raise UnsupportedBackupProtocol(data.protocol) from e
            self._log.error(f"Compile failed: {e}")
            raise

    async def decompile(self, data: BackupProcessRequest) -> BackupProcessResult:
        plugin = _get_plugin()

        input_file = get_file_name(data.type, "imported")
        output_file = get_file_name(data.type, "decompiled")

        try:
            options = {
                "inputFile": input_file,
                "outputFile": output_file,
                "password": data.password,
                "version": data.protocol,
            }
            result = await plugin.decompile(to_js(options, create_pyproxies=False))
            result_py = result.to_py() if hasattr(result, "to_py") else result
            size = result_py.get("size", 0)
            self._log.info(f"Decompiled {input_file} -> {output_file}, size={size}")
            return BackupProcessResult(payload=b"", size=size)
        except Exception as e:
            error_msg = str(e)
            if "INVALID_CREDENTIALS" in error_msg:
                raise InvalidBackupCredentials() from e
            if "UNSUPPORTED_PROTOCOL" in error_msg:
                raise UnsupportedBackupProtocol(data.protocol) from e
            self._log.error(f"Decompile failed: {e}")
            raise


async def write_staging_file(file_name: str, data: bytes) -> int:
    plugin = _get_plugin()

    data_b64 = base64.b64encode(data).decode("ascii")
    options = {"fileName": file_name, "data": data_b64}
    result = await plugin.writeFile(to_js(options, create_pyproxies=False))
    result_py = result.to_py() if hasattr(result, "to_py") else result
    return result_py.get("size", 0)


async def read_staging_file(file_name: str) -> bytes:
    plugin = _get_plugin()

    options = {"fileName": file_name}
    result = await plugin.readFile(to_js(options, create_pyproxies=False))
    result_py = result.to_py() if hasattr(result, "to_py") else result
    data_b64 = result_py.get("data", "")
    return base64.b64decode(data_b64)


async def cleanup_staging() -> None:
    plugin = _get_plugin()
    if plugin is None:
        return
    await plugin.cleanup(to_js({}, create_pyproxies=False))


async def delete_staging_file(file_name: str) -> None:
    plugin = _get_plugin()
    if plugin is None:
        return
    options = {"fileName": file_name}
    await plugin.deleteFile(to_js(options, create_pyproxies=False))
