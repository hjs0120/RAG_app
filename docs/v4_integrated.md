# V4 통합 설계·개발 문서 — REST API 기반 RAG 서버 아키텍처

**goal_v4** 설계문서와 **phase_v4** 단계별 개발 계획을 통합한 문서입니다.

---

# Part I. 설계 및 목표 (goal_v4)

---

## 0. 범위 (Scope)

| 항목        | 내용                                      |
| --------- | --------------------------------------- |
| **목표**    | 로컬 기반 RAG를 REST API 기반 서버 시스템으로 확장     |
| **대상 버전** | v4                                      |
| **핵심 변화** | PySide6 UI → 서버 제어 패널(Control Panel), 실제 질의응답 → Web Client 제공 |
| **API 서버** | FastAPI + Uvicorn (ASGI)                 |
| **Admin UI** | PySide6 (기존 확장)                         |
| **Web Client** | HTML/JS (채팅 인터페이스)                    |

---

## 1. 전체 아키텍처 개편 방향

### 1.1 기존 구조 (v3)

```
사용자
  → PySide6 UI (tab_usage.py)
  → rag_pipeline.py (로컬 직접 호출)
  → FAISS 인덱스 / LLM
```

단일 프로세스, 로컬 전용

---

### 1.2 V4 구조

```
┌─────────────────────────────────────────────────────────────────────┐
│  사용자 (Web 브라우저)                                                  │
│    → Web Client (index.html)                                         │
│    → fetch API (비동기)                                                │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ HTTP
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI 서버 (Uvicorn ASGI)                                         │
│    POST /api/ask → core/rag 모듈 로드 → FAISS + LLM                   │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ 제어
                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PySide6 Admin UI (Control Panel)                                    │
│    [서버 서비스 탭] → 서버 시작/중단, 설정, 로그 모니터링                    │
│    [사용 탭], [DB 생성 탭] → 기존 기능 유지                                │
└──────────────────────────────────────┴──────────────────────────────┘
```

핵심 목표:

> 로컬 UI와 Web 기반 질의응답 서비스를 분리하여, 브라우저에서 접근 가능한 RAG 서버 구축

---

## 2. 단계별 설계

### 2-1. 서버 서비스 탭 UI

#### 2-1-1. 목적

- 서버 시작/중단 제어 및 상태 모니터링
- API 서버를 Admin UI에서 원클릭으로 관리
- 실시간 로그로 디버깅 및 운영 가시성 확보

#### 2-1-2. UI 레이아웃

기존 [사용 탭], [DB 생성 탭] **앞에** **[서버 서비스 탭]** 추가 → **메인(Default) 탭**으로 설정

```
┌─────────────────────────────────────────────────────────────────────┐
│  [서버 서비스]  [사용]  [DB 생성]                                       │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─ 서버 설정 ──────────────────────────────────────────────────┐   │
│  │  호스트: [ 127.0.0.1  ]    포트: [ 8081  ]                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ 서버 제어 ──────────────────────────────────────────────────┐   │
│  │  [서버 시작]  [서버 중단]     ● 상태: 중지됨 (또는 실행 중)        │   │
│  │  (LED 인디케이터: 녹색=실행, 회색=중지, 빨강=에러)                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─ 실시간 로그 ─────────────────────────────────────────────────┐  │
│  │  [INFO] API 서버 시작: http://127.0.0.1:8081                    │  │
│  │  [INFO] POST /api/ask - 200 - 1.2s                             │  │
│  │  [ERROR] ...                                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

#### 2-1-3. 신규 개발 모듈

```
src/ui/tabs/tab_server_service.py   # 서버 서비스 탭 (설정/버튼/로그)
src/server/                           # 서버 관련 모듈 (신규 디렉터리)
src/server/api_server.py              # FastAPI 앱 정의 및 엔드포인트
src/server/server_manager.py          # Uvicorn 서브프로세스 제어 (시작/중단)
```

---

### 2-2. FastAPI 기반 API 서버

#### 2-2-1. 목적

- RAG 파이프라인을 HTTP API로 노출
- Web Client 및 외부 시스템에서 REST로 질의 가능
- 기존 core/rag 로직 재사용 (코드 중복 최소화)

#### 2-2-2. API 스펙

**POST /api/ask**

Request
```json
{
  "query": "질문 내용",
  "top_k": 5
}
```

| 필드   | 타입   | 필수 | 설명          |
| ----- | ------ | ---- | ------------- |
| query | string | O    | 사용자 질문     |
| top_k | int    | X    | 검색 Chunk 수 (기본값 5) |

Response
```json
{
  "status": "success",
  "answer": "생성된 답변 텍스트",
  "sources": [
    {
      "chunk_id": "MOUS_RULE_2024_101_1",
      "text": "관련 청크 텍스트...",
      "metadata": {
        "structure_path": "제1장 > 제1절 > 제101조 > 1항",
        "physical_page": 7,
        "file_name": "이동식 해양구조물 규칙_2024.pdf"
      }
    }
  ]
}
```

| 필드    | 타입   | 설명                |
| ------ | ------ | ------------------- |
| status | string | "success" / "error" |
| answer | string | LLM 생성 답변        |
| sources| array  | 참조 Chunk 목록      |

#### 2-2-3. 서버 구현 원칙

- **통합**: 기존 `core/rag` 모듈을 서버 프로세스 내에서 로드하여 사용
- **별도 프로세스**: Uvicorn을 서브프로세스로 실행 (PySide6 메인 루프와 분리)
- **CORS**: Web Client 도메인에 대해 CORS 허용 설정

#### 2-2-4. 기타 엔드포인트

| Method | Path          | 설명                |
| ------ | ------------- | -------------------- |
| GET    | /health       | 서버 상태 확인 (200 OK) |
| GET    | /api/config   | top_k 기본값 등 설정 조회 |

---

### 2-3. Web Client

#### 2-3-1. 목적

- 브라우저에서 RAG 질의응답 사용
- 서버 제어 없이 순수 Web으로 접근 가능
- 출처(Source) 시각화로 신뢰성 확보

#### 2-3-2. 위치 및 구조

```
web_client/
├── index.html       # 메인 페이지 (채팅 UI)
├── style.css        # 스타일
└── app.js           # fetch API, 메시지 렌더링
```

- FastAPI에서 정적 파일 서빙: `/web_client` → `web_client/` 디렉터리

#### 2-3-3. 기능 상세

| 기능           | 설명                                             |
| -------------- | ------------------------------------------------ |
| 채팅 인터페이스 | 사용자/봇 말풍선 형식, 스크롤 가능한 메시지 영역      |
| 질문 입력      | 텍스트 입력창 + 전송 버튼                           |
| 출처 표시      | 확장형 카드 뷰 (structure_path, file_name, page) |
| 로딩 표시      | 답변 생성 중 스피너/플레이스홀더                      |
| 에러 처리      | 네트워크/API 에러 시 사용자 친화적 메시지             |

---

## 3. UI 구조 개편

### 탭 구조 (v3 → v4)

| v3 | v4 |
| -- | -- |
| [사용], [DB 생성] | [서버 서비스] → [사용] → [DB 생성] |

- 신규: `tab_server_service.py` → [서버 서비스 탭] (메인 탭)
- 기본 선택 탭: [서버 서비스]

---

## 4. V4 개발 순서 (개요)

| Step | 내용 |
| ---- | ---- |
| 1 | `api_server.py` — FastAPI 앱, POST /api/ask, core/rag 연동 |
| 2 | `server_manager.py` — Uvicorn 서브프로세스 시작/중단, 로그 파이프 |
| 3 | `tab_server_service.py` — 설정 UI, 시작/중단 버튼, LED, 로그 |
| 4 | `web_client/` — 채팅 UI, fetch API, 출처 카드 뷰 |
| 5 | main_window.py 수정 — 탭 순서·기본 탭, 통합 테스트 |

---

## 5. 디렉터리 구조

```
RAG_app/
├── src/
│   ├── app.py
│   ├── core/                    # 기존 유지
│   ├── db/
│   ├── llm/
│   ├── rag/
│   ├── server/                  # V4 신규
│   │   ├── api_server.py
│   │   └── server_manager.py
│   └── ui/
│       ├── main_window.py
│       └── tabs/
│           ├── tab_server_service.py  # V4 신규
│           ├── tab_usage.py
│           ├── tab_db_create.py
│           └── tab_review.py
├── web_client/                  # V4 신규
│   ├── index.html
│   ├── style.css
│   └── app.js
├── storage/pdf_images/          # V4 추가 (Phase 5)
│   └── {doc_id}/
├── docs/
│   └── v4_integrated.md         # 이 문서
└── ...
```

---

## 6. 기술 스택

| 구분       | 기술                    |
| ---------- | ----------------------- |
| API 서버   | FastAPI                 |
| ASGI 서버  | Uvicorn                 |
| Admin UI   | PySide6                 |
| Web Client | HTML5, JavaScript (Vanilla) |
| 통신       | fetch API, JSON         |

---

## 7. V4 완료 기준 (Definition of Done)

- [서버 서비스 탭]에서 서버 시작/중단 정상 동작
- POST /api/ask 호출 시 답변 및 sources 정상 반환
- Web Client에서 채팅 형식으로 질의응답 가능
- 출처(Source) 카드 뷰 및 출처 클릭 시 팝업 이미지 표시
- 실시간 로그 출력 동작
- 기존 [사용 탭], [DB 생성 탭] 기능 유지

---

## 8. PDF 이미지 서빙 및 웹 뷰어

출처(Source)에 해당하는 PDF 페이지를 웹에서 이미지로 볼 수 있도록 하는 기능이다. Phase 5에서 개발한다.

### 8.1 아키텍처

- **이미지 생성**: PyMuPDF(fitz)로 PDF 각 페이지를 `.jpg`로 변환 (DPI 150~200, quality 80)
- **저장 구조**: `storage/pdf_images/{doc_id}/1.jpg`, `2.jpg`, ...
- **정적 서빙**: FastAPI `StaticFiles` → `/view/images`
- **API 확장**: sources에 `image_url` 포함
- **UI**: 출처 클릭 시 **팝업(모달)**로 해당 페이지 이미지 표시 (2분할 → 팝업으로 확정)

### 8.2 구현 고려사항

1. **하이라이트 (Bbox)**: 이미지 URL + bbox 좌표 전달 → 프론트에서 position:absolute 오버레이
2. **보안**: 필요 시 `FileResponse`로 인증 토큰 검사 후 이미지 전달
3. **용량**: JPG (quality 80) 권장

---

## 9. 최종 정리

V4의 핵심:

> 로컬 RAG를 REST API 서버로 확장하여, 브라우저 기반 Web Client에서 질의응답 서비스를 제공

**핵심 원칙: Server-Side RAG & Web-First UX**

1. **서버 아키텍처**: FastAPI + Uvicorn 기반 REST API, core/rag 재사용
2. **역할 분리**: PySide6=Admin(제어/DB관리), Web Client=질의응답
3. **Web-First UX**: 채팅형 UI, 출처 카드 뷰 및 팝업 이미지로 신뢰성 확보

---

# Part II. 단계별 개발 계획 (phase_v4)

---

## 개요

- **목표**: 로컬 RAG를 REST API 기반 서버 시스템으로 확장
- **핵심 방향**: FastAPI 서버 + 서버 서비스 탭 + Web Client 채팅 인터페이스
- **UI**: PySide6 — 서버 서비스 탭 신규 추가, 메인 탭
- **탭 순서**: [서버 서비스] → [사용] → [DB 생성]

---

## 테스트 및 환경

### 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024-7-92.pdf`
- **인덱스**: `output/rules.index`, `output/rules_meta.jsonl`
- **API 테스트**: Web Client 또는 `curl`/Postman으로 POST /api/ask

### Python 환경

- **권장**: Conda `PySide6` (V3와 동일)
- **V4 추가 의존성**: `uvicorn`, `fastapi`

```powershell
pip install uvicorn fastapi
```

### 서버 실행

```powershell
# 방법 1: Uvicorn 직접
uvicorn src.server.api_server:app --host 127.0.0.1 --port 8081

# 방법 2: Admin UI [서버 서비스 탭] → [서버 시작]
python -m src.app
```

### API 테스트

```powershell
curl -X POST http://127.0.0.1:8081/api/ask -H "Content-Type: application/json" -d "{\"query\": \"제101조 내용은?\", \"top_k\": 5}"
```

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
| 5 | PDF 이미지 서빙 및 웹 뷰어 (2분할→팝업, 출처 클릭 시 이미지) | [x] |
| 6 | main_window 탭 통합 및 통합 테스트 | [x] |
| 7 | V4 통합 검증 및 문서화 | [x] |

---

## Phase 1: FastAPI 앱 및 POST /api/ask 엔드포인트

### 목표

FastAPI 앱 정의, POST /api/ask 구현, core/rag 모듈 연동으로 RAG 질의응답 제공.

### 작업 내용

1. `src/server/` 생성 — `__init__.py`
2. `src/server/api_server.py` — FastAPI 앱, POST /api/ask, core/rag 임포트
3. CORS 미들웨어, GET /health (선택)
4. Response: `{"status","answer","sources"}` 스펙 준수

### 수동 검증

1. `uvicorn src.server.api_server:app --host 127.0.0.1 --port 8081` 실행
2. curl로 POST /api/ask 호출
3. `status`, `answer`, `sources` 포함 여부 확인
4. V3 [사용 탭] 결과와 유사한지 확인

### 진도 체크

- [x] api_server.py FastAPI 앱 생성
- [x] POST /api/ask 구현
- [x] core/rag 연동
- [x] Response 스펙 준수
- [x] CORS 설정
- [x] 수동 검증 완료

---

## Phase 2: Uvicorn 서브프로세스 제어

### 목표

Admin UI에서 서버 시작/중단 가능하도록 Uvicorn 서브프로세스 제어, 로그 파이프.

### 작업 내용

1. `src/server/server_manager.py` — ServerManager 클래스
   - `start(host, port)`, `stop()`, `is_running()`, `get_log_callback()`
   - subprocess.Popen으로 uvicorn 실행
   - stdout/stderr → 로그 콜백
2. 포트 충돌 등 에러 처리

### 진도 체크

- [x] ServerManager 구현
- [x] start/stop/is_running 동작
- [x] 로그 파이프
- [x] 에러 처리
- [x] 수동 검증 완료

---

## Phase 3: 서버 서비스 탭 UI

### 목표

호스트·포트 설정, [서버 시작]/[서버 중단], LED 인디케이터, 실시간 로그 출력창 구현.

### 작업 내용

1. `src/ui/tabs/tab_server_service.py` — 설정, 제어, 로그 영역
2. ServerManager 연동
3. LED: 녹색(실행), 회색(중지), 빨강(에러)
4. main_window 수정은 Phase 6에서 수행

### 진도 체크

- [x] tab_server_service.py 생성
- [x] 호스트/포트 UI
- [x] 시작/중단 버튼 연동
- [x] LED 인디케이터
- [x] 실시간 로그
- [x] ServerManager 연동
- [x] 수동 검증 완료

---

## Phase 3-1: 서버 시작 시 모델 사전 로드

### 목표

[서버 시작] 시 bge-m3, FAISS, Ollama 사전 로드. 첫 /api/ask 대기 시간 제거, 로그에 진행 상황 표시.

### 작업 내용

1. `api_server.py` — FastAPI lifespan 훅
2. 순차 로드: bge-m3 → FAISS → Ollama
3. TQDM/transformers 로그 억제 (TQDM_DISABLE, TRANSFORMERS_VERBOSITY)
4. main_window: closeEvent에서 서버 실행 중 창 닫기 시 종료 확인 팝업

### 진도 체크

- [x] lifespan 추가
- [x] bge-m3, FAISS, Ollama 사전 로드
- [x] 로그 억제
- [x] 창 닫기 시 확인 팝업
- [x] 수동 검증 완료

---

## Phase 3-2: 동시 요청 개수 제한

### 목표

동시 처리 1개, 큐 최대 3개 제한. 초과 시 즉시 거절, 대기 시 순서·안내 메시지 제공.

### 동작 시나리오

- 1~4번 요청: 처리 또는 큐 대기
- 5번 요청: 큐 초과 → `status="rejected"`
- status: `success` | `error` | `rejected` | `queued`

### 작업 내용

1. api_server: MAX_QUEUE_SIZE, MAX_CONCURRENT 설정
2. 초과 시 `status="rejected"`, 안내 메시지
3. 대기 시 `status="queued"`, queue_position, message
4. Web Client: rejected/queued/success 분기 처리

### 진도 체크

- [x] 요청 큐·슬롯 제한 로직
- [x] 초과 시 거절
- [x] 큐 대기 순차 처리
- [x] 대기 시 순서·안내 메시지
- [x] Admin UI rejected 처리
- [ ] Web Client rejected 분기 (Phase 4에서 반영)
- [x] 수동 검증 완료

---

## Phase 4: Web Client

### 목표

브라우저 채팅 UI, fetch POST /api/ask, 출처 카드 뷰 구현.

### 작업 내용

1. `web_client/index.html`, `style.css`, `app.js`
2. 채팅 영역, 입력 영역, 출처 카드 (접기/펼치기)
3. api_server 정적 파일 서빙: `/web_client`
4. rejected/queued/success 처리

### 진도 체크

- [x] index.html, app.js, style.css
- [x] fetch POST /api/ask
- [x] 출처 카드 뷰
- [x] 로딩 표시
- [x] 에러 처리 (rejected 포함)
- [x] 정적 파일 서빙
- [ ] 수동 검증 완료

---

## Phase 5: PDF 이미지 서빙 및 웹 뷰어

### 목표

출처 클릭 시 해당 PDF 페이지를 이미지로 표시. 팝업 방식 확정.

### 작업 내용

1. `src/core/pdf_to_images.py`, `scripts/export_pdf_images.py` — PDF→이미지 변환
2. `storage/pdf_images/{doc_id}/` 저장
3. api_server: `/view/images` 마운트, sources에 `image_url` 추가
4. tab_db_create: 임베딩 완료 시 export_pdf_to_images 자동 호출
5. Web Client: 출처 클릭 → 팝업, 상단에 출처 정보 표기

### 진도 체크

- [x] pdf_to_images, export_pdf_images
- [x] storage/pdf_images, /view/images
- [x] sources.image_url
- [x] 출처 클릭 → 팝업 이미지
- [x] 팝업 상단 출처 표기
- [x] DB 생성 시 이미지 자동 export
- [x] 수동 검증 완료

---

## Phase 6: main_window 탭 통합 및 통합 테스트

### 목표

[서버 서비스] 탭 추가, 탭 순서·기본 탭 설정. 전체 흐름 통합 테스트.

### 현재 상태

- main_window에 이미 [서버 서비스] 탭 첫 번째로 추가됨
- 별도 추가 개발 없이 수동 검증으로 Phase 6 완료 가능

### 진도 체크

- [x] 탭 순서 (서버 서비스 → 사용 → DB 생성)
- [x] [서버 서비스] 기본 탭
- [x] 서버 시작 → Web Client 질의 → 출처 팝업 전체 흐름 검증
- [x] 기존 탭 기능 유지
- [x] 수동 검증 완료

---

## Phase 7: V4 통합 검증 및 문서화

### 목표

V4 완료 기준 충족 여부 검증, 문서 정리.

### 작업 내용

1. 완료 기준 6개 항목 수동 테스트
2. readme.md 갱신 (V4 구조, API, Web Client)
3. requirements.txt에 uvicorn, fastapi 추가

### 진도 체크

- [x] 서버 탭 시작/중단 정상
- [x] POST /api/ask 답변·sources 정상
- [x] Web Client 채팅 질의응답 가능
- [x] 출처 카드 및 팝업 이미지 표시
- [x] 실시간 로그 동작
- [x] 기존 탭 유지
- [x] readme.md 갱신
- [x] phase_v4 진도 반영
- [x] requirements.txt 의존성 반영

---

## 토큰 최소화 가이드

| Phase | 집중 디렉터리/파일 |
|-------|-------------------|
| 1 | `api_server.py`, `rag_pipeline.py` |
| 2 | `server_manager.py` |
| 3 | `tab_server_service.py`, `server_manager.py` |
| 3-1 | `api_server.py` |
| 3-2 | `api_server.py`, `web_client/app.js` |
| 4 | `web_client/`, `api_server.py` |
| 5 | `pdf_to_images`, `storage/pdf_images`, `api_server`, `web_client` |
| 6 | `main_window.py`, `tab_server_service.py` |
| 7 | `readme.md`, `requirements.txt` |

---

## 관련 문서

| 문서 | 용도 |
|------|------|
| `readme.md` | 프로젝트 개요, 실행 방법 |
| `requirements.txt` | Python 의존성 |
| `docs/ollama_setup.md` | Ollama 설정 |
| `docs/chunk_diagnosis.md` | Chunk 검증 |
