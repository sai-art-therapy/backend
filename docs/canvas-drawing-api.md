# 캔버스 직접 그리기 API 연동 명세

기존 카메라/앨범 업로드 API인 `POST /tests/{test_id}/image`는 그대로 사용합니다.
앱에서 직접 그린 그림만 아래 신규 API로 전송합니다.

- 테스트 서버: `https://gdam-test.duckdns.org`
- Swagger: `https://gdam-test.duckdns.org/docs`
- 프론트 확인 기준: `sai-art-therapy/frontend`의 `dev` 브랜치

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

전체 multipart 요청은 Nginx 기준 최대 30MB입니다. 이미지 자체는 최대 10MB이며
이미지 픽셀 수는 최대 25,000,000입니다.

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
- 좌표 계산은 `(event.clientX - rect.left) / rect.width`,
  `(event.clientY - rect.top) / rect.height`를 사용하고 마지막에 `0~1`로 clamp합니다.
- `t_ms`: 그리기 시작 시점을 0으로 둔 경과 시간입니다.
- 각 stroke 안에서 `t_ms`는 이전 point보다 작아질 수 없습니다.
- `duration_ms`: 그리기 시작부터 완료까지 걸린 전체 시간입니다.
- 시간은 시스템 시계 변경의 영향을 받지 않도록 `performance.now()`로 측정합니다.
- 첫 번째 `pointerdown`을 시작 시점으로 잡고 제출 직전까지 측정합니다. 중간에 멈춘
  시간과 실행 취소/전체 지우기에 사용한 시간도 포함하며 타이머를 다시 시작하지 않습니다.
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

프론트 판정 기준은 아래처럼 보수적으로 적용합니다.

- `mouse`: 항상 `unavailable`
- `touch`: OS/네이티브 계층에서 실제 압력 지원을 명확히 확인한 경우가 아니면
  `unavailable`
- `pen`: 접촉 중 수집한 pressure에서 실제 변화가 확인되는 경우만 `measured`
- 접촉 중 값이 계속 `0.5`뿐이거나 판단이 애매하면 `unavailable`로 바꾸고 해당
  stroke의 모든 point에서 `pressure` 키를 제거
- `pointerup`에서 나오는 `0`은 필압 지원 증거로 사용하지 않음

화면에 그릴 때는 필압을 알 수 없는 입력에도 UI용 기본 선 굵기를 사용할 수 있지만,
그 기본값을 point의 `pressure`로 저장하면 안 됩니다.

### 데이터 제한

| 항목 | 제한 |
| --- | --- |
| `schema_version` | 현재 `1`만 허용 |
| 캔버스 너비/높이 | 각각 `1~10,000` 정수 |
| `duration_ms` | `1~86,400,000` |
| stroke 개수 | `1~10,000` |
| point 개수 | stroke마다 최소 1개, 전체 최대 250,000개 |
| `stroke_id` | 선택값, 최대 100자 |
| `brush_width_px` | 선택값, `0` 초과 `200` 이하 |

브라우저 성능과 payload 크기를 위해 move point는 최대 약 60Hz로 샘플링하는 것을
권장합니다. 30분 연속 입력도 약 108,000 point이므로 서버 한도 안에 들어옵니다.

## 캔버스 구현 규칙 (v1 결정사항)

- Pointer Events(`pointerdown/move/up/cancel`)를 사용합니다.
- 캔버스에 `touch-action: none`을 적용하고 `pointerdown`에서
  `setPointerCapture(pointerId)`를 호출합니다.
- 멀티터치로 점이 섞이지 않도록 primary pointer 하나만 기록합니다.
- point/stroke 원본은 `useRef`에 보관하고 매 point마다 React state를 갱신하지 않습니다.
- v1 도구는 **펜, stroke 단위 실행 취소, 전체 지우기**까지만 구현합니다.
- 자유형 픽셀 지우개는 v1에서 구현하지 않습니다. 현재 백엔드 schema에는 지우개
  동작을 표현할 `tool/action` 필드가 없어 화면 결과와 원본 stroke 데이터가 달라질 수
  있기 때문입니다.
- 실행 취소/전체 지우기 후 제출할 때는 화면에 남은 최종 stroke만 전송합니다.
- stroke가 하나도 없으면 제출 버튼을 비활성화합니다.
- 제출 중에는 버튼과 뒤로가기를 막아 중복 업로드를 방지합니다.

### 이미지 내보내기

- PNG를 우선 사용합니다.
- 투명 배경 그대로 내보내지 말고 **흰 배경 위에 그림만** 합성해서 내보냅니다.
- 버튼, 툴바 등 UI는 이미지에 포함하지 않습니다.
- 표시용 CSS 크기와 실제 canvas bitmap 크기가 다를 수 있습니다. payload의
  `canvas.width`, `canvas.height`에는 export PNG와 같은 실제 bitmap 크기를 넣습니다.
  좌표는 CSS 크기나 device pixel ratio와 무관하게 계속 `0~1`로 보냅니다.

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

export type CanvasDrawingUploadResponse = {
  test_id: number;
  drawing_id: number;
  filename: string;
  saved_path: string;
  input_type: "canvas";
  test_status: string;
  pdi_status: string;
  next_action: "analyze_image";
  duration_ms: number;
  drawing_time_minutes: number;
  stroke_count: number;
  point_count: number;
  pressure_point_count: number;
  pressure_available: boolean;
  message: string;
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

  const response = await axiosInstance.post<CanvasDrawingUploadResponse>(
    `/tests/${testId}/drawing`,
    formData,
    {
      timeout: 60_000,
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return response.data;
};
```

현재 프론트의 `axiosInstance.ts`는 공통 기본 헤더가
`Content-Type: application/json`입니다. 따라서 이 요청에서는 기존
`uploadTestImage`와 동일하게 `multipart/form-data`로 덮어써야 합니다. boundary 문자열은
직접 만들지 않고 Axios/브라우저가 생성하도록 둡니다.

`drawing_data`는 일반 문자열 파트가 아니라 반드시 파일 파트로 보내야 합니다.
일반 문자열 파트는 웹 서버의 multipart 필드 크기 제한에 걸릴 수 있습니다.

`duration_ms`와 `t_ms`는 정수로 보내야 하므로 `Math.round()`를 사용하고,
`duration_ms`는 아주 짧은 입력에서도 `Math.max(1, ...)`로 최소 1을 보장합니다.

PNG 생성은 원본 캔버스를 덮어쓰지 않고 별도 export canvas에 흰 배경을 먼저 칠한 뒤
원본을 합성하는 방식이 안전합니다.

```ts
const exportCanvas = document.createElement("canvas");
exportCanvas.width = canvas.width;
exportCanvas.height = canvas.height;
const exportCtx = exportCanvas.getContext("2d")!;
exportCtx.fillStyle = "#ffffff";
exportCtx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
exportCtx.drawImage(canvas, 0, 0);

const blob = await new Promise<Blob>((resolve, reject) => {
  exportCanvas.toBlob(
    (value) => (value ? resolve(value) : reject(new Error("PNG 생성 실패"))),
    "image/png",
  );
});
const pngFile = new File([blob], "drawing.png", { type: "image/png" });
```

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

## 최신 프론트 `dev` 브랜치 적용 위치

확인 시점의 프론트에는 직접 그리기 카드만 있고 클릭 동작, 캔버스 화면, 라우트,
API 타입이 아직 없습니다. 다음 파일을 함께 변경해야 합니다.

| 파일 | 필요한 변경 |
| --- | --- |
| `src/types/test.type.ts` | 위 payload/stroke/point 타입과 `CanvasDrawingUploadResponse` 추가 |
| `src/apis/test/test.ts` | `uploadCanvasDrawing()` 추가. 응답을 `string`이 아닌 객체 타입으로 지정 |
| `src/pages/test/TestThirdStep.tsx` | `앱에서 그림 그리기` 카드 클릭 시 `testId`, `childId`를 가지고 새 화면으로 이동 |
| 신규 `src/pages/test/TestDrawingStep.tsx` | 캔버스 입력, 실행 취소/전체 지우기, PNG+JSON 생성, 업로드 구현 |
| `src/routes/index.tsx` | 예: `/test-drawing-step` 라우트 등록 |
| `src/pages/test/TestLoadingStep.tsx` | `drawingSource`에 따라 분석 완료 후 시간 입력 화면을 건너뛰도록 분기 |

직접 그리기 업로드 성공 후에는 아래 state를 넘겨 분석 화면으로 이동합니다.

```ts
navigate("/test-loading-step", {
  state: {
    testId,
    childId,
    drawingSource: "canvas",
    imageFile: pngFile,
    imageUrl: URL.createObjectURL(pngFile),
  },
});
```

`saved_path`는 서버 내부 저장 경로이므로 브라우저 이미지 URL로 사용하지 않습니다.
미리보기와 다음 화면에는 위에서 만든 `pngFile`/object URL을 전달합니다. 기존 사진 경로와
동일하게 새로 만든 PNG를 `user_uploaded_image` sessionStorage에도 저장해두면 새로고침 후
결과 화면 fallback 동작을 유지할 수 있습니다. 저장 용량 초과 시에는 업로드 자체를
실패시키지 않고 경고 로그만 남깁니다.

사진/앨범 경로에는 기존 동작을 유지하고 `drawingSource: "image"`를 명시하거나 값을
생략할 수 있습니다.

### 분석 후 화면 분기

현재 `TestLoadingStep.tsx`는 분석 성공 후 항상 `/test-time-input-step`으로 이동합니다.
직접 그리기는 `duration_ms`를 백엔드에 함께 저장하므로 시간을 다시 입력받지 않습니다.

- 카메라/앨범: 기존처럼 `/test-time-input-step`으로 이동
- 앱에서 직접 그리기: `/test-question-intro-step`으로 바로 이동

직접 그리기 업로드 성공 시 라우터 state 등에 `drawingSource: "canvas"`를 전달하고,
분석 성공 시 이 값으로 다음 화면을 분기하면 됩니다. 캔버스 흐름에서는
`POST /tests/{test_id}/pdi/time`을 다시 호출하지 않습니다.

```ts
const drawingSource = location.state?.drawingSource;
const nextPath =
  drawingSource === "canvas"
    ? "/test-question-intro-step"
    : "/test-time-input-step";
```

두 경로 모두 `testId`, `childId`, `childName`, `reportId`, `imageFile`, `imageUrl` state를
그대로 전달합니다.

### React StrictMode 중복 분석 방지

현재 `src/main.tsx`가 `StrictMode`를 사용하고, `TestLoadingStep.tsx`는 mount effect에서
즉시 분석 API를 호출합니다. 개발 환경에서 effect가 재실행되어 분석 요청이 두 번 갈 수
있으므로 `useRef` guard를 추가합니다.

```ts
const hasStartedAnalyzeRef = useRef(false);

useEffect(() => {
  if (!testId || hasStartedAnalyzeRef.current) return;
  hasStartedAnalyzeRef.current = true;
  startAnalyze(Number(testId));
}, [testId]);
```

검사 ID 누락 시 기존 안내/이동 처리는 guard보다 먼저 유지합니다.

`TestQuestionIntroStep.tsx`도 mount effect에서 `startPdiQuestions()`를 호출하므로 같은 방식의
`useRef` guard를 추가해야 합니다. 그렇지 않으면 개발 환경에서 PDI 시작 요청 역시 중복될
수 있습니다.

### 기존 응답 타입 정리

현재 `uploadTestImage()`와 `analyzeTest()`의 Axios 응답 제네릭이 `string`으로 되어 있지만
백엔드는 객체를 반환합니다. 캔버스 작업과 함께 실제 응답 객체 타입으로 고치고
`as any` 캐스팅을 제거하는 것을 권장합니다. 특히 분석 응답에는 이 단계의 `report_id`가
없습니다. `reportId`를 분석 응답에서 꺼내는 로직에 의존하지 말고, 최종 리포트 생성/목록
조회 단계에서 받은 ID를 사용합니다.

## 오류 응답

- `400`: 분석할 이미지가 없거나 이후 분석 요청 형식이 잘못됨
- `401`: 토큰 만료. 공용 Axios interceptor가 로그인 화면으로 이동
- `404`: 로그인 사용자의 검사 ID가 아님
- `409`: 분석/PDI/리포트가 이미 진행되어 그림을 교체할 수 없음
- `413`: 이미지 또는 그리기 데이터가 허용 크기를 초과함
- `415`: PNG/JPEG/WEBP가 아닌 파일
- `422`: 좌표, 시간, 필압 또는 JSON 형식이 잘못됨

오류의 `detail.code`는 프론트 로그 및 분기 처리에 사용할 수 있습니다.
표시 메시지는 `error.response?.data?.detail?.message`를 우선 사용하고, 문자열 detail인
기존 API도 있으므로 `error.response?.data?.detail`도 fallback으로 처리합니다.

`409 drawing_not_replaceable`이면 같은 `testId`로 계속 재시도하지 말고 검사 시작
화면으로 안내합니다. 업로드 재시도는 검사 상태가 `created`, `image_uploaded`,
`analysis_failed`일 때만 허용됩니다.

## 완료 조건 체크리스트

- [ ] 펜/손가락/마우스로 선을 그릴 수 있고 모바일 스크롤과 충돌하지 않음
- [ ] primary pointer 하나만 기록하며 pointer cancel 후에도 입력이 잠기지 않음
- [ ] 좌표가 모두 `0~1`, stroke 내부 시간이 오름차순이고 전체 시간 이내임
- [ ] 필압 미지원 입력의 point JSON에 `pressure` 키가 존재하지 않음
- [ ] 필압 지원 펜은 모든 point에 실제 `pressure`가 있음
- [ ] 실행 취소/전체 지우기 후 화면과 전송 stroke가 일치함
- [ ] 투명 배경이 아닌 흰 배경 PNG가 생성됨
- [ ] `drawing_data`가 JSON 문자열이 아니라 이름이 있는 Blob 파일 파트로 전송됨
- [ ] `saved_path`를 이미지 URL로 쓰지 않고 로컬 PNG preview를 전달함
- [ ] 제출 연타와 StrictMode로 인한 업로드/분석 중복 호출이 없음
- [ ] PDI 시작 요청도 StrictMode에서 한 번만 호출됨
- [ ] 직접 그리기만 시간 입력 화면을 건너뛰고 사진/앨범 흐름은 그대로임
- [ ] 422/409/413/네트워크 오류 후 사용자가 재시도하거나 빠져나갈 수 있음
- [ ] 실제 배포 환경에서 로그인 → 검사 생성 → 직접 그리기 → 분석 → PDI까지 확인함

## 백엔드 배포 시 1회 실행

신규 `htp_canvas_drawings` 테이블을 생성해야 합니다.

```bash
python scripts/create_tables.py
```

Nginx를 앞단에 사용하는 서버는 이미지 10MB, JSON 15MB, multipart overhead를
수용하도록 HTTPS server block에 아래 설정이 필요합니다.

```nginx
client_max_body_size 30M;
client_body_timeout 120s;
```

설정 변경 후 `nginx -t`로 검증하고 Nginx를 reload합니다.
