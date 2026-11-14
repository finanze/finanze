import asyncio
from io import BytesIO
from math import sqrt

from application.ports.image_normalizer import ImageNormalizer
from domain.ai import AIAttachment
from domain.importing import AIImportFailed, ImportResultCode
from PIL import Image, ImageOps, UnidentifiedImageError

PASSTHROUGH_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
EXIF_ORIENTATION = 0x0112
JPEG_QUALITY = 90


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in (image.info or {})
    )


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
            out = BytesIO()
            if _has_alpha(result):
                result.save(out, format="PNG", optimize=True)
                mime_type = "image/png"
            else:
                if result.mode not in {"RGB", "L"}:
                    result = result.convert("RGB")
                result.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
                mime_type = "image/jpeg"
    except (UnidentifiedImageError, OSError) as e:
        raise AIImportFailed(
            ImportResultCode.UNSUPPORTED_FILE_FORMAT, "Unreadable image"
        ) from e

    data = out.getvalue()
    if len(data) > max_bytes:
        raise AIImportFailed(ImportResultCode.AI_FILE_TOO_LARGE)
    return AIAttachment(mime_type=mime_type, data=data, name=image.name)


class PillowImageNormalizer(ImageNormalizer):
    async def normalize(
        self, image: AIAttachment, max_pixels: int, max_bytes: int
    ) -> AIAttachment:
        return await asyncio.to_thread(_normalize, image, max_pixels, max_bytes)
