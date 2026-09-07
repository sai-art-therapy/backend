# 만료형 리포트 공유 API

아이의 그림과 해석 내용을 완전 공개 URL로 노출하지 않고, 리포트 소유자가 발급한
무작위 공유 토큰으로 하나의 완료된 리포트만 제한적으로 조회하는 API입니다.

## 보안 원칙

- 기본 유효기간은 72시간이며 서버 환경 변수로 1~168시간 안에서 설정합니다.
- 새 링크를 발급하면 같은 리포트의 이전 공유 링크는 즉시 폐기됩니다.
- DB에는 원본 토큰이 아니라 SHA-256 해시만 저장합니다.
- 공유 응답에는 사용자 ID, 자녀 ID, 내부 파일 경로, YOLO 원본 JSON, PDI 원본,
  전체 리포트 원본 JSON을 포함하지 않습니다.
- 로그인용 `Bearer` JWT와 공유용 `Share` 토큰을 별도 인증 방식으로 구분합니다.
- 리포트 본문과 이미지는 `no-store`로 응답합니다.

## 1. 공유 토큰 발급

리포트 소유자의 로그인 JWT가 필요합니다.

```http
POST /reports/{report_id}/shares
Authorization: Bearer {access_token}
```

완료된 리포트만 공유할 수 있습니다.

```json
{
  "share_token": "무작위_공유_토큰",
  "token_type": "Share",
  "expires_at": "2026-09-10T17:00:00"
}
```

## 2. 프론트 공유 URL 생성

공유 토큰과 리포트 내용을 쿼리 파라미터에 넣지 않습니다. URL fragment는 서버와
HTTP Referrer로 전송되지 않으므로 다음 형식을 사용합니다.

```text
https://sai-gdam.vercel.app/share/result#token={share_token}
```

공유 페이지는 최초 진입 시 fragment에서 토큰을 읽어 `sessionStorage`에 저장한 뒤,
`history.replaceState`로 주소창의 fragment를 제거합니다. 로그인 토큰 저장소에는
공유 토큰을 저장하지 않습니다.

## 3. 공유 리포트 조회

로그인 JWT가 필요하지 않습니다.

```http
GET /shared-reports
Authorization: Share {share_token}
```

응답의 `report`에는 공유 화면에 필요한 자녀 표시 정보, 검사일, 요약, HTP 탭,
관계 해석, 추천, 안전 안내와 아래 이미지 API 주소만 포함됩니다.

```json
{
  "share": {
    "expires_at": "2026-09-10T17:00:00"
  },
  "report": {
    "child": {
      "name": "민준",
      "age": 6,
      "gender": "male"
    },
    "images": {
      "original_image_url": "/shared-reports/images/original",
      "result_image_url": "/shared-reports/images/result"
    }
  }
}
```

## 4. 공유 이미지 조회

`<img src>`로 직접 연결하면 인증 헤더를 넣을 수 없으므로, 프론트에서 Blob으로
받아 `URL.createObjectURL()` 결과를 이미지 `src`로 사용합니다.

```http
GET /shared-reports/images/original
Authorization: Share {share_token}
```

또는 분석 결과 이미지는 다음 주소를 사용합니다.

```http
GET /shared-reports/images/result
Authorization: Share {share_token}
```

공유 페이지에서 사용하는 요청은 로그인용 Axios 인스턴스와 분리해야 합니다.
공유 토큰 오류가 로그인 JWT 삭제나 `/login` 강제 이동으로 이어지면 안 됩니다.

## 5. 공유 링크 폐기

리포트 소유자의 로그인 JWT가 필요합니다.

```http
DELETE /reports/{report_id}/shares
Authorization: Bearer {access_token}
```

```json
{
  "revoked": true
}
```

## 오류 응답

- `400`: 완료되지 않은 리포트 공유 시도
- `401`: `Authorization: Share` 헤더가 없거나 형식이 잘못됨
- `404`: 소유하지 않은 리포트, 만료·폐기·위조된 공유 토큰 또는 없는 이미지

보안을 위해 만료, 폐기, 위조 토큰은 동일하게 `404`로 처리합니다.
