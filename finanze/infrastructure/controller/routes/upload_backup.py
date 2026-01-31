from quart import jsonify, request

from domain.backup import UploadBackupRequest
from domain.use_cases.upload_backup import UploadBackup


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


async def upload_backup(upload_backup_uc: UploadBackup):
    body = await request.get_json()
    types = body.get("types")
    if not types:
        return {"message": "Field 'types' is required"}, 400

    force = body.get("force", False)

    upload_request = UploadBackupRequest(types=types, force=force)
    result = await upload_backup_uc.execute(upload_request)

    response = {
        "pieces": {
            backup_type.value: {
                "local": _serialize_backup_info(full_backup_info.local),
                "remote": _serialize_backup_info(full_backup_info.remote),
                "last_update": full_backup_info.last_update.isoformat(),
                "has_local_changes": full_backup_info.has_local_changes,
                "status": full_backup_info.status.value,
            }
            for backup_type, full_backup_info in result.pieces.items()
        }
    }

    return jsonify(response), 200
