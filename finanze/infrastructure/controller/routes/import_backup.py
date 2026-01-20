from quart import request, jsonify

from domain.backup import ImportBackupRequest
from domain.exception.exceptions import InvalidBackupCredentials
from domain.use_cases.import_backup import ImportBackup


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


async def import_backup(import_backup_uc: ImportBackup):
    body = await request.get_json() or {}
    password = body.get("password")
    types = body.get("types")
    force = body.get("force", False)
    if not types:
        return {"message": "Field 'types' is required"}, 400

    import_req = ImportBackupRequest(password=password, types=types, force=force)

    try:
        result = await import_backup_uc.execute(import_req)
    except InvalidBackupCredentials as e:
        return {"message": str(e) or "INVALID_CREDENTIALS"}, 401

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
