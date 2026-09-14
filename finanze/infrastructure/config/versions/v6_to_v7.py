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
    if not isinstance(stablecoins, list):
        stablecoins = []
        crypto["stablecoins"] = stablecoins

    if "PUSD" not in stablecoins:
        stablecoins.append("PUSD")

    data["version"] = 7
    return data
