"""Real production PDI/RAG/report calls with in-memory persistence only."""
import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--seed-isolated-rag", action="store_true")
    parser.add_argument("--rag-dir", type=Path)
    args = parser.parse_args()
    args.results_dir.mkdir(parents=True, exist_ok=False)
    if args.seed_isolated_rag:
        os.environ["CHROMA_PATH"] = str((args.results_dir / "chroma").resolve())
    elif args.rag_dir:
        os.environ["CHROMA_PATH"] = str(args.rag_dir.resolve())
    from app.models import HtpTest
    from app.services import pdi_service as pdi, htp_report_service as report, openai_service as ai
    from app.services.htp_rag_service import search_htp_knowledge_for_report
    if args.seed_isolated_rag:
        from app.services.htp_ingest_service import build_htp_document, build_htp_metadata, load_htp_sources
        from app.services.chroma_service import get_collection
        from app.core.config import CHROMA_HTP_COLLECTION, OPENAI_EMBEDDING_MODEL
        chunks = json.loads((REPO / "app/data/rag/htp_report_generation/htp_knowledge.json").read_text(encoding="utf-8"))["chunks"]
        sources = load_htp_sources()
        documents = [build_htp_document(chunk, sources) for chunk in chunks]
        embedded = ai.client.embeddings.create(model=OPENAI_EMBEDDING_MODEL, input=documents)
        get_collection(CHROMA_HTP_COLLECTION).add(
            ids=[chunk["id"] for chunk in chunks], documents=documents,
            metadatas=[build_htp_metadata(chunk, sources) for chunk in chunks],
            embeddings=[item.embedding for item in sorted(embedded.data, key=lambda item: item.index)],
        )
        save(args.results_dir / "rag_setup.json", {"isolated": True, "chunk_count": len(chunks)})
        print(f"Isolated production RAG documents indexed: {len(chunks)}", flush=True)
    result = json.loads(args.analysis.read_text(encoding="utf-8"))
    test = HtpTest(id=0, visual_features_json=result["visual_features_json"],
                   yolo_result_json=result["yolo_result_json"], result_image_path=result["result_image_path"],
                   pdi_status="not_started")
    # No writes to app DB and no invented child/PDI answers.
    db = MagicMock()
    original_generate = ai.generate_json_answer
    captured = []

    def generate(prompt):
        response = original_generate(prompt)
        captured.append(response)
        save(args.results_dir / f"generated_{len(captured):02d}.json", response)
        return response

    try:
        with patch.object(ai, "generate_json_answer", generate), patch.object(report, "generate_json_answer", generate):
            interactions = pdi.create_pdi_questions(test, db)
            questions = pdi.format_pdi_questions(interactions)
            save(args.results_dir / "pdi_questions.json", questions)
            print(json.dumps({"questions": questions}, ensure_ascii=False), flush=True)
            pdi.skip_pdi(test)
            knowledge = search_htp_knowledge_for_report(test, [])
            save(args.results_dir / "rag.json", knowledge)
            generated = report.generate_htp_report(test, [], knowledge)
            save(args.results_dir / "report.json", generated)
            print(json.dumps({"report_summary": generated["summary"], "rag_count": len(knowledge),
                              "grounding_guard": "passed", "persistence": "in-memory, no app DB writes"}, ensure_ascii=False), flush=True)
    except Exception as exc:
        save(args.results_dir / "error.json", {"type": type(exc).__name__})
        print("Grounding verification failed:", type(exc).__name__, flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
