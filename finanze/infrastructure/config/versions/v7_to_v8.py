def migrate(data: dict) -> dict:
    general = data.get("general")
    if not isinstance(general, dict):
        general = {}
        data["general"] = general

    if "editMode" not in general:
        general["editMode"] = "QUICK"

    data["version"] = 8
    return data
