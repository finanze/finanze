def migrate(data: dict) -> dict:
    if "fetch" in data:
        data["importing"] = data.pop("fetch")

    import_config = data.get("importing")
    if isinstance(import_config, dict) and "virtual" in import_config:
        import_config["sheets"] = import_config.pop("virtual")

    data["version"] = 4
    return data
