from domain.crypto import ConnectCryptoWallet as ConnectCryptoWalletRequest
from domain.use_cases.connect_crypto_wallet import ConnectCryptoWallet
from flask import request


def connect_crypto_wallet(connect_crypto_wallet_uc: ConnectCryptoWallet):
    body = request.json

    if (
        not body
        or not body.get("entityId")
        or not body.get("address")
        or not body.get("name")
    ):
        return {"message": "entityId, address and name are required"}, 400

    connect_crypto_wallet_uc.execute(
        ConnectCryptoWalletRequest(
            entity_id=body.get("entityId"),
            address=body.get("address"),
            name=body.get("name"),
        )
    )
    return "", 204
