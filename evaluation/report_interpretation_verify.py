"""Generate real reports from wholly synthetic fixtures; no drawing data is read.

All observations and PDI answers are invented test inputs, never actual child data.
Grounding guards and lexical diagnostics are recorded; semantic review remains manual.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def interpretation_diagnostics(result):
    """Review aids, not an assertion that an LLM report is semantically grounded."""
    interpretations = {k: v["interpretation"] for k, v in result["tabs"].items()}
    interpretations["relationships"] = result["relationship_analysis"]["interpretation"]
    return {
        "interpretations": interpretations,
        "sentence_counts": {k: len([s for s in re.split(r"[.!?]+", text) if s.strip()])
                            for k, text in interpretations.items()},
        "character_counts": {k: len(text) for k, text in interpretations.items()},
        "manual_semantic_review_required": True,
        "review_dimensions": ["object_vs_part_attributes", "physical_vs_abstract_relationships",
                              "rag_conditions", "unmeasured_facts", "pdi_attribution",
                              "interpretation_information", "positive_note_grounding"],
    }


def synthetic_visual(sparse=False):
    """Construct test values independently of any image or stored analysis."""
    def flags(names):
        return {name: {"detected": present} for name, present in names.items()}

    def counts(names):
        return {name: {"count": count} for name, count in names.items()}

    return {
        "house": {"detected": True, "relative_size": "large", "position": {"x": "right", "y": "bottom"},
                  "parts": {**flags(dict(door=not sparse, roof=True, wall=True, chimney=False)),
                            **counts(dict(window=0 if sparse else 3))}},
        "tree": {"detected": True, "relative_size": "medium", "position": {"x": "center", "y": "middle"},
                 "parts": {**flags(dict(trunk=True, crown=True, roots=False, branch=not sparse)),
                           **counts(dict(fruit=0 if sparse else 2, flower=0))}},
        "person": {"detected": True, "relative_size": "small", "position": {"x": "left", "y": "middle"},
                   "parts": {**flags(dict(head=True, face=True, shoes=not sparse)),
                             **counts(dict(arms=2, legs=2, hands=0 if sparse else 2, feet=0 if sparse else 2))}},
        "relationships": {name: {"touching": False, "overlap": False, "distance_level": distance}
                          for name, distance in (("house_tree", "middle"), ("house_person", "far"), ("tree_person", "middle"))},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--rag-dir", type=Path, required=True)
    args = parser.parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=False)
    os.environ["CHROMA_PATH"] = str(args.rag_dir.resolve())
    from app.services import htp_report_service as report, htp_rag_service as rag
    from app.services.chroma_service import get_collection
    from app.core.config import CHROMA_HTP_COLLECTION
    count = get_collection(CHROMA_HTP_COLLECTION).count()
    if not count:
        raise RuntimeError("Real RAG verification requires a populated evaluation index")
    files = ["app/services/" + name + ".py" for name in
             ("htp_report_service", "htp_rag_service", "yolo_service", "htp_vlm_fallback_service", "pdi_service")]
    save(args.results_dir / "manifest.json", {"rag_chunks": count, "all_inputs_synthetic": True,
         "sha256": {name: hashlib.sha256((REPO / name).read_bytes()).hexdigest() for name in files}})
    examples = [
        ("complete_without_pdi", False, []),
        ("complete_with_pdi", False, [
            ("house", "이 집은 누구의 집인가요?", "우리 가족이 같이 사는 집이에요."),
            ("tree", "이 나무의 열매는 어떤 의미인가요?", "가족과 같이 먹으려고 그렸어요."),
            ("person", "이 사람은 누구인가요?", "저예요. 나무를 보러 가고 있어요."),
        ]),
        ("sparse_without_pdi", True, []),
        ("complete_without_rag", False, []),
    ]
    generate = report.generate_json_answer
    failed = []
    for name, sparse, answers in examples:
        directory = args.results_dir / name
        directory.mkdir()
        test = SimpleNamespace(visual_features_json=synthetic_visual(sparse),
                               yolo_result_json={}, result_image_path=None,
                               child=None, pdi_status="completed" if answers else "skipped")
        pdi = [SimpleNamespace(target_type=t, question_text=q, answer_text=a) for t, q, a in answers]
        save(directory / "input.json", {"visual": test.visual_features_json, "pdi": [vars(item) for item in pdi],
                                       "all_inputs_synthetic": True})

        calls = []

        def capture(prompt):
            number = len(calls) + 1
            calls.append(number)
            (directory / f"prompt_{number:02d}.txt").write_text(prompt, encoding="utf-8")
            result = generate(prompt)
            save(directory / f"generated_{number:02d}.json", result)
            return result

        try:
            knowledge = [] if name == "complete_without_rag" else rag.search_htp_knowledge_for_report(test, pdi)
            save(directory / "rag.json", knowledge)
            with patch.object(report, "generate_json_answer", capture):
                result = report.generate_htp_report(test, pdi, knowledge)
            if len(calls) != 1:
                raise ValueError("Production report generation must use exactly one LLM call")
            save(directory / "report.json", result)
            diagnostics = {"grounding_guard": "passed", "rag_count": len(knowledge), "generation_calls": len(calls),
                           **interpretation_diagnostics(result)}
            save(directory / "diagnostics.json", diagnostics)
            print(json.dumps({"case": name, **diagnostics}, ensure_ascii=False), flush=True)
        except Exception as exc:
            save(directory / "error.json", {"type": type(exc).__name__,
                 "validation_error": str(exc) if isinstance(exc, ValueError) else None})
            print(f"{name}: {type(exc).__name__}", flush=True)
            failed.append(name)
    save(args.results_dir / "summary.json", {"cases": len(examples), "failed_cases": failed,
         "manual_semantic_review_required": True})
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
