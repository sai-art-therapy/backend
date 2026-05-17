from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.htp_pdi import HtpPdiInteraction
from app.models.htp_test import HtpTest


def create_mock_pdi_questions(htp_test: HtpTest, db: Session) -> List[HtpPdiInteraction]:
    """개발 테스트용 PDI 질문 생성.

    추후 실제 구현에서는:
    1. visual_features_json 확인
    2. HTP RAG에서 기본 PDI/관련 지식 검색
    3. GPT로 기본 질문 + 이미지 기반 맞춤 질문 생성
    """
    # 기존 질문이 있다면 중복 생성을 막기 위해 삭제 후 재생성
    db.query(HtpPdiInteraction).filter(
        HtpPdiInteraction.htp_test_id == htp_test.id
    ).delete()

    mock_questions = [
        {
            "round_no": 1,
            "sort_order": 1,
            "target_type": "house",
            "question_type": "default_pdi",
            "question_text": "이 집에는 누가 살고 있나요?",
            "reason": "집 그림의 의미를 아이의 설명으로 확인하기 위함",
        },
        {
            "round_no": 1,
            "sort_order": 2,
            "target_type": "house",
            "question_type": "image_based",
            "question_text": "이 집에는 들어가는 문이 있을까요? 있다면 어디에 있을까요?",
            "reason": "이미지 분석에서 문이 뚜렷하게 탐지되지 않아 확인하기 위함",
        },
        {
            "round_no": 1,
            "sort_order": 3,
            "target_type": "tree",
            "question_type": "default_pdi",
            "question_text": "이 나무는 살아있는 나무인가요?",
            "reason": "나무 그림의 생동감과 아이의 설명을 함께 확인하기 위함",
        },
        {
            "round_no": 1,
            "sort_order": 4,
            "target_type": "tree",
            "question_type": "image_based",
            "question_text": "이 나무는 땅에 잘 서 있는 나무일까요?",
            "reason": "이미지 분석에서 뿌리가 뚜렷하게 탐지되지 않아 확인하기 위함",
        },
        {
            "round_no": 1,
            "sort_order": 5,
            "target_type": "person",
            "question_type": "default_pdi",
            "question_text": "이 사람은 어떤 기분인가요?",
            "reason": "사람 그림의 정서적 의미를 아이의 표현으로 확인하기 위함",
        },
        {
            "round_no": 1,
            "sort_order": 6,
            "target_type": "person",
            "question_type": "image_based",
            "question_text": "이 사람은 지금 무엇을 하고 싶어 하나요?",
            "reason": "이미지 분석에서 사람이 작게 표현되어 행동 의도와 감정을 확인하기 위함",
        },
    ]

    interactions = []

    for item in mock_questions:
        interaction = HtpPdiInteraction(
            htp_test_id=htp_test.id,
            round_no=item["round_no"],
            sort_order=item["sort_order"],
            target_type=item["target_type"],
            question_type=item["question_type"],
            question_text=item["question_text"],
            reason=item["reason"],
        )
        db.add(interaction)
        interactions.append(interaction)

    htp_test.pdi_status = "accepted"
    htp_test.test_status = "waiting_pdi_answers"

    return interactions


def format_pdi_questions(interactions: List[HtpPdiInteraction]) -> list[dict]:
    return [
        {
            "question_id": interaction.id,
            "round_no": interaction.round_no,
            "sort_order": interaction.sort_order,
            "target_type": interaction.target_type,
            "question_type": interaction.question_type,
            "question_text": interaction.question_text,
            "reason": interaction.reason,
        }
        for interaction in sorted(interactions, key=lambda x: (x.round_no, x.sort_order))
    ]


def save_pdi_answers(
    htp_test: HtpTest,
    answers: list,
    db: Session,
) -> dict:
    """PDI 답변 저장.

    현재는 mock 흐름:
    - 답변 저장
    - 추가 질문 없이 바로 PDI 완료 처리

    추후 실제 구현:
    - GPT가 답변을 보고 추가 질문 필요 여부 판단
    - need_followup=True면 followup 질문 생성
    """
    question_ids = [item.question_id for item in answers]

    interactions = (
        db.query(HtpPdiInteraction)
        .filter(
            HtpPdiInteraction.htp_test_id == htp_test.id,
            HtpPdiInteraction.id.in_(question_ids),
        )
        .all()
    )

    interaction_map = {interaction.id: interaction for interaction in interactions}

    missing_ids = [qid for qid in question_ids if qid not in interaction_map]
    if missing_ids:
        return {
            "ok": False,
            "missing_ids": missing_ids,
        }

    now = datetime.utcnow()

    for answer in answers:
        interaction = interaction_map[answer.question_id]
        interaction.answer_text = answer.answer_text
        interaction.answered_at = now

    all_interactions = (
        db.query(HtpPdiInteraction)
        .filter(HtpPdiInteraction.htp_test_id == htp_test.id)
        .order_by(HtpPdiInteraction.round_no, HtpPdiInteraction.sort_order)
        .all()
    )

    answered_count = sum(1 for item in all_interactions if item.answer_text)

    htp_test.pdi_status = "completed"
    htp_test.test_status = "ready_to_generate_report"
    htp_test.pdi_summary_json = {
        "status": "completed",
        "answered_count": answered_count,
        "summary": "PDI 답변이 저장되었습니다. 추후 GPT 요약 결과로 교체 예정입니다.",
    }

    return {
        "ok": True,
        "saved_count": len(answers),
        "answered_count": answered_count,
        "need_followup": False,
        "followup_questions": [],
    }


def skip_pdi(htp_test: HtpTest) -> None:
    htp_test.pdi_status = "skipped"
    htp_test.test_status = "ready_to_generate_report"
    htp_test.pdi_summary_json = {
        "status": "skipped",
        "answered_count": 0,
        "summary": "이번 리포트는 아이의 추가 답변 없이 이미지 분석 결과를 중심으로 작성됩니다.",
    }
