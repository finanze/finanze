import datetime
from dataclasses import asdict
from typing import Union

from dateutil.tz import tzlocal

from infrastructure.sheets.exporter.sheets_summary_exporter import LAST_UPDATE_FIELD, set_field_value, \
    format_field_value

NO_HEADERS_FOUND = "NO_HEADERS_FOUND"
ENTITY_COLUMN = "entity"
TYPE_COLUMN = "investmentType"
ENTITY_UPDATED_AT = "entityUpdatedAt"


def update_sheet(
        sheet,
        data: Union[dict, object],
        config: dict,
        last_update: dict[str, datetime] = None):
    sheet_id, sheet_range, field_paths = config["spreadsheetId"], config["range"], config["data"]
    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    cells = result.get('values', None)
    if not cells:
        rows = [[NO_HEADERS_FOUND]]
    else:
        rows = map_rows(data, cells, field_paths, last_update, config)
        if not rows:
            return

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{sheet_range}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    )

    request.execute()


def map_rows(
        data: Union[dict, object],
        cells: list[list[str]],
        field_paths: list[str],
        last_update: dict[str, datetime],
        config) -> list[list[str]]:
    per_entity_date = False
    last_update_row_index, column_index = next(
        ((index, row.index(LAST_UPDATE_FIELD)) for index, row in enumerate(cells) if LAST_UPDATE_FIELD in row),
        (-1, None))

    if last_update and column_index is None:
        per_entity_date = True
        last_update_row_index, column_index = next(
            ((index, row.index(ENTITY_UPDATED_AT)) for index, row in enumerate(cells) if ENTITY_UPDATED_AT in row),
            (-1, None))

    if column_index is not None:
        if per_entity_date:
            entity_last_update_row = map_last_update_row(last_update, config)
            cells[last_update_row_index] = [*["" for _ in range(column_index)], *entity_last_update_row]
        else:
            last_update_date = datetime.datetime.now(tzlocal())
            config_datetime_format = config.get("datetimeFormat")
            if config_datetime_format:
                formated_last_update_date = last_update_date.strftime(config_datetime_format)
            else:
                formated_last_update_date = last_update_date.isoformat()

            set_field_value(cells[last_update_row_index], column_index + 1, formated_last_update_date, config)

            for i, cell in enumerate(cells[last_update_row_index]):
                if i < column_index or i > column_index + 1:
                    cells[last_update_row_index][i] = ""

    header_row_index, columns = next(
        ((index, row) for index, row in enumerate(cells[last_update_row_index + 1:], last_update_row_index + 1) if
         row), (None, None))
    if header_row_index is None or columns is None:
        if column_index is not None:
            set_field_value(cells[last_update_row_index], column_index + 2, NO_HEADERS_FOUND, config)
            return cells
        else:
            return [[NO_HEADERS_FOUND]]

    product_rows = map_products(data, columns, field_paths, config)
    return [
        *cells[:header_row_index + 1],
        *product_rows,
        *[["" for _ in range(100)] for _ in range(500)],
    ]


def map_products(
        data: Union[dict, object],
        columns: list[str],
        field_paths: list[str],
        config) -> list[list[str]]:
    product_rows = []
    if isinstance(data, dict):
        for entity, entity_data in data.items():
            for field_path in field_paths:
                try:
                    path_tokens = field_path.split(".")
                    target_data = entity_data
                    for field in path_tokens:
                        target_data = getattr(target_data, field)

                    for product in target_data:
                        product_rows.append(map_product_row(product, entity, field_path, columns, config))
                except AttributeError:
                    pass
    else:
        for field_path in field_paths:
            target_data = data
            path_tokens = field_path.split(".")
            for field in path_tokens:
                if not hasattr(target_data, field):
                    continue
                target_data = getattr(target_data, field)

            for product in target_data:
                product_rows.append(map_product_row(product, None, None, columns, config))

    return product_rows


def map_product_row(details, entity, p_type, columns, config) -> list[str]:
    rows = []
    details = asdict(details)
    if ENTITY_COLUMN not in details:
        details[ENTITY_COLUMN] = entity
    if p_type:
        details[TYPE_COLUMN] = format_type_name(p_type)
    for column in columns:
        if column in details:
            rows.append(format_field_value(details[column], config))
        else:
            rows.append("")

    return rows


def format_type_name(value):
    tokens = value.split(".")
    if len(tokens) >= 2:
        return tokens[-2].upper()
    else:
        return value.upper()


def map_last_update_row(last_update: dict[str, datetime], config):
    last_update = sorted(last_update.items(), key=lambda item: item[1], reverse=True)
    last_update_row = [None]
    for k, v in last_update:
        last_update_row.append(k)
        last_update_date = v.astimezone(tz=tzlocal())
        config_datetime_format = config.get("datetimeFormat")
        if config_datetime_format:
            formated_last_update_date = last_update_date.strftime(config_datetime_format)
        else:
            formated_last_update_date = last_update_date.isoformat()
        last_update_row.append(formated_last_update_date)
    last_update_row.extend(["" for _ in range(10)])
    return last_update_row
