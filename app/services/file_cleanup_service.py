import logging
from pathlib import Path
from typing import Iterable


logger = logging.getLogger(__name__)


def collect_htp_test_file_paths(htp_tests: Iterable[object]) -> set[str]:
    """Collect every locally stored image path owned by the given HTP tests."""
    paths: set[str] = set()

    for htp_test in htp_tests:
        for attribute in ("original_image_path", "result_image_path"):
            value = getattr(htp_test, attribute, None)
            if isinstance(value, str) and value:
                paths.add(value)

        yolo_result = getattr(htp_test, "yolo_result_json", None)
        if isinstance(yolo_result, dict):
            result_paths = yolo_result.get("result_image_paths")
            if isinstance(result_paths, dict):
                paths.update(
                    value
                    for value in result_paths.values()
                    if isinstance(value, str) and value
                )

        canvas_drawing = getattr(htp_test, "canvas_drawing", None)
        rendered_path = getattr(canvas_drawing, "rendered_image_path", None)
        if isinstance(rendered_path, str) and rendered_path:
            paths.add(rendered_path)

    return paths


def delete_managed_files(
    file_paths: Iterable[str],
    upload_root: Path | str = Path("uploads"),
) -> None:
    """Best-effort delete for regular files located strictly below uploads/."""
    managed_root = Path(upload_root).resolve()

    for raw_path in set(file_paths):
        try:
            candidate = Path(raw_path).resolve()

            if not candidate.is_relative_to(managed_root):
                logger.warning("Skipped unmanaged file during cleanup: %s", raw_path)
                continue

            if candidate.is_file():
                candidate.unlink()
        except OSError:
            logger.exception("Failed to remove managed file: %s", raw_path)
