# 캔버스 직접 그리기 API 연동 명세

기존 카메라/앨범 업로드 API인 `POST /tests/{test_id}/image`는 그대로 사용합니다.
앱에서 직접 그린 그림만 아래 신규 API로 전송합니다.

## 요청

```http
POST /tests/{test_id}/drawing
Authorization: Bearer {access_token}
Content-Type: multipart/form-data
```

| 필드 | 형식 | 필수 | 설명 |
| --- | --- | --- | --- |
| `file` | PNG/JPEG/WEBP 파일 | O | 캔버스를 이미지로 내보낸 결과. 최대 10MB |
| `drawing_data` | `application/json` 파일 | O | 캔버스 크기, 시간, stroke/point 데이터. 최대 15MB |

`drawing_data` 예시:

```json
{
  "schema_version": 1,
  "canvas": {
    "width": 1024,
    "height": 768
  },
  "duration_ms": 125430,
  "strokes": [
    {
      "stroke_id": "stroke-1",
      "pointer_type": "pen",
      "pressure_source": "measured",
      "brush_width_px": 4,
      "points": [
        { "x": 0.12, "y": 0.34, "t_ms": 0, "pressure": 0.31 },
        { "x": 0.13, "y": 0.35, "t_ms": 16, "pressure": 0.47 }
      ]
    },
    {
      "stroke_id": "stroke-2",
      "pointer_type": "touch",
      "pressure_source": "unavailable",
      "brush_width_px": 4,
      "points": [
        { "x": 0.51, "y": 0.44, "t_ms": 520 },
        { "x": 0.52, "y": 0.46, "t_ms": 536 }
      ]
    }
  ]
}
```

### 좌표와 시간

- `x`, `y`: 기기 해상도와 무관하도록 `0.0` 이상 `1.0` 이하로 정규화합니다.
- `t_ms`: 그리기 시작 시점을 0으로 둔 경과 시간입니다.
- 각 stroke 안에서 `t_ms`는 이전 point보다 작아질 수 없습니다.
- `duration_ms`: 그리기 시작부터 완료까지 걸린 전체 시간입니다.
- 백엔드는 `duration_ms`를 그대로 보관하고 기존 리포트 호환을 위해 분 단위 값도 자동 저장합니다.

### 필압 규칙

- 실제 필압을 측정한 stroke는 `pressure_source: "measured"`로 보내고 모든 point에 `pressure`를 포함합니다.
- 손가락, 마우스 등 실제 필압을 알 수 없는 stroke는 `pressure_source: "unavailable"`로 보내고 point에서 `pressure`를 생략합니다.
- 화면 표시용 기본값 `0.5`를 측정 필압으로 전송하면 안 됩니다.
- 화면 표시용 선 굵기는 `brush_width_px`로 별도 전송할 수 있습니다.
- `unavailable`인데 pressure가 들어오거나, `measured`인데 일부 pressure가 빠지면 API가 422로 거절합니다.

`PointerEvent.pressure`는 필압을 지원하지 않는 입력에서 `0.5`로 나타날 수 있으므로,
그 값을 그대로 실측값으로 판단하지 않습니다. 필압 지원 여부를 확신할 수 없으면
`unavailable`을 사용합니다.

## 프론트 요청 예시

```ts
export type DrawingPoint = {
  x: number;
  y: number;
  t_ms: number;
  pressure?: number;
};

export type DrawingStroke = {
  stroke_id?: string;
  pointer_type: "pen" | "touch" | "mouse" | "unknown";
  pressure_source: "measured" | "unavailable";
  brush_width_px?: number;
  points: DrawingPoint[];
};

export type CanvasDrawingData = {
  schema_version: 1;
  canvas: { width: number; height: number };
  duration_ms: number;
  strokes: DrawingStroke[];
};

export const uploadCanvasDrawing = async (
  testId: number,
  file: File,
  drawingData: CanvasDrawingData,
) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append(
    "drawing_data",
    new Blob([JSON.stringify(drawingData)], { type: "application/json" }),
    "drawing.json",
  );

  const response = await axiosInstance.post(
    `/tests/${testId}/drawing`,
    formData,
    { timeout: 60_000 },
  );
  return response.data;
};
```

브라우저가 `multipart/form-data`의 boundary를 자동 생성해야 하므로 명시적인
`Content-Type` 헤더는 넣지 않습니다.

`drawing_data`는 일반 문자열 파트가 아니라 반드시 파일 파트로 보내야 합니다.
일반 문자열 파트는 웹 서버의 multipart 필드 크기 제한에 걸릴 수 있습니다.

## 성공 응답

```json
{
  "test_id": 123,
  "drawing_id": 45,
  "filename": "drawing.png",
  "saved_path": "uploads/htp/original/test_123_canvas_....png",
  "input_type": "canvas",
  "test_status": "image_uploaded",
  "pdi_status": "not_started",
  "next_action": "analyze_image",
  "duration_ms": 125430,
  "drawing_time_minutes": 2,
  "stroke_count": 2,
  "point_count": 4,
  "pressure_point_count": 2,
  "pressure_available": true,
  "message": "직접 그린 그림과 그리기 데이터가 저장되었습니다."
}
```

성공 후에는 기존과 동일하게 `POST /tests/{test_id}/analyze`를 호출합니다.

### 최신 프론트 `dev` 브랜치에서 필요한 화면 분기

현재 `TestLoadingStep.tsx`는 분석 성공 후 항상 `/test-time-input-step`으로 이동합니다.
직접 그리기는 `duration_ms`를 백엔드에 함께 저장하므로 시간을 다시 입력받지 않습니다.

- 카메라/앨범: 기존처럼 `/test-time-input-step`으로 이동
- 앱에서 직접 그리기: `/test-question-intro-step`으로 바로 이동

직접 그리기 업로드 성공 시 라우터 state 등에 `drawingSource: "canvas"`를 전달하고,
분석 성공 시 이 값으로 다음 화면을 분기하면 됩니다. 캔버스 흐름에서는
`POST /tests/{test_id}/pdi/time`을 다시 호출하지 않습니다.

## 오류 응답

- `404`: 로그인 사용자의 검사 ID가 아님
- `409`: 분석/PDI/리포트가 이미 진행되어 그림을 교체할 수 없음
- `413`: 이미지 또는 그리기 데이터가 허용 크기를 초과함
- `415`: PNG/JPEG/WEBP가 아닌 파일
- `422`: 좌표, 시간, 필압 또는 JSON 형식이 잘못됨

오류의 `detail.code`는 프론트 로그 및 분기 처리에 사용할 수 있습니다.

## 백엔드 배포 시 1회 실행

신규 `htp_canvas_drawings` 테이블을 생성해야 합니다.

```bash
python scripts/create_tables.py
```
