from domain.backup import BackupFileType

FILE_NAMES = {
    BackupFileType.DATA: {
        "exported": "EXPORTED_DATA",
        "compiled": "COMPILED_DATA",
        "imported": "IMPORTED_DATA",
        "decompiled": "DECOMPILED_DATA",
    },
    BackupFileType.CONFIG: {
        "exported": "EXPORTED_CONFIG",
        "compiled": "COMPILED_CONFIG",
        "imported": "IMPORTED_CONFIG",
        "decompiled": "DECOMPILED_CONFIG",
    },
}


def get_file_name(backup_type: BackupFileType, stage: str) -> str:
    return FILE_NAMES[backup_type][stage]
