import asyncio
from io import BytesIO
from math import sqrt

from application.ports.image_normalizer import ImageNormalizer
from domain.ai import AIAttachment
from domain.importing import AIImportFailed, ImportResultCode
from PIL import Image, ImageOps, UnidentifiedImageError

# WebP is re-encoded, llama.cpp vision cannot decode it
PASSTHROUGH_TYPES = {"image/png", "image/jpeg", "image/gif"}
EXIF_ORIENTATION = 0x0112
JPEG_QUALITY = 90
MIN_SPLIT_HEIGHT = 64
SPLIT_BAND = (0.35, 0.65)


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in (image.info or {})
    )


def _encode(image: Image.Image) -> tuple[bytes, str]:
    out = BytesIO()
    if _has_alpha(image):
        image.save(out, format="PNG", optimize=True)
        return out.getvalue(), "image/png"
    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    image.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), "image/jpeg"


def _normalize(image: AIAttachment, max_pixels: int, max_bytes: int) -> AIAttachment:
    try:
        with Image.open(BytesIO(image.data)) as source:
            width, height = source.size
            orientation = source.getexif().get(EXIF_ORIENTATION, 1)
            if (
                image.mime_type in PASSTHROUGH_TYPES
                and width * height <= max_pixels
                and len(image.data) <= max_bytes
                and orientation == 1
            ):
                return image

            result = ImageOps.exif_transpose(source)
            width, height = result.size
            if width * height > max_pixels:
                scale = sqrt(max_pixels / float(width * height))
                result = result.resize(
                    (max(1, int(width * scale)), max(1, int(height * scale))),
                    Image.Resampling.LANCZOS,
                )
            data, mime_type = _encode(result)
    except (UnidentifiedImageError, OSError) as e:
        raise AIImportFailed(
            ImportResultCode.UNSUPPORTED_FILE_FORMAT, "Unreadable image"
        ) from e

    if len(data) > max_bytes:
        raise AIImportFailed(ImportResultCode.AI_FILE_TOO_LARGE)
    return AIAttachment(mime_type=mime_type, data=data, name=image.name)


def _split(image: AIAttachment, max_bytes: int) -> list[AIAttachment]:
    try:
        with Image.open(BytesIO(image.data)) as source:
            source.load()
            width, height = source.size
            if height < MIN_SPLIT_HEIGHT:
                return []
            start, end = (int(height * ratio) for ratio in SPLIT_BAND)
            band = source.convert("L").crop((0, start, width, end))
            brightness = list(
                band.resize((1, end - start), Image.Resampling.BOX).getdata()
            )
            middle = (end - start) // 2
            # The brightest row is the gap between text lines, closest to the middle wins ties
            cut = start + max(
                range(len(brightness)),
                key=lambda row: (brightness[row], -abs(row - middle)),
            )
            halves = [
                _encode(source.crop((0, 0, width, cut))),
                _encode(source.crop((0, cut, width, height))),
            ]
    except (UnidentifiedImageError, OSError):
        return []
    if any(len(data) > max_bytes for data, _ in halves):
        return []
    return [
        AIAttachment(mime_type=mime_type, data=data, name=image.name)
        for data, mime_type in halves
    ]


class PillowImageNormalizer(ImageNormalizer):
    async def normalize(
        self, image: AIAttachment, max_pixels: int, max_bytes: int
    ) -> AIAttachment:
        return await asyncio.to_thread(_normalize, image, max_pixels, max_bytes)

    async def split(self, image: AIAttachment, max_bytes: int) -> list[AIAttachment]:
        return await asyncio.to_thread(_split, image, max_bytes)
