from uuid import UUID

from domain.crypto import (
    UpdateCryptoWalletConnection as UpdateCryptoWalletConnectionRequest,
)
from domain.use_cases.update_crypto_wallet import UpdateCryptoWalletConnection
from flask import request


def update_crypto_wallet(update_crypto_wallet_uc: UpdateCryptoWalletConnection):
    body = request.json

    wallet_connection_id = body.get("id")

    if not body or not wallet_connection_id or not body.get("name"):
        return {"message": "id and name are required"}, 400

    try:
        wallet_connection_id = UUID(wallet_connection_id)
    except ValueError:
        return {"message": "Invalid wallet/entity ids format"}, 400

    update_crypto_wallet_uc.execute(
        UpdateCryptoWalletConnectionRequest(
            id=wallet_connection_id,
            name=body.get("name"),
        )
    )
    return "", 204
