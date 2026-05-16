from datetime import datetime

from app.db.session import SessionLocal
from app.models.user import User
from app.models.child import Child
from app.models.htp_test import HtpTest
from app.models.chat import ChatSession, ChatMessage


def main():
    db = SessionLocal()

    try:
        # 1. 테스트 사용자 생성
        user = User(
            email="test_parent@example.com",
            name="테스트 부모",
            nickname="테스트맘",
            provider="google",
            provider_id="google-test-provider-id",
            caregiver_type="mother",
            agreed_to_service=True,
            agreed_to_service_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # 2. 테스트 자녀 생성
        child = Child(
            user_id=user.id,
            name="테스트 아이",
            birth_year=2016,
            gender="female",
        )
        db.add(child)
        db.commit()
        db.refresh(child)

        # 3. 테스트 HTP 검사 기록 생성
        htp_test = HtpTest(
            user_id=user.id,
            child_id=child.id,
            test_status="completed",
            test_date=datetime.utcnow(),
            consent_agreed=True,
            consent_agreed_at=datetime.utcnow(),
            original_image_path="uploads/htp/original/sample_house.png",
            result_image_path="uploads/htp/result/sample_house_result.png",
            yolo_result_json={
                "objects": [
                    {
                        "label": "house",
                        "confidence": 0.92,
                        "bbox": [10, 20, 100, 120],
                    },
                    {
                        "label": "tree",
                        "confidence": 0.88,
                        "bbox": [140, 30, 220, 180],
                    },
                ]
            },
            summary_text="테스트 아이는 전반적으로 안정적인 정서 기반을 갖추고 있어요.",
            main_emotion="stable",
            report_text="테스트 리포트입니다. 그림에서 안정감과 자기표현 관련 특징이 관찰되었습니다.",
            report_json={
                "title": "테스트 아이의 마음 이야기",
                "summary": "테스트 아이는 전반적으로 안정적인 정서 기반을 갖추고 있어요.",
                "elements": {
                    "house": {
                        "label": "집",
                        "category": "정서・가족 인식",
                        "status": "양호",
                        "basis": "집 그림 기반",
                        "description": "문과 창문이 적절한 크기로 그려져 타인에게 열려 있는 태도를 보여줍니다.",
                        "tags": ["개방적 태도", "안정적 가족감", "감정 발산 방식 점검"],
                        "bbox": [10, 20, 100, 120],
                        "image_path": "uploads/htp/result/sample_house_result.png",
                    }
                },
            },
            recommendations_json=[
                {
                    "title": "집에서 함께 그림 그리기",
                    "description": "아이와 함께 가족 그림을 그리고 이야기를 나눠보세요.",
                    "type": "home_activity",
                },
                {
                    "title": "자연 속 놀이 활동 권장",
                    "description": "흙 놀이, 모래 놀이처럼 안정감을 키우는 신체 활동이 도움이 됩니다.",
                    "type": "outdoor_activity",
                },
                {
                    "title": "전문 상담 고려",
                    "description": "결과가 걱정되시거나 지속적인 변화가 보인다면 아동 심리 전문가와 상담해보세요.",
                    "type": "referral",
                },
            ],
        )
        db.add(htp_test)
        db.commit()
        db.refresh(htp_test)

        # 4. 테스트 채팅방 생성
        chat_session = ChatSession(
            user_id=user.id,
            child_id=child.id,
            htp_test_id=htp_test.id,
            title="테스트 리포트 상담방",
        )
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)

        # 5. 테스트 메시지 생성
        user_message = ChatMessage(
            session_id=chat_session.id,
            role="user",
            content="최근 HTP 리포트를 바탕으로 아이를 어떻게 도와주면 좋을까요?",
            sources_json=None,
        )

        assistant_message = ChatMessage(
            session_id=chat_session.id,
            role="assistant",
            content="아이의 감정을 먼저 공감해주고, 안정적인 일상 루틴을 만들어주는 것이 좋습니다.",
            sources_json=[
                {
                    "title": "테스트 육아 가이드",
                    "url": "https://example.com/parenting-guide",
                }
            ],
        )

        db.add(user_message)
        db.add(assistant_message)
        db.commit()

        print("테스트 데이터 삽입 완료")
        print(f"user_id: {user.id}")
        print(f"child_id: {child.id}")
        print(f"htp_test_id: {htp_test.id}")
        print(f"chat_session_id: {chat_session.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()