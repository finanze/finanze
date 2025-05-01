from domain.use_cases.update_sheets import UpdateSheets


def update_sheets(update_sheets: UpdateSheets):
    update_sheets.execute()
    return "", 204
