from quart import jsonify, request

from domain.crypto import (
    ConnectCryptoWallet as ConnectCryptoWalletRequest,
    AddressSource,
)
from domain.public_key import ScriptType
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet


async def connect_crypto_wallet(connect_crypto_wallet_uc: ConnectCryptoWallet):
    body = await request.get_json()

    if (
        not body
        or not body.get("entityId")
        or body.get("addresses") is None
        or not body.get("name")
        or not body.get("source")
    ):
        return {"message": "source, entityId, address and name are required"}, 400

    addresses = body.get("addresses")
    source = body.get("source")
    try:
        source = AddressSource(source)
    except ValueError:
        return {"message": f"Invalid source value: {source}"}, 400

    xpub = body.get("xpub")
    raw_script_type = body.get("script_type")
    raw_account = body.get("account")

    script_type = None
    account = 0

    if xpub or raw_script_type or raw_account is not None:
        if not xpub or not raw_script_type:
            return {
                "message": "xpub and script_type are required when providing HD wallet params"
            }, 400

        try:
            script_type = ScriptType(raw_script_type)
        except ValueError:
            return {
                "message": f"Invalid script_type. Valid values: {[st.value for st in ScriptType]}"
            }, 400

        if raw_account is not None:
            try:
                account = int(raw_account)
                if account < 0:
                    raise ValueError
            except (ValueError, TypeError):
                return {"message": "Invalid account parameter"}, 400
    elif not addresses:
        return {
            "message": "Either addresses or HD wallet parameters (xpub and script_type) must be provided"
        }, 400

    response = await connect_crypto_wallet_uc.execute(
        ConnectCryptoWalletRequest(
            entity_id=body.get("entityId"),
            addresses=addresses,
            name=body.get("name"),
            address_source=source,
            xpub=xpub,
            script_type=script_type,
            account=account,
        )
    )
    return jsonify(response), 200
