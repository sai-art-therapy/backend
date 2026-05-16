from app.db.base import Base
from app.db.session import engine

# 모델 import가 반드시 필요합니다.
# 그래야 Base.metadata에 테이블 정보가 등록됩니다.
import app.models  # noqa: F401


def main():
    Base.metadata.create_all(bind=engine)
    print("테이블 생성 완료")


if __name__ == "__main__":
    main()