# RAG_app V3 — Canonical + Raw 기반 아키텍처 전환 단계별 개발 계획

## 개요

- **기반 문서**: `goal_v3.md`
- **목표**: V2 문서 종속 구조 → Canonical 기반 범용 RAG 아키텍처 전환
- **핵심 방향**: Raw JSONL 중간 포맷 도입 + Canonical JSON 정규화 + UI 시각적 확장

---

## UI 프레임워크

- **PySide6** (Qt for Python 6) 기반 — V2 유지
- 기본 폼 사이즈: **1920×1080 (FHD) 기준** 확장 (goal_v3.md §2. 핵심 원칙)
- 텍스트 영역 대폭 확장, 탭(Tab) 구조 적극 활용, 스크롤 최소화

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024-7-92.pdf`
- **기존 인덱스**: `output/rules.index`, `output/rules_meta.jsonl`

---

## Python 가상환경

- **권장 환경**: Conda 가상환경 `PySide6`
- **Python 경로 예시**: `D:\001. Anaconda\PySide6\python.exe` (설치 경로에 따라 상이)
- **Cursor 기본 인터프리터**: `.vscode/settings.json`의 `python.defaultInterpreterPath`에 위 경로 지정 — 미설정 시 base anaconda 사용됨

### 테스트 실행

```powershell
# 방법 1: conda 활성화 후 실행
conda activate PySide6
python scripts/test_chunk_canonical_phase4.py
python scripts/test_rag_canonical_phase5.py

# 방법 2: Python 경로 직접 지정
& "D:\001. Anaconda\PySide6\python.exe" scripts/test_rag_canonical_phase5.py
```

### 주요 의존성 (PySide6 환경 기준)

- **PySide6** — UI
- **PyMuPDF** — PDF 추출
- **faiss** — 벡터 검색 (conda 설치, GPU 버전 가능)
- **sentence-transformers** — BGE 임베딩

---

## Phase 진도 요약

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | Canonical Schema 확정 — 데이터클래스, 검증, 출처 포매터 | [x] |
| 2 | PDF → Raw JSONL 변환 모듈 (`extract_pdf_raw.py`) | [x] |
| 3 | Raw → Canonical 변환 규칙 (`rule_marine_regulation.py`) | [x] |
| 4 | Chunk 모듈 Canonical 기반으로 수정 (`chunk_builder.py`) | [x] |
| 5 | FAISS 연동 및 RAG 파이프라인 출처 표기 개선 | [x] |
| 6 | DB 생성 탭 UI 확장 — Raw/Canonical 미리보기 + 검수 기능 | [ ] |
| 7 | V3 통합 검증 및 문서화 | [ ] |

각 Phase의 **진도 체크** 항목을 검증 후 `[ ]` → `[x]`로 바꾸고, 위 표의 완료도 필요 시 ☑로 갱신하면 된다.

**각 Phase 완료 시** 해당 Phase 끝의 **커밋 메시지**를 참고하여 커밋을 정리한다.

---

## Phase 1: Canonical Schema 확정

### 목표

모든 문서를 수용할 수 있는 Canonical JSON 구조를 코드로 확정하고, 출처 자동 생성 기반을 마련한다.

### 작업 내용

1. **`src/core/canonical_schema.py` 신규 생성**

   - `CanonicalSource`, `CanonicalLocation`, `CanonicalStructureItem`, `CanonicalContent` 데이터클래스 정의
   - `CanonicalRecord` 최상위 클래스 — `doc_id`, `doc_type`, `source`, `location`, `structure`, `content`
   - `to_dict()` / `from_dict()` 직렬화 메서드
   - 필수 필드: `doc_id`, `doc_type`, `content.text`
   - 선택 필드: `structure`, `location`, `source.organization`, `source.version`

   ```json
   {
     "doc_id": "MOUS_RULE_2024",
     "doc_type": "regulation",
     "source": {
       "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
       "organization": "KR",
       "version": "2024"
     },
     "location": { "physical_page": 7 },
     "structure": [
       { "level": 1, "type": "chapter", "label": "제 1 장 총칙" },
       { "level": 3, "type": "article", "label": "제 101조" }
     ],
     "content": { "text": "이 규칙은 ... 적용한다.", "language": "ko" }
   }
   ```

2. **`src/core/canonical_validator.py` 신규 생성**

   - 필수 필드 존재 여부 검사
   - `structure` level 순서 검증
   - 유효하지 않은 레코드 리스트 반환

3. **`src/rag/citation_formatter.py` 신규 생성**

   - `format_citation(record: CanonicalRecord) → str`
   - 출력 예: `"p.7, 제 1 장 총칙 > 제 101조"`
   - `structure` 없을 경우 `"p.7"` 단독 반환

4. **수동 변환 검증**

   - 기존 문서(`이동식 해양구조물 규칙_2024-7-92.pdf`)의 레코드 10개를 Canonical로 수동 작성
   - `canonical_validator`로 검증 통과 여부 확인

### Phase 1에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/canonical_schema.py` (신규) | Canonical JSON 데이터클래스 |
| `src/core/canonical_validator.py` (신규) | 스키마 검증 유틸 |
| `src/rag/citation_formatter.py` (신규) | 출처 문자열 자동 생성 |

### 수동 검증 방법

1. `canonical_schema.CanonicalRecord.from_dict(...)` → `to_dict()` 왕복 직렬화 확인
2. `canonical_validator.validate(records)` → 오류 없이 통과 확인
3. `citation_formatter.format_citation(record)` → `"p.7, 제 1 장 총칙 > 제 101조"` 형태 출력 확인

### 진도 체크

- [x] `canonical_schema.py` 데이터클래스 작성
- [x] `from_dict` / `to_dict` 직렬화 구현
- [x] `canonical_validator.py` 필수 필드 검증 구현
- [x] `citation_formatter.py` 출처 포매터 구현
- [x] 수동 변환 10개 레코드 검증 통과
- [x] 수동 검증 완료

### Phase 1 완료 시 커밋

```
feat(core): Phase 1 — Canonical Schema 확정

- canonical_schema, canonical_validator, citation_formatter 신규
```

---

## Phase 2: PDF → Raw JSONL 변환 모듈

### 목표

PDF에서 블록 단위 Raw JSONL을 생성하는 모듈을 작성한다. 기존 `extract_pymupdf.py`의 추출 로직을 Raw 구조로 재구성하여 파일 포맷 독립성을 확보한다.

### 작업 내용

1. **`src/core/extract_pdf_raw.py` 신규 생성**

   - `extract_raw(pdf_path, doc_id, after_toc, exclude_header_footer, ...) → list[dict]`
   - 각 블록을 Raw JSONL 스펙으로 반환:

   ```json
   {
     "doc_id": "MOUS_RULE_2024",
     "source_type": "pdf",
     "block_id": 102,
     "block_type": "text",
     "page": 7,
     "text": "제 1 장 총칙",
     "bbox": [50.0, 100.0, 400.0, 120.0],
     "style": { "font_size": 14.0, "bold": true, "indent": 0 }
   }
   ```

   - 기존 `extract_pymupdf.py` + `line_rebuild.py` + `normalize.py` 로직 통합
   - 머릿말/꼬리말 필터, 수식 필터, 표·그림 필터 옵션 유지
   - `toc_detector`로 본문 시작 페이지 감지 → `after_toc` 옵션 유지
   - `bbox` 필드 보존 (Canonical 변환 후에는 제거, Raw 단계에서만 유지)

2. **`src/core/raw_validator.py` 신규 생성**

   - 필수 필드 (`doc_id`, `source_type`, `block_id`, `block_type`, `text`) 존재 여부 검사
   - 유효하지 않은 블록 목록 반환

3. **기존 파일 처리 방침**

   - `extract_pymupdf.py` — `tab_db_create.py`에서 즉시 교체 대상. Phase 6 UI 연동 전까지 병행 유지 가능
   - `line_rebuild.py`, `normalize.py` — `extract_pdf_raw.py` 내부에서 직접 호출, 독립 노출 불필요

### Phase 2에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/extract_pdf_raw.py` (신규) | PDF → Raw JSONL 변환 |
| `src/core/raw_validator.py` (신규) | Raw JSONL 스키마 검증 |
| `src/core/extract_pymupdf.py` | 참조용 유지 (Phase 6 교체 시 삭제) |
| `src/core/line_rebuild.py` | 내부 호출로 전환 |
| `src/core/normalize.py` | 내부 호출로 전환 |
| `src/core/toc_detector.py` | `after_toc` 감지 재사용 |

### 수동 검증 방법

1. `extract_raw("이동식 해양구조물 규칙_2024-7-92.pdf", doc_id="MOUS_RULE_2024")` 실행
2. 반환된 블록 리스트에 `bbox`, `style.font_size`, `block_id` 포함 여부 확인
3. `raw_validator.validate(blocks)` → 오류 없이 통과 확인
4. V2 `extract_pymupdf.py` 결과와 텍스트 내용 비교하여 누락 없는지 확인

### 진도 체크

- [x] `extract_pdf_raw.py` 기본 블록 추출 구현
- [x] `bbox`, `style` 필드 포함 확인
- [x] `after_toc` 옵션 동작 확인
- [x] 머릿말/꼬리말, 수식, 표·그림 필터 옵션 구현
- [x] `raw_validator.py` 구현
- [x] V2 추출 결과와 텍스트 비교 검증
- [x] 수동 검증 완료

### Phase 2 완료 시 커밋

```
feat(core): Phase 2 — PDF → Raw JSONL 변환 모듈

- extract_pdf_raw, raw_validator 신규
```

---

## Phase 3: Raw → Canonical 변환 규칙 (`rule_marine_regulation.py`)

### 목표

Raw JSONL을 Canonical JSON으로 변환하는 규칙 모듈을 작성한다. 기존 `parse_state_machine.py` + `rules.py`의 로직을 Canonical 구조에 맞게 재구성한다.

### 작업 내용

1. **`src/core/rule_marine_regulation.py` 신규 생성**

   - `map_to_canonical(raw_blocks: list[dict], source_meta: dict) → list[CanonicalRecord]`
   - 각 Raw 블록을 분석하여 `structure` 계층 추론:
     - `rules.classify_line(text)` 활용 — chapter/section/article/paragraph 분류
     - 현재까지 누적된 계층 스택(state machine 방식) 유지
   - `CanonicalRecord` 생성 시 `bbox` 제외 (Raw에서만 유지)
   - `structure_path` 문자열 자동 조합 (`citation_formatter` 활용)

2. **변환 흐름**

   ```
   Raw block
     → rules.classify_line(text) → kind (chapter/section/article/paragraph)
     → 계층 스택 갱신
     → CanonicalRecord(structure=현재_스택, content.text=text, location.physical_page=page)
   ```

3. **예외 처리**

   - 분류 불가 블록(`block_type="text"`, kind=None) → `structure` 필드 생략, `content.text`만 저장
   - 표·그림 캡션 블록 → `doc_type="caption"` 또는 구조에서 제외 (선택)

4. **기존 파일 처리 방침**

   - `parse_state_machine.py` — `rule_marine_regulation.py`로 대체. Phase 6 UI 연동 전까지 병행 유지 가능
   - `rules.py` — `rule_marine_regulation.py` 내부에서 재사용 (수정 불필요)

### Phase 3에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/rule_marine_regulation.py` (신규) | Raw → Canonical 변환 규칙 |
| `src/core/rules.py` | `classify_line` 재사용 |
| `src/core/canonical_schema.py` | `CanonicalRecord` 생성 |
| `src/rag/citation_formatter.py` | `structure_path` 조합 |
| `src/core/parse_state_machine.py` | 참조용 유지 (Phase 6 교체 시 삭제) |

### 수동 검증 방법

1. `map_to_canonical(raw_blocks, source_meta)` 실행
2. `CanonicalRecord.structure`에 chapter/section/article/paragraph 계층이 올바르게 채워지는지 확인
3. `canonical_validator.validate(canonical_records)` → 오류 없이 통과 확인
4. `citation_formatter.format_citation(record)` → `"p.7, 제 1 장 총칙 > 제 101조"` 형태 출력 확인
5. V2 `parse_state_machine.py` 결과와 구조 계층 비교

### 진도 체크

- [x] `map_to_canonical` 기본 구현
- [x] chapter/section/article/paragraph 계층 스택 상태머신 구현
- [x] 분류 불가 블록 예외 처리
- [x] `canonical_validator` 통과 확인
- [x] V2 파싱 결과와 구조 비교 검증
- [x] 수동 검증 완료

### Phase 3 완료 시 커밋

```
feat(core): Phase 3 — Raw → Canonical 변환 규칙

- rule_marine_regulation 신규, map_to_canonical 구현
```

---

## Phase 4: Chunk 모듈 Canonical 기반으로 수정

### 목표

`chunk_builder.py`가 Canonical JSON을 입력으로 받아 Chunk를 생성하도록 수정한다.

### 작업 내용

1. **`src/core/chunk_builder.py` 수정**

   - 기존 입력: `list[dict]` (V2 JSONL 레코드)
   - 변경 입력: `list[CanonicalRecord]` 또는 `list[dict]` (Canonical to_dict 변환 결과)
   - Chunk 메타 구조 변경:

   ```json
   {
     "chunk_id": "MOUS_RULE_2024_101_1",
     "doc_id": "MOUS_RULE_2024",
     "text": "...",
     "metadata": {
       "structure_path": "제1장 > 제1절 > 제101조 > 1항",
       "physical_page": 7,
       "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf"
     }
   }
   ```

   - `structure_path`: Canonical `structure` 계층에서 자동 조합 (`citation_formatter` 활용)
   - `physical_page`: `location.physical_page` 직접 사용
   - 기존 `min_chunk_len`, `target_len`, `max_len` 파라미터 유지

2. **`src/core/chunk_validate.py` 보완**

   - Canonical 기반 Chunk 필드 검증 추가
   - `chunk_id`, `doc_id`, `text`, `metadata.structure_path` 필수 확인

3. **하위 호환 고려**

   - V2 JSONL 레코드 형식도 입력 가능하도록 `from_legacy(records)` 변환 헬퍼 추가 (선택)
   - Phase 5~6 연동 전까지 V2 파이프라인 병행 가능하도록 설계

### Phase 4에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/chunk_builder.py` | Canonical 입력 지원으로 수정 |
| `src/core/chunk_validate.py` | Canonical chunk 필드 검증 추가 |
| `src/core/canonical_schema.py` | `CanonicalRecord` 참조 |
| `src/rag/citation_formatter.py` | `structure_path` 조합 |

### 수동 검증 방법

1. Phase 3 결과 `canonical_records`를 `build_chunks(canonical_records)` 에 입력
2. 생성된 Chunk에 `metadata.structure_path`, `metadata.physical_page` 포함 여부 확인
3. `chunk_validate.validate(chunks)` → 오류 없이 통과 확인
4. V2 Chunk 결과와 텍스트 내용 비교 (누락 없는지 확인)

### 진도 체크

- [x] `chunk_builder.py` Canonical 입력 처리 구현
- [x] `metadata.structure_path` 자동 조합 확인
- [x] `metadata.physical_page` 정확 반영 확인
- [x] `chunk_validate.py` 검증 보완
- [x] V2 결과와 Chunk 텍스트 비교 검증
- [x] 수동 검증 완료

### Phase 4 완료 시 커밋

```
feat(chunk): Phase 4 — Chunk 모듈 Canonical 기반 수정

- chunk_builder: CanonicalRecord/dict 입력 지원, 자동 형식 감지
- Chunk meta: structure_path, physical_page, file_name 자동 조합
- chunk_validate: Canonical Chunk 필드 검증 추가
- V2 JSONL 하위 호환 유지
- scripts/test_chunk_canonical_phase4.py 검증 스크립트 추가
```

---

## Phase 5: FAISS 연동 및 RAG 파이프라인 출처 표기 개선

### 목표

Canonical 기반 Chunk를 FAISS에 인덱싱하고, RAG 파이프라인의 출처 표기를 Canonical 구조 기반으로 개선한다. 기존 RAG 기능이 동일하게 동작하는지 검증한다.

### 작업 내용

1. **FAISS 연동 확인**

   - `faiss_index.build_index_from_chunks(chunks)` — Canonical Chunk 입력 시 동작 확인
   - 메타 저장 시 `metadata.structure_path`, `metadata.physical_page` 포함 확인
   - `embedding_bge.py` — 인터페이스 변경 없음 (텍스트 → 벡터 변환만 수행)

2. **`src/rag/rag_pipeline.py` 출처 표기 개선**

   - `_format_source(i, meta)` → `citation_formatter`를 활용하여 `structure_path` 기반 출처 문자열 생성
   - 출력 예: `"[1] MOUS_RULE_2024, p.7, 제 1 장 총칙 > 제 101조"`
   - 기존 `article`, `section`, `paragraph` 필드 기반 포맷도 하위 호환으로 유지

3. **기존 RAG 기능 동일 동작 확인**

   - 질문 → FAISS 검색 → Chunk 재조합 → Ollama 답변 흐름 전체 검증
   - V2 인덱스(기존 rules.index)와 V3 인덱스 모두 로드 가능해야 함

### Phase 5에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/core/faiss_index.py` | Canonical Chunk 메타 저장 확인 |
| `src/core/embedding_bge.py` | 인터페이스 유지 (변경 최소) |
| `src/rag/rag_pipeline.py` | 출처 표기 `structure_path` 기반 개선 |
| `src/rag/citation_formatter.py` | 출처 포매터 재사용 |
| `src/db/db_manager.py` | 인터페이스 유지 (변경 최소) |

### 수동 검증 방법

1. Phase 4 결과 Chunk로 `build_index_from_chunks()` 실행 → `rules.index`, `rules_meta.jsonl` 생성 확인
2. 사용 탭에서 질문 입력 → 검색 결과에 `structure_path` 출처 표시 확인
3. 답변 생성 후 출처 드롭다운에 `"p.7, 제 1 장 총칙 > 제 101조"` 형태 표시 확인
4. V2 기존 인덱스 로드 후 RAG 동작 확인 (하위 호환)

### 진도 체크

- [x] Canonical Chunk → FAISS 인덱스 생성 확인
- [x] `rag_pipeline._format_source` 개선 (`structure_path` 활용)
- [x] 출처 드롭다운/답변에 개선된 출처 표시 확인
- [x] 기존 V2 인덱스 하위 호환 동작 확인
- [x] 수동 검증 완료

### Phase 5 완료 시 커밋

```
feat(rag): Phase 5 — FAISS 연동 및 RAG 출처 표기 개선

- faiss_index: Canonical meta(physical_page) 지원
- citation_formatter: format_citation_from_meta(meta) 추가
- rag_pipeline: structure_path 기반 _format_source 개선
- tab_usage: _format_source_display, _format_location Canonical 대응
- chunk_assembler: structure_path 기반 그룹핑
- scripts/test_rag_canonical_phase5.py 검증 스크립트 추가
```

---

## Phase 6: DB 생성 탭 UI 확장 — Raw/Canonical 미리보기 + 검수 기능

### 목표

DB 생성 탭을 V3 파이프라인에 맞게 확장한다. Raw JSONL 미리보기, Raw → Canonical 변환 미리보기, bbox 하이라이트 검수 기능을 추가한다. FHD 기준 시각적 확장을 적용한다.

### 작업 내용

1. **`src/ui/tabs/tab_db_create.py` 파이프라인 교체**

   - Extract 단계: `extract_pymupdf.py` → `extract_pdf_raw.py` 교체
   - Parse 단계: `parse_state_machine.py` → `rule_marine_regulation.py` 교체
   - 기존 Extract/Parse 단계를 **Raw 추출** / **Canonical 변환** 단계로 UI 라벨 변경

2. **Raw JSONL 미리보기 추가**

   - Extract 완료 후 Raw block 목록 표시 (QListWidget 또는 QTreeWidget)
   - block_id, page, block_type, text 미리보기

3. **Canonical 미리보기 추가**

   - Canonical 변환 완료 후 계층 Tree View 표시 (QTreeWidget)
   - 선택 항목 → 우측에 `structure_path`, `content.text`, `location.physical_page` 표시

4. **검수 기능 확장 (`ReviewDialog` 수정)**

   - **Raw 검수**: 좌측 PDF Viewer + 우측 Raw block 목록
     - 블록 선택 시 `bbox` 영역 하이라이트 (`tab_review._draw_bbox_on_pixmap` 활용)
   - **Canonical 검수**: 계층 Tree View + 선택 항목 텍스트 표시
   - 검수 탭 전환: `QTabWidget`으로 Raw / Canonical 전환

5. **UI 시각적 확장 (goal_v3.md 핵심 원칙 §2)**

   - 앱 기본 크기 1920×1080 기준 설정
   - 텍스트 미리보기 영역 최소 4~6줄 이상 확보
   - 좌우 분할(QSplitter) 적극 활용, 스크롤 최소화

6. **구식 모듈 정리**

   - `extract_pymupdf.py` 삭제 (UI 연동 완료 후)
   - `parse_state_machine.py` 삭제 (UI 연동 완료 후)

### Phase 6에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `src/ui/tabs/tab_db_create.py` | V3 파이프라인 연동, Raw/Canonical 미리보기 UI |
| `src/ui/tabs/tab_review.py` | `_draw_bbox_on_pixmap`, `_render_page_to_pixmap` 재사용 |
| `src/core/extract_pdf_raw.py` | Extract 단계 교체 |
| `src/core/rule_marine_regulation.py` | Parse 단계 교체 |
| `src/core/extract_pymupdf.py` | 교체 완료 후 삭제 |
| `src/core/parse_state_machine.py` | 교체 완료 후 삭제 |
| `src/ui/main_window.py` | 앱 기본 크기 조정 |

### 수동 검증 방법

1. DB 생성 탭에서 PDF Import → Raw 추출 → Raw 미리보기 리스트 표시 확인
2. Canonical 변환 → Canonical Tree View에 계층 구조 표시 확인
3. 검수 창 열기 → Raw 탭에서 block 선택 시 PDF에 bbox 하이라이트 확인
4. Canonical 탭에서 항목 선택 시 텍스트 표시 확인
5. Chunk 생성 → 임베딩까지 전체 흐름 동작 확인
6. 앱 창이 FHD 기준으로 여유 있게 표시되는지 확인

### 진도 체크

- [ ] `tab_db_create.py` Extract 단계 → `extract_pdf_raw.py` 교체
- [ ] `tab_db_create.py` Parse 단계 → `rule_marine_regulation.py` 교체
- [ ] Raw JSONL 미리보기 리스트 구현
- [ ] Canonical Tree View 미리보기 구현
- [ ] `ReviewDialog` Raw 검수 탭 (bbox 하이라이트) 구현
- [ ] `ReviewDialog` Canonical 검수 탭 구현
- [ ] UI 시각적 확장 (FHD 기준, 텍스트 영역 확대)
- [ ] `extract_pymupdf.py` 삭제
- [ ] `parse_state_machine.py` 삭제
- [ ] 수동 검증 완료

### Phase 6 완료 시 커밋

```
feat(ui): Phase 6 — DB 생성 탭 Raw/Canonical 미리보기 + 검수

(완료 후 커밋 메시지 정리)
```

---

## Phase 7: V3 통합 검증 및 문서화

### 목표

V3 완료 기준(goal_v3.md §7)을 충족하는지 검증하고, 문서를 정리한다.

### V3 완료 기준 (goal_v3.md §7)

- PDF → Raw JSONL 정상 생성 (`extract_pdf_raw.py`)
- Raw → Canonical 정상 변환 (`rule_marine_regulation.py`)
- Canonical → Chunk → FAISS 정상 동작
- 기존 RAG 기능 동일 동작
- 출처 표기: 장/절/조/페이지 자동 출력 (`citation_formatter`)
- Raw/Canonical 검수 기능 동작

### 작업 내용

1. **통합 검증**

   - 위 완료 기준 6개 항목 수동 테스트
   - 실제 PDF(`이동식 해양구조물 규칙_2024-7-92.pdf`) 전체 파이프라인 실행
   - V2 결과와 V3 결과의 RAG 답변 품질 비교

2. **문서 작성**

   - `readme.md` 갱신 (V3 구조, 파이프라인 흐름, 디렉토리 구조 반영)
   - `phase_v3.md` 진도 반영
   - V3 완료 기준 디렉토리 구조:

   ```
   src/core/
   ├── canonical_schema.py       (신규)
   ├── canonical_validator.py    (신규)
   ├── extract_pdf_raw.py        (신규, extract_pymupdf.py 대체)
   ├── rule_marine_regulation.py (신규, parse_state_machine.py 대체)
   ├── raw_validator.py          (신규)
   ├── chunk_builder.py          (수정)
   ├── chunk_validate.py         (수정)
   ├── embedding_bge.py          (유지)
   ├── faiss_index.py            (유지)
   ├── rules.py                  (유지, rule_marine_regulation에서 재사용)
   ├── table_figure_filter.py    (유지)
   ├── table_figure_rules.py     (유지)
   ├── equation_filter.py        (유지)
   ├── line_rebuild.py           (유지, extract_pdf_raw 내부 사용)
   ├── normalize.py              (유지, extract_pdf_raw 내부 사용)
   └── toc_detector.py           (유지)
   src/rag/
   ├── citation_formatter.py     (신규)
   ├── rag_pipeline.py           (수정)
   ├── chunk_assembler.py        (유지)
   ├── prompt_templates.py       (유지)
   └── rag_config.py             (유지)
   ```

### Phase 7에서 다루는 소스

| 파일 | 내용 |
|------|------|
| `readme.md` | V3 구조 반영 |
| `phase_v3.md` | 진도 반영 |
| `goal_v3.md` | 필요 시 보완 |

### 수동 검증 방법

1. PDF → Raw → Canonical → Chunk → 임베딩 → RAG 전체 흐름 실행
2. 출처 표기에 `"p.7, 제 1 장 총칙 > 제 101조"` 형태 출력 확인
3. 검수 창에서 Raw bbox 하이라이트, Canonical Tree 탐색 동작 확인
4. V2 기존 인덱스로 RAG 동작 확인 (하위 호환)

### 진도 체크

- [ ] PDF → Raw JSONL 정상 생성 확인
- [ ] Raw → Canonical 정상 변환 확인
- [ ] Canonical → Chunk → FAISS 정상 동작 확인
- [ ] 기존 RAG 기능 동일 동작 확인
- [ ] 출처 표기 장/절/조/페이지 자동 출력 확인
- [ ] Raw/Canonical 검수 기능 동작 확인
- [ ] `readme.md` 갱신
- [ ] `phase_v3.md` 진도 반영

### Phase 7 완료 시 커밋

```
docs: Phase 7 — V3 통합 검증 및 문서화

(완료 후 커밋 메시지 정리)
```

---

## 토큰 최소화 가이드

| Phase | 집중할 디렉터리/파일 | 참고 문서 |
|-------|----------------------|-----------|
| 1 | `src/core/canonical_schema.py`, `canonical_validator.py`, `src/rag/citation_formatter.py` | goal_v3.md §2-1 |
| 2 | `src/core/extract_pdf_raw.py`, `raw_validator.py`, `extract_pymupdf.py` (참조) | goal_v3.md §2-2 |
| 3 | `src/core/rule_marine_regulation.py`, `rules.py`, `parse_state_machine.py` (참조) | goal_v3.md §2-3, §4 |
| 4 | `src/core/chunk_builder.py`, `chunk_validate.py` | goal_v3.md §2-3 |
| 5 | `src/core/faiss_index.py`, `src/rag/rag_pipeline.py`, `citation_formatter.py` | goal_v3.md §2-3, §7 |
| 6 | `src/ui/tabs/tab_db_create.py`, `tab_review.py` | goal_v3.md §3, 핵심 원칙 §2 |
| 7 | `readme.md`, `phase_v3.md` | goal_v3.md §7 |

매 Phase는 위 표에 해당하는 파일만 열어 작업하면 토큰 사용을 최소화할 수 있다.
