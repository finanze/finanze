import json
import logging
from dataclasses import asdict
from datetime import date, datetime
from uuid import UUID

from dateutil.tz import tzlocal
from pytz import utc

from application.use_cases.update_sheets import DETAILS_FIELD
from domain.dezimal import Dezimal
from domain.financial_entity import FinancialEntity
from domain.global_position import GlobalPosition
from domain.settings import SummarySheetConfig, BaseSheetConfig

LAST_UPDATE_FIELD = "last_update"
COUNT_FIELD = "count"

ERROR_VALUE = "ERR"

_log = logging.getLogger(__name__)


def update_summary(
        sheet,
        global_positions: dict[FinancialEntity, GlobalPosition],
        config: SummarySheetConfig):
    sheet_id, sheet_range = config.spreadsheetId, config.range

    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    values = result.get('values')
    if not values:
        _log.warning(f"Got empty sheet for {sheet_range}, aborting summary export...")
        return

    cells = values + [[""]]

    global_position_by_entity_name = {
        entity.name.lower(): global_position for entity, global_position in global_positions.items()
    }

    entity = None
    last_end = 0
    for row_i in range(len(cells)):
        if not cells[row_i]:
            continue
        title = cells[row_i][0]
        last_row = row_i == len(cells) - 1
        if title.lower() in global_position_by_entity_name or last_row:
            if not entity:
                entity = title.lower()
                continue
            update_entity_summary(global_position_by_entity_name.get(entity, {}),
                                  cells[last_end:row_i + 1 if last_row else row_i],
                                  config)
            entity = title.lower()
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
        config: SummarySheetConfig):
    if not global_position:
        return

    header = current_cells[0]
    if LAST_UPDATE_FIELD in header:
        last_update_index = header.index(LAST_UPDATE_FIELD)
        last_update_date = global_position.date.astimezone(tz=tzlocal())
        config_datetime_format = config.datetimeFormat
        if config_datetime_format:
            formated_last_update_date = last_update_date.strftime(config_datetime_format)
        else:
            formated_last_update_date = last_update_date.isoformat()

        set_field_value(header, last_update_index + 1, formated_last_update_date, config)

    pos_dict = asdict(global_position)
    parent = None
    field_columns = []
    prev_row = None
    last_row_grid_category = False
    parent_list_index = 0
    for row in current_cells:
        if not row and (last_row_grid_category or not prev_row):
            prev_row = row.copy()
            last_row_grid_category = False
            field_columns = []
            parent = None
            continue
        prev_row = row.copy()
        last_row_grid_category = False

        title = row[0] if row else None
        if title in pos_dict:
            parent = pos_dict[title]
            field_columns = row[1:]
            parent_list_index = -1
            continue

        parent_list = isinstance(parent, list)
        if parent_list:
            parent_list_index += 1
        else:
            parent_list_index = -1

        last_row_grid_category = True
        for column_i in range(len(field_columns)):
            column = field_columns[column_i]
            if not column:
                set_field_value(row, column_i + 1, "", config)
                continue

            if parent is None:
                continue

            if not parent_list and (title not in parent or not parent[title]):
                value = ""
            else:
                if column == COUNT_FIELD:
                    if not parent_list and DETAILS_FIELD in parent[title]:
                        value = len(parent[title].get(DETAILS_FIELD))
                    else:
                        value = ""
                else:
                    complex_column = '.' in column
                    fields = column.split(".")
                    obj = parent[title] if not parent_list else parent[parent_list_index - 1]
                    value = obj.get(fields[0], ERROR_VALUE)
                    if complex_column:
                        for field in fields[1:]:
                            if isinstance(value, dict):
                                value = value.get(field, ERROR_VALUE)
                                if value == ERROR_VALUE:
                                    break
                            else:
                                value = ERROR_VALUE
                                break

            set_column_i = column_i + 1
            if len(row) == 0:
                row.append("")
            set_field_value(row, set_column_i, value, config)


def set_field_value(row: list[str], index: int, value, config: BaseSheetConfig):
    value = format_field_value(value, config)
    if len(row) > index:
        row[index] = value
    else:
        row.append(value)


def format_field_value(value, config: BaseSheetConfig):
    if value is None:
        return ""

    if isinstance(value, date) and not isinstance(value, datetime):
        config_date_format = config.dateFormat
        if config_date_format:
            return value.strftime(config_date_format)

        return value.isoformat()[:10]

    elif isinstance(value, datetime):
        value = value.replace(tzinfo=utc).astimezone(tzlocal())
        config_date_format = config.datetimeFormat
        if config_date_format:
            return value.strftime(config_date_format)

        return value.isoformat()

    elif isinstance(value, dict) or isinstance(value, list):
        return json.dumps(value, default=str)

    elif isinstance(value, Dezimal):
        return float(value)

    elif isinstance(value, UUID):
        return str(value)

    return value
