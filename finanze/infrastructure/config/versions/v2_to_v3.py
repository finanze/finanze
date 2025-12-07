from infrastructure.config.base_config import DEFAULT_STABLECOINS


def migrate(data: dict) -> dict:
    assets = data.get("assets")
    if not isinstance(assets, dict):
        assets = {}
        data["assets"] = assets

    crypto = assets.get("crypto")
    if not isinstance(crypto, dict):
        crypto = {}
        assets["crypto"] = crypto

    stablecoins = crypto.get("stablecoins")
    if not isinstance(stablecoins, list) or len(stablecoins) == 0:
        crypto["stablecoins"] = list(DEFAULT_STABLECOINS)

    data["version"] = 3
    return data
