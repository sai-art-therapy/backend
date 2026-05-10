def get_report_context(report_id: str | None) -> str:
    """
    나중에 PostgreSQL에서 report_id로 HTP 리포트를 조회하도록 수정할 예정.
    지금은 RAG 챗봇 테스트용 mock context.
    """
    if not report_id:
        return "연결된 HTP 리포트 없음"

    return """
[HTP 리포트 참고 요약]
- 이 내용은 전문 심리 진단이 아니라 부모 관찰을 돕기 위한 참고 정보입니다.
- 아이가 위축되거나 불안해 보일 수 있는 표현이 일부 관찰되었습니다.
- 상담 답변에서는 이를 단정하지 말고, 정서적 안정감 제공과 대화법 중심으로 안내합니다.
"""