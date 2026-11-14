from html.parser import HTMLParser
from typing import Optional

from domain.template_header_aliases import (
    HEADER_ALIASES,
    header_alias_score,
    normalize_header,
)

_MAX_SPAN = 100
_MAX_PREAMBLE_ROWS = 15
_SKIPPED_TAGS = ("script", "style")
_KNOWN_FIELDS = tuple(HEADER_ALIASES.keys())


class _TableContext:
    def __init__(self):
        self.rows: list[list[str]] = []
        self.row: Optional[list[str]] = None
        self.cell: Optional[list[str]] = None
        self.colspan = 1
        self.rowspan = 1
        self.is_header = False
        self.col_index = 0
        self.pending_rowspans: dict[int, tuple[int, str]] = {}
        self.has_child_tables = False


class _TableCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._stack: list[_TableContext] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIPPED_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "table":
            if self._stack and self._stack[-1].cell is not None:
                self._stack[-1].has_child_tables = True
            self._stack.append(_TableContext())
            return
        if not self._stack:
            return
        table = self._stack[-1]
        if tag == "tr":
            self._close_row(table)
            table.row = []
            table.col_index = 0
            self._consume_spanned(table)
        elif tag in ("td", "th"):
            self._close_cell(table)
            if table.row is None:
                table.row = []
                table.col_index = 0
                self._consume_spanned(table)
            attr_map = dict(attrs)
            table.cell = []
            table.colspan = _parse_span(attr_map.get("colspan"))
            table.rowspan = _parse_span(attr_map.get("rowspan"))
            table.is_header = tag == "th"
        elif tag == "br" and table.cell is not None:
            table.cell.append(" ")

    def handle_startendtag(self, tag, attrs):
        if (
            not self._skip_depth
            and tag == "br"
            and self._stack
            and self._stack[-1].cell is not None
        ):
            self._stack[-1].cell.append(" ")

    def handle_endtag(self, tag):
        if tag in _SKIPPED_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth or not self._stack:
            return
        table = self._stack[-1]
        if tag == "table":
            self._finish_table(self._stack.pop())
        elif tag == "tr":
            self._close_row(table)
        elif tag in ("td", "th"):
            self._close_cell(table)

    def handle_data(self, data):
        if self._skip_depth or not self._stack:
            return
        table = self._stack[-1]
        if table.cell is not None:
            table.cell.append(data)

    def close(self):
        super().close()
        while self._stack:
            self._finish_table(self._stack.pop())

    def _consume_spanned(self, table: _TableContext):
        if table.row is None:
            return
        while table.col_index in table.pending_rowspans:
            remaining, text = table.pending_rowspans.pop(table.col_index)
            table.row.append(text)
            if remaining > 1:
                table.pending_rowspans[table.col_index] = (remaining - 1, text)
            table.col_index += 1

    def _consume_trailing_spanned(self, table: _TableContext):
        if table.row is None or not table.pending_rowspans:
            return
        trailing = [
            col for col in sorted(table.pending_rowspans) if col >= table.col_index
        ]
        for col in trailing:
            while table.col_index < col:
                table.row.append("")
                table.col_index += 1
            self._consume_spanned(table)

    def _close_cell(self, table: _TableContext):
        if table.cell is None or table.row is None:
            table.cell = None
            return
        self._consume_spanned(table)
        text = " ".join("".join(table.cell).split())
        table.row.append(text)
        if table.colspan > 1:
            table.row.extend([""] * (table.colspan - 1))
        if table.rowspan > 1:
            for offset in range(table.colspan):
                carry = text if (table.is_header and offset == 0) else ""
                table.pending_rowspans[table.col_index + offset] = (
                    table.rowspan - 1,
                    carry,
                )
        table.col_index += table.colspan
        table.cell = None
        table.colspan = 1
        table.rowspan = 1
        table.is_header = False

    def _close_row(self, table: _TableContext):
        self._close_cell(table)
        self._consume_trailing_spanned(table)
        if table.row:
            table.rows.append(table.row)
        table.row = None
        table.col_index = 0

    def _finish_table(self, table: _TableContext):
        self._close_row(table)
        if not table.rows:
            return
        if table.has_child_tables and not any(
            cell for row in table.rows for cell in row
        ):
            return
        if table.has_child_tables and max(len(row) for row in table.rows) <= 1:
            return
        self.tables.append(table.rows)


def _parse_span(value: Optional[str]) -> int:
    try:
        return min(max(int(value), 1), _MAX_SPAN)
    except (TypeError, ValueError):
        return 1


def _header_matches(row: list[str]) -> int:
    matched = set()
    for cell in row:
        if not cell:
            continue
        for field in _KNOWN_FIELDS:
            if header_alias_score(field, cell) is not None:
                matched.add(field)
    return len(matched)


def _score_table(
    rows: list[list[str]],
) -> tuple[tuple[int, int, int, int], int, Optional[tuple[str, ...]]]:
    best_h_idx = 0
    best_matches = 0
    for idx, row in enumerate(rows[:30]):
        matches = _header_matches(row)
        if matches > best_matches:
            best_matches = matches
            best_h_idx = idx
    data_rows = sum(
        1 for row in rows[best_h_idx + 1 :] if any(cell.strip() for cell in row)
    )
    max_cols = max((len(row) for row in rows), default=0)
    sig = (
        tuple(normalize_header(c) for c in rows[best_h_idx] if c.strip())
        if best_matches >= 2
        else None
    )
    score = (1 if best_matches >= 2 else 0, best_matches, data_rows, max_cols)
    return score, best_h_idx, sig


def extract_html_tables(text: str) -> list[list[list[str]]]:
    collector = _TableCollector()
    collector.feed(text)
    collector.close()
    return collector.tables


def read_html_tables(text: str) -> list[list[str]]:
    tables = extract_html_tables(text)
    if not tables:
        return []
    if len(tables) == 1:
        return tables[0]

    scored = [_score_table(tbl) for tbl in tables]
    best_idx = max(range(len(tables)), key=lambda idx: scored[idx][0])
    _, best_h_idx, best_sig = scored[best_idx]
    if best_sig is None:
        return [row for tbl in tables for row in tbl]

    preamble: list[list[str]] = []
    for idx in range(best_idx):
        _, _, sig = scored[idx]
        if sig is not None:
            continue
        candidate = tables[idx]
        if max((len(r) for r in candidate), default=0) <= 3:
            for row in candidate:
                if any(c.strip() for c in row):
                    preamble.append(row)
                    if len(preamble) >= _MAX_PREAMBLE_ROWS:
                        break
        if len(preamble) >= _MAX_PREAMBLE_ROWS:
            break

    combined = list(preamble) + list(tables[best_idx])
    for idx in range(best_idx + 1, len(tables)):
        _, h_idx, sig = scored[idx]
        if sig == best_sig:
            combined.extend(tables[idx][h_idx + 1 :])
    return combined
