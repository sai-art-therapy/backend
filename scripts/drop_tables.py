from app.db.base import Base
from app.db.session import engine

# 모델 import가 반드시 필요합니다.
import app.models  # noqa: F401


def main():
    Base.metadata.drop_all(bind=engine)
    print("테이블 삭제 완료")


if __name__ == "__main__":
    main()