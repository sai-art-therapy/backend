import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image

from app.services.image_upload_service import (
    PHOTO_MAX_IMAGE_BYTES,
    ImageUploadValidationError,
    normalize_photo_upload,
)


def _image_bytes(image_format: str, size: tuple[int, int] = (80, 60)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=image_format)
    return buffer.getvalue()


class ImageUploadServiceTest(unittest.TestCase):
    def test_normalizes_supported_web_formats_to_jpeg(self):
        for image_format in ("JPEG", "PNG", "WEBP"):
            with self.subTest(image_format=image_format):
                normalized = normalize_photo_upload(_image_bytes(image_format))

                self.assertEqual(normalized.source_format, image_format)
                self.assertEqual(normalized.extension, ".jpg")
                with Image.open(BytesIO(normalized.content)) as image:
                    self.assertEqual(image.format, "JPEG")
                    self.assertEqual(image.size, (80, 60))

    def test_accepts_heif_and_normalizes_it_to_jpeg(self):
        normalized = normalize_photo_upload(_image_bytes("HEIF"))

        self.assertEqual(normalized.source_format, "HEIF")
        with Image.open(BytesIO(normalized.content)) as image:
            self.assertEqual(image.format, "JPEG")

    def test_applies_exif_orientation_before_saving(self):
        buffer = BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new("RGB", (80, 40), "white").save(
            buffer,
            format="JPEG",
            exif=exif,
        )

        normalized = normalize_photo_upload(buffer.getvalue())

        self.assertEqual((normalized.width, normalized.height), (40, 80))

    def test_rejects_file_larger_than_limit_before_decoding(self):
        with self.assertRaises(ImageUploadValidationError) as context:
            normalize_photo_upload(b"x" * (PHOTO_MAX_IMAGE_BYTES + 1))

        self.assertEqual(context.exception.code, "image_too_large")
        self.assertEqual(context.exception.status_code, 413)

    def test_rejects_unsupported_image_by_actual_content(self):
        with self.assertRaises(ImageUploadValidationError) as context:
            normalize_photo_upload(_image_bytes("BMP"))

        self.assertEqual(context.exception.code, "unsupported_image_format")
        self.assertEqual(context.exception.status_code, 415)

    def test_rejects_image_over_pixel_limit(self):
        with patch(
            "app.services.image_upload_service.PHOTO_MAX_IMAGE_PIXELS",
            10,
        ):
            with self.assertRaises(ImageUploadValidationError) as context:
                normalize_photo_upload(_image_bytes("PNG", size=(4, 3)))

        self.assertEqual(context.exception.code, "invalid_image_dimensions")


if __name__ == "__main__":
    unittest.main()
