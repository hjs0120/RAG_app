# RAG_app V4 — REST API 기반 서버 시스템 확장 단계별 개발 계획

## 개요

- **기반 문서**: `goal_v4.md`
- **목표**: 로컬 RAG를 REST API 기반 서버 시스템으로 확장
- **핵심 방향**: FastAPI 서버 + 서버 서비스 탭 + Web Client 채팅 인터페이스

---

## UI 프레임워크

- **PySide6** (Qt for Python 6) 기반 — V3 유지
- **서버 서비스 탭** 신규 추가 → 메인(Default) 탭
- 탭 순서: [서버 서비스] → [사용] → [DB 생성]

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024-7-92.pdf`
- **기존 인덱스**: `output/rules.index`, `output/rules_meta.jsonl`
- **API 테스트**: Web Client 또는 `curl`/Postman으로 POST /api/ask 호출

---

## Python 가상환경

- **권장 환경**: Conda 가상환경 `PySide6` (V3와 동일)
- **Python 경로 예시**: `D:\001. Anaconda\PySide6\python.exe`
- **V4 추가 의존성**: `uvicorn`, `fastapi`

### 의존성 설치

```powershell
pip install uvicorn fastapi
```

### 서버 실행 (Phase 1 완료 후)

```powershell
# 방법 1: Uvicorn 직접 실행
uvicorn src.server.api_server:app --host 127.0.0.1 --port 8081

# 방법 2: Admin UI에서 [서버 서비스 탭] → [서버 시작] 클릭
python -m src.app
```

### API 테스트 (Phase 1 완료 후)

```powershell
# curl 예시
curl -X POST http://127.0.0.1:8081/api/ask -H "Content-Type: application/json" -d "{\"query\": \"제101조 내용은?\", \"top_k\": 5}"
```

### 주요 의존성 (V4 기준)

- **PySide6** — Admin UI
- **FastAPI** — API 서버
- **Uvicorn** — ASGI 서버
- **PyMuPDF** — PDF 추출
- **faiss** — 벡터 검색
- **sentence-transformers** — BGE 임베딩

---

## Phase 진도 요약

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | FastAPI 앱 및 POST /api/ask 엔드포인트, core/rag 연동 | [x] |
| 2 | Uvicorn 서브프로세스 제어 (server_manager.py) | [x] |
| 3 | 서버 서비스 탭 UI (설정/버튼/LED/로그) | [x] |
| 3-1 | 서버 시작 시 모델 사전 로드 (bge-m3, FAISS, Ollama) | [x] |
| 3-2 | 동시 요청 개수 제한 (큐 대기·순차 처리·거절 안내) | [x] |
| 4 | Web Client (채팅 UI, fetch API, 출처 카드 뷰) | [x] |
| 5 | PDF 이미지 서빙 및 웹 뷰어 (2분할, 출처 클릭 시 이미지 표시) | [x] |
| 6 | main_window 탭 통합 및 통합 테스트 | [x] |
| 7 | V4 통합 검증 및 문서화 | [x] |

각 Phase의 **진도 체크** 항목을 검증 후 `[ ]` → `[x]`로 바꾸고, 위 표의 완료도 필요 시 갱신한다.

**각 Phase 완료 시** 해당 Phase 끝의 **커밋 메시지**를 참고하여 커밋을 정리한다.

---

## Phase 1: FastAPI 앱 및 POST /api/ask 엔드포인트

### 목표

FastAPI 앱을 정의하고, POST /api/ask 엔드포인트를 구현한다. 기존 core/rag 모듈을 서버 프로세스 내에서 로드하여 RAG 질의응답을 제공한다.

### 작업 내용

1. **`src/server/` 디렉터리 신규 생성**

   - `src/server/__init__.py` (빈 파일 또는 패키지 초기화)

2. **`src/server/api_server.py` 신규 생성**

   - FastAPI 앱 인스턴스 생성
   - `POST /api/ask` 엔드포인트 구현:
     - Request body: `{"query": str, "top_k": int (optional, default 5)}`
     - Response: `{"status": "success"|"error", "answer": str, "sources": list}`
     - core/rag 모듈(rag_pipeline, db_manager) 임포트 후 질의 처리
     - 예외 처리: status="error", answer에 에러 메시지
   - CORS 미들웨어 설정 (Web Client 도메인 허용)
   - `GET /health` 엔드포인트 (200 OK 반환, 선택)

3. **RAG 연동**

   - `rag_pipeline.run(query, top_k)` 또는 기존 파이프라인 인터페이스 호출
   - 반환값을 Response 스펙에 맞게 변환 (answer, sources)

4. **정적 파일 서빙 (선택, Phase 4에서 활용)**

   - `app.mount("/web_client", StaticFiles(directory="web_client"), name="web_client")`
   - 또는 Phase 4에서 추가

### Phase 1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/server/__init__.py` (신규) | 패키지 초기화 |
| `src/server/api_server.py` (신규) | FastAPI 앱, /api/ask 엔드포인트 |
| `src/rag/rag_pipeline.py` | RAG 파이프라인 (연동) |
| `src/db/db_manager.py` | DB 로드 (연동) |

### 수동 검증 방법

1. `uvicorn src.server.api_server:app --host 127.0.0.1 --port 8081` 실행
2. `curl -X POST http://127.0.0.1:8081/api/ask -H "Content-Type: application/json" -d "{\"query\": \"제101조\", \"top_k\": 5}"` 호출
3. Response에 `status`, `answer`, `sources` 필드 포함 여부 확인
4. 답변 및 sources 내용이 V3 [사용 탭] 결과와 유사한지 확인

### 진도 체크

- [x] `src/server/api_server.py` FastAPI 앱 생성
- [x] POST /api/ask 엔드포인트 구현
- [x] core/rag 모듈 연동 (rag_pipeline 호출)
- [x] Response 스펙 (answer, sources) 준수
- [x] CORS 설정 (필요 시)
- [x] 수동 검증 완료

### Phase 1 완료 시 커밋

```
feat(server): Phase 1 — FastAPI 앱 및 POST /api/ask 엔드포인트

- api_server.py 신규, core/rag 연동
- CORS 설정
```

---

## Phase 2: Uvicorn 서브프로세스 제어 (server_manager.py)

### 목표

Admin UI에서 서버를 시작/중단할 수 있도록 Uvicorn을 서브프로세스로 실행·제어하는 모듈을 작성한다. 로그를 파이프하여 실시간 출력이 가능하도록 한다.

### 작업 내용

1. **`src/server/server_manager.py` 신규 생성**

   - `ServerManager` 클래스:
     - `start(host: str, port: int) -> bool` — Uvicorn 서브프로세스 시작
     - `stop() -> bool` — 서브프로세스 종료
     - `is_running() -> bool` — 실행 상태 반환
     - `get_log_callback() -> Callable` — 로그 수신 콜백 등록
   - `subprocess.Popen`으로 `uvicorn src.server.api_server:app --host HOST --port PORT` 실행
   - stdout/stderr 리다이렉션 또는 파이프 → 로그 콜백으로 전달
   - 프로세스 종료 시 정리 (SIGTERM 또는 SIGINT)

2. **로그 포맷**

   - Uvicorn 기본 로그 포맷 유지
   - API 요청 로그 (`POST /api/ask - 200`) 포함되도록 설정

3. **에러 처리**

   - 포트 이미 사용 중 등 시작 실패 시 에러 반환
   - 비정상 종료 시 상태 정리

### Phase 2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/server/server_manager.py` (신규) | Uvicorn 서브프로세스 제어 |
| `src/server/api_server.py` | 참조 (엔트리포인트) |

### 수동 검증 방법

1. `ServerManager` 인스턴스 생성 후 `start("127.0.0.1", 8081)` 호출
2. `is_running()` → True 반환 확인
3. `curl`로 /api/ask 호출 → 정상 응답 확인
4. `stop()` 호출 → 프로세스 종료 확인
5. 로그 콜백으로 로그 수신 확인

### 진도 체크

- [x] `ServerManager` 클래스 구현
- [x] `start()`, `stop()`, `is_running()` 동작
- [x] 로그 파이프/콜백 구현
- [x] 포트 충돌 등 에러 처리
- [x] 수동 검증 완료

### Phase 2 완료 시 커밋

```
feat(server): Phase 2 — Uvicorn 서브프로세스 제어

- server_manager.py 신규
```

---

## Phase 3: 서버 서비스 탭 UI

### 목표

Admin UI에 [서버 서비스 탭]을 추가한다. 호스트·포트 설정, [서버 시작]/[서버 중단] 버튼, 상태 LED 인디케이터, 실시간 로그 출력창을 구현한다.

### 작업 내용

1. **`src/ui/tabs/tab_server_service.py` 신규 생성**

   - **서버 설정 영역**
     - QLineEdit: 호스트 (기본값 127.0.0.1)
     - QSpinBox: 포트 (기본값 8081)
   - **서버 제어 영역**
     - QPushButton: [서버 시작], [서버 중단]
     - QLabel 또는 커스텀 위젯: 상태 LED 인디케이터 (녹색=실행, 회색=중지, 빨강=에러)
     - ServerManager와 연동
   - **실시간 로그 영역**
     - QPlainTextEdit (읽기 전용) — 로그 출력
     - ServerManager의 로그 콜백에 연결
     - 스크롤 자동 하단 유지

2. **상태 표시**

   - 서버 시작 시 [서버 시작] 비활성화, [서버 중단] 활성화
   - 서버 중단 시 [서버 시작] 활성화, [서버 중단] 비활성화
   - LED: 녹색(실행), 회색(중지), 빨강(에러)

3. **main_window.py 수정 준비**

   - Phase 5에서 탭 추가 및 순서 설정
   - Phase 3에서는 tab_server_service.py만 구현

### Phase 3에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_server_service.py` (신규) | 서버 서비스 탭 UI |
| `src/server/server_manager.py` | ServerManager 연동 |
| `src/ui/main_window.py` | Phase 5에서 수정 |

### 수동 검증 방법

1. `tab_server_service`를 임시로 main_window에 추가하여 실행
2. 호스트/포트 입력 후 [서버 시작] 클릭 → 서버 기동 확인
3. LED가 녹색으로 변경, 로그에 `Uvicorn running` 등 출력 확인
4. [서버 중단] 클릭 → 서버 종료, LED 회색 확인
5. curl로 /api/ask 호출 시 로그에 요청 기록 출력 확인

### 진도 체크

- [x] `tab_server_service.py` 생성
- [x] 호스트/포트 설정 UI
- [x] [서버 시작]/[서버 중단] 버튼 연동
- [x] LED 인디케이터 구현
- [x] 실시간 로그 출력창 구현
- [x] ServerManager 연동
- [x] 수동 검증 완료

### Phase 3 완료 시 커밋

```
feat(ui): Phase 3 — 서버 서비스 탭 UI

- tab_server_service.py 신규
- ServerManager 연동
```

---

## Phase 3-1: 서버 시작 시 모델 사전 로드

### 목표

[서버 시작] 클릭 시 API 서버뿐 아니라 bge-m3, FAISS 인덱스, Ollama 모델까지 사전 로드한다. 첫 /api/ask 요청 시 대기 시간을 없애고, 로그에 모델 로드 진행 상황을 표시한다.

### 작업 내용

1. **`src/server/api_server.py` 수정**

   - FastAPI `lifespan` 훅 추가
   - 서버 시작 시 순차 실행:
     1. bge-m3 임베딩 모델 로드 (`preload_model`)
     2. FAISS 인덱스 + RAG 파이프라인 로드 (`_get_pipeline`)
     3. Ollama LLM 모델 로드 (`OllamaClient.load_model`)
   - 각 단계별 로그 출력:
     - `INFO: bge-m3 임베딩 모델 로딩 중...` / `bge-m3 로드 완료`
     - `INFO: FAISS 인덱스 로딩 중...` / `FAISS 인덱스 로드 완료`
     - `INFO: Ollama 모델 로딩 중...` / `Ollama 모델 로드 완료`
   - 로드 실패 시 WARNING 로그만 출력, 첫 요청 시 재시도 (기존 lazy 로드 유지)

2. **로그 표시**

   - lifespan 내부 `print` → 서브프로세스 stdout → ServerManager 파이프 → 탭 로그창
   - 기존 시간 정보 `[HH:MM:SS]` 형식 그대로 적용

3. **bge-m3 로딩 진행도 로그 억제**

   - `embedding_bge.py` 모듈 로드 시 `TQDM_DISABLE=1`, `TRANSFORMERS_VERBOSITY=error` 환경 변수 설정
   - "Loading weights" tqdm 진행 바 출력 억제 → `bge-m3 임베딩 모델 로딩 중...` / `bge-m3 로드 완료` 로그만 표시

4. **창 닫기 시 서버 종료 확인 팝업**

   - `main_window.py`에 `closeEvent` 오버라이드
   - 서버 실행 중 X 버튼으로 창 닫기 시 → "서버가 실행중입니다. 서버를 종료할까요?" 팝업
   - 예 → 서버 중단 후 창 닫기 / 아니오 → 창 유지

### Phase 3-1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/server/api_server.py` | lifespan, 모델 사전 로드 |
| `src/core/embedding_bge.py` | TQDM/transformers 로그 억제 |
| `src/ui/main_window.py` | closeEvent, 서버 종료 확인 팝업 |

### 수동 검증 방법

1. Admin UI [서버 서비스] 탭에서 [서버 시작] 클릭
2. 로그창에서 `bge-m3 로딩 중...` → `로드 완료` 순서 확인 (Loading weights 진행 바 미출력)
3. `FAISS 인덱스 로딩 중...` → `로드 완료` 확인
4. `Ollama 모델 로딩 중...` → `로드 완료` 확인
5. Uvicorn `Application startup complete` 이후 첫 /api/ask 요청이 지연 없이 응답하는지 확인
6. 서버 실행 중 메인 윈도우 X 버튼 클릭 → "서버를 종료할까요?" 팝업 확인, 예/아니오 동작 검증

### 진도 체크

- [x] api_server lifespan 추가
- [x] bge-m3 사전 로드 및 로그
- [x] bge-m3 로딩 진행도 로그 억제 (TQDM_DISABLE, TRANSFORMERS_VERBOSITY)
- [x] FAISS 인덱스 사전 로드 및 로그
- [x] Ollama 모델 사전 로드 및 로그
- [x] 창 닫기 시 서버 종료 확인 팝업
- [x] 수동 검증 완료

### Phase 3-1 완료 시 커밋

```
feat(server): Phase 3-1 — 서버 시작 시 모델 사전 로드

- api_server: lifespan으로 bge-m3, FAISS, Ollama 사전 로드
- 로그에 모델 로드 진행 상황 표시
- embedding_bge: bge-m3 로딩 시 TQDM/transformers 진행 로그 억제
- main_window: 창 닫기 시 서버 실행 중이면 종료 확인 팝업
```

---

## Phase 3-2: 동시 요청 개수 제한 (큐 대기·순차 처리·거절 안내)

### 목표

서버 실행 후 여러 Web Client가 동시에 접속했을 때 최대 동시 요청 개수를 제한한다. 초과 요청은 큐에 최대 N개까지 대기시키고, 큐도 가득 찬 경우에는 즉시 거절·안내한다. 큐에 쌓인 요청은 선입선출(FIFO)로 순차 처리하며, 대기 중인 클라이언트에는 남은 순서·상태를 안내한다.

### 동작 시나리오 예시

- **제한**: 동시 처리 1개, 큐 최대 3개 (총 4개까지 수용 가능)
- **5명의 클라이언트**가 순차적으로 질문을 보낸 경우:
  - 1번 요청: 즉시 처리 시작
  - 2·3·4번 요청: 큐에 대기, "앞에서 온 질문을 먼저 처리 중입니다. 잠시만 기다려주세요" + 남은 처리 순서 안내
  - 5번 요청: 큐 초과 → 즉시 거절, "서버가 혼잡하여 잠시 후에 이용해 주세요" 응답
  - 1번 완료 → 2번 처리 시작 시, 2번 클라이언트는 실제 답변 수신 / 3·4번은 대기 메시지 유지 및 순서 갱신
  - 순차 완료 시마다 대기 클라이언트들에게 남은 순서 안내 (예: "곧 처리됩니다. 대기 순서: 2번째" 등)

### 작업 내용

1. **`src/server/api_server.py` 수정**

   - 설정: `MAX_QUEUE_SIZE` (큐 최대 개수, 기본 3), `MAX_CONCURRENT` (동시 처리 개수, 기본 1)
   - 요청 큐 구조: `asyncio.Queue` 또는 threading 기반 큐
   - 슬롯 관리: 현재 처리 중 개수 + 큐 대기 개수 ≤ `MAX_QUEUE_SIZE` + `MAX_CONCURRENT` 만 수용
   - 초과 요청: 즉시 `status="rejected"`, `answer="서버가 혼잡하여 잠시 후에 이용해 주세요."` 반환

2. **큐 대기 중 클라이언트 응답**

   - 대기 요청: 동기 응답 대신 스트리밍 또는 폴링 방식 중 선택
   - **옵션 A**: SSE(Server-Sent Events)로 상태 업데이트 (대기 중 / 순서 N번째 / 답변 도착)
   - **옵션 B**: 단일 응답에서 `status="queued"`, `queue_position=N`, `message="앞에서 온 질문을 먼저 처리 중입니다. 잠시만 기다려주세요."` 반환 후, 클라이언트가 별도 폴링으로 완료 여부 조회
   - 순차 처리 완료 시 해당 클라이언트에게만 실제 `answer`, `sources` 전달

3. **API 응답 스펙 확장**

   - `status`: `"success"` | `"error"` | `"rejected"` | `"queued"`
   - `queue_position`: (옵션) 대기 중일 때 남은 순서
   - `message`: 거절/대기 안내 문구 (예: "서버가 혼잡하여 잠시 후에 이용해 주세요", "앞에서 온 질문을 먼저 처리 중입니다. 잠시만 기다려주세요. 대기 순서: 2번째")

4. **Web Client 연동 (Phase 4 연계)**

   - `status="rejected"` → 사용자에게 거절 메시지 표시
   - `status="queued"` → 대기 메시지 + 순서 안내 표시, 필요 시 폴링/SSE로 완료 시점까지 갱신
   - `status="success"` → 기존과 동일하게 답변·출처 표시

5. **서버 설정 UI (선택)**

   - `tab_server_service.py`에 큐 크기/동시 처리 수 설정 입력 추가 (기본값으로도 가능)

### Phase 3-2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/server/api_server.py` | 큐 관리, 요청 수 제한, 거절·대기 응답 |
| `web_client/app.js` | status별 UI 처리 (거절/대기/성공) |
| `src/ui/tabs/tab_server_service.py` | (선택) 큐 크기 설정 UI |

### 수동 검증 방법

1. `MAX_QUEUE_SIZE=3`, `MAX_CONCURRENT=1`로 서버 기동
2. 5개의 클라이언트(브라우저 탭 또는 curl)에서 거의 동시에 질문 전송
3. 5번째 요청이 즉시 `status="rejected"` 및 안내 메시지 반환 확인
4. 2·3·4번 요청이 대기 메시지 + 순서 안내를 받는지 확인
5. 1번 완료 → 2번 답변 수신, 3·4번 대기 메시지 갱신 확인
6. 순차 완료 후 모든 대기 요청이 최종 답변을 수신하는지 확인

### 진도 체크

- [x] api_server에 요청 큐 및 슬롯 제한 로직 구현
- [x] 초과 요청 즉시 거절 (`status="rejected"`)
- [x] 큐 대기 요청 순차 처리 (FIFO)
- [x] 대기 중 클라이언트에게 순서·안내 메시지 제공 (blocking 방식, 응답 시점에 답변 전달)
- [x] Admin UI(tab_usage)에서 rejected 처리
- [ ] Web Client에서 rejected 분기 처리 (Phase 4 구현 시 반영)
- [x] 수동 검증 완료 (PySide6 환경에서 5개 동시 요청 시 1개 rejected 확인)

### Phase 3-2 완료 시 커밋

```
feat(server): Phase 3-2 — 동시 요청 개수 제한

- api_server: 요청 큐, 최대 동시 처리 제한
- 초과 시 거절, 대기 시 순서·안내 메시지
- Web Client: rejected/queued/success 처리
```

---

## Phase 4: Web Client (채팅 UI, fetch API, 출처 카드 뷰)

### 목표

브라우저에서 RAG 질의응답을 사용할 수 있는 Web Client를 작성한다. 모던한 채팅 인터페이스, fetch API를 통한 /api/ask 호출, 출처(Source) 확장형 카드 뷰를 구현한다.

### 작업 내용

1. **`web_client/` 디렉터리 신규 생성**

2. **`web_client/index.html` 신규 생성**

   - 채팅 영역: 사용자/봇 메시지 표시 (스크롤 가능)
   - 입력 영역: 텍스트 입력창 + 전송 버튼
   - 출처 영역: 답변 하단에 sources 카드 뷰 (접기/펼치기)
   - 서버 URL 설정: 설정 가능하거나 기본값 `http://127.0.0.1:8081`

3. **`web_client/style.css` 신규 생성**

   - 말풍선 스타일 (사용자: 우측, 봇: 좌측)
   - 출처 카드 뷰 스타일 (structure_path, file_name, page)
   - 로딩 스피너/플레이스홀더
   - 모바일 대응 (선택)

4. **`web_client/app.js` 신규 생성**

   - `async ask(query)` — fetch POST /api/ask 호출
   - 메시지 렌더링: 사용자 메시지, 봇 답변, sources 카드
   - 로딩 표시: 요청 중 플레이스홀더
   - 에러 처리: 네트워크/API 에러 시 사용자 메시지 표시

5. **API 서버 정적 파일 서빙**

   - `api_server.py`에 `app.mount("/web_client", StaticFiles(directory="web_client"), name="web_client")` 추가
   - 또는 `/` 루트에서 `web_client/index.html` 서빙
   - 접근 URL: `http://127.0.0.1:8081/web_client/` 또는 `http://127.0.0.1:8081/`

### Phase 4에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `web_client/index.html` (신규) | 채팅 UI 마크업 |
| `web_client/style.css` (신규) | 스타일 |
| `web_client/app.js` (신규) | fetch API, 메시지 렌더링 |
| `src/server/api_server.py` | 정적 파일 서빙 추가 |

### 수동 검증 방법

1. Admin UI에서 서버 시작 (또는 uvicorn 직접 실행)
2. 브라우저에서 `http://127.0.0.1:8081/web_client/` 접속
3. 질문 입력 후 전송 → 봇 답변 말풍선 표시 확인
4. 출처 카드에 structure_path, file_name, page 표시 확인
5. 로딩 중 스피너/플레이스홀더 표시 확인
6. 서버 중단 후 질문 → 에러 메시지 표시 확인

### 진도 체크

- [x] `web_client/index.html` 채팅 UI
- [x] `web_client/app.js` fetch API 연동
- [x] `web_client/style.css` 스타일
- [x] 출처 카드 뷰 (structure_path, file_name, page)
- [x] 로딩 표시
- [x] 에러 처리 (네트워크/API/Phase 3-2 rejected)
- [x] api_server 정적 파일 서빙
- [ ] 수동 검증 완료

### Phase 4 완료 시 커밋

```
feat(web): Phase 4 — Web Client 채팅 UI

- web_client/index.html, style.css, app.js 신규
- fetch POST /api/ask, 출처 카드 뷰
- api_server 정적 파일 서빙
```

---

## Phase 5: PDF 이미지 서빙 및 웹 뷰어

### 목표

출처(Source)에 해당하는 PDF 페이지를 웹에서 이미지로 볼 수 있도록 한다. 서버는 PDF를 미리 이미지로 변환·저장하고, API 응답에 이미지 URL을 포함하며, Web Client는 좌우 2분할(Split View)에서 출처 클릭 시 우측 뷰어에 해당 페이지 이미지를 표시한다.

### 🛠️ PDF 이미지 서빙 아키텍처 설계

#### 1. 백엔드: PDF 페이지 이미지화 전략

- 서버 실행 시나 DB 생성 시점에 미리 이미지를 만들어 두는 것이 성능상 유리하다.
- **이미지 생성**: PyMuPDF(fitz)로 PDF 각 페이지를 `.png` 또는 `.jpg`로 변환한다.
- **해상도**: 웹에서 글자가 읽힐 정도인 **DPI 150~200** 정도가 적당하다.
- **저장 구조**:
  ```
  /storage/pdf_images/
    └── {doc_id}/
          ├── 1.jpg
          ├── 2.jpg
          └── ...
  ```
- **정적 파일 서빙**: FastAPI에서 `StaticFiles`로 해당 폴더를 노출한다.
  ```python
  from fastapi.staticfiles import StaticFiles
  app.mount("/view/images", StaticFiles(directory="storage/pdf_images"), name="images")
  ```

#### 2. API 응답 데이터 확장

- 기존에는 출처에 page 번호만 보냈다면, 이제는 **해당 페이지의 이미지 URL**을 함께 포함한다.
- **응답 예시**:
  ```json
  {
    "answer": "해당 규정에 따르면...",
    "sources": [
      {
        "doc_id": "rules_2024",
        "page": 45,
        "image_url": "http://api.server.com/view/images/rules_2024/45.jpg",
        "text": "제 3조..."
      }
    ]
  }
  ```

#### 3. 웹 클라이언트 UI 구성 (구현: 팝업 방식으로 확정)

- 채팅 영역은 전체 너비 사용.
- **출처 클릭 시**: 우측 고정 패널 대신 **팝업(모달)**을 띄워 해당 페이지 이미지를 크게 표시.
- **팝업 상단**: 출처 정보(구조 경로 · 파일명 · p.페이지)를 표기하여 이미지에서 해당 출처를 찾기 쉽게 함.
- 닫기: × 버튼, 배경 클릭, Escape 키.

### 🚀 구현 시 고려할 디테일

1. **하이라이트 표시 (Bbox)**  
   페이지만이 아니라 근거 문장에 **노란색 박스(Highlight)**를 넣고 싶다면:
   - **백엔드**: 이미지 URL과 함께 해당 텍스트의 bbox 좌표(V3에서 이미 추출)를 전달한다.
   - **프론트엔드**: 이미지 위에 `position: absolute`인 투명 div를 두고, 좌표만큼 덮어 씌운다.

2. **보안 및 권한**  
   URL로 모든 페이지를 열람하는 것이 부담된다면, FastAPI의 `FileResponse`로 **요청 시점에 인증 토큰을 검사**한 뒤 이미지를 바이너리로 전달하는 방식을 쓸 수 있다.

3. **저장 용량 최적화**  
   PNG보다 **JPG (quality 80)**를 권장한다. 텍스트 위주 문서는 용량이 줄면서도 가독성을 유지한다.

### 개발 로드맵 (Phase 5 세부 작업) — 완료 반영

| 순서 | 구분 | 내용 | 비고 |
|------|------|------|------|
| 1 | Backend | PDF를 이미지로 변환하는 유틸리티 (`pdf_to_images.py`, `scripts/export_pdf_images.py`) | JPG, jpg_quality, DPI 150 |
| 2 | Backend | FastAPI `/view/images` 마운트, API 응답 sources.metadata에 `image_url` 추가 | |
| 3 | Backend | DB 생성 탭: 임베딩 완료 시 `export_pdf_to_images` 자동 호출 (tab_db_create.py) | 띄어쓰기 파일명 대응 |
| 4 | Web | 출처 클릭 시 **팝업**으로 페이지 이미지 표시, **상단에 출처 정보** 표기 | 2분할 → 팝업으로 변경 |

### Phase 5에서 다루는 소스

| 파일/디렉터리 | 내용 |
|---------------|------|
| `src/core/pdf_to_images.py` (신규) | PDF → 이미지 변환 유틸리티 |
| `src/ui/tabs/tab_db_create.py` | 임베딩 완료 시 export_pdf_to_images 호출 |
| `storage/pdf_images/` (또는 `output/pdf_images/`) | doc_id별 페이지 이미지 저장 |
| `src/server/api_server.py` | `/view/images` 마운트, sources 스키마에 `image_url` 추가 |
| `web_client/index.html`, `style.css` | 출처 팝업 모달 (상단 출처 문구 + 이미지) |
| `web_client/app.js` | 출처 클릭 → 팝업 표시, 닫기(×/배경/Esc) |

### 진도 체크

- [x] PDF → 이미지 변환 유틸리티 클래스 (PyMuPDF, DPI 150~200, JPG quality 80) — `src/core/pdf_to_images.py`, `scripts/export_pdf_images.py`
- [x] 저장 경로 `storage/pdf_images/{doc_id}/` 및 정적 서빙 `/view/images`
- [x] API 응답 sources에 `image_url` (metadata.image_url, `/view/images/{doc_id}/{page}.jpg`) 포함
- [x] Web Client: 출처 클릭 시 **팝업**으로 페이지 이미지 표시 (우측 패널 제거)
- [x] 팝업 상단에 출처 정보(구조 경로 · 파일명 · p.페이지) 표기
- [x] DB 생성 시점 이미지 자동 export (tab_db_create 연동)
- [ ] (선택) bbox 하이라이트, (선택) 인증 기반 FileResponse
- [x] 수동 검증 완료

### Phase 5 종결 요약

- **구현**: pdf_to_images, DB 생성 시 자동 export, /view/images 서빙, 출처 팝업(상단 출처 표기).
- **UI 변경**: 2분할 → 출처 클릭 시 팝업으로 확정 (가독성 개선).

### Phase 5 완료 시 커밋

```
feat(web): Phase 5 — PDF 이미지 서빙 및 웹 뷰어 (종결)

- pdf_to_images, storage/pdf_images, DB 생성 시 자동 export
- api_server: /view/images, sources에 image_url
- web_client: 출처 클릭 시 팝업(상단 출처 표기)으로 이미지 표시
```

---

## Phase 6: main_window 탭 통합 및 통합 테스트

### 목표

main_window에 [서버 서비스 탭]을 추가하고, 탭 순서 및 기본 탭을 설정한다. 서버 시작 → Web Client 질의까지 전체 흐름을 통합 테스트한다.

### 현재 상태 (이미 반영됨)

- **`main_window.py`**에서 이미 [서버 서비스] 탭을 **첫 번째**로 추가하고, [사용 탭], [DB 생성 탭] 순으로 `addTab()` 되어 있음.
- QTabWidget 기본 동작으로 **첫 탭(서버 서비스)**이 기본 선택됨.
- 창 닫기 시 서버 실행 중이면 종료 확인 팝업 동작함.
- 따라서 **별도 추가 개발 없이**, 아래 수동 검증만 진행하면 Phase 6 완료로 볼 수 있음.

### 작업 내용

1. **`src/ui/main_window.py` 수정**

   - `tab_server_service` 임포트 및 인스턴스 생성
   - 탭 순서: [서버 서비스] → [사용] → [DB 생성]
   - 기본 선택 탭: [서버 서비스]
   - `addTab()` 순서 조정

2. **통합 테스트 시나리오**

   - Admin UI 실행 → [서버 서비스 탭]이 기본으로 표시되는지 확인
   - [서버 시작] 클릭 → 서버 기동, 로그 출력 확인
   - 브라우저에서 Web Client 접속 → 질문 입력 → 답변 수신 확인
   - 출처 카드 표시 확인
   - [서버 중단] 클릭 → 서버 종료 확인
   - [사용 탭], [DB 생성 탭] 기존 기능 동작 확인

3. **에러 케이스 확인**

   - 이미 실행 중인 서버에 다시 시작 시도 → 적절한 처리
   - Web Client에서 서버 중단 상태로 질문 → 에러 메시지 확인

### Phase 6에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/main_window.py` | 탭 순서 및 기본 탭 설정 |
| `src/ui/tabs/tab_server_service.py` | 탭 연동 |
| `src/ui/tabs/__init__.py` | tab_server_service export (필요 시) |

### 수동 검증 방법

1. `python -m src.app` 실행
2. [서버 서비스] 탭이 기본으로 선택되는지 확인
3. [서버 시작] → Web Client에서 질의 → [서버 중단] 전체 흐름 확인
4. [사용 탭]에서 기존 RAG 동작 확인
5. [DB 생성 탭]에서 기존 파이프라인 동작 확인

### 진도 체크

- [x] main_window 탭 순서 설정 (서버 서비스 → 사용 → DB 생성, 이미 반영됨)
- [x] [서버 서비스] 기본 탭 (첫 탭으로 이미 적용)
- [x] 서버 시작 → Web Client 질의 → 출처 팝업까지 전체 흐름 수동 검증
- [x] [사용 탭], [DB 생성 탭] 기존 기능 유지 확인
- [x] 수동 검증 완료 (Phase 5·6 종결)

### Phase 6 완료 시 커밋

```
feat(ui): Phase 6 — main_window 탭 통합

- main_window: [서버 서비스] 탭 추가, 기본 탭 설정
- 통합 테스트 완료
```

---

## Phase 7: V4 통합 검증 및 문서화

### 목표

V4 완료 기준(goal_v4.md §7)을 충족하는지 검증하고, 문서를 정리한다.

### V4 완료 기준 (goal_v4.md §7)

- [서버 서비스 탭]에서 서버 시작/중단 정상 동작
- POST /api/ask 호출 시 답변 및 sources 정상 반환
- Web Client에서 채팅 형식으로 질의응답 가능
- 출처(Source) 카드 뷰 정상 표시
- 실시간 로그 출력 동작
- 기존 [사용 탭], [DB 생성 탭] 기능 유지

### 작업 내용

1. **통합 검증**

   - 위 완료 기준 6개 항목 수동 테스트
   - curl/Postman으로 API 직접 호출 검증
   - Web Client E2E 검증
   - 기존 탭 기능 회귀 테스트

2. **문서 작성**

   - `readme.md` 갱신 (V4 구조, API 사용법, Web Client 접속 방법 반영)
   - `phase_v4.md` 진도 반영
   - requirements.txt에 `uvicorn`, `fastapi` 추가 (필요 시)

3. **V4 디렉토리 구조 확정**

   ```
   src/
   ├── server/                  (V4 신규)
   │   ├── __init__.py
   │   ├── api_server.py
   │   └── server_manager.py
   └── ui/tabs/
       ├── tab_server_service.py  (V4 신규)
       ├── tab_usage.py
       ├── tab_db_create.py
       └── tab_review.py
   web_client/                  (V4 신규)
   ├── index.html
   ├── style.css
   └── app.js
   ```

### Phase 7에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `readme.md` | V4 구조 반영 |
| `phase_v4.md` | 진도 반영 |
| `requirements.txt` | uvicorn, fastapi 추가 |
| `goal_v4.md` | 필요 시 보완 |

### 수동 검증 방법

1. [서버 서비스 탭] 서버 시작/중단 동작 확인
2. POST /api/ask 응답 (answer, sources) 확인
3. Web Client 채팅 형식 질의응답 확인
4. 출처 카드 뷰 표시 확인
5. 실시간 로그 출력 확인
6. [사용 탭], [DB 생성 탭] 기존 기능 동작 확인

### 진도 체크

- [x] [서버 서비스 탭] 서버 시작/중단 정상 동작
- [x] POST /api/ask 답변 및 sources 정상 반환
- [x] Web Client 채팅 질의응답 가능
- [x] 출처 카드 뷰 및 출처 클릭 시 팝업 이미지 표시
- [x] 실시간 로그 출력 동작
- [x] 기존 [사용 탭], [DB 생성 탭] 기능 유지
- [x] `readme.md` 갱신 (V4 구조, 실행 방법, Web Client 접속)
- [x] `phase_v4.md` 진도 반영 (Phase 5·6·7 종결)
- [x] requirements.txt 의존성 반영 (uvicorn, fastapi)

### Phase 7 종결 요약

- 통합 검증 기준 충족 (서버 탭, API, Web Client, 출처 팝업, 로그, 기존 탭 유지).
- `readme.md`에 V4 현황, 실행 방법, Web Client 접속, 디렉터리 구조 반영.
- `requirements.txt`에 fastapi, uvicorn 추가.

### Phase 7 완료 시 커밋

```
docs: Phase 7 — V4 통합 검증 및 문서화 (종결)

- readme.md: V4 구조, API, Web Client 사용법 갱신
- phase_v4.md: Phase 5·6·7 진도 반영
- requirements.txt: uvicorn, fastapi 추가
```

---

## 토큰 최소화 가이드

| Phase | 집중할 디렉터리/파일 | 참고 문서 |
|-------|----------------------|-----------|
| 1 | `src/server/api_server.py`, `src/rag/rag_pipeline.py` | goal_v4.md §2-2 |
| 2 | `src/server/server_manager.py` | goal_v4.md §2-1, §4 |
| 3 | `src/ui/tabs/tab_server_service.py`, `src/server/server_manager.py` | goal_v4.md §2-1 |
| 3-1 | `src/server/api_server.py` | phase_v4.md Phase 3-1 |
| 3-2 | `src/server/api_server.py`, `web_client/app.js` | phase_v4.md Phase 3-2 |
| 4 | `web_client/`, `src/server/api_server.py` | goal_v4.md §2-3 |
| 5 | `pdf_to_images`, `storage/pdf_images`, `api_server`, `web_client` | goal_v4.md §8, phase_v4.md Phase 5 |
| 6 | `src/ui/main_window.py`, `src/ui/tabs/tab_server_service.py` | goal_v4.md §3, §4 |
| 7 | `readme.md`, `phase_v4.md`, `requirements.txt` | goal_v4.md §7 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
