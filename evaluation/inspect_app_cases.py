"""Read only the requested failure and recent local app detection evidence."""
import json
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def main():
    from sqlalchemy import create_engine, text
    from app.core.config import DATABASE_URL
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, required=True)
    output = parser.parse_args().results_dir
    output.mkdir(exist_ok=False)
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"connect_timeout": 10})
    try:
        with engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            rows = connection.execute(text(
                "SELECT id, original_image_path, yolo_result_json, visual_features_json "
                "FROM htp_tests WHERE id = 253 OR id IN "
                "(SELECT id FROM htp_tests ORDER BY id DESC LIMIT 5) ORDER BY id"
            )).mappings().all()
            for row in rows:
                data = dict(row)
                (output / f"test_{row['id']}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                result = data.get("yolo_result_json") or {}
                print(json.dumps({"id": row["id"], "image_path": row["original_image_path"],
                                  "mains": [d for d in result.get("all_detections", []) if d.get("label") in
                                            {"tree", "house", "person", "male_person", "female_person"}]}, ensure_ascii=False))
    except Exception as exc:
        # Connection exceptions can contain credentials/hostnames; report type only.
        print("Database audit failed:", type(exc).__name__)
        raise SystemExit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
