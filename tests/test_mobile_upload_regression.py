import unittest
from io import BytesIO

from PIL import Image

from app.services.image_upload_service import (
    PHOTO_MAX_IMAGE_BYTES,
    ImageUploadValidationError,
    normalize_photo_upload,
)


def _image_bytes(image_format: str, size: tuple[int, int] = (320, 240)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, "white").save(output, format=image_format)
    return output.getvalue()


class MobileUploadRegressionTest(unittest.TestCase):
    def test_accepts_jpeg_at_exactly_25_mb(self):
        jpeg = _image_bytes("JPEG")
        padded = jpeg + (b"\0" * (PHOTO_MAX_IMAGE_BYTES - len(jpeg)))

        normalized = normalize_photo_upload(padded)

        self.assertEqual(normalized.source_format, "JPEG")
        self.assertEqual((normalized.width, normalized.height), (320, 240))

    def test_rejects_jpeg_over_25_mb(self):
        jpeg = _image_bytes("JPEG")
        padded = jpeg + (b"\0" * (PHOTO_MAX_IMAGE_BYTES + 1 - len(jpeg)))

        with self.assertRaises(ImageUploadValidationError) as context:
            normalize_photo_upload(padded)

        self.assertEqual(context.exception.status_code, 413)
        self.assertEqual(context.exception.code, "image_too_large")

    def test_accepts_heif_and_converts_to_jpeg(self):
        normalized = normalize_photo_upload(_image_bytes("HEIF"))

        self.assertEqual(normalized.source_format, "HEIF")
        self.assertEqual(normalized.extension, ".jpg")

    def test_resizes_long_edge_to_4096(self):
        normalized = normalize_photo_upload(_image_bytes("JPEG", (5000, 1000)))

        self.assertEqual((normalized.width, normalized.height), (4096, 819))


if __name__ == "__main__":
    unittest.main()
