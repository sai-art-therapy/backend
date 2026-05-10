from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ingest_service import ingest_parenting_guides


if __name__ == "__main__":
    result = ingest_parenting_guides(reset=True)
    print(result)