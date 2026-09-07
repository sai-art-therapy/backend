# GDAM Backend Docker 실행

이 구성은 로컬 재현성과 CI 컨테이너 런타임 검증을 위한 것입니다. 현재 EC2의
systemd 배포를 자동으로 변경하지 않습니다.

이미지는 CPU 서버 실행을 기준으로 PyTorch와 torchvision의 CPU wheel을 사용해
불필요한 CUDA 라이브러리를 포함하지 않습니다.

## 준비

1. Docker Desktop 또는 Docker Engine과 Compose v2를 설치합니다.
2. 환경 파일을 준비합니다.

   ```bash
   cp .env.docker.example .env.docker
   ```

3. `.env.docker`의 `OPENAI_API_KEY`, `POSTGRES_PASSWORD`,
   `JWT_SECRET_KEY`를 실제 로컬 값으로 변경합니다.
4. 모델 파일을 아래 경로에 둡니다.

   ```plain text
   ml_models/yolo/house_best.pt
   ml_models/yolo/tree_best.pt
   ml_models/yolo/person_best.pt
   ```

## 실행과 확인

```bash
docker compose --env-file .env.docker up --build
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
```

`live`는 프로세스 생존을, `ready`는 PostgreSQL·YOLO 모델·업로드 저장소를
확인합니다. 모델 파일이 없으면 컨테이너는 실행되어도 `ready`가 실패하는 것이
정상입니다.

Swagger는 `http://127.0.0.1:8000/docs`에서 확인합니다.

## CI 자동 검증

Pull Request와 `main` 변경 시 GitHub Actions에서 다음 과정을 매번 새 환경에서
수행합니다.

1. 단위 테스트 통과
2. CPU 전용 Backend 이미지 빌드 및 로컬 Docker 엔진에 적재
3. Compose 설정 유효성 검사
4. Backend와 PostgreSQL 컨테이너 기동
5. Backend가 UID 10001 비루트 사용자로 실행되는지 확인
6. PostgreSQL 연결과 `/health/live` 응답 확인
7. 모델 파일이 없는 CI 환경에서 `/health/ready`가 원인을 구분해 503을 반환하는지 확인
8. Backend 컨테이너 재시작 후 생존 확인
9. 컨테이너와 CI 전용 볼륨 정리

CI는 실제 YOLO 모델 파일과 외부 API Secret을 사용하지 않습니다. 모델 추론과
로그인·분석·리포트 전체 E2E는 별도 테스트 환경에서 수행해야 합니다.

## 데이터 보존

- PostgreSQL: `postgres_data`
- 업로드 이미지: `uploads_data`
- ChromaDB: `chroma_data`
- YOLO 모델: 호스트의 `./ml_models`를 읽기 전용으로 연결

`docker compose down`은 컨테이너만 내리고 볼륨을 보존합니다.
`docker compose down --volumes`는 로컬 DB와 업로드 데이터를 삭제하므로 필요한
경우에만 실행합니다.

## 운영 전환 전 확인

- 현재 Nginx·systemd 배포를 롤백 수단으로 유지
- EC2의 `uploads/`, PostgreSQL, ChromaDB 백업과 복구 테스트
- Nginx가 전달하는 프록시 주소만 신뢰하도록 Uvicorn 설정
- CPU 추론 시간과 이미지 크기 측정
- 운영 Secret은 GitHub Environment 또는 EC2 전용 파일로 주입

Docker 운영 전환은 로그인 → 업로드 → 분석 → PDI → 리포트 전체 E2E가 통과한 뒤
별도 PR과 배포 절차로 진행합니다.
