# 리포트 이미지 조회 API

과거 검사 리포트의 그림은 공개 파일 URL이 아니라 로그인 사용자용 API로 조회합니다.
백엔드는 요청한 사용자가 해당 리포트의 소유자인지 확인한 뒤 이미지를 반환합니다.

## 엔드포인트

```http
GET /reports/{report_id}/images/{image_kind}
Authorization: Bearer {access_token}
```

- `report_id`: 리포트 상세 응답의 `report_id`
- `image_kind`: `original` 또는 `result`
- 응답 본문: JPEG, PNG 또는 WEBP 이미지 바이너리
- 캐시: 로그인 사용자 브라우저의 private cache에서 최대 5분

성공 예시:

```http
HTTP/1.1 200 OK
Content-Type: image/jpeg
Cache-Control: private, max-age=300
X-Content-Type-Options: nosniff
```

오류 응답:

- `401`: 로그인 토큰이 없거나 유효하지 않음
- `404`: 본인 소유의 리포트가 아니거나, 요청한 종류의 이미지가 없거나, 저장 파일을 찾을 수 없음
- `422`: `image_kind`가 `original`, `result` 중 하나가 아님

권한이 없는 리포트와 존재하지 않는 리포트는 모두 `404`로 응답하여 다른 사용자의 검사 존재 여부를 노출하지 않습니다.

## 리포트 응답에서 URL 확인

`GET /reports/{report_id}`의 `images`에 다음 필드가 추가됩니다.

```json
{
  "images": {
    "original_image_path": "uploads/htp/original/example.jpg",
    "result_image_path": "uploads/htp/result/example.jpg",
    "original_image_url": "/reports/123/images/original",
    "result_image_url": "/reports/123/images/result"
  }
}
```

이미지가 없는 종류의 URL은 `null`입니다. 기존 `*_image_path`는 하위 호환을 위해 남겨 두었지만 프론트에서는 새 `*_image_url`을 사용해야 합니다.

리포트 목록 응답에는 결과 이미지가 있을 때 다음 값이 포함됩니다.

```json
{
  "report_id": 123,
  "result_image_url": "/reports/123/images/result"
}
```

## 프론트 연동

일반 `<img src="API 주소">` 요청에는 현재 localStorage의 Bearer 토큰이 자동으로 붙지 않습니다. 프로젝트의 `axiosInstance`로 Blob을 받은 다음 객체 URL을 만들어 사용합니다.

```ts
const response = await axiosInstance.get(
  report.images.original_image_url,
  { responseType: "blob" },
);

const imageObjectUrl = URL.createObjectURL(response.data);
setImageUrl(imageObjectUrl);

// 컴포넌트 정리 시 반드시 호출
URL.revokeObjectURL(imageObjectUrl);
```

검사 직후 전달받은 로컬 `File`이 있더라도, 과거 리포트 진입 및 새로고침에서는 이 API를 사용해야 합니다. 이미지 API 주소 앞에는 `VITE_API_BASE_URL`을 직접 붙이지 않아도 `axiosInstance`의 `baseURL`이 적용됩니다.

## 보안 범위

- DB에서 리포트 소유권을 확인합니다.
- DB 경로가 조작되어도 서버의 `uploads/` 폴더 밖 파일은 반환하지 않습니다.
- JPEG, PNG, WEBP 확장자만 반환합니다.
- `/uploads` 폴더 자체는 공개하지 않습니다.
- 현재 공유 리포트 화면처럼 로그인하지 않은 제3자에게 이미지를 공개하는 용도는 아닙니다. 공개 공유가 필요하면 별도의 만료형 공유 토큰 API가 필요합니다.
