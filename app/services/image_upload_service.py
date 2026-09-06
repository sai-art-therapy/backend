from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener


PHOTO_MAX_IMAGE_BYTES = 25 * 1024 * 1024
PHOTO_MAX_IMAGE_PIXELS = 60_000_000
PHOTO_MAX_OUTPUT_DIMENSION = 4096
ALLOWED_PHOTO_FORMATS = {"JPEG", "PNG", "WEBP", "HEIF"}

register_heif_opener(thumbnails=False)


class ImageUploadValidationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class NormalizedPhoto:
    content: bytes
    source_format: str
    source_width: int
    source_height: int
    width: int
    height: int
    extension: str = ".jpg"


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba_image = image.convert("RGBA")
        background = Image.new("RGB", rgba_image.size, "white")
        background.paste(rgba_image, mask=rgba_image.getchannel("A"))
        return background
    return image.convert("RGB")


def normalize_photo_upload(image_bytes: bytes) -> NormalizedPhoto:
    if not image_bytes:
        raise ImageUploadValidationError("empty_image", "이미지 파일이 비어 있습니다.")
    if len(image_bytes) > PHOTO_MAX_IMAGE_BYTES:
        raise ImageUploadValidationError(
            "image_too_large",
            (
                "카메라/앨범 이미지는 "
                f"{PHOTO_MAX_IMAGE_BYTES // (1024 * 1024)}MB 이하여야 합니다."
            ),
            status_code=413,
        )

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            source_format = image.format or ""
            source_width, source_height = image.size

            if source_format not in ALLOWED_PHOTO_FORMATS:
                raise ImageUploadValidationError(
                    "unsupported_image_format",
                    "JPEG, PNG, WEBP, HEIC, HEIF 이미지만 업로드할 수 있습니다.",
                    status_code=415,
                )
            if (
                source_width <= 0
                or source_height <= 0
                or source_width * source_height > PHOTO_MAX_IMAGE_PIXELS
            ):
                raise ImageUploadValidationError(
                    "invalid_image_dimensions",
                    "이미지 크기가 올바르지 않거나 60MP 허용 범위를 초과했습니다.",
                )

            image.load()
            normalized_image = ImageOps.exif_transpose(image)
            normalized_image.thumbnail(
                (PHOTO_MAX_OUTPUT_DIMENSION, PHOTO_MAX_OUTPUT_DIMENSION),
                Image.Resampling.LANCZOS,
            )
            normalized_image = _to_rgb(normalized_image)

            output = BytesIO()
            normalized_image.save(
                output,
                format="JPEG",
                quality=92,
                subsampling=0,
                optimize=True,
            )
            width, height = normalized_image.size
    except ImageUploadValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageUploadValidationError(
            "invalid_image",
            "읽을 수 없거나 손상된 이미지 파일입니다.",
        ) from exc

    return NormalizedPhoto(
        content=output.getvalue(),
        source_format=source_format,
        source_width=source_width,
        source_height=source_height,
        width=width,
        height=height,
    )
