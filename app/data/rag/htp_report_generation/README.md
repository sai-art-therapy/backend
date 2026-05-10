# HTP Report Generation RAG Data

HTP 검사 결과 리포트 생성에 사용할 RAG 지식데이터입니다.

## Files

- sources.json: HTP 검사/미술심리 해석 관련 출처 목록
- htp_knowledge.json: HTP 리포트 생성용 지식데이터

## Usage

집-나무-사람 그림 분석 결과와 아이의 답변을 바탕으로 GPT가 HTP 검사 결과 리포트를 생성할 때 사용합니다.

## Rule

- 대화형 챗봇이 아니라 단발성 리포트 생성용 RAG입니다.
- HTP 그림 특징만으로 아이의 심리 상태를 단정하지 않습니다.
- 전문가 해석을 대체하지 않습니다.
- 그림 분석 결과, 아이 답변, 생활 맥락을 함께 고려하는 방식으로 작성합니다.
