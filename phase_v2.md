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
| 1 | 프로젝트 구조 리팩토링 — core/rag/db_manager/ui 분리 강화 | ☐ |
| 2 | DB Manager 모듈 신설 (load/save/append/remove/rebuild) | ☐ |
| 3 | 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개로 재구성 | ☐ |
| 4 | 사용 탭 — 모델 관리, 질문 & 검색 영역 | ☐ |
| 5 | 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역 | ☐ |
| 6 | 사용 탭 — 출처 영역 (PDF 뷰어 연동) | ☐ |
| 7 | DB 생성 탭 — 파이프라인 통합 (PDF→텍스트→Chunk→임베딩) | ☐ |
| 8 | 증분 임베딩 (Incremental Embedding) | ☐ |
| 9 | Chunk 단위 삭제 기능 | ☐ |
| 10 | V2 통합 검증 및 문서화 | ☐ |

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

- [ ] `src/db/` 디렉터리 생성
- [ ] core/rag/llm/ui 모듈 역할 분리 확인
- [ ] 기존 import 경로 동작 확인
- [ ] 수동 검증 완료

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

- [ ] load_index, save_index 구현
- [ ] append_chunks 구현 (기존 index + new vectors)
- [ ] remove_chunks 구현 (제외 후 재구성)
- [ ] rebuild_index 구현
- [ ] index ↔ meta 동기화 확인
- [ ] 수동 검증 완료

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

- [ ] main_window 탭 2개로 변경
- [ ] tab_usage.py, tab_db_create.py 스켈레톤 생성
- [ ] 기존 탭 로직 보존(임시 import 또는 복사)
- [ ] 수동 검증 완료

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

- [ ] 모델 목록 표시, 선택 UI
- [ ] 모델 로드 상태 표시
- [ ] 질문 입력 영역 (대형 텍스트 박스)
- [ ] Top-k 조절
- [ ] 검색 / 답변 생성 버튼
- [ ] 수동 검증 완료

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

- [ ] 검색 결과 리스트 (점수, section, article, page, preview)
- [ ] 선택 시 상세 보기
- [ ] 조합 컨텍스트 영역 (길이, 그룹 구분)
- [ ] 답변 영역 (충분한 크기)
- [ ] 출처 분리 표시
- [ ] 수동 검증 완료

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

- [ ] 출처 클릭 이벤트
- [ ] PDF 뷰어 영역 (페이지 렌더링)
- [ ] 출처 → page → PDF 표시 연동
- [ ] 수동 검증 완료

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
| `src/ui/tabs/tab_review.py` | 검수 UI 로직 통합 또는 재사용 |
| `src/ui/main_window.py` | app_state 등 공유 상태 |

### 수동 검증 방법

1. DB 생성 탭에서 PDF Import → Extract → Parse → Chunk → 임베딩까지 일련의 흐름으로 실행 가능한지 확인
2. 검수 기능이 통합되어 있는지 확인
3. 생성된 index, meta 파일이 정상적으로 저장되는지 확인

### 진도 체크

- [ ] PDF → 텍스트 추출 구역 (Import, Extract, Parse)
- [ ] 검수 구역 (PDF·JSONL 뷰, 수정·저장)
- [ ] Chunk 생성 구역
- [ ] 임베딩 생성 구역
- [ ] 파이프라인 흐름 연동
- [ ] 수동 검증 완료

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

- DB 생성 탭에 "기존 인덱스에 추가" 옵션
- 기존 index 경로, meta 경로 선택
- 추가할 chunk JSONL 선택
- [추가] 버튼

3. **db_manager 연동**

- `append_chunks()` 활용

### Phase 8에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/db/db_manager.py` | append_chunks (Phase 2에서 구현) |
| `src/ui/tabs/tab_db_create.py` | 증분 추가 UI |
| `src/core/embedding_bge.py` | batch encode |

### 수동 검증 방법

1. 기존 index가 있는 상태에서 새 chunk JSONL 추가
2. 추가 후 검색 시 기존 + 새 chunk가 모두 검색되는지 확인
3. meta.jsonl에 새 chunk가 append되었는지 확인

### 진도 체크

- [ ] append_chunks 동작 확인
- [ ] "기존 인덱스에 추가" UI
- [ ] index + meta 동기화
- [ ] 수동 검증 완료

---

## Phase 9: Chunk 단위 삭제 기능

### 목표

특정 chunk를 선택 후 DB에서 제거할 수 있게 한다.

### 작업 내용

1. **기술적 구현**

- FAISS IndexFlatIP는 개별 벡터 삭제 미지원
- 전략: 삭제 대상 ID 제외 → 새 index 재구성 → 저장
- `db_manager.remove_chunks()` 활용

2. **UI**

- 전체 chunk 리스트 보기 (meta에서 로드)
- 필터 (doc_id, section 등)
- 선택 삭제 (다중 선택 가능)
- [삭제 후 재구성] 버튼

3. **확인**

- 삭제 전 확인 다이얼로그
- 삭제 후 index, meta 자동 저장

### Phase 9에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/db/db_manager.py` | remove_chunks (Phase 2에서 구현) |
| `src/ui/tabs/tab_db_create.py` | Chunk 리스트, 필터, 삭제 UI |

### 수동 검증 방법

1. Chunk 리스트에서 특정 chunk 선택 후 삭제
2. 삭제 후 해당 chunk가 검색 결과에서 제외되는지 확인
3. index와 meta가 동기화된 상태로 유지되는지 확인

### 진도 체크

- [ ] Chunk 리스트 표시 (meta 기반)
- [ ] doc_id, section 필터
- [ ] 선택 삭제, 재구성
- [ ] 삭제 확인 다이얼로그
- [ ] 수동 검증 완료

---

## Phase 10: V2 통합 검증 및 문서화

### 목표

V2 성공 기준을 충족하는지 검증하고, 문서를 정리한다.

### V2 성공 기준 (goal_v2.md §9)

- 모델 선택 후 질문 → 답변 생성
- 검색 결과 충분히 가시화
- 기존 index에 chunk 추가 가능
- chunk 선택 후 삭제 가능
- 전체 DB 재생성 없이 관리 가능

### 작업 내용

1. **통합 검증**

- 위 5개 항목 수동 테스트
- 테스트 시나리오 문서화

2. **문서 작성**

- `docs/v2_migration.md`: V1 → V2 변경 사항, 사용법
- `docs/v2_phase_summary.md`: Phase별 완료 내용 요약
- `readme.md` 갱신 (V2 구조 반영)

3. **커밋 정리**

- Phase 단위 또는 기능 단위로 커밋

### Phase 10에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `docs/v2_migration.md` (신규) | V2 마이그레이션 가이드 |
| `docs/v2_phase_summary.md` (신규) | Phase 완료 요약 |
| `readme.md` | V2 구조 반영 |
| `phase_v2.md` | 진도 반영 |

### 수동 검증 방법

1. V2 성공 기준 5개 항목 각각 확인
2. 문서에 기술된 사용법대로 동작하는지 확인

### 진도 체크

- [ ] 모델 선택 후 질문 → 답변 생성 확인
- [ ] 검색 결과 가시화 확인
- [ ] 증분 추가 확인
- [ ] Chunk 삭제 확인
- [ ] 전체 재생성 없이 관리 확인
- [ ] docs 작성
- [ ] readme 갱신
- [ ] phase_v2.md 진도 반영

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
| 9 | `db_manager.py`, `tab_db_create.py` | goal_v2.md §6.2 |
| 10 | `docs/`, `readme.md`, `phase_v2.md` | goal_v2.md §9 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
