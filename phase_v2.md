# RAG_app V2 — 사용성 중심 재설계 단계별 개발 계획

## 개요

- **기반 문서**: `goal_v2.md`
- **목표**: 프로토타입(V1) → 실사용 RAG 워크벤치(V2) 전환
- **핵심 방향**: UX 재설계 + DB 관리 기능 확장

---

## UI 프레임워크

- **PySide6** (Qt for Python 6) 기반
- `QMainWindow`, `QTabWidget`, `QGroupBox`, `QPushButton` 등 Qt 위젯 사용

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024.pdf`
- **인덱스**: `output/rules.index`, `output/rules_meta.jsonl` (기존 생성된 FAISS 인덱스 활용)

---

## Phase 진도 요약

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | 프로젝트 구조 리팩토링 — core/rag/db_manager/ui 분리 강화 | ☑ |
| 2 | DB Manager 모듈 신설 (load/save/append/remove/rebuild) | ☑ |
| 3 | 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개로 재구성 | ☑ |
| 4 | 사용 탭 — 모델 관리, 질문 & 검색 영역 | ☑ |
| 5 | 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역 | ☑ |
| 6 | 사용 탭 — 출처 영역 (PDF 뷰어 연동) | ☑ |
| 7 | DB 생성 탭 — 파이프라인 통합 (PDF→텍스트→Chunk→임베딩) | ☑ |
| 8 | 증분 임베딩 (Incremental Embedding) | ☑ |
| 9 | 출처 가독성 개선 (페이지/장/절/항 표시) | ☑ |
| 10 | V2 통합 검증 및 문서화 | ☑ |

각 Phase의 **진도 체크** 항목을 검증 후 `[ ]` → `[x]`로 바꾸고, 위 표의 완료도 필요 시 ✅로 갱신하면 된다.

---

## Phase 1: 프로젝트 구조 리팩토링 — core/rag/db_manager/ui 분리 강화

### 목표

UI와 로직 혼재를 해소하고, 모듈별 역할을 명확히 분리한다.

### 작업 내용

1. **디렉터리 구조 정리**

```
RAG_app/
├── src/
│   ├── app.py
│   ├── core/              # 추출, 파싱, Chunk, 임베딩 등 핵심 로직
│   │   ├── __init__.py
│   │   ├── extract_pymupdf.py
│   │   ├── line_rebuild.py
│   │   ├── normalize.py
│   │   ├── parse_state_machine.py
│   │   ├── rules.py
│   │   ├── export_jsonl.py
│   │   ├── chunk_builder.py
│   │   ├── chunk_validate.py
│   │   ├── embedding_bge.py
│   │   └── faiss_index.py
│   ├── rag/               # RAG 파이프라인 (검색, 재조합, 프롬프트)
│   │   ├── __init__.py
│   │   ├── rag_pipeline.py
│   │   ├── chunk_assembler.py
│   │   ├── prompt_templates.py
│   │   └── rag_config.py
│   ├── db/                # DB Manager (인덱스 관리 전담)
│   │   ├── __init__.py
│   │   └── db_manager.py   # Phase 2에서 구현
│   ├── llm/               # LLM 클라이언트
│   │   ├── __init__.py
│   │   └── ollama_client.py
│   └── ui/                # UI 전용
│       ├── __init__.py
│       ├── main_window.py
│       └── tabs/
│           ├── __init__.py
│           ├── tab_usage.py       # 사용 탭 (Phase 3~6에서 구성)
│           └── tab_db_create.py   # DB 생성 탭 (Phase 7에서 구성)
├── data/
├── output/
├── models/
├── requirements.txt
├── goal_v2.md
└── phase_v2.md
```

2. **모듈 역할 정리**

- `core/`: 데이터 추출, 파싱, Chunk 생성, 임베딩, FAISS 인덱스 생성(저수준)
- `rag/`: RAG 쿼리, Chunk 재조합, 프롬프트, 출처 관리
- `db/`: 인덱스 로드/저장, 증분 추가, Chunk 삭제, 재구성(고수준)
- `ui/`: PySide6 위젯, 이벤트 핸들러, core/rag/db 호출만 수행

3. **기존 탭 → 신규 탭 매핑 준비**

- 기존: tab_import, tab_extract, tab_parse, tab_export, tab_review, tab_chunk, tab_embedding, tab_rag
- V2: tab_usage (사용), tab_db_create (DB 생성) — 2개로 통합

### Phase 1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/` 전체 | 디렉터리 구조, import 경로 정리 |
| `src/db/__init__.py` (신규) | db 패키지 초기화 |
| `src/ui/tabs/` | 기존 탭 파일 정리(삭제 전 참조용 유지) |

### 수동 검증 방법

1. `python src/app.py` 실행 시 기존 기능이 정상 동작하는지 확인
2. import 에러 없이 앱이 기동하는지 확인

### 진도 체크

- [x] `src/db/` 디렉터리 생성
- [x] core/rag/llm/ui 모듈 역할 분리 확인
- [x] 기존 import 경로 동작 확인
- [x] 수동 검증 완료

---

## Phase 2: DB Manager 모듈 신설

### 목표

인덱스 관리 기능을 `db_manager.py`로 통합한다. load/save/append/remove/rebuild API를 제공한다.

### 작업 내용

1. **`src/db/db_manager.py` 신규 생성**

- `load_index(index_path, meta_path)` → (faiss_index, meta_list)
- `save_index(index, meta_list, index_path, meta_path)`
- `append_chunks(chunk_list, index_path, meta_path)` — 기존 index + meta 로드 → 임베딩 → add → 저장
- `remove_chunks(chunk_ids, index_path, meta_path)` — 대상 제외 → 새 index 재구성 → 저장
- `rebuild_index(meta_list, index_path, meta_path)` — meta만 있을 때 전체 재구성

2. **메타데이터 일관성**

- 각 벡터 메타: `doc_id`, `section`, `article`, `page`, `chunk_id`, `full_text`
- index와 meta.jsonl 항상 동기화

3. **무결성 보장**

- append/삭제 시 자동 백업 (선택)
- 에러 발생 시 롤백 고려

### Phase 2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/db/db_manager.py` (신규) | load_index, save_index, append_chunks, remove_chunks, rebuild_index |
| `src/core/embedding_bge.py` | db_manager에서 호출 |
| `src/core/faiss_index.py` | db_manager에서 활용 |

### 수동 검증 방법

1. `db_manager.load_index()` → 기존 index/meta 로드 확인
2. `db_manager.append_chunks()` → 새 chunk 1개 추가 후 검색 결과에 포함되는지 확인
3. `db_manager.remove_chunks()` → 특정 chunk 제거 후 검색에서 제외되는지 확인

### 진도 체크

- [x] load_index, save_index 구현
- [x] append_chunks 구현 (기존 index + new vectors)
- [x] remove_chunks 구현 (제외 후 재구성)
- [x] rebuild_index 구현
- [x] index ↔ meta 동기화 확인
- [x] 수동 검증 완료

---

## Phase 3: 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개로 재구성

### 목표

기존 다수 탭을 **사용 탭**, **DB 생성 탭** 2개로 통합한다.

### 작업 내용

1. **main_window.py 수정**

- 기존 8개 탭 제거
- 탭 2개만 등록: `[ 사용 탭 ]`, `[ DB 생성 탭 ]`

2. **tab_usage.py (사용 탭) 스켈레톤**

- Phase 4~6에서 상세 구현
- 현재: 빈 레이아웃 + QGroupBox 배치만

3. **tab_db_create.py (DB 생성 탭) 스켈레톤**

- Phase 7에서 상세 구현
- 현재: 빈 레이아웃 + QGroupBox 배치만 (Import, Extract, Parse, Chunk, Embedding 구역 구분)

4. **레이아웃 원칙**

- 스크롤 과도 분리 금지
- 가로 공간 충분히 활용
- 좌: 검색 결과 / 우: 답변 구조 추천 (사용 탭)

### Phase 3에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/main_window.py` | 탭 2개로 재구성 |
| `src/ui/tabs/tab_usage.py` (신규) | 사용 탭 스켈레톤 |
| `src/ui/tabs/tab_db_create.py` (신규) | DB 생성 탭 스켈레톤 |
| `src/ui/tabs/tab_*.py` (기존) | 필요 시 삭제 또는 보관 |

### 수동 검증 방법

1. 앱 실행 → 탭 2개(사용, DB 생성)만 표시되는지 확인
2. 탭 전환 시 오류 없이 동작하는지 확인

### 진도 체크

- [x] main_window 탭 2개로 변경
- [x] tab_usage.py, tab_db_create.py 스켈레톤 생성
- [x] 기존 탭 로직 보존(임시 import 또는 복사) — 기존 tab_*.py 파일 유지
- [x] 수동 검증 완료 (PySide6 환경에서 앱 실행 후 확인)

---

## Phase 4: 사용 탭 — 모델 관리, 질문 & 검색 영역

### 목표

사용 탭에 **모델 관리**와 **질문 & 검색** 영역을 구현한다.

### 작업 내용

1. **모델 관리 영역**

- Ollama 모델 목록 표시 (API 조회)
- 모델 선택 콤보박스
- 모델 로드 상태 표시
- 현재 모델 정보 표시

2. **질문 & 검색 영역**

- 질문 입력 영역 (대형 텍스트 박스, `QPlainTextEdit`)
- Top-k 조절 슬라이더/스핀박스
- [검색] 버튼
- [답변 생성] 버튼

3. **레이아웃**

- 상단: 모델 관리
- 중단: 질문 입력 + 검색/답변 버튼
- 비동기 처리(QThread) 유지

### Phase 4에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_usage.py` | 모델 관리, 질문 & 검색 UI |
| `src/llm/ollama_client.py` | 모델 목록 조회 (필요 시 확장) |
| `src/rag/rag_pipeline.py` | 검색/답변 호출 |

### 수동 검증 방법

1. Ollama 실행 상태에서 모델 목록이 표시되는지 확인
2. 모델 선택 후 질문 입력 → [검색] 클릭 시 동작하는지 확인
3. [답변 생성] 클릭 시 동작하는지 확인

### 진도 체크

- [x] 모델 목록 표시, 선택 UI
- [x] 모델 로드 상태 표시
- [x] 질문 입력 영역 (대형 텍스트 박스)
- [x] Top-k 조절
- [x] 검색 / 답변 생성 버튼
- [x] 수동 검증 완료

---

## Phase 5: 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역

### 목표

검색 결과를 가독성 있게 표시하고, 조합 컨텍스트와 답변 영역을 구현한다.

### 작업 내용

1. **검색 결과 영역**

- Top-k 결과 리스트 (QListWidget 또는 QTableWidget)
- 점수 표시
- section/article 정보 표시
- page 정보 표시
- chunk 미리보기 충분히 표시
- 선택 시 상세 보기

2. **조합 컨텍스트 영역**

- 실제 LLM에 전달된 assembled context 표시
- 길이 표시 (토큰 또는 문자 수)
- 그룹 단위 구분 표시

3. **답변 영역**

- 충분한 크기의 답변 출력 영역 (`QTextEdit`)
- 출처 분리 표시
- 출처 클릭 시 해당 chunk 하이라이트 (V2.1 확장 고려)

4. **레이아웃**

- 좌: 검색 결과
- 우: 조합 컨텍스트 + 답변
- 또는 상/하/좌/우 분할로 가독성 확보

### Phase 5에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_usage.py` | 검색 결과, 조합 컨텍스트, 답변 영역 |
| `src/rag/rag_pipeline.py` | RAGResult 구조 (retrieved_chunks, assembled_context 등) |

### 수동 검증 방법

1. 검색 후 Top-k 결과가 리스트에 표시되는지 확인
2. 점수, section, page, chunk 미리보기가 보이는지 확인
3. 답변 생성 후 조합 컨텍스트와 답변이 각각 표시되는지 확인
4. 출처가 분리되어 표시되는지 확인

### 진도 체크

- [x] 검색 결과 리스트 (점수, section, article, page, preview)
- [x] 선택 시 상세 보기
- [x] 조합 컨텍스트 영역 (길이, 그룹 구분)
- [x] 답변 영역 (충분한 크기)
- [x] 출처 분리 표시
- [x] 수동 검증 완료

### Phase 5 추가 구현 (완료)

- UI 단분리: 좌(모델/FAISS/질문/검색/컨텍스트/답변) | 우(출처/PDF)
- 모델 사전 로드 완료 시에만 검색/답변 생성 버튼 활성화
- 답변 인용 출처만 드롭다운에 표시 (`_extract_cited_sources`)

---

## Phase 6: 사용 탭 — 출처 영역 (PDF 뷰어 연동)

### 목표

출처를 클릭하면 해당 PDF의 페이지를 PDF 뷰어로 표시한다.

### 작업 내용

1. **출처 영역**

- 출처 목록 표시 (doc_id, page, section 등)
- 출처 클릭 시 해당 chunk 정보 전달

2. **PDF 뷰어**

- 검수 탭(tab_review)의 PDF 뷰어 로직 재사용 또는 통합
- PyMuPDF로 페이지 이미지 렌더링 → QLabel/QGraphicsView 등에 표시
- 출처의 page 값에 해당하는 PDF 페이지 표시

3. **연동**

- 출처 클릭 → PDF 파일 경로 확인 (meta에서 또는 설정)
- 해당 page로 PDF 뷰어 전환

### Phase 6에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_usage.py` | 출처 영역, PDF 뷰어 영역 |
| `src/ui/tabs/tab_review.py` | PDF 렌더링 로직 참조/통합 |

### 수동 검증 방법

1. 출처 클릭 시 PDF 뷰어에 해당 페이지가 표시되는지 확인
2. 여러 출처 클릭 시 페이지 전환이 정상 동작하는지 확인

### 진도 체크

- [x] 출처 클릭 이벤트 (출처 드롭다운 선택 → PDF 뷰어 연동)
- [x] PDF 뷰어 영역 (우측 배치, 너비 맞춤/세로 스크롤)
- [x] 출처 → page → PDF 표시 연동
- [x] 인덱스 등록 시 원본 PDF 폴더 선택
- [x] bge-m3 모델 확인 및 다운로드 버튼
- [x] 수동 검증 완료

### Phase 6 추가 구현 (완료)

- 출처를 목록→드롭다운으로 변경
- PDF 뷰어: 뷰포트 너비 맞춤, 세로 스크롤 (tab_review 방식)
- 확대/축소 제거, 항상 전체 너비 표시

---

## Phase 7: DB 생성 탭 — 파이프라인 통합 (PDF→텍스트→Chunk→임베딩)

### 목표

PDF 추출, 검수, Chunk 생성, 임베딩을 **하나의 통합 작업 공간**으로 구성한다.

### 작업 내용

1. **탭 내 구역 구성**

- **1️⃣ PDF → 텍스트 추출**: Import, Extract, Parse, 검수
- **2️⃣ Chunk 생성**: JSONL 생성, Merge/Split 규칙 적용
- **3️⃣ 임베딩 생성**: bge-m3 로딩, FAISS Index 생성, index 파일 저장

2. **검수 기능 통합**

- 텍스트 추출 검수는 별도 서브탭 또는 접이식 영역으로 구성
- PDF·JSONL 좌우 분할 뷰, 라인 네비게이션, 수정·저장

3. **플로우**

- 상단부터 순서대로: Import → Extract → Parse → (검수) → Chunk 생성 → 임베딩
- 각 단계 완료 후 다음 단계 활성화
- 출력 경로, 옵션 통합 관리

### Phase 7에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_db_create.py` | 통합 파이프라인 UI |
| `src/core/` | extract, parse, export, chunk_builder, embedding_bge, faiss_index |
| `src/core/toc_detector.py` | 본문 시작 감지 → content_start_pdf_page |
| `src/ui/tabs/tab_review.py` | 검수 UI 로직 통합 또는 재사용 |
| `src/ui/main_window.py` | app_state 등 공유 상태 |
| `docs_meta.json` (output) | doc_id → content_start_pdf_page (Phase 10 표시용) |

### 수동 검증 방법

1. DB 생성 탭에서 PDF Import → Extract → Parse → Chunk → 임베딩까지 일련의 흐름으로 실행 가능한지 확인
2. 검수 기능이 통합되어 있는지 확인
3. 생성된 index, meta 파일이 정상적으로 저장되는지 확인

### 진도 체크

- [x] PDF → 텍스트 추출 구역 (Import, Extract, Parse)
- [x] 검수 구역 (PDF·JSONL 뷰, 수정·저장)
- [x] Chunk 생성 구역
- [x] 임베딩 생성 구역
- [x] 파이프라인 흐름 연동
- [x] 본문 시작 페이지 저장 (content_start_pdf_page → docs_meta.json, Phase 10 매핑용)
- [x] 수동 검증 완료

### Phase 7 추가 구현 (완료)

- **추출·필터**: `extract_pymupdf` 머릿말/꼬리말 8% 비율, 장/절 헤더·제목 조각(총칙, 일반사항 등) 여백 예외 보존. `equation_filter`에서 장/절 헤더·제목 조각을 들여쓰기 예외로 추가(중앙 정렬 제목이 수식으로 제거되던 문제 해결)
- **구조 병합**: `line_rebuild`에서 "제 1 장" + "총칙" → "제 1 장 총칙", "제 1 절" + "일반사항" → "제 1 절 일반사항" 병합
- **content_page**: `export_jsonl.build_record`에서 `content_start_pdf_page` 기반 `content_page`(문서 본문 페이지) 계산·저장. `chunk_builder` meta에 pages(content_page) 반영
- **docs_meta**: `tab_db_create`에서 `docs_meta.json`에 doc_id → content_start_pdf_page 저장 (Phase 10 출처 표시용)
- **검수 탭**: `tab_review`, `tab_db_create` 검수 창에서 **page (문서)** = content_page를 메인으로 표시, **PDF 물리**를 보조로 표시 — PDF 뷰어 번호와 동일하게 검수자 혼동 방지

### Phase 7 종결 요약

DB 생성 탭의 통합 파이프라인(Import → Extract → Parse → 검수 → Chunk → 임베딩)을 구현하고, 본문 시작 페이지(content_start_pdf_page)를 docs_meta에 저장하여 문서·물리 페이지 매핑 기반을 마련하였다. 추출 품질 개선(장/절 제목 equation_filter 예외, line_rebuild 병합)으로 "제 1 장 총칙", "제 1 절 일반사항" 등 구조 헤더가 정상 추출되도록 했으며, 검수 탭과 export에 content_page를 반영해 검수자·사용자 관점의 페이지 번호를 통일하였다.

---

### Phase 7 연계: 본문 시작 페이지 저장 (페이지 번호 매핑용)

표지·목차 때문에 **물리 PDF 페이지**와 **문서 본문 페이지**가 다를 수 있다.  
(예: 본문 1페이지 = PDF 7페이지) 이 매핑을 위해 추출 시 본문 시작 physical page를 저장한다.

- `toc_detector.detect_toc_start` → `body_start` 인덱스 → 해당 라인의 `page` = `content_start_pdf_page`
- export/chunk 파이프라인에서 doc_id별 `content_start_pdf_page` 수집
- `docs_meta.json` 또는 index 저장 시 `{ "doc_id": "xxx", "content_start_pdf_page": 7 }` 형태로 저장  
  (Phase 10에서 표시용·Phase 6 PDF 뷰어용으로 사용)

---

## Phase 8: 증분 임베딩 (Incremental Embedding)

### 목표

새로운 chunk 파일을 기존 FAISS index에 **추가**할 수 있게 한다.

### 작업 내용

1. **기능 구현**

- 기존 index + meta JSONL 로드
- 새로운 chunk JSONL 로드
- 새 chunk 임베딩 생성 (bge-m3)
- FAISS index.add() 수행
- meta_list append
- 저장

2. **UI**

- DB 생성 탭에 "기존 인덱스에 추가" 옵션 (그룹 7)
- 기존 index 경로, meta 경로 선택 (meta 미입력 시 자동 추론)
- 추가할 chunk JSONL 선택
- [추가] 버튼 + 프로그레스바

3. **db_manager 연동**

- `append_chunks()` 활용

### Phase 8에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/db/db_manager.py` | append_chunks (Phase 2에서 구현) |
| `src/ui/tabs/tab_db_create.py` | 증분 추가 UI (AppendWorker + 그룹 7) |
| `src/core/embedding_bge.py` | batch encode |

### 완료 내용

- `AppendWorker` (QObject 비동기) 구현 — chunk JSONL 로드 → `append_chunks` 호출
- DB 생성 탭 그룹 7 "기존 인덱스에 추가 (증분 임베딩)" UI 추가
- 인덱스 경로 선택 시 `_meta.jsonl` 자동 추론

### 부가 수정 — PDF 뷰어 페이지 체계 정리

Phase 8 진행 중 `content_page`/`physical_page` 이중 체계로 PDF 뷰어와 출처 표시가 불일치하는 문제를 발견하여 **물리 페이지 단일 체계**로 전면 정리했다.

| 파일 | 변경 내용 |
|------|-----------|
| `src/core/export_jsonl.py` | `content_page` 계산 제거, `page`(물리) 단일 저장 |
| `src/core/chunk_builder.py` | `build_chunk_meta` — 물리 `page`만 수집 |
| `src/core/faiss_index.py` | `physical_page` 필드 제거, `page`만 저장 |
| `src/db/db_manager.py` | 동일 |
| `src/rag/rag_pipeline.py` | `_format_source` 단순화 |
| `src/ui/tabs/tab_usage.py` | `_load_docs_meta`, `_content_to_physical_page` 등 변환 전체 제거, `page` 직접 뷰어에 사용 |
| `src/ui/tabs/tab_db_create.py` | `content_start_pdf_page` 저장·전달 코드 제거 |

> **재작업 필요**: Export → Chunk → 임베딩 재실행 시 물리 페이지로 올바르게 저장됨.

### 진도 체크

- [x] append_chunks 동작 확인
- [x] "기존 인덱스에 추가" UI
- [x] index + meta 동기화
- [x] 수동 검증 완료
- [x] PDF 뷰어/출처 페이지 체계 단일화 (물리 페이지 기준)

---

## Phase 9: 출처 가독성 개선 (페이지/장/절/항 표시)

### 배경

현재 출처는 청크 단위(doc_id, page, section, chunk_id)로 표시되어 사용자가 PDF에서 해당 위치를 찾기 어렵다. "몇 페이지에 몇 장 몇 절 몇 항" 형태로 알려주면 찾기 수월하다.

### ⚠️ 설계 변경 사항 (Phase 8 부가 수정 반영)

Phase 8 진행 중 **물리 페이지 ↔ 문서 본문 페이지 이중 체계가 근본 문제**임을 확인하여 전면 폐기했다.

- `content_start_pdf_page`, `docs_meta.json`, `content_page` 계산 → **모두 제거**
- 전 파이프라인(export → chunk → faiss meta → UI)이 **물리 페이지 단일 체계**로 통일됨
- `docs_meta.json` 파일 사용 중단

따라서 Phase 9의 "물리↔본문 매핑" 관련 계획은 **폐기**한다.  
PDF 자체에 표지·목차를 포함하지 않도록 문서를 전처리하면, 물리 페이지 = 본문 페이지가 되어 별도 매핑이 불필요하다.

### 남은 작업 — 출처 포맷 개선

| 방안 | 설명 |
|------|------|
| **A. 기존 meta 활용** | chunk meta에 이미 `article`, `section`, `paragraph`, `page` 포함. 포맷 함수만 추가해 `"p.12, 제10조, 제3절, (2)항"` 형태로 표시. **권장.** |
| B. 임베딩 단계 설계 변경 | chunk_builder/faiss meta에 `chapter`(장) 등 계층 정보를 명시적으로 포함. 신규 문서에 유리. |

### Phase 9에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/rag/rag_pipeline.py` | `_format_source` 가독성 개선 |
| `src/ui/tabs/tab_usage.py` | 출처 드롭다운 표시 개선 |
| `src/core/chunk_builder.py` | (선택) meta에 `chapter` 필드 추가 |

### 완료 내용

- `_format_location(meta)` 헬퍼 추가 — `article`→제X조, `section`, `paragraph`→(X)항 포맷
- `rag_pipeline._format_source`: `[i] doc_id, p.XX, 제X조, 절, chunk_id` 형태로 개선
- `tab_usage._format_source_display`: `[i] p.XX  제X조, 절  (doc_id)` — 드롭다운 가독성 향상
- `tab_usage._format_search_result`: `score | p.XX | 제X조, 절 | doc_id` 형태로 개선
- PDF 뷰어 정보 표시: `doc_id | p.XX | 위치 | 파일명` 형태로 개선

### 진도 체크

- [x] `_format_source` 개선 (p.xx, 제x조, 절, 항)
- [x] 출처 드롭다운/답변 표시에 적용
- [x] 수동 검증 완료

---

## Phase 10: V2 통합 검증 및 문서화

### 목표

V2 성공 기준을 충족하는지 검증하고, 문서를 정리한다.

### V2 성공 기준 (goal_v2.md §9)

- 모델 선택 후 질문 → 답변 생성
- 검색 결과 충분히 가시화
- 기존 index에 chunk 추가 가능
- 출처 가독성 있는 표시 (제X조, 절, 항)
- 전체 DB 재생성 없이 관리 가능

### 작업 내용

1. **통합 검증**

- 위 5개 항목 수동 테스트

2. **문서 작성**

- `readme.md` 갱신 (V2 전체 구조, 출처 표시 형태, 디렉터리 구조 반영)
- `phase_v2.md` 진도 반영

### Phase 10에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `readme.md` | V2 구조 반영 |
| `phase_v2.md` | 진도 반영 |

### 완료 내용

- `readme.md` 전면 갱신: V2 Phase 1~10 완료 현황, 주요 기능표, 디렉터리 구조, 출처 표시 형태, 문서 목록
- V2 성공 기준 5개 항목 달성 확인
- `phase_v2.md` 모든 Phase 진도 반영 완료

### 진도 체크

- [x] 모델 선택 후 질문 → 답변 생성 확인
- [x] 검색 결과 가시화 확인
- [x] 증분 추가 확인
- [x] 출처 가독성 개선 (제X조, 절, 항 표시)
- [x] 전체 재생성 없이 관리 확인
- [x] readme 갱신
- [x] phase_v2.md 진도 반영

---

## 토큰 최소화 가이드

| Phase | 집중할 디렉터리/파일 | 참고 문서 |
|-------|----------------------|-----------|
| 1 | `src/` 전체, `src/db/` | goal_v2.md §8 |
| 2 | `src/db/db_manager.py`, `faiss_index.py`, `embedding_bge.py` | goal_v2.md §8.2 |
| 3 | `main_window.py`, `tab_usage.py`, `tab_db_create.py` | goal_v2.md §3 |
| 4 | `tab_usage.py`, `ollama_client.py`, `rag_pipeline.py` | goal_v2.md §4 |
| 5 | `tab_usage.py`, `rag_pipeline.py` | goal_v2.md §4.2 |
| 6 | `tab_usage.py`, `tab_review.py` | goal_v2.md §4.2 6️⃣ |
| 7 | `tab_db_create.py`, `core/`, `tab_review.py` | goal_v2.md §5 |
| 8 | `db_manager.py`, `tab_db_create.py` | goal_v2.md §6.1 |
| 9 | rag_pipeline.py, tab_usage.py | phase_v2.md Phase 9 |
| 10 | `docs/`, `readme.md`, `phase_v2.md` | goal_v2.md §9 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
