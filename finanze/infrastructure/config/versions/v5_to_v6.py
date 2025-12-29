from datetime import datetime


def migrate(data: dict) -> dict:
    data["lastUpdate"] = datetime.now().astimezone().isoformat()
    data["version"] = 6
    return data
