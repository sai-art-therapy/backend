import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.services import htp_vlm_fallback_service as vlm
from app.services import yolo_service as yolo


def _detection(label, confidence, bbox):
    return {
        "label": label,
        "display_label": label,
        "confidence": confidence,
        "bbox": bbox,
        "use_for_display": label in {"house", "tree", "person"},
        "use_for_analysis": True,
    }


class _FakeResponse:
    def __init__(self, payload):
        self.output_text = json.dumps(payload)


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []
        self.responses = self

    def with_options(self, **options):
        return self

    def create(self, **request):
        self.calls.append(request)
        return _FakeResponse(self.payload)


class HtpVlmMainRecoveryTests(unittest.TestCase):
    def test_missing_main_alone_triggers_one_vlm_call(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "main-only-trigger.png"
            Image.new("RGB", (100, 100), "white").save(image_path)
            original = [
                _detection(
                    "sun", 0.9,
                    {"x1": 10, "y1": 10, "x2": 30, "y2": 30},
                )
            ]
            fake_client = _FakeClient({
                "verified": [],
                "missing": [
                    {"label": "house", "present": False, "bbox": None},
                    {"label": "person", "present": False, "bbox": None},
                ] + [
                    {"label": label, "present": False, "bbox": None}
                    for parent in ("house", "person")
                    for label in vlm._RECOVERED_PARENT_DETAILS[parent]
                ],
            })
            with (
                patch.object(vlm, "OPENAI_VLM_FALLBACK_ENABLED", True),
                patch.object(vlm, "client", fake_client),
            ):
                corrected, metadata = vlm.apply_vlm_fallback(
                    str(image_path), original, set(), set(), set()
                )

        self.assertEqual(len(fake_client.calls), 1)
        self.assertIsNone(metadata["error"])
        self.assertTrue(metadata["triggered"])
        self.assertEqual(metadata["verified_count"], 0)
        self.assertEqual(corrected, original)

    def test_orphan_shoe_does_not_create_person_feature(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "orphan-shoe.png"
            Image.new("RGB", (200, 200), "white").save(image_path)
            detections = [
                _detection(
                    "sneakers", 0.3,
                    {"x1": 40, "y1": 140, "x2": 80, "y2": 180},
                )
            ]
            features = yolo._create_visual_features_from_yolo(
                str(image_path), detections
            )

        self.assertFalse(features["person"]["detected"])
        self.assertEqual(features["person"]["parts"], {})

    def test_test_253_shoes_above_recovered_person_are_not_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "test-253-coordinates.png"
            Image.new("RGB", (1200, 1200), "white").save(image_path)
            detections = [
                _detection(
                    "person", 0.5,
                    {"x1": 220, "y1": 625, "x2": 459, "y2": 904},
                ),
                _detection(
                    "sneakers", 0.6674,
                    {"x1": 214, "y1": 146, "x2": 539, "y2": 373},
                ),
                _detection(
                    "sneakers", 0.3251,
                    {"x1": 289, "y1": 347, "x2": 545, "y2": 559},
                ),
            ]
            features = yolo._create_visual_features_from_yolo(
                str(image_path), detections
            )

        self.assertTrue(features["person"]["detected"])
        self.assertFalse(features["person"]["parts"]["shoes"]["detected"])

    def test_single_call_recovers_mains_and_rejects_shoe_and_fruit(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "main-recovery.png"
            Image.new("RGB", (400, 300), "white").save(image_path)
            detections = [
                _detection("tree", 0.9, {"x1": 220, "y1": 20, "x2": 380, "y2": 280}),
                _detection("trunk", 0.8, {"x1": 270, "y1": 100, "x2": 320, "y2": 270}),
                _detection("crown", 0.8, {"x1": 240, "y1": 30, "x2": 360, "y2": 140}),
                _detection("sneakers", 0.3, {"x1": 125, "y1": 160, "x2": 155, "y2": 185}),
                _detection("head", 0.8, {"x1": 130, "y1": 25, "x2": 175, "y2": 70}),
            ]
            payload = {
                "verified": [{"candidate_id": 0, "present": False}],
                "missing": [
                    {"label": "root", "present": False, "bbox": None},
                    # A positive fruit proposal outside the crown is still rejected.
                    {"label": "fruit", "present": True, "bbox": [120, 30, 135, 45]},
                    {"label": "flower", "present": False, "bbox": None},
                    {"label": "house", "present": True, "bbox": [10, 10, 100, 120]},
                    {"label": "person", "present": True, "bbox": [110, 20, 200, 210]},
                    {"label": "wall", "present": True, "bbox": [20, 40, 90, 115]},
                    {"label": "roof", "present": True, "bbox": [20, 15, 90, 45]},
                    {"label": "door", "present": False, "bbox": None},
                    {"label": "window", "present": False, "bbox": None},
                    {"label": "chimney", "present": True, "bbox": [75, 10, 88, 35]},
                    {"label": "head", "present": True, "bbox": [130, 25, 175, 70]},
                    {"label": "face", "present": True, "bbox": [135, 35, 170, 65]},
                    {"label": "eye", "present": False, "bbox": None},
                    {"label": "nose", "present": False, "bbox": None},
                    {"label": "mouth", "present": False, "bbox": None},
                    {"label": "arm", "present": True, "bbox": [115, 70, 135, 145]},
                    {"label": "hand", "present": True, "bbox": [110, 135, 130, 155]},
                    {"label": "leg", "present": True, "bbox": [135, 130, 155, 195]},
                    {"label": "foot", "present": True, "bbox": [130, 190, 155, 205]},
                    {"label": "shoes", "present": False, "bbox": None},
                ],
            }
            fake_client = _FakeClient(payload)
            relevant_indexes, selected_parent_types = (
                yolo._get_vlm_relevant_detection_indexes(detections)
            )
            self.assertIn(3, relevant_indexes)
            self.assertEqual(selected_parent_types, {"tree"})
            with (
                patch.object(vlm, "OPENAI_VLM_FALLBACK_ENABLED", True),
                patch.object(vlm, "client", fake_client),
            ):
                corrected, metadata = vlm.apply_vlm_fallback(
                    str(image_path), detections,
                    set().union(*yolo.MAIN_OBJECT_LABELS.values()),
                    relevant_indexes, selected_parent_types,
                )

            self.assertEqual(len(fake_client.calls), 1)
            self.assertIsNone(metadata["error"])
            self.assertEqual(metadata["removed_count"], 1)
            self.assertEqual(metadata["added_count"], 10)
            labels = [item["label"] for item in corrected]
            self.assertIn("house", labels)
            self.assertIn("person", labels)
            self.assertNotIn("sneakers", labels)
            self.assertNotIn("fruit", labels)
            self.assertEqual(labels.count("head"), 1)
            recovered = [
                item for item in corrected
                if item["label"] in {"house", "person"}
            ]
            self.assertTrue(all(item["source"] == "openai_vlm" for item in recovered))
            self.assertTrue(all(item["confidence"] == 0.5 for item in recovered))
            self.assertTrue(all(item["use_for_display"] is True for item in recovered))

            house_bbox = {"x1": 10, "y1": 10, "x2": 100, "y2": 120}
            person_bbox = {"x1": 110, "y1": 20, "x2": 200, "y2": 210}
            self.assertEqual(
                yolo._pick_best_bbox(
                    corrected, "house", allow_subobject_fallback=False
                ),
                house_bbox,
            )
            self.assertEqual(
                yolo._pick_best_bbox(
                    corrected, "person", allow_subobject_fallback=False
                ),
                person_bbox,
            )

            features = yolo._create_visual_features_from_yolo(
                str(image_path), corrected
            )

        self.assertTrue(features["house"]["detected"])
        self.assertTrue(features["person"]["detected"])
        self.assertTrue(features["tree"]["detected"])
        self.assertTrue(features["tree"]["parts"]["trunk"]["detected"])
        self.assertEqual(features["tree"]["parts"]["fruit"]["count"], 0)
        self.assertTrue(features["house"]["parts"]["wall"]["detected"])
        self.assertTrue(features["house"]["parts"]["roof"]["detected"])
        self.assertTrue(features["house"]["parts"]["chimney"]["detected"])
        self.assertFalse(features["house"]["parts"]["door"]["detected"])
        self.assertEqual(features["house"]["parts"]["window"]["count"], 0)
        self.assertIn("roof_detected", features["house"]["tags"])
        self.assertIn("door_not_detected", features["house"]["tags"])
        self.assertTrue(features["person"]["parts"]["head"]["detected"])
        self.assertTrue(features["person"]["parts"]["face"]["detected"])
        self.assertEqual(features["person"]["parts"]["arms"]["count"], 1)
        self.assertEqual(features["person"]["parts"]["hands"]["count"], 1)
        self.assertEqual(features["person"]["parts"]["legs"]["count"], 1)
        self.assertEqual(features["person"]["parts"]["feet"]["count"], 1)
        self.assertFalse(features["person"]["parts"]["shoes"]["detected"])
        self.assertNotIn("hands_not_detected", features["person"]["tags"])
        self.assertNotIn("feet_not_detected", features["person"]["tags"])
        display = yolo._create_display_detections(corrected)
        self.assertEqual({item["type"] for item in display}, {"house", "person", "tree"})
        self.assertEqual(
            next(item["bbox"] for item in display if item["type"] == "house"),
            house_bbox,
        )
        self.assertEqual(
            next(item["bbox"] for item in display if item["type"] == "person"),
            person_bbox,
        )

    def test_invalid_response_remains_fail_open(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "fail-open.png"
            Image.new("RGB", (100, 100), "white").save(image_path)
            original = [
                _detection(
                    "sneakers", 0.3,
                    {"x1": 20, "y1": 60, "x2": 40, "y2": 80},
                )
            ]
            fake_client = _FakeClient({"invalid": True})
            with (
                patch.object(vlm, "OPENAI_VLM_FALLBACK_ENABLED", True),
                patch.object(vlm, "client", fake_client),
            ):
                corrected, metadata = vlm.apply_vlm_fallback(
                    str(image_path), original, set(), {0}, set()
                )

        self.assertEqual(len(fake_client.calls), 1)
        self.assertIs(corrected, original)
        self.assertTrue(metadata["error"].startswith("ValueError:"))

    def test_branch_remains_excluded_from_trigger_b(self):
        missing = vlm._missing_labels(
            [_detection("tree", 0.9, {"x1": 0, "y1": 0, "x2": 100, "y2": 100})],
            {"tree"},
        )
        self.assertNotIn("branch", missing)


if __name__ == "__main__":
    unittest.main()
