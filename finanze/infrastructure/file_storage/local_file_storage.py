import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional

from math import sqrt

from application.ports.file_storage_port import FileStoragePort
from domain.file_upload import FileUpload


class LocalFileStorage(FileStoragePort):
    MAX_IMAGE_PIXELS = 8_000_000

    def __init__(
        self,
        upload_dir: Path,
        static_url_prefix: str,
        *,
        jpeg_quality: int = 82,
    ):
        self.upload_dir = upload_dir
        self.static_url_prefix = static_url_prefix
        self.jpeg_quality = jpeg_quality
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def _is_image(self, file: FileUpload) -> bool:
        content_type = (file.content_type or "").lower()
        if content_type.startswith("image/"):
            return True

        ext = Path(file.filename or "").suffix.lower()
        return ext in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
            ".tif",
            ".tiff",
            ".bmp",
        }

    def _compress_image_if_needed(self, file: FileUpload) -> FileUpload:
        from PIL import Image, ImageOps

        raw = file.data.read()
        image_bytes = BytesIO(raw)
        image_bytes.seek(0)

        try:
            with Image.open(image_bytes) as im:
                im = ImageOps.exif_transpose(im)

                width, height = im.size
                pixels = width * height

                if pixels > self.MAX_IMAGE_PIXELS and width > 0 and height > 0:
                    scale = sqrt(self.MAX_IMAGE_PIXELS / float(pixels))
                    new_w = max(1, int(width * scale))
                    new_h = max(1, int(height * scale))
                    im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)

                original_format = (im.format or "").upper()

                out = BytesIO()
                # Keep PNG when it has transparency; otherwise pick JPEG for better size.
                has_alpha = im.mode in {"RGBA", "LA"} or (
                    im.mode == "P" and "transparency" in (im.info or {})
                )

                if original_format == "PNG" and has_alpha:
                    save_format = "PNG"
                    im.save(out, format=save_format, optimize=True)
                    out_content_type = "image/png"
                    out_filename = Path(file.filename).with_suffix(".png").name
                else:
                    save_format = "JPEG"
                    if im.mode not in {"RGB", "L"}:
                        im = im.convert("RGB")
                    im.save(
                        out,
                        format=save_format,
                        quality=self.jpeg_quality,
                        optimize=True,
                        progressive=True,
                    )
                    out_content_type = "image/jpeg"
                    out_filename = Path(file.filename).with_suffix(".jpg").name

                out.seek(0)

                return FileUpload(
                    filename=out_filename,
                    content_type=out_content_type,
                    content_length=len(out.getbuffer()),
                    data=out,
                )
        except Exception:
            # If we can't process it as an image, fall back to the original bytes.
            fallback = BytesIO(raw)
            fallback.seek(0)
            return FileUpload(
                filename=file.filename,
                content_type=file.content_type,
                content_length=len(raw),
                data=fallback,
            )

    def save(self, file: FileUpload, folder: str, keep_name: bool = False) -> str:
        if not file.filename:
            raise ValueError("No filename provided")

        folder_path = self.upload_dir / folder
        folder_path.mkdir(parents=True, exist_ok=True)

        effective_file = file
        if self._is_image(file):
            effective_file = self._compress_image_if_needed(file)

        if not keep_name:
            file_extension = Path(effective_file.filename).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"
        else:
            unique_filename = effective_file.filename

        file_path = folder_path / unique_filename

        try:
            with open(file_path, "wb") as f:
                while True:
                    chunk = effective_file.data.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            raise ValueError(f"Failed to save file: {str(e)}")

        return f"{folder}/{unique_filename}"

    def save_from_url(
        self, file_url: str, folder: str, filename: Optional[str] = None
    ) -> str:
        import requests

        response = requests.get(file_url, stream=True, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"Failed to fetch file from URL: {file_url}")

        content_type = response.headers.get("Content-Type", "application/octet-stream")
        content_length = int(response.headers.get("Content-Length", 0) or 0)

        if not filename:
            filename = file_url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4()}"

        # Buffer the response so it can be processed (and rewound) reliably.
        data = BytesIO(response.content)
        data.seek(0)

        file_upload = FileUpload(
            filename=filename,
            content_type=content_type,
            content_length=content_length or len(response.content),
            data=data,
        )

        return self.save(file_upload, folder, keep_name=True)

    def delete(self, file_path: str) -> bool:
        try:
            full_path = self.upload_dir / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception:
            return False

    def get_url(self, file_path: str) -> str:
        return f"{self.static_url_prefix}/{file_path}"

    def delete_by_url(self, file_url: str) -> bool:
        file_path = Path(file_url.replace(self.static_url_prefix + "/", ""))
        return self.delete(str(file_path))
