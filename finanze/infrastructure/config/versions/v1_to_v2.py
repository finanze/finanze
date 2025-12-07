def migrate(data: dict) -> dict:
    if "scrape" in data:
        data["fetch"] = data.pop("scrape")

    export = data.get("export")
    if isinstance(export, dict):
        sheets = export.get("sheets")
        if isinstance(sheets, dict):
            sheets.pop("summary", None)
            if "investments" in sheets:
                sheets["position"] = sheets.pop("investments")

    data["version"] = 2
    return data
