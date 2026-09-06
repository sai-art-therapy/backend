# GDAM 백엔드 운영 가이드

## 배포와 상태 확인

- `main` 브랜치에 병합되면 GitHub Actions가 테스트를 통과한 커밋만 EC2에 자동 배포합니다.
- 배포 스크립트는 DB, YOLO 모델 파일, 업로드 저장 공간을 확인하는
  `GET /health/ready`가 성공해야 배포를 완료합니다.
- 프로세스 생존 여부만 확인할 때는 `GET /health/live`를 사용합니다.
- Uvicorn은 `127.0.0.1:8000`에만 바인딩하며, 외부 요청은 Nginx HTTPS를 통해서만
  전달됩니다.

```bash
curl --fail https://gdam-test.duckdns.org/health/ready
```

정상 응답 예시는 다음과 같습니다.

```json
{
  "status": "ready",
  "checks": {
    "database": true,
    "models": true,
    "storage": true
  }
}
```

## 운영 환경 변수

- `JWT_SECRET_KEY`: 32자 이상의 임의 문자열이 필수입니다.
- `SQLALCHEMY_ECHO`: 운영에서는 `false`를 유지합니다.
- `RAG_ADMIN_ENABLED`: 관리자 RAG API를 사용할 때만 잠시 `true`로 변경합니다.
- `RAG_ADMIN_TOKEN`: 관리자 API 활성화 시 필요한 32자 이상의 별도 임의 문자열입니다.

관리자 API는 기본적으로 404를 반환하도록 비활성화되어 있습니다. 데이터 재적재가
꼭 필요한 경우에만 환경 변수를 설정하고 다음처럼 호출한 뒤 다시 비활성화합니다.

```bash
curl -X POST \
  -H "X-Admin-Token: ${RAG_ADMIN_TOKEN}" \
  https://gdam-test.duckdns.org/api/admin/rag/ingest-htp
```

토큰은 코드, 문서, 메신저, 명령 기록에 실제 값으로 남기지 않습니다.

## 개인정보 파일 정리

회원 또는 자녀를 삭제하면 해당 HTP 검사에 연결된 원본 이미지, YOLO 결과 이미지,
직접 그리기 렌더링 이미지도 `uploads/`에서 함께 삭제합니다. DB 삭제 성공 후 파일
정리를 수행하며, `uploads/` 밖의 경로는 안전을 위해 삭제하지 않습니다.

## 콘솔에서 별도로 확인할 항목

다음 항목은 저장소 코드만으로 강제할 수 없으므로 운영자가 주기적으로 확인합니다.

- AWS 보안 그룹에서 외부 인바운드 `8000/tcp` 규칙 제거
- SSH `22/tcp` 접근 대상을 필요한 관리자 IP로 제한
- GitHub `main` 브랜치에 PR 및 CI 통과 보호 규칙 설정
- PostgreSQL과 `uploads/`의 외부 저장소 백업 및 복구 테스트
- 배포 실패, 5xx 증가, 디스크 부족 알림 연결

## 아직 남은 인증 개선

현재 Google OAuth에는 요청 위조 방지를 위한 `state` 검증이 적용되어 있습니다. 다만
로그인 성공 JWT를 프론트 콜백 URL의 쿼리 문자열로 전달하는 기존 계약은 유지됩니다.
이를 일회용 교환 코드 방식으로 바꾸려면 프론트와 백엔드를 동시에 변경해야 합니다.
