from uuid import UUID

from quart import jsonify, request

from domain.exception.exceptions import EntityNotFound
from domain.use_cases.get_crypto_wallet_addresses import GetCryptoWalletAddresses


async def get_crypto_wallet_addresses(
    get_crypto_wallet_addresses_uc: GetCryptoWalletAddresses,
):
    wallet_id = request.args.get("wallet_id")
    if not wallet_id:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "wallet_id parameter is required"}
        ), 400

    try:
        wallet_uuid = UUID(wallet_id)
    except ValueError:
        return jsonify(
            {"code": "INVALID_REQUEST", "message": "Invalid wallet_id format"}
        ), 400

    try:
        wallet = await get_crypto_wallet_addresses_uc.execute(wallet_uuid)
    except EntityNotFound:
        return jsonify({"code": "NOT_FOUND", "message": "Wallet not found"}), 404
    except ValueError as e:
        return jsonify({"code": "INVALID_REQUEST", "message": str(e)}), 400

    hd = wallet.hd_wallet
    receiving = []
    change = []
    if hd:
        for addr in hd.addresses:
            entry = {
                "index": addr.index,
                "path": addr.path,
                "address": addr.address,
                "pubkey": addr.pubkey,
                "change": addr.change,
                "balance": addr.balance,
            }
            if addr.change == 0:
                receiving.append(entry)
            else:
                change.append(entry)

    return jsonify(
        {
            "id": str(wallet.id),
            "name": wallet.name,
            "address_source": wallet.address_source.value,
            "hd_wallet": {
                "xpub": hd.xpub,
                "script_type": hd.script_type.value,
                "coin_type": hd.coin_type.value,
                "receiving": receiving,
                "change": change,
            }
            if hd
            else None,
        }
    ), 200
