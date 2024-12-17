import datetime
from dataclasses import asdict
from typing import Union

from dateutil.tz import tzlocal

from infrastructure.sheets.exporter.sheets_summary_exporter import LAST_UPDATE_FIELD, set_field_value, \
    format_field_value

NO_HEADERS_FOUND = "NO_HEADERS_FOUND"
ENTITY_COLUMN = "entity"
TYPE_COLUMN = "investmentType"


def update_category(sheet, global_position: dict, sheet_id: str, sheet_name: str, subcategory: Union[str, list[str]]):
    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_name).execute()
    cells = result.get('values', None)
    if not cells:
        rows = [[NO_HEADERS_FOUND]]
    else:
        rows = map_rows(global_position, cells, subcategory)
        if not rows:
            return

    request = sheet.values().update(
        spreadsheetId=sheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        body={"values": rows},
    )

    request.execute()


def map_rows(global_positions, cells, subcategory) -> list[list[str]]:
    last_update_row_index, column_index = next(
        ((index, row.index(LAST_UPDATE_FIELD)) for index, row in enumerate(cells) if LAST_UPDATE_FIELD in row),
        (-1, None))

    if column_index is not None:
        set_field_value(cells[last_update_row_index], column_index + 1, datetime.datetime.now(tzlocal()).isoformat())
        for i, cell in enumerate(cells[last_update_row_index]):
            if i < column_index or i > column_index + 1:
                cells[last_update_row_index][i] = ""

    header_row_index, columns = next(
        ((index, row) for index, row in enumerate(cells[last_update_row_index + 1:], last_update_row_index + 1) if
         row), (None, None))
    if header_row_index is None or columns is None:
        if column_index is not None:
            set_field_value(cells[last_update_row_index], column_index + 2, NO_HEADERS_FOUND)
            return cells
        else:
            return [[NO_HEADERS_FOUND]]

    product_rows = map_products(global_positions, columns, subcategory)
    return [
        *cells[:header_row_index + 1],
        *product_rows,
        *[["" for _ in range(20)] for _ in range(20)],
    ]


def map_products(global_positions, columns: list[str], subcategory: Union[str, list]) -> list[list[str]]:
    subcategories = [subcategory] if isinstance(subcategory, str) else subcategory
    product_rows = []
    for entity, position in global_positions.items():
        try:
            if position.investments is None:
                continue
            investments_dict = asdict(position.investments)
            for subcategory in subcategories:
                subcategory_dict = investments_dict[subcategory]
                if subcategory_dict is None:
                    continue
                products = subcategory_dict["details"]
                for product in products:
                    product_rows.append(map_product_row(product, entity, subcategory, columns))
        except AttributeError:
            pass

    return product_rows


def map_product_row(details, entity, p_type, columns) -> list[str]:
    rows = []
    details[ENTITY_COLUMN] = entity
    details[TYPE_COLUMN] = format_type_name(p_type)
    for column in columns:
        if column in details:
            rows.append(format_field_value(details[column]))
        else:
            rows.append("")

    return rows


def format_type_name(value):
    return value.upper()
