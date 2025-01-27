import json
from dataclasses import asdict
from datetime import date, datetime

from dateutil.tz import tzlocal
from pytz import utc

from application.use_cases.update_sheets import DETAILS_FIELD, ADDITIONAL_DATA_FIELD
from domain.global_position import GlobalPosition

LAST_UPDATE_FIELD = "lastUpdate"
COUNT_FIELD = "count"

ERROR_VALUE = "ERR"


def update_summary(
        sheet,
        global_positions: dict[str, GlobalPosition],
        config: dict):
    sheet_id, sheet_range = config["spreadsheetId"], config["range"]

    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    cells = result.get('values', [[]]) + [[""]]

    bank = None
    last_end = 0
    for row_i in range(len(cells)):
        if not cells[row_i]:
            continue
        title = cells[row_i][0]
        last_row = row_i == len(cells) - 1
        if title in global_positions or last_row:
            if not bank:
                bank = title
                continue
            update_entity_summary(global_positions.get(bank, {}), cells[last_end:row_i + 1 if last_row else row_i],
                                  config)
            bank = title
            last_end = row_i

    batch_update = {
        "value_input_option": "USER_ENTERED",
        "data": [
            {"range": sheet_range, "values": cells},
        ],
    }

    request = sheet.values().batchUpdate(spreadsheetId=sheet_id, body=batch_update)

    request.execute()


def update_entity_summary(
        global_position: GlobalPosition,
        current_cells: list[list[str]],
        config):
    if not global_position:
        return

    header = current_cells[0]
    if LAST_UPDATE_FIELD in header:
        last_update_index = header.index(LAST_UPDATE_FIELD)
        last_update_date = global_position.date.astimezone(tz=tzlocal())
        config_datetime_format = config.get("datetimeFormat")
        if config_datetime_format:
            formated_last_update_date = last_update_date.strftime(config_datetime_format)
        else:
            formated_last_update_date = last_update_date.isoformat()

        set_field_value(header, last_update_index + 1, formated_last_update_date, config)

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
                    set_field_value(row, column_i + 1, "", config)
                    continue

                if parent is None:
                    continue

                if column == COUNT_FIELD:
                    if DETAILS_FIELD in parent:
                        value = len(parent.get(DETAILS_FIELD))
                    else:
                        value = ""
                else:
                    value = parent.get(column, None)
                    if value is None:
                        additional_data = parent.get(ADDITIONAL_DATA_FIELD, None)
                        if additional_data:
                            value = additional_data.get(column, ERROR_VALUE)

                set_field_value(row, column_i + 1, value, config)

        else:
            last_row_grid_category = True
            for column_i in range(len(field_columns)):
                column = field_columns[column_i]
                if not column:
                    set_field_value(row, column_i + 1, "", config)
                    continue

                if parent is None:
                    continue

                if title not in parent or not parent[title]:
                    value = ""
                else:
                    if column == COUNT_FIELD:
                        if DETAILS_FIELD in parent[title]:
                            value = len(parent[title].get(DETAILS_FIELD))
                        else:
                            value = ""
                    else:
                        complex_column = '.' in column
                        fields = column.split(".")
                        value = parent[title].get(fields[0], ERROR_VALUE)
                        if complex_column:
                            for field in fields[1:]:
                                if isinstance(value, dict):
                                    value = value.get(field, ERROR_VALUE)
                                    if value == ERROR_VALUE:
                                        break
                                else:
                                    value = ERROR_VALUE
                                    break

                set_field_value(row, column_i + 1, value, config)


def set_field_value(row: list[str], index: int, value, config):
    value = format_field_value(value, config)
    if len(row) > index:
        row[index] = value
    else:
        row.append(value)


def format_field_value(value, config):
    if value is None:
        return ""

    if isinstance(value, date) and not isinstance(value, datetime):
        config_date_format = config.get("dateFormat")
        if config_date_format:
            return value.strftime(config_date_format)

        return value.isoformat()[:10]

    elif isinstance(value, datetime):
        value = value.replace(tzinfo=utc).astimezone(tzlocal())
        config_date_format = config.get("datetimeFormat")
        if config_date_format:
            return value.strftime(config_date_format)

        return value.isoformat()

    elif isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, default=str)

    return value
