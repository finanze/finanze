from dataclasses import dataclass, field
from html.parser import HTMLParser
from io import BytesIO
from typing import Optional

from application.ports.file_rw_port import TableRWPort
from application.ports.image_normalizer import ImageNormalizer
from application.ports.pdf_page_renderer import PdfPageRenderer
from domain.ai import AIAttachment, AIInputModality
from domain.exception.exceptions import (
    NoTableFound,
    PdfNoTextLayer,
    UnsupportedFileFormat,
)
from domain.file_upload import FileUpload
from domain.importing import AIImportFailed, ImportResultCode
from infrastructure.templating.cell_values import cell_text, is_empty_cell
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 4_200_000
MAX_TEXT_PAGES = 40
MAX_RENDERED_PAGES = 10
MAX_TEXT_CHARS = 200_000
CHUNK_CHARS = 12_000
TABLE_CHUNK_ROWS = 40
MIN_PAGE_TEXT_CHARS = 20
PDF_MIME = "application/pdf"
TEXT_EXTENSIONS = (".txt", ".text")
TEXT_CONTENT_TYPES = ("text/plain",)

IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)
HEIF_BRANDS = (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


@dataclass
class DocumentSegment:
    text: str
    attachments: list[AIAttachment] = field(default_factory=list)


@dataclass
class ImportDocument:
    segments: list[DocumentSegment]
    modality: Optional[AIInputModality] = None
    pages: Optional[int] = None


def image_mime(data: bytes) -> Optional[str]:
    for signature, mime in IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in HEIF_BRANDS:
        return "image/heic"
    return None


class _TextCollector(HTMLParser):
    BLOCK_TAGS = {"p", "div", "tr", "br", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in self.BLOCK_TAGS:
            self.parts.append("\n")
        elif tag in ("td", "th"):
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def _html_text(data: bytes) -> str:
    collector = _TextCollector()
    collector.feed(data.decode("utf-8", errors="replace"))
    return "".join(collector.parts)


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def text_segments(text: str) -> list[DocumentSegment]:
    lines = [line.rstrip() for line in text[:MAX_TEXT_CHARS].splitlines()]
    segments, current, size = [], [], 0
    for line in lines:
        if not line.strip():
            continue
        if current and size + len(line) > CHUNK_CHARS:
            segments.append(DocumentSegment("\n".join(current)))
            current, size = [], 0
        current.append(line)
        size += len(line) + 1
    if current:
        segments.append(DocumentSegment("\n".join(current)))
    return segments


def table_segments(rows: list[list]) -> list[DocumentSegment]:
    lines = [
        " | ".join(cell_text(cell).strip() for cell in row)
        for row in rows
        if any(not is_empty_cell(cell) for cell in row)
    ]
    if not lines:
        return []
    header, body = lines[0], lines[1:] or []
    if not body:
        return [DocumentSegment(header)]
    return [
        DocumentSegment("\n".join([header, *body[i : i + TABLE_CHUNK_ROWS]]))
        for i in range(0, len(body), TABLE_CHUNK_ROWS)
    ]


def _pdf_texts(data: bytes) -> list[str]:
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(""):
            raise AIImportFailed(
                ImportResultCode.UNSUPPORTED_FILE_FORMAT, "Encrypted PDF"
            )
        pages = reader.pages[:MAX_TEXT_PAGES]
        texts = []
        for page in pages:
            try:
                texts.append(page.extract_text(extraction_mode="layout") or "")
            except Exception:
                texts.append(page.extract_text() or "")
        return texts
    except PdfReadError as e:
        raise AIImportFailed(
            ImportResultCode.UNSUPPORTED_FILE_FORMAT, "Unreadable PDF"
        ) from e


class ImportDocumentReader:
    def __init__(
        self,
        table_rw_port: TableRWPort,
        image_normalizer: Optional[ImageNormalizer] = None,
        page_renderer: Optional[PdfPageRenderer] = None,
    ):
        self._table_rw_port = table_rw_port
        self._image_normalizer = image_normalizer
        self._page_renderer = page_renderer

    async def read(self, upload: FileUpload) -> ImportDocument:
        upload.data.seek(0)
        data = upload.data.read(MAX_FILE_BYTES + 1)
        upload.data.seek(0)
        if not data:
            raise AIImportFailed(ImportResultCode.UNSUPPORTED_FILE_FORMAT, "Empty file")
        if len(data) > MAX_FILE_BYTES:
            raise AIImportFailed(ImportResultCode.AI_FILE_TOO_LARGE)

        mime = image_mime(data)
        if mime is not None:
            image = await self._normalize(
                AIAttachment(mime_type=mime, data=data, name=upload.filename)
            )
            return ImportDocument(
                segments=[DocumentSegment("", [image])],
                modality=AIInputModality.IMAGE,
                pages=1,
            )

        if data.lstrip()[:5] == b"%PDF-":
            return await self._read_pdf(data, upload.filename)

        filename = (upload.filename or "").lower()
        content_type = (upload.content_type or "").split(";", 1)[0].strip().lower()
        if filename.endswith(TEXT_EXTENSIONS) or content_type in TEXT_CONTENT_TYPES:
            return self._text_document(_decode_text(data))

        try:
            rows = await self._table_rw_port.parse(upload)
        except NoTableFound:
            return self._text_document(_html_text(data))
        except (UnsupportedFileFormat, PdfNoTextLayer) as e:
            raise AIImportFailed(ImportResultCode.UNSUPPORTED_FILE_FORMAT) from e
        finally:
            upload.data.seek(0)
        segments = table_segments(rows)
        if not segments:
            raise AIImportFailed(ImportResultCode.AI_EXTRACTION_EMPTY)
        return ImportDocument(segments=segments)

    def _text_document(self, text: str) -> ImportDocument:
        segments = text_segments(text)
        if not segments:
            raise AIImportFailed(ImportResultCode.AI_EXTRACTION_EMPTY)
        return ImportDocument(segments=segments)

    async def _read_pdf(self, data: bytes, filename: Optional[str]) -> ImportDocument:
        texts = _pdf_texts(data)
        text_pages = [
            text for text in texts if len(text.strip()) >= MIN_PAGE_TEXT_CHARS
        ]
        if text_pages and len(text_pages) * 2 >= len(texts):
            segments = text_segments("\n".join(text_pages))
            if segments:
                return ImportDocument(segments=segments, pages=len(texts))

        if self._page_renderer is not None:
            pages = await self._page_renderer.render(
                data, MAX_RENDERED_PAGES, MAX_IMAGE_PIXELS
            )
            if pages:
                images = [await self._normalize(page) for page in pages]
                return ImportDocument(
                    segments=[DocumentSegment("", [image]) for image in images],
                    modality=AIInputModality.IMAGE,
                    pages=len(images),
                )

        return ImportDocument(
            segments=[
                DocumentSegment(
                    "",
                    [
                        AIAttachment(
                            mime_type=PDF_MIME, data=data, name=filename or None
                        )
                    ],
                )
            ],
            modality=AIInputModality.DOCUMENT,
            pages=len(texts),
        )

    async def _normalize(self, image: AIAttachment) -> AIAttachment:
        if self._image_normalizer is not None:
            return await self._image_normalizer.normalize(
                image, MAX_IMAGE_PIXELS, MAX_IMAGE_BYTES
            )
        if image.mime_type == "image/heic":
            raise AIImportFailed(ImportResultCode.UNSUPPORTED_FILE_FORMAT, "HEIC")
        if len(image.data) > MAX_IMAGE_BYTES:
            raise AIImportFailed(ImportResultCode.AI_FILE_TOO_LARGE)
        return image
