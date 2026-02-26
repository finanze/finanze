from uuid import UUID

from domain import native_entities
from domain.entity import EntityType
from domain.public_key import ScriptType, AddressDerivationPreviewRequest
from domain.use_cases.derive_crypto_addresses import DeriveCryptoAddresses
from domain.exception.exceptions import EntityNotFound
from quart import jsonify, request


async def derive_crypto_addresses(derive_crypto_addresses_uc: DeriveCryptoAddresses):
    xpub = request.args.get("xpub")
    entity_id = request.args.get("network")
    script_type = request.args.get("script_type")
    account = request.args.get("account", "0")
    range_param = request.args.get("range", "5")

    if not xpub:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "xpub parameter is required"}
        ), 400

    if not entity_id:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "network parameter is required"}
        ), 400

    try:
        entity_uuid = UUID(entity_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid network (entity_id) format"}
        ), 400

    try:
        range_value = int(range_param)
        if range_value < 1:
            raise ValueError("Range must be at least 1")
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid range parameter"}
        ), 400

    try:
        account_value = int(account)
        if account_value < 0:
            raise ValueError("Account must be non-negative")
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid account parameter"}
        ), 400

    entity = native_entities.get_native_by_id(entity_uuid, EntityType.CRYPTO_WALLET)
    if not entity:
        return jsonify(
            {
                "code": "ENTITY_NOT_FOUND",
                "message": f"Entity with id {entity_id} not found",
            }
        ), 404

    script_type_enum = None
    if script_type:
        try:
            script_type_enum = ScriptType(script_type)
        except ValueError:
            return jsonify(
                {
                    "code": "INVALID_REQUEST",
                    "message": f"Invalid script_type. Valid values: {[st.value for st in ScriptType]}",
                }
            ), 400

    derivation_request = AddressDerivationPreviewRequest(
        xpub=xpub,
        entity=entity,
        range=range_value,
        script_type=script_type_enum,
        account=account_value,
    )

    try:
        result = await derive_crypto_addresses_uc.execute(derivation_request)
    except EntityNotFound:
        return jsonify(
            {
                "code": "ENTITY_NOT_FOUND",
                "message": f"Entity with id {entity_id} not found",
            }
        ), 404
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    return jsonify(
        {
            "key_type": result.key_type,
            "script_type": result.script_type.value,
            "coin": result.coin.value,
            "base_path": result.base_path,
            "receiving": [
                {
                    "index": addr.index,
                    "path": addr.path,
                    "address": addr.address,
                    "pubkey": addr.pubkey,
                    "change": addr.change,
                }
                for addr in result.receiving
            ],
            "change": [
                {
                    "index": addr.index,
                    "path": addr.path,
                    "address": addr.address,
                    "pubkey": addr.pubkey,
                    "change": addr.change,
                }
                for addr in result.change
            ],
        }
    ), 200
