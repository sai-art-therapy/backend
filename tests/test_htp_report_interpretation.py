import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import htp_rag_service as rag, htp_report_service as report


def visual_fixture():
    return {
        "house": {"detected": True, "relative_size": "medium", "position": {"x": "left", "y": "middle"},
                  "parts": {"door": {"detected": True}, "window": {"count": 1},
                            "roof": {"detected": True}, "wall": {"detected": True}, "chimney": {"detected": False}}},
        "tree": {"detected": True, "relative_size": "medium", "position": {"x": "right", "y": "top"},
                 "parts": {"trunk": {"detected": True}, "crown": {"detected": True}, "roots": {"detected": True},
                           "branch": {"detected": False}, "fruit": {"count": 5}, "flower": {"count": 0}}},
        "person": {"detected": True, "relative_size": "small", "position": {"x": "center", "y": "middle"},
                   "parts": {"arms": {"count": 2}, "legs": {"count": 2}, "hands": {"count": 2},
                             "feet": {"count": 2}, "shoes": {"detected": True}}},
        "relationships": {"house_person": {"touching": False, "overlap": False, "distance_level": "middle"}},
    }


class HtpReportInterpretationTests(unittest.TestCase):
    def test_rag_queries_include_measured_parts_without_changing_counts_or_absence(self):
        visual = visual_fixture()
        for query, facts in (
            (rag.build_feature_query_for_house(visual), ("지붕 탐지 여부 True", "벽 탐지 여부 True", "굴뚝 탐지 여부 False")),
            (rag.build_feature_query_for_tree(visual), ("가지 탐지 여부 False", "열매 개수 5", "꽃 개수 0")),
            (rag.build_feature_query_for_person(visual), ("팔 개수 2", "다리 개수 2", "신발 탐지 여부 True")),
        ):
            for fact in facts:
                self.assertIn(fact, query)
        self.assertIn("굴뚝 탐지 여부 None", rag.build_feature_query_for_house({}))

    def test_composition_query_preserves_object_specific_size_and_unknown_absence(self):
        visual = visual_fixture()
        test = SimpleNamespace(visual_features_json=visual, child=None)
        queries = rag.build_htp_rag_queries(test, [])
        composition = rag.build_feature_query_for_composition(visual)
        self.assertIn(composition, queries)
        self.assertIn("'relative_size': 'small'", composition)
        self.assertIn("'relative_size': 'medium'", composition)
        self.assertEqual(rag.build_feature_query_for_composition({}), "")

    def test_production_report_keeps_interpretation_and_runs_grounding_after_generation(self):
        visual = visual_fixture()
        test = SimpleNamespace(visual_features_json=visual, child=None, pdi_status="skipped",
                               result_image_path=None, yolo_result_json={})
        interpretation = "작은 크기의 사람 표현은 자기표현의 신중함과 관련해 참고할 수 있습니다."
        generated = {"tabs": {"person": {"interpretation": interpretation}}}
        with patch.object(report, "generate_json_answer", return_value=generated) as generate:
            result = report.generate_htp_report(test, [], [{"document": "작은 사람 그림은 신중한 자기표현의 가능성을 참고한다."}])
        self.assertEqual(result["tabs"]["person"]["interpretation"], interpretation)
        prompt = generate.call_args.args[0]
        self.assertIn("PDI가 없어도 관찰 특징 + 관련 RAG", prompt)
        self.assertIn("summary.disclaimer에", prompt)
        self.assertIn("touching=false", prompt)
        for bad in ("문이 열려 있습니다.", "집과 사람이 서로 접촉하고 있습니다."):
            with self.subTest(bad=bad), patch.object(report, "generate_json_answer", return_value={"summary": bad}):
                with self.assertRaises(ValueError):
                    report.generate_htp_report(test, [], [])

    def test_pdi_is_provided_as_attributed_support_for_visual_interpretation(self):
        test = SimpleNamespace(visual_features_json=visual_fixture(), child=None, pdi_status="completed",
                               result_image_path=None, yolo_result_json={})
        pdi = [SimpleNamespace(question_text="이 사람은 누구인가요?", answer_text="저예요.", target_type="person")]
        with patch.object(report, "generate_json_answer", return_value={}) as generate:
            report.generate_htp_report(test, pdi, [])
        prompt = generate.call_args.args[0]
        self.assertIn("[person] Q: 이 사람은 누구인가요? / A: 저예요.", prompt)
        self.assertIn("답변 요약으로 대체하지 말 것", prompt)
        self.assertIn("JSON의 관찰값을 덮어쓰지 말 것", prompt)

    def test_abstract_exchange_survives_while_physical_contradictions_are_rejected(self):
        test = SimpleNamespace(visual_features_json=visual_fixture(), child=None, pdi_status="skipped",
                               result_image_path=None, yolo_result_json={})
        generated = {"relationship_analysis": {
            "observations": ["집과 사람은 맞닿거나 겹치지 않습니다."],
            "interpretation": "집과 사람의 배치는 교류 관심과 심리적 거리를 살펴보는 단서일 수 있습니다.",
        }}
        with patch.object(report, "generate_json_answer", return_value=generated):
            result = report.generate_htp_report(test, [], [])
        self.assertEqual(result["relationship_analysis"], generated["relationship_analysis"])
        for text in ("집과 사람이 맞닿아 있습니다.", "집과 사람이 겹쳐 있습니다."):
            with self.subTest(text=text), patch.object(report, "generate_json_answer", return_value={"summary": text}):
                with self.assertRaises(ValueError):
                    report.generate_htp_report(test, [], [])

    def test_composition_does_not_supply_unmeasured_part_attributes_or_missing_objects(self):
        visual = visual_fixture()
        visual["house"]["relative_size"] = "large"
        visual["tree"]["detected"] = False
        query = rag.build_feature_query_for_composition(visual)
        self.assertIn("'house': {'relative_size': 'large'", query)
        self.assertNotIn("roof", query)
        self.assertNotIn("'tree':", query)
        self.assertNotIn("parts", query)

    def test_prompt_preserves_attribute_scope_and_conditional_rag_requirements(self):
        test = SimpleNamespace(visual_features_json=visual_fixture(), child=None, pdi_status="skipped",
                               result_image_path=None, yolo_result_json={})
        with patch.object(report, "generate_json_answer", return_value={}) as generate:
            report.generate_htp_report(test, [], [])
        prompt = generate.call_args.args[0]
        for rule in ("객체 전체의 relative_size", "부위의 detected/count", "교류 관심/관계 지향/심리적 거리",
                     "적용 조건이 관찰값에 맞을 때만", "RAG가 비었거나 관련 근거가 없으면",
                     "미탐지를 미완성·결핍·문제로 바꾸지 말 것", "직접적인 RAG 근거가 없으면 열매는 관찰만"):
            with self.subTest(rule=rule):
                self.assertIn(rule, prompt)

    def test_generation_remains_one_call_without_rewriting_report_fields(self):
        test = SimpleNamespace(visual_features_json=visual_fixture(), child=None, pdi_status="skipped",
                               result_image_path=None, yolo_result_json={})
        for knowledge in ([], [{"document": "작은 사람 그림: 신중한 자기표현 가능성"}]):
            generated = {"tabs": {"person": {"observations": ["사람이 작게 탐지되었습니다."],
                                            "interpretation": "작은 사람 표현은 신중한 자기표현과 관련될 수 있습니다.",
                                            "positive_note": "팔과 다리가 표현되었습니다.", "tags": ["사람"]}}}
            with self.subTest(has_rag=bool(knowledge)), patch.object(report, "generate_json_answer", return_value=generated) as generate:
                result = report.generate_htp_report(test, [], knowledge)
            generate.assert_called_once()
            self.assertEqual(result["tabs"]["person"]["observations"], ["사람이 작게 탐지되었습니다."])
            self.assertEqual(result["tabs"]["person"]["interpretation"],
                             "작은 사람 표현은 신중한 자기표현과 관련될 수 있습니다.")
            self.assertEqual(result["tabs"]["person"]["positive_note"], "팔과 다리가 표현되었습니다.")
            self.assertEqual(result["tabs"]["person"]["tags"], ["사람"])
            self.assertNotIn("semantic_review", result["rag"])
            self.assertIn("RAG가 비었거나 관련 근거가 없으면", generate.call_args.args[0])



if __name__ == "__main__":
    unittest.main()
