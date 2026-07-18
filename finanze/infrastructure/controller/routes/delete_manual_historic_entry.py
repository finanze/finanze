from uuid import UUID

from domain.exception.exceptions import ManualHistoricEntryNotFound
from domain.historic import (
    DeleteManualHistoricEntryRequest,
    HistoricTxDeletion,
)
from domain.use_cases.delete_manual_historic_entry import DeleteManualHistoricEntry
from quart import jsonify, request


async def delete_manual_historic_entry(
    delete_uc: DeleteManualHistoricEntry, entry_id: str
):
    raw_mode = request.args.get("tx_deletion", HistoricTxDeletion.NONE.value)

    try:
        req = DeleteManualHistoricEntryRequest(
            entry_id=UUID(entry_id),
            tx_deletion=HistoricTxDeletion(raw_mode),
        )
    except (ValueError, TypeError) as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    try:
        await delete_uc.execute(req)
    except ManualHistoricEntryNotFound as e:
        return jsonify({"code": "NOT_FOUND", "message": str(e)}), 404

    return "", 204
