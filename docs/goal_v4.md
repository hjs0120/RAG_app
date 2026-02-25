**v4 설계문서 (REST API 기반 서버 시스템 확장)** 내용을 정리

---

# 설계문서 — V4 REST API 기반 RAG 서버 아키텍처

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

# 1. 전체 아키텍처 개편 방향

## 1.1 기존 구조 (v3)

```
사용자
  → PySide6 UI (tab_usage.py)
  → rag_pipeline.py (로컬 직접 호출)
  → FAISS 인덱스 / LLM
```

단일 프로세스, 로컬 전용

---

## 1.2 V4 구조

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
└─────────────────────────────────────────────────────────────────────┘
```

핵심 목표:

> 로컬 UI와 Web 기반 질의응답 서비스를 분리하여, 브라우저에서 접근 가능한 RAG 서버 구축

---

# 2. 단계별 개발 계획

---

## 2-1. 1단계 — 서버 서비스 탭 UI 추가

### 2-1-1. 목적

* 서버 시작/중단 제어 및 상태 모니터링
* API 서버를 Admin UI에서 원클릭으로 관리
* 실시간 로그로 디버깅 및 운영 가시성 확보

---

### 2-1-2. UI 레이아웃

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

---

### 2-1-3. 신규 개발 모듈

```
src/ui/tabs/tab_server_service.py   # 서버 서비스 탭 (설정/버튼/로그)
src/server/                           # 서버 관련 모듈 (신규 디렉터리)
src/server/api_server.py              # FastAPI 앱 정의 및 엔드포인트
src/server/server_manager.py          # Uvicorn 서브프로세스 제어 (시작/중단)
```

---

## 2-2. 2단계 — FastAPI 기반 API 서버 설계

### 2-2-1. 목적

* RAG 파이프라인을 HTTP API로 노출
* Web Client 및 외부 시스템에서 REST로 질의 가능
* 기존 core/rag 로직 재사용 (코드 중복 최소화)

---

### 2-2-2. API 스펙

#### POST /api/ask

**Request**
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

**Response**
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

---

### 2-2-3. 서버 구현 원칙

* **통합**: 기존 `core/rag` 모듈을 서버 프로세스 내에서 로드하여 사용
* **별도 프로세스**: Uvicorn을 서브프로세스로 실행 (PySide6 메인 루프와 분리)
* **CORS**: Web Client 도메인에 대해 CORS 허용 설정

---

### 2-2-4. 기타 엔드포인트 (선택)

| Method | Path          | 설명                |
| ------ | ------------- | -------------------- |
| GET    | /health       | 서버 상태 확인 (200 OK) |
| GET    | /api/config   | top_k 기본값 등 설정 조회 |

---

## 2-3. 3단계 — Web Client 설계

### 2-3-1. 목적

* 브라우저에서 RAG 질의응답 사용
* 서버 제어 없이 순수 Web으로 접근 가능
* 출처(Source) 시각화로 신뢰성 확보

---

### 2-3-2. 위치 및 구조

```
web_client/
├── index.html       # 메인 페이지 (채팅 UI)
├── style.css        # 스타일
└── app.js           # fetch API, 메시지 렌더링
```

* FastAPI에서 정적 파일 서빙: `/web_client` → `web_client/` 디렉터리

---

### 2-3-3. 기능 상세

| 기능           | 설명                                             |
| -------------- | ------------------------------------------------ |
| 채팅 인터페이스 | 사용자/봇 말풍선 형식, 스크롤 가능한 메시지 영역      |
| 질문 입력      | 텍스트 입력창 + 전송 버튼                           |
| 출처 표시      | 확장형 카드 뷰 (structure_path, file_name, page) |
| 로딩 표시      | 답변 생성 중 스피너/플레이스홀더                      |
| 에러 처리      | 네트워크/API 에러 시 사용자 친화적 메시지             |

---

### 2-3-4. 통신 방식

* `fetch()` API로 `POST /api/ask` 호출
* JSON Request/Response
* 비동기 처리 (async/await 또는 Promise)

---

# 3. UI 구조 개편 (V4)

## 현재 탭 구조 (v3 완료 기준)

```
src/ui/tabs/
├── tab_usage.py       # 사용 탭
├── tab_db_create.py   # DB 생성 탭
└── tab_review.py      # 검수 뷰 유틸
```

## V4 추가/수정 방향

### 신규 탭 추가

* `tab_server_service.py` → [서버 서비스 탭] (메인 탭으로 설정)

### main_window.py 수정

* 탭 순서: [서버 서비스] → [사용] → [DB 생성]
* 기본 선택 탭: [서버 서비스]

---

# 4. V4 개발 순서

### Step 1

`src/server/api_server.py` 작성  
→ FastAPI 앱, POST /api/ask 엔드포인트, core/rag 연동

### Step 2

`src/server/server_manager.py` 작성  
→ Uvicorn 서브프로세스 시작/중단, 로그 파이프

### Step 3

`tab_server_service.py` 작성  
→ 설정 UI, 시작/중단 버튼, LED 인디케이터, 로그 출력창

### Step 4

`web_client/index.html`, `app.js`, `style.css` 작성  
→ 채팅 UI, fetch API 연동, 출처 카드 뷰

### Step 5

main_window.py 수정 → 탭 순서 및 기본 탭 설정  
→ 통합 테스트 (서버 시작 → 브라우저에서 질의)

---

# 5. 디렉토리 구조 (V4 반영)

```
RAG_app/
├── src/
│   ├── app.py
│   ├── core/                    # 기존 유지
│   ├── db/
│   ├── llm/
│   ├── rag/
│   ├── server/                  # V4 신규
│   │   ├── api_server.py        # FastAPI 앱
│   │   └── server_manager.py    # Uvicorn 제어
│   └── ui/
│       ├── main_window.py       # 탭 순서 수정
│       └── tabs/
│           ├── tab_server_service.py  # V4 신규
│           ├── tab_usage.py
│           ├── tab_db_create.py
│           └── tab_review.py
├── web_client/                  # V4 신규
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docs/
│   ├── goal_v3.md
│   └── goal_v4.md               # 이 문서
├── ...
```

---

# 6. 기술 스택

| 구분       | 기술                    |
| ---------- | ----------------------- |
| API 서버   | FastAPI                 |
| ASGI 서버  | Uvicorn                 |
| Admin UI   | PySide6                 |
| Web Client | HTML5, JavaScript (Vanilla) |
| 통신       | fetch API, JSON         |

---

# 7. V4 완료 기준 (Definition of Done)

* [서버 서비스 탭]에서 서버 시작/중단 정상 동작
* POST /api/ask 호출 시 답변 및 sources 정상 반환
* Web Client에서 채팅 형식으로 질의응답 가능
* 출처(Source) 카드 뷰 정상 표시
* 실시간 로그 출력 동작
* 기존 [사용 탭], [DB 생성 탭] 기능 유지

---

# 8. PDF 이미지 서빙 및 웹 뷰어 (V4 추가 개발)

출처(Source)에 해당하는 PDF 페이지를 웹에서 이미지로 볼 수 있도록 하는 기능이다. Phase 5에서 개발한다.

## 8.1 PDF 이미지 서빙 아키텍처

### 8.1.1 백엔드: PDF 페이지 이미지화 전략

- 서버 실행 시나 DB 생성 시점에 미리 이미지를 만들어 두는 것이 성능상 유리하다.
- **이미지 생성**: PyMuPDF(fitz) 라이브러리로 PDF 각 페이지를 `.png` 또는 `.jpg`로 변환한다.
- **해상도**: 웹에서 글자가 읽힐 정도인 **DPI 150~200** 정도가 적당하다.
- **저장 구조**:
  ```
  /storage/pdf_images/
    └── {doc_id}/
          ├── 1.jpg
          ├── 2.jpg
          └── ...
  ```
- **정적 파일 서빙**: FastAPI에서 `StaticFiles`를 사용하여 해당 폴더를 외부에 노출한다.
  ```python
  from fastapi.staticfiles import StaticFiles
  app.mount("/view/images", StaticFiles(directory="storage/pdf_images"), name="images")
  ```

### 8.1.2 API 응답 데이터 확장

- 기존에는 출처 정보에 page 번호만 보냈다면, 이제는 **해당 페이지의 이미지 URL**을 함께 포함한다.
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

### 8.1.3 웹 클라이언트 UI 구성

- **좌우 2분할(Split View)** 구조로 설계한다.
- **좌측 (Chat Area)**: 질문·답변, 출처 버튼/카드가 나열된다.
- **우측 (Viewer Area)**: 평소에는 비어 있거나 안내 문구만 있다가, **출처를 클릭하면** `<img>`의 `src`를 해당 `image_url`로 바꿔 해당 페이지 이미지를 보여준다.

## 8.2 구현 시 고려할 디테일

1. **하이라이트 표시 (Bbox)**  
   페이지만 보여주는 것이 아니라, 답변의 근거가 되는 특정 문장에 **노란색 박스(Highlight)**를 넣고 싶다면:
   - **백엔드**: 이미지 URL과 함께 해당 텍스트의 bbox 좌표(V3에서 이미 추출)를 전달한다.
   - **프론트엔드**: 이미지 위에 `position: absolute`인 투명 div를 두고, 좌표만큼 덮어 씌운다.

2. **보안 및 권한**  
   URL로 모든 페이지 이미지를 열람하는 것이 부담된다면, FastAPI의 `FileResponse`를 사용하여 **요청 시점에 인증 토큰을 검사**한 뒤 이미지를 바이너리로 전송하는 방식을 쓸 수 있다.

3. **저장 용량 최적화**  
   PNG보다 **JPG (quality 80)**를 권장한다. 텍스트 위주 문서는 용량이 줄면서도 가독성을 유지한다.

## 8.3 V4 추가 개발 로드맵 (이미지 뷰어)

| 순서 | 구분 | 내용 |
|------|------|------|
| 1 | Backend | PDF를 이미지로 변환하는 유틸리티 클래스 작성 (`pdf_to_images.py`) |
| 2 | Backend | FastAPI 정적 파일 경로 설정 및 API 응답 스키마 수정 (sources에 `image_url` 등) |
| 3 | Web | 2분할 레이아웃 HTML/CSS 구현 (좌: 채팅, 우: 뷰어) |
| 4 | Web | 출처 클릭 시 우측 `<img>`의 `src`를 해당 `image_url`로 업데이트하는 JS 이벤트 리스너 |

---

# 9. 최종 정리

V4의 핵심은:

> 로컬 RAG를 REST API 서버로 확장하여, 브라우저 기반 Web Client에서 질의응답 서비스를 제공

Admin UI(PySide6)는 서버 제어 패널 역할을 유지하고,  
실제 사용자 인터페이스는 Web Client로 분리된다.

---

**V4 개발 핵심 원칙: Server-Side RAG & Web-First UX**

"로컬 RAG를 서버로 노출하고, 브라우저에서 접근 가능한 모던한 채팅 인터페이스를 제공한다."

1. **서버 아키텍처**  
   FastAPI + Uvicorn 기반 REST API로 RAG 파이프라인 노출. 기존 core/rag 모듈 재사용.

2. **역할 분리**  
   PySide6: Admin(제어/설정/DB관리), Web Client: 사용자 질의응답.

3. **Web-First UX**  
   채팅형 UI, 출처 카드 뷰로 사용성 및 신뢰성 확보.
