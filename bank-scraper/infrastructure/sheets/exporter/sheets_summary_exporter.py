from dataclasses import asdict
from datetime import date

from dateutil.tz import tzlocal

from domain.global_position import GlobalPosition

SUMMARY_SHEET = "Summary"
SHEET_RANGE = f"{SUMMARY_SHEET}!A:Z"

LAST_UPDATE_FIELD = "lastUpdate"
ADDITIONAL_DATA_FIELD = "additionalData"
COUNT_FIELD = "count"
DETAILS_FIELD = "details"

ERROR_VALUE = "ERR"


def update_summary(sheet, global_position: dict[str, GlobalPosition], sheet_id: str):
    result = sheet.values().get(spreadsheetId=sheet_id, range=SHEET_RANGE).execute()
    cells = result.get('values', [[]]) + [[""]]

    bank = None
    last_end = 0
    for row_i in range(len(cells)):
        if not cells[row_i]:
            continue
        title = cells[row_i][0]
        last_row = row_i == len(cells) - 1
        if title in global_position or last_row:
            if not bank:
                bank = title
                continue
            update_entity_summary(global_position.get(bank, {}), cells[last_end:row_i + 1 if last_row else row_i])
            bank = title
            last_end = row_i

    batch_update = {
        "value_input_option": "RAW",
        "data": [
            {"range": SHEET_RANGE, "values": cells},
        ],
    }

    request = sheet.values().batchUpdate(spreadsheetId=sheet_id, body=batch_update)

    request.execute()


def update_entity_summary(global_position: GlobalPosition, current_cells: list[list[str]]):
    if not global_position:
        return

    header = current_cells[0]
    last_update_index = header.index(LAST_UPDATE_FIELD)
    set_field_value(header, last_update_index + 1, global_position.date.astimezone(tz=tzlocal()).isoformat())

    pos_dict = asdict(global_position)
    parent = None
    field_columns = []
    prev_row = None
    last_row_final_simple_category = False
    last_row_grid_category = False
    for row in current_cells:
        if (not row and (last_row_grid_category or not prev_row)) or last_row_final_simple_category:
            prev_row = row.copy()
            last_row_final_simple_category, last_row_grid_category = False, False
            field_columns = []
            parent = None
            continue
        prev_row = row.copy()
        last_row_final_simple_category, last_row_grid_category = False, False

        title = row[0] if row else None
        if title in pos_dict:
            parent = pos_dict[title]
            field_columns = row[1:]
            continue

        if not title:
            last_row_final_simple_category = True
            if not row:
                row.append("")

            for column_i in range(len(field_columns)):
                column = field_columns[column_i]
                if not column:
                    set_field_value(row, column_i + 1, "")
                    continue

                if column == COUNT_FIELD:
                    value = len(parent.get(DETAILS_FIELD))
                else:
                    value = parent.get(column, None)
                    if value is None:
                        additional_data = parent.get(ADDITIONAL_DATA_FIELD, None)
                        if additional_data:
                            value = additional_data.get(column, ERROR_VALUE)

                set_field_value(row, column_i + 1, value)

        else:
            last_row_grid_category = True
            for column_i in range(len(field_columns)):
                column = field_columns[column_i]
                if not column:
                    set_field_value(row, column_i + 1, "")
                    continue

                if title not in parent:
                    value = ERROR_VALUE
                else:
                    if column == COUNT_FIELD:
                        value = len(parent[title].get(DETAILS_FIELD))
                    else:
                        value = parent[title].get(column, ERROR_VALUE)

                set_field_value(row, column_i + 1, value)


def set_field_value(row: list[str], index: int, value):
    value = format_field_value(value)
    if len(row) > index:
        row[index] = value
    else:
        row.append(value)


def format_field_value(value):
    if value is None:
        return ""

    if isinstance(value, date):
        return value.isoformat()[:10]
    return value
