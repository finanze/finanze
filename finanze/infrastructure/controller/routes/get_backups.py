from typing import Optional

from quart import jsonify, request

from domain.backup import BackupsInfoRequest
from domain.use_cases.get_backups import GetBackups
from domain.cloud_auth import CloudAuthToken


def _serialize_backup_info(backup_info):
    if backup_info is None:
        return None
    return {
        "id": str(backup_info.id),
        "protocol": backup_info.protocol,
        "date": backup_info.date.isoformat(),
        "type": backup_info.type.value,
        "size": backup_info.size,
    }


def _extract_cloud_token_from_header(headers) -> Optional[CloudAuthToken]:
    auth_header = headers.get("Cloud-Authorization")
    if not auth_header:
        return None

    parts = auth_header.split(" ", 1)
    if len(parts) != 2:
        return None

    token_type, access_token = parts

    return CloudAuthToken(
        access_token=access_token,
        refresh_token="",
        token_type=token_type,
        expires_at=0,
    )


async def get_backups(get_backups_uc: GetBackups):
    params = request.args or {}
    only_local = params.get("only_local")
    if only_local is not None:
        only_local = str(only_local).lower() == "true"
    else:
        only_local = False

    cloud_token = _extract_cloud_token_from_header(request.headers)
    result = await get_backups_uc.execute(
        BackupsInfoRequest(only_local=only_local),
        cloud_token=cloud_token,
    )

    response = {
        "pieces": {
            backup_type.value: {
                "local": _serialize_backup_info(full_backup_info.local),
                "remote": _serialize_backup_info(full_backup_info.remote),
                "last_update": full_backup_info.last_update.isoformat(),
                "has_local_changes": full_backup_info.has_local_changes,
                "status": full_backup_info.status.value
                if full_backup_info.status
                else None,
            }
            for backup_type, full_backup_info in result.pieces.items()
        }
    }

    return jsonify(response), 200
