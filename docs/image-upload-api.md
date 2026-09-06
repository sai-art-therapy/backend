# 카메라/앨범 이미지 업로드 API

카메라로 촬영하거나 앨범에서 선택한 HTP 그림은 기존 API로 전송합니다.

```http
POST /tests/{test_id}/image
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

| 필드 | 필수 | 제한 |
| --- | --- | --- |
| `file` | O | JPEG, PNG, WebP, HEIC, HEIF / 최대 25MB / 최대 60MP |

서버는 파일명 확장자나 요청의 MIME 값이 아니라 이미지의 실제 내용을 검사합니다.
허용된 이미지는 EXIF 방향을 보정하고, 긴 변이 4096px를 넘으면 비율을 유지해 축소한 뒤
고품질 JPEG로 정규화하여 저장합니다. 투명한 영역은 흰 배경으로 합성됩니다.

RAW/DNG는 지원하지 않습니다. iPhone ProRAW 등 RAW 촬영본은 기기 또는 프론트에서
JPEG/HEIC 등 일반 이미지로 변환한 뒤 업로드해야 합니다.

성공 후에는 기존과 동일하게 `POST /tests/{test_id}/analyze`를 호출합니다.

## 프론트 처리 기준

- 파일 선택창은 `accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.jpg,.jpeg,.png,.webp,.heic,.heif"`를 사용합니다.
- 프론트에서 압축하더라도 원본 업로드 제한은 25MB로 안내합니다.
- 브라우저가 HEIC를 미리보기로 디코딩하지 못해도 원본 파일은 그대로 서버에 전송할 수 있습니다.
- 분석이 시작된 검사는 이미지를 교체할 수 없으므로 `409 image_not_replaceable`을 받으면 새 검사를 시작하도록 안내합니다.
- 오류 메시지는 `error.response?.data?.detail?.message`를 우선 표시합니다.

## 오류 응답

| 상태 | `detail.code` | 의미 |
| --- | --- | --- |
| `409` | `image_not_replaceable` | 분석/PDI/리포트가 이미 진행되어 이미지 교체 불가 |
| `413` | `image_too_large` | 25MB 초과 |
| `415` | `unsupported_image_format` | 실제 이미지 형식이 허용 목록에 없음 |
| `422` | `empty_image` | 빈 파일 |
| `422` | `invalid_image` | 읽을 수 없거나 손상된 이미지 |
| `422` | `invalid_image_dimensions` | 크기가 잘못되었거나 60MP 초과 |

Nginx의 `client_max_body_size 30M` 설정은 25MB 이미지와 multipart overhead를
수용하므로 그대로 사용합니다.
