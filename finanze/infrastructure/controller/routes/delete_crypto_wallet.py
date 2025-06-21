from uuid import UUID

from domain.use_cases.delete_crypto_wallet import DeleteCryptoWalletConnection


def delete_crypto_wallet(
    delete_crypto_wallet_uc: DeleteCryptoWalletConnection, wallet_connection_id: str
):
    try:
        wallet_uuid = UUID(wallet_connection_id)
    except ValueError:
        return {"message": "Invalid wallet ID format"}, 400

    delete_crypto_wallet_uc.execute(wallet_uuid)
    return "", 204
