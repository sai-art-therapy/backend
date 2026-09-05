import unittest

from app.services.htp_report_service import _assert_report_grounding
from app.services.pdi_service import _filter_grounded_pdi_questions


def _visual():
    return {
        "house": {
            "parts": {
                "door": {"detected": False},
                "window": {"count": 0},
                "roof": {"detected": True},
                "chimney": {"detected": True},
                "wall": {"detected": True},
            }
        },
        "tree": {
            "parts": {
                "trunk": {"detected": True},
                "crown": {"detected": True},
                "branch": {"detected": False},
                "roots": {"detected": False},
                "fruit": {"count": 3},
                "flower": {"count": 0},
            }
        },
        "person": {
            "parts": {
                "head": {"detected": True},
                "face": {"detected": False},
                "hands": {"count": 2},
                "feet": {"count": 2},
                "arms": {"count": 2},
                "legs": {"count": 2},
                "shoes": {"detected": False},
            }
        },
        "relationships": {
            "house_tree": {"overlap": False, "touching": False},
            "house_person": {"overlap": False, "touching": False},
            "tree_person": {"overlap": False, "touching": False},
        },
    }


class HtpGroundingTests(unittest.TestCase):
    def test_pdi_absent_shoes_and_window_are_not_confused_with_feet_and_door(self):
        visual = _visual()
        visual["house"]["parts"]["door"]["detected"] = True
        questions = [dict(question_type="missing_element", question_text=text)
                     for text in ("신발을 그리지 않은 이유가 있나요?", "창문이 없는 이유가 있나요?")]
        self.assertEqual(_filter_grounded_pdi_questions(questions, visual), questions)

    def test_pdi_present_count_parts_and_unknown_features_cannot_be_missing(self):
        questions = [dict(question_type="missing_element", question_text=text)
                     for text in ("팔과 다리를 왜 그리지 않았나요?", "손과 발이 없는 이유가 있나요?",
                                  "벽과 굴뚝이 없나요?", "울타리를 왜 그리지 않았나요?")]
        self.assertEqual(_filter_grounded_pdi_questions(questions, _visual()), [])

    def test_mislabeled_default_question_cannot_claim_present_arms_are_missing(self):
        questions = [{"question_type": "default_pdi", "question_text": "팔을 그리지 않으셨는데 이유가 있나요?"}]
        self.assertEqual(_filter_grounded_pdi_questions(questions, _visual()), [])

    def test_absent_branch_does_not_license_unmeasured_leaf_absence(self):
        questions = [{"question_type": "missing_element", "question_text": "나무에 잎사귀나 가지를 그리지 않으신 이유가 있나요?"}]
        self.assertEqual(_filter_grounded_pdi_questions(questions, _visual()), [])

    def test_report_checks_relationships_outside_relationship_section(self):
        with self.assertRaisesRegex(ValueError, "house_person.touching=false"):
            _assert_report_grounding({"summary": {"one_line_summary": "집과 사람이 맞닿아 있습니다."}}, _visual())

    def test_pdi_drops_missing_question_that_includes_present_roof(self):
        questions = [
            {
                "question_type": "missing_element",
                "question_text": "문이나 지붕이 없는데 왜 그리지 않았나요?",
            },
            {
                "question_type": "missing_element",
                "question_text": "문과 창문을 왜 그리지 않았나요?",
            },
            {
                "question_type": "image_based",
                "question_text": "지붕은 어떤 곳인가요?",
            },
        ]

        grounded = _filter_grounded_pdi_questions(questions, _visual())

        self.assertEqual(
            [item["question_text"] for item in grounded],
            ["문과 창문을 왜 그리지 않았나요?", "지붕은 어떤 곳인가요?"],
        )

    def test_report_rejects_door_state_not_present_in_visual_features(self):
        with self.assertRaisesRegex(ValueError, "unsupported door state"):
            _assert_report_grounding(
                {"tabs": {"house": {"observations": ["문이 열려 있습니다."]}}},
                _visual(),
            )

    def test_report_accepts_explicitly_unknown_door_state(self):
        for text in ("문이 열렸는지 닫혔는지 알 수 없습니다.",
                     "문이 열렸는지 닫혔는지에 대한 정보가 없어 해석은 어렵습니다."):
            with self.subTest(text=text):
                _assert_report_grounding({"tabs": {"house": {"interpretation": text}}}, _visual())

    def test_unrelated_uncertainty_does_not_license_open_door(self):
        with self.assertRaisesRegex(ValueError, "unsupported door state"):
            _assert_report_grounding({"summary": "문이 열려 있습니다. 아이의 기분은 알 수 없습니다."}, _visual())

    def test_report_rejects_positive_touching_when_feature_is_false(self):
        with self.assertRaisesRegex(ValueError, "house_person.touching=false"):
            _assert_report_grounding(
                {
                    "relationship_analysis": {
                        "observations": ["집과 사람이 서로 접촉하고 있습니다."]
                    }
                },
                _visual(),
            )

    def test_report_accepts_grounded_presence_and_negative_relationship(self):
        visual = _visual()
        visual["house"]["parts"]["door"]["detected"] = True
        _assert_report_grounding(
            {
                "tabs": {"house": {"observations": ["문이 탐지되었습니다."]}},
                "relationship_analysis": {
                    "observations": ["집과 사람이 서로 접촉하지 않습니다."]
                },
            },
            visual,
        )


if __name__ == "__main__":
    unittest.main()
