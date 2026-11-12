import re
from dataclasses import field
from io import BytesIO
from typing import Any

import pypdf._text_extraction._layout_mode._fixed_width_page as _pdf_fwp
from application.ports.file_rw_port import TableRWPort
from domain.dezimal import Dezimal
from domain.exception.exceptions import (
    NoTableFound,
    PdfNoTextLayer,
    UnsupportedFileFormat,
)
from domain.export import FileFormat, NumberFormat
from domain.file_upload import FileUpload
from domain.template_header_aliases import (
    HEADER_ALIASES,
    header_alias_score,
    normalize_header,
)
from infrastructure.templating.cell_values import detect_date_pattern, parse_number
from pydantic.dataclasses import dataclass
from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError
from pypdf.generic import ArrayObject, ContentStream, StreamObject

_SCALE = 10
_MAX_PREAMBLE_ROWS = 15
_CTRL_SPACE_TABLE = str.maketrans(
    {**dict.fromkeys(range(0, 32), " "), 0xA0: " ", 0x202F: " ", 0x2007: " "}
)
_SINGLE_SPACE_TOKENS = re.compile(r"\S(?: ?\S)*")
_GRAPHICS_OP_RE = re.compile(rb"\b(?:re|m|l|c|Do)\b")
_PAGE_FOOTER_RE = re.compile(
    r"^(?:-\s*\d+\s*-|(?:p[aá]gina|page|pag\.?)\s+\d+(?:\s+(?:de|of|/)\s+\d+)?|\d+\s*/\s*\d+)$",
    re.IGNORECASE,
)
_SHORT_DAY_MONTH_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}$")
_KNOWN_FIELDS = tuple(HEADER_ALIASES.keys())
_EXTRA_TABLE_HEADERS = frozenset(
    {
        "saldo",
        "balance",
        "saldo disponible",
        "saldo contable",
        "saldo tras operacion",
        "balance inicial",
        "balance final",
        "oficina",
        "sucursal",
        "categoria",
        "subcategoria",
        "comentario",
        "estado",
        "status",
    }
)


@dataclass
class PdfSpan:
    x0: int
    x1: int
    y: int
    height: int
    text: str


@dataclass
class PdfPage:
    number: int
    spans: list[PdfSpan] = field(default_factory=list)
    has_graphics_or_images: bool = False


@dataclass
class PdfDocument:
    pages: list[PdfPage] = field(default_factory=list)
    has_text_layer: bool = False


@dataclass
class _PdfLine:
    y: int
    height: int
    spans: list[PdfSpan]


@dataclass
class _HeaderCol:
    x0: int
    x1: int
    text: str


@dataclass
class _HeaderBand:
    start_idx: int
    end_idx: int
    y_top: int
    y_bottom: int
    cols: list[_HeaderCol]
    import_matches: int
    signature: tuple[str, ...]


def _scaled(value: Any) -> int:
    if value is None:
        return 0
    return int(round(Dezimal(str(value)) * _SCALE, 0).val)


def _clean_raw_text(raw: str) -> str:
    return raw.translate(_CTRL_SPACE_TABLE)


_NARROW_CHARS = frozenset(" .,;:|!ilI1'-")
_NON_NUMERIC_FIELDS = (
    "date",
    "order_date",
    "name",
    "type",
    "ref",
    "iban",
    "isin",
    "ticker",
    "symbol",
    "counterparty",
    "market",
    "portfolio_name",
    "entity",
    "currency",
)


def _split_tj_span(
    tx: int, displaced_tx: int, ty: int, fh: int, raw_text: str
) -> list[PdfSpan]:
    cleaned = _clean_raw_text(raw_text)
    if not cleaned.strip():
        return []
    matches = list(_SINGLE_SPACE_TOKENS.finditer(cleaned))
    total_len = max(len(cleaned), 1)
    width = max(displaced_tx - tx, total_len * max(fh // 2, 30))
    if len(matches) == 1:
        token = matches[0].group(0).strip()
        return [
            PdfSpan(
                x0=tx,
                x1=max(displaced_tx, tx + 10),
                y=ty,
                height=max(fh, 60),
                text=token,
            )
        ]

    spans: list[PdfSpan] = []
    for match in matches:
        token = match.group(0).strip()
        if not token:
            continue
        start, end = match.span()
        x0 = tx + (width * start) // total_len
        x1 = tx + (width * end) // total_len
        if x1 <= x0:
            x1 = x0 + 10
        spans.append(PdfSpan(x0=x0, x1=x1, y=ty, height=max(fh, 60), text=token))
    return spans


def _page_has_graphics_or_images(page: Any) -> bool:
    try:
        resources = page.get("/Resources")
        if resources is not None:
            res_obj = resources.get_object()
            xobjects = res_obj.get("/XObject") if hasattr(res_obj, "get") else None
            if xobjects is not None and len(xobjects.get_object()) > 0:
                return True
        contents = page.get("/Contents")
        if contents is None:
            return False
        obj = contents.get_object()
        streams = obj if isinstance(obj, ArrayObject) else [obj]
        for item in streams:
            stream_obj = item.get_object()
            if isinstance(stream_obj, StreamObject):
                raw = stream_obj.get_data()
                if raw and _GRAPHICS_OP_RE.search(raw):
                    return True
    except Exception:
        return False
    return False


def _extract_page_spans(page: Any, reader: PdfReader) -> list[PdfSpan]:
    contents = page.get("/Contents")
    if contents is not None:
        contents = contents.get_object()
    if not isinstance(contents, (ArrayObject, StreamObject)):
        return []

    fonts = page._layout_mode_fonts()
    ops = iter(ContentStream(contents, reader, "bytes").operations)
    state_mgr = _pdf_fwp.TextStateManager()
    tj_ops = []
    for operands, op in ops:
        if op in (b"BT", b"q"):
            _, tjs = _pdf_fwp.recurse_to_target_op(
                ops,
                state_mgr,
                b"ET" if op == b"BT" else b"Q",
                fonts,
                True,
            )
            tj_ops.extend(tjs)
        elif op == b"Tf":
            _pdf_fwp.set_font_operation(state_mgr, fonts, operands)
        else:
            state_mgr.set_state_param(op, operands)

    if not tj_ops:
        return []

    spans: list[PdfSpan] = []
    seen: set[tuple[int, int, str]] = set()
    for tj in tj_ops:
        if tj.rotated:
            continue
        raw_text = tj.text or ""
        stripped = " ".join(_clean_raw_text(raw_text).split())
        if not stripped:
            continue
        tx = _scaled(tj.tx)
        dx = _scaled(tj.displaced_tx)
        ty = _scaled(-tj.ty if tj.flip_vertical else tj.ty)
        fh = _scaled(tj.font_height or 9)
        dedup_key = (tx // 25, ty // 25, stripped)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        spans.extend(_split_tj_span(tx, dx, ty, fh, raw_text))
    return spans


def extract_pdf_document(data: bytes) -> PdfDocument:
    if b"%PDF-" not in data[:1024]:
        raise UnsupportedFileFormat("Invalid PDF file")

    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        raw_pages = list(reader.pages)
    except Exception as e:
        raise UnsupportedFileFormat("Invalid PDF file") from e

    pages: list[PdfPage] = []
    has_text = False
    for index, raw_page in enumerate(raw_pages, start=1):
        try:
            spans = _extract_page_spans(raw_page, reader)
        except (PdfReadError, PdfStreamError, Exception) as e:
            raise UnsupportedFileFormat("Invalid PDF content stream") from e
        if spans:
            has_text = True
        has_graphics = False if spans else _page_has_graphics_or_images(raw_page)
        pages.append(
            PdfPage(
                number=index,
                spans=spans,
                has_graphics_or_images=has_graphics,
            )
        )
    return PdfDocument(pages=pages, has_text_layer=has_text)


def _group_page_lines(spans: list[PdfSpan]) -> list[_PdfLine]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda s: (-s.y, s.x0))
    raw_lines: list[list[PdfSpan]] = []
    for span in ordered:
        if raw_lines:
            prev_line = raw_lines[-1]
            tol = max(18, min(prev_line[0].height, span.height) * 35 // 100)
            if abs(prev_line[0].y - span.y) <= tol:
                prev_line.append(span)
                continue
        raw_lines.append([span])

    lines: list[_PdfLine] = []
    for group in raw_lines:
        group.sort(key=lambda s: s.x0)
        merged: list[PdfSpan] = []
        for span in group:
            if merged:
                prev = merged[-1]
                inline_gap = max(18, min(prev.height, span.height) // 4)
                if span.x0 - prev.x1 <= inline_gap:
                    merged[-1] = PdfSpan(
                        x0=min(prev.x0, span.x0),
                        x1=max(prev.x1, span.x1),
                        y=(prev.y + span.y) // 2,
                        height=max(prev.height, span.height),
                        text=f"{prev.text} {span.text}".strip(),
                    )
                    continue
            merged.append(span)
        avg_y = sum(s.y for s in merged) // len(merged)
        max_h = max(s.height for s in merged)
        lines.append(_PdfLine(y=avg_y, height=max_h, spans=merged))
    lines.sort(key=lambda line: -line.y)
    return lines


def _is_number_cell(text: str) -> bool:
    stripped = text.strip()
    if not stripped or not any(ch.isdigit() for ch in stripped):
        return False
    if _SHORT_DAY_MONTH_RE.fullmatch(stripped):
        return False
    try:
        parse_number(stripped, NumberFormat.EUROPEAN)
        return True
    except ValueError:
        return False


def _is_date_cell(text: str) -> bool:
    stripped = text.strip()
    if not stripped or not any(ch.isdigit() for ch in stripped):
        return False
    return detect_date_pattern([stripped]) is not None


def _looks_like_data_token(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _SHORT_DAY_MONTH_RE.fullmatch(stripped):
        return True
    return _is_date_cell(stripped) or _is_number_cell(stripped)


def _line_text(line: _PdfLine) -> str:
    return " ".join(s.text for s in line.spans).strip()


def _score_header_cols(cols: list[_HeaderCol]) -> tuple[int, int]:
    matched_fields = set()
    extra = 0
    for col in cols:
        norm = normalize_header(col.text)
        if not norm:
            continue
        matched_any = False
        for field_name in _KNOWN_FIELDS:
            if header_alias_score(field_name, col.text) is not None:
                matched_fields.add(field_name)
                matched_any = True
        if not matched_any and norm in _EXTRA_TABLE_HEADERS:
            extra += 1
    return len(matched_fields), extra


def _merge_header_line(cols: list[_HeaderCol], line: _PdfLine) -> list[_HeaderCol]:
    updated = [_HeaderCol(x0=c.x0, x1=c.x1, text=c.text) for c in cols]
    for span in line.spans:
        best_idx = None
        best_dist = None
        for idx, col in enumerate(updated):
            overlap = min(col.x1, span.x1) - max(col.x0, span.x0)
            if overlap >= -40:
                dist = abs((col.x0 + col.x1) // 2 - (span.x0 + span.x1) // 2)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_idx = idx
        if best_idx is not None:
            target = updated[best_idx]
            updated[best_idx] = _HeaderCol(
                x0=min(target.x0, span.x0),
                x1=max(target.x1, span.x1),
                text=f"{target.text} {span.text}".strip(),
            )
        else:
            updated.append(_HeaderCol(x0=span.x0, x1=span.x1, text=span.text))
    updated.sort(key=lambda c: c.x0)
    return updated


def _find_header_bands(lines: list[_PdfLine]) -> list[_HeaderBand]:
    bands: list[_HeaderBand] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if any(_looks_like_data_token(s.text) for s in line.spans):
            idx += 1
            continue

        cols = [_HeaderCol(x0=s.x0, x1=s.x1, text=s.text) for s in line.spans]
        end_idx = idx
        y_bottom = line.y
        cur_height = line.height
        base_norm = normalize_header(_line_text(line))

        for next_idx in range(idx + 1, min(idx + 3, len(lines))):
            nxt = lines[next_idx]
            if y_bottom - nxt.y > cur_height * 13 // 10:
                break
            if abs(nxt.height - line.height) > 15:
                break
            if any(_looks_like_data_token(s.text) for s in nxt.spans):
                break
            nxt_norm = normalize_header(_line_text(nxt))
            if nxt_norm == base_norm:
                end_idx = next_idx
                y_bottom = nxt.y
                continue
            prev_score = sum(_score_header_cols(cols))
            candidate_cols = _merge_header_line(cols, nxt)
            if (
                len(candidate_cols) > len(cols)
                and sum(_score_header_cols(candidate_cols)) <= prev_score
            ):
                break
            cols = candidate_cols
            end_idx = next_idx
            y_bottom = nxt.y
            cur_height = max(cur_height, nxt.height)

        import_matches, extra_matches = _score_header_cols(cols)
        if len(cols) >= 2 and (
            import_matches >= 2
            or (import_matches >= 1 and import_matches + extra_matches >= 2)
        ):
            sig = tuple(
                normalize_header(c.text) for c in cols if normalize_header(c.text)
            )
            bands.append(
                _HeaderBand(
                    start_idx=idx,
                    end_idx=end_idx,
                    y_top=line.y,
                    y_bottom=y_bottom,
                    cols=cols,
                    import_matches=import_matches,
                    signature=sig,
                )
            )
            idx = end_idx + 1
            continue
        idx += 1
    return bands


def _compute_column_boundaries(
    cols: list[_HeaderCol], data_lines: list[_PdfLine]
) -> list[int]:
    if len(cols) <= 1:
        return []
    data_spans = [span for line in data_lines for span in line.spans]
    boundaries: list[int] = []
    for i in range(len(cols) - 1):
        left, right = cols[i], cols[i + 1]
        if left.x1 < right.x0:
            lo = left.x1
            hi = max(right.x0, right.x1)
            mid_target = (left.x1 + right.x0) // 2
        else:
            lo = (left.x0 + left.x1) // 2
            hi = (right.x0 + right.x1) // 2
            if hi <= lo:
                hi = lo + 10
            mid_target = (lo + hi) // 2

        events = {lo, hi, right.x0}
        for span in data_spans:
            if lo <= span.x0 <= hi:
                events.add(span.x0)
            if lo <= span.x1 <= hi:
                events.add(span.x1)
        sorted_pts = sorted(pt for pt in events if lo <= pt <= hi)
        candidates: list[tuple[int, int, int, int]] = []
        for j in range(len(sorted_pts) - 1):
            a, b = sorted_pts[j], sorted_pts[j + 1]
            cand = (a + b) // 2
            straddle = sum(1 for s in data_spans if s.x0 < cand < s.x1)
            gap_width = b - a
            dist = abs(cand - mid_target)
            candidates.append((straddle, dist // 80, -gap_width, cand))

        if candidates:
            candidates.sort()
            boundaries.append(candidates[0][3])
        else:
            boundaries.append(mid_target)
    return boundaries


def _assign_col(span: PdfSpan, boundaries: list[int]) -> int:
    center = (span.x0 + span.x1) // 2
    for idx, bound in enumerate(boundaries):
        if center < bound:
            return idx
    return len(boundaries)


def _reconstruct_section_rows(
    cols: list[_HeaderCol], data_lines: list[_PdfLine]
) -> list[list[str]]:
    filtered_lines = [
        line for line in data_lines if not _PAGE_FOOTER_RE.match(_line_text(line))
    ]
    if not filtered_lines:
        return []

    boundaries = _compute_column_boundaries(cols, filtered_lines)
    num_cols = len(cols)
    mapped_lines: list[tuple[int, int, list[str]]] = []
    for line in filtered_lines:
        cells = [""] * num_cols
        for span in line.spans:
            c_idx = _assign_col(span, boundaries)
            cells[c_idx] = (
                f"{cells[c_idx]} {span.text}".strip() if cells[c_idx] else span.text
            )
        if any(cells):
            mapped_lines.append((line.y, line.height, cells))

    if not mapped_lines:
        return []

    numeric_cols = {
        c_idx
        for c_idx in range(num_cols)
        if sum(1 for _, _, cells in mapped_lines if _is_number_cell(cells[c_idx])) > 0
        and not any(
            header_alias_score(field_name, cols[c_idx].text) is not None
            for field_name in _NON_NUMERIC_FIELDS
        )
        and normalize_header(cols[c_idx].text) not in {"oficina", "sucursal"}
    }
    date_cols = {
        c_idx
        for c_idx in range(num_cols)
        if header_alias_score("date", cols[c_idx].text) is not None
        or header_alias_score("order_date", cols[c_idx].text) is not None
    }

    anchor_indices = [
        idx
        for idx, (_, _, cells) in enumerate(mapped_lines)
        if (
            any(_is_number_cell(cells[c]) for c in numeric_cols)
            if numeric_cols
            else any(_is_date_cell(cells[c]) for c in date_cols)
        )
    ]
    if not anchor_indices:
        return [cells for _, _, cells in mapped_lines]

    anchors_y = [mapped_lines[idx][0] for idx in anchor_indices]
    median_fh = sorted(h for _, h, _ in mapped_lines)[len(mapped_lines) // 2]
    max_outer_reach = max(220, median_fh * 3)

    anchor_set = set(anchor_indices)
    non_anchor_indices = [
        idx
        for idx in range(len(mapped_lines))
        if idx not in anchor_set
        and anchors_y[-1] - max_outer_reach
        <= mapped_lines[idx][0]
        <= anchors_y[0] + max_outer_reach
    ]

    tol = max(25, median_fh // 3)
    has_lines_above_first_anchor = any(
        mapped_lines[idx][0] > anchors_y[0] + tol for idx in non_anchor_indices
    )
    has_above_empty_anchor_cell = False
    if not has_lines_above_first_anchor:
        for idx in non_anchor_indices:
            ly, _, lcells = mapped_lines[idx]
            nearest_r = min(range(len(anchors_y)), key=lambda r: abs(anchors_y[r] - ly))
            if ly > anchors_y[nearest_r] + tol:
                anchor_cells = mapped_lines[anchor_indices[nearest_r]][2]
                if any(lcells[c] and not anchor_cells[c] for c in range(num_cols)):
                    has_above_empty_anchor_cell = True
                    break

    vertically_centered = has_lines_above_first_anchor or has_above_empty_anchor_cell

    row_buckets: list[list[list[tuple[int, str]]]] = [
        [[] for _ in range(num_cols)] for _ in anchor_indices
    ]
    for r, line_idx in enumerate(anchor_indices):
        ly, _, cells = mapped_lines[line_idx]
        for c in range(num_cols):
            if cells[c]:
                row_buckets[r][c].append((ly, cells[c]))

    for line_idx in non_anchor_indices:
        ly, _, cells = mapped_lines[line_idx]
        if vertically_centered:
            target_r = min(range(len(anchors_y)), key=lambda r: abs(anchors_y[r] - ly))
        else:
            above = [r for r, ay in enumerate(anchors_y) if ay >= ly - tol]
            target_r = above[-1] if above else 0
        for c in range(num_cols):
            if cells[c]:
                row_buckets[target_r][c].append((ly, cells[c]))

    rows: list[list[str]] = []
    for bucket in row_buckets:
        row: list[str] = []
        for col_entries in bucket:
            col_entries.sort(key=lambda item: -item[0])
            row.append(" ".join(text for _, text in col_entries).strip())
        if any(row):
            rows.append(row)
    return rows


def _filter_summary_rows(
    cols: list[_HeaderCol], rows: list[list[str]]
) -> list[list[str]]:
    if len(rows) <= 1:
        return rows
    date_cols = [
        idx
        for idx, col in enumerate(cols)
        if header_alias_score("date", col.text) is not None
    ]
    amount_cols = [
        idx
        for idx, col in enumerate(cols)
        if any(
            header_alias_score(field_name, col.text) is not None
            for field_name in ("amount", "amount_in", "amount_out")
        )
    ]
    if not date_cols:
        return rows
    populated_dates = sum(1 for row in rows if any(row[c].strip() for c in date_cols))
    if populated_dates * 2 <= len(rows):
        return rows
    kept = []
    for row in rows:
        has_date = any(row[c].strip() for c in date_cols)
        has_amount = any(row[c].strip() for c in amount_cols) if amount_cols else False
        if not has_date and not has_amount:
            continue
        kept.append(row)
    return kept


def reconstruct_pdf_table(document: PdfDocument) -> list[list[str]]:
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    first_page_preamble: list[list[str]] = []
    captured_preamble = False

    for page in document.pages:
        lines = _group_page_lines(page.spans)
        if not lines:
            continue
        bands = _find_header_bands(lines)
        if not bands:
            continue

        if not captured_preamble:
            captured_preamble = True
            for pre_line in lines[: bands[0].start_idx]:
                txt = _line_text(pre_line)
                if txt and not _PAGE_FOOTER_RE.match(txt):
                    first_page_preamble.append([txt])
                    if len(first_page_preamble) >= _MAX_PREAMBLE_ROWS:
                        break

        for b_idx, band in enumerate(bands):
            end_line = len(lines)
            if b_idx + 1 < len(bands):
                end_line = bands[b_idx + 1].start_idx
                if end_line > band.end_idx + 1:
                    prev_candidate = lines[end_line - 1]
                    if len(prev_candidate.spans) == 1 and not _looks_like_data_token(
                        prev_candidate.spans[0].text
                    ):
                        end_line -= 1

            section_lines: list[_PdfLine] = []
            band_height = max(
                (lines[i].height for i in range(band.start_idx, band.end_idx + 1)),
                default=60,
            )
            for l_idx in range(band.end_idx + 1, end_line):
                cand_line = lines[l_idx]
                if (
                    section_lines
                    and len(cand_line.spans) <= 2
                    and cand_line.height >= band_height + 25
                    and not any(_looks_like_data_token(s.text) for s in cand_line.spans)
                ):
                    break
                section_lines.append(cand_line)
            section_rows = _reconstruct_section_rows(band.cols, section_lines)
            entry = groups.get(band.signature)
            if entry is None:
                groups[band.signature] = {
                    "cols": band.cols,
                    "import_matches": band.import_matches,
                    "rows": list(section_rows),
                }
            else:
                if len(section_rows) > 0:
                    if len(band.cols) == len(entry["cols"]):
                        entry["rows"].extend(section_rows)

    if not groups:
        raise NoTableFound("No table found in PDF")

    best_entry = None
    best_score = None
    for entry in groups.values():
        cols = entry["cols"]
        cleaned_rows = _filter_summary_rows(cols, entry["rows"])
        entry["rows"] = cleaned_rows
        has_date = any(header_alias_score("date", c.text) is not None for c in cols)
        score = (
            1 if len(cleaned_rows) > 0 else 0,
            1 if has_date and len(cleaned_rows) > 1 else 0,
            entry["import_matches"],
            len(cleaned_rows),
            len(cols),
        )
        if best_score is None or score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is None:
        raise NoTableFound("No table found in PDF")

    headers = [col.text for col in best_entry["cols"]]
    return [*first_page_preamble, headers, *best_entry["rows"]]


class PDFFileTableAdapter(TableRWPort):
    async def convert(self, rows: list[list[str]], format: FileFormat) -> bytes:
        raise ValueError("PDFFileTableAdapter does not support export")

    async def parse(self, upload: FileUpload) -> list[list[Any]]:
        upload.data.seek(0)
        data = upload.data.read()
        document = extract_pdf_document(data)
        if not document.pages:
            raise NoTableFound("Empty PDF file")
        if not document.has_text_layer:
            if any(page.has_graphics_or_images for page in document.pages):
                raise PdfNoTextLayer("PDF file has no selectable text layer")
            raise NoTableFound("Empty PDF file")
        return reconstruct_pdf_table(document)
