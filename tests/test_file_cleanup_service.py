import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.services.file_cleanup_service import (
    collect_htp_test_file_paths,
    delete_managed_files,
)


class FileCleanupServiceTest(unittest.TestCase):
    def test_collects_all_known_htp_image_paths_without_duplicates(self):
        htp_test = SimpleNamespace(
            original_image_path="uploads/original.jpg",
            result_image_path="uploads/result.jpg",
            yolo_result_json={
                "result_image_paths": {
                    "all": "uploads/result.jpg",
                    "house": "uploads/house.jpg",
                    "invalid": None,
                }
            },
            canvas_drawing=SimpleNamespace(
                rendered_image_path="uploads/canvas.jpg"
            ),
        )

        self.assertEqual(
            collect_htp_test_file_paths([htp_test]),
            {
                "uploads/original.jpg",
                "uploads/result.jpg",
                "uploads/house.jpg",
                "uploads/canvas.jpg",
            },
        )

    def test_deletes_only_files_inside_upload_root(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            uploads = temp_path / "uploads"
            uploads.mkdir()
            managed_file = uploads / "managed.jpg"
            managed_file.write_bytes(b"managed")
            outside_file = temp_path / "outside.jpg"
            outside_file.write_bytes(b"outside")

            previous_directory = os.getcwd()
            os.chdir(temp_path)
            try:
                delete_managed_files(
                    ["uploads/managed.jpg", "outside.jpg"],
                    upload_root=uploads,
                )
            finally:
                os.chdir(previous_directory)

            self.assertFalse(managed_file.exists())
            self.assertTrue(outside_file.exists())


if __name__ == "__main__":
    unittest.main()
