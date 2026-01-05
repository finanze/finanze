from quart import jsonify, request

from domain.backup import BackupsInfoRequest
from domain.use_cases.get_backups import GetBackups


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


async def get_backups(get_backups_uc: GetBackups):
    params = request.args or {}
    only_local = params.get("only_local")
    if only_local is not None:
        only_local = str(only_local).lower() == "true"
    else:
        only_local = False
    result = await get_backups_uc.execute(BackupsInfoRequest(only_local=only_local))

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
