
**v3 설계문서 (Canonical + Raw 기반 아키텍처 전환)** 내용을 정리

---

# 설계문서 — V3 문서 Canonical 구조 기반 RAG 아키텍처

---

## 0. 범위 (Scope)

| 항목        | 내용                                      |
| --------- | --------------------------------------- |
| **목표**    | 문서 유형에 독립적인 Canonical 구조 기반 RAG 아키텍처 구축 |
| **대상 버전** | v3                                      |
| **입력 파일** | PDF (우선), 향후 Excel / CSV / 기타 문서 확장     |
| **중간 포맷** | Raw JSONL (파일 추출 공통 포맷)                 |
| **정규 포맷** | Canonical JSON (문서 의미 구조 포맷)            |
| **출력**    | Chunk JSONL → FAISS → RAG               |
| **UI 확장** | Raw/Canonical 검수 기능 추가                  |

---

# 1. 전체 아키텍처 개편 방향

## 1.1 기존 구조 (v2)

```
PDF
  → extract_pymupdf.py (라인 추출)
  → line_rebuild.py / normalize.py (라인 재조합)
  → parse_state_machine.py (path 태깅)
  → export_jsonl.py (JSONL 저장)
  → chunk_builder.py (Chunk 생성)
  → embedding_bge.py + faiss_index.py (임베딩/인덱스)
  → rag_pipeline.py (RAG)
```

문서 유형 종속적 구조

---

## 1.2 V3 구조

```
파일 (PDF / Excel / CSV ...)
      ↓
Extractor Layer (파일별)
      ↓
Raw JSONL (공통 추출 포맷)
      ↓
Structure Mapper (rule_*.py)
      ↓
Canonical JSON (문서 의미 구조)
      ↓
chunk_builder.py (Canonical 기반으로 수정)
      ↓
embedding_bge.py + faiss_index.py
      ↓
rag_pipeline.py
```

핵심 목표:

> 파일 포맷과 문서 의미 구조를 완전히 분리한다.

---

# 2. 단계별 개발 계획

---

# 2-1. 1단계 — Canonical JSON 구조 확정

## 2-1-1. 목적

* 모든 문서를 수용할 수 있는 문서 의미 구조 정의
* 문서 유형에 독립적인 RAG 기반 확보
* 출처 표기 자동화 기반 마련

---

## 2-1-2. Canonical JSON 스펙

```json
{
  "doc_id": "MOUS_RULE_2024",
  "doc_type": "regulation",

  "source": {
    "file_name": "이동식 해양구조물 규칙_2024.pdf",
    "organization": "KR",
    "version": "2024"
  },

  "location": {
    "physical_page": 7,
    "logical_page": 1
  },

  "structure": [
    { "level": 1, "type": "chapter", "label": "제 1 장 총칙" },
    { "level": 2, "type": "section", "label": "제 1 절 일반사항" },
    { "level": 3, "type": "article", "label": "제 101조" },
    { "level": 4, "type": "paragraph", "label": "1항" }
  ],

  "content": {
    "text": "이 규칙은 ... 적용한다.",
    "language": "ko"
  }
}
```

---

## 2-1-3. 설계 원칙

### ① 필수 필드

* doc_id
* doc_type
* content.text

### ② 선택 필드

* structure
* location
* organization
* version

※ 존재하지 않는 필드는 Null 대신 "생략" 권장

---

## 2-1-4. bbox 처리 방침

* bbox는 Canonical에서 제거
* Raw JSON 단계에서만 유지
* PDF 기반 하이라이트 기능 대비

---

## 2-1-5. 신규 개발 모듈

```
src/core/canonical_schema.py     # Canonical JSON 데이터클래스 / 검증
src/core/canonical_validator.py  # Canonical 스키마 검증 유틸
src/rag/citation_formatter.py    # 출처 문자열 자동 생성
```

---

# 2-2. 2단계 — Raw JSONL 중간 포맷 정의 및 PDF 변환

## 2-2-1. 목적

* 파일 형식 제거
* 텍스트 블록 중심 공통 구조 확보
* 미래 Excel/CSV 확장 대비

---

## 2-2-2. Raw JSONL 최소 스펙

```json
{
  "doc_id": "MOUS_RULE_2024",
  "source_type": "pdf",

  "block_id": 102,
  "block_type": "text",

  "page": 7,
  "text": "제 1 장 총칙",

  "bbox": [x0, y0, x1, y1],

  "style": {
    "font_size": 14,
    "bold": true,
    "indent": 0
  }
}
```

---

## 2-2-3. Raw 설계 원칙

* 최소 필드 고정

  * doc_id
  * source_type
  * block_id
  * block_type
  * text
* 나머지는 문서 유형별 확장 필드

예:

Excel:

```
row
column
sheet_name
```

CSV:

```
row_index
```

---

## 2-2-4. PDF → Raw 변환 개발

신규 모듈:

```
src/core/extract_pdf_raw.py   # PyMuPDF 기반 → Raw JSONL 변환 (기존 extract_pymupdf.py 대체)
src/core/raw_validator.py     # Raw JSONL 스키마 검증
```

기존 `extract_pymupdf.py`의 라인 추출 로직을 Raw 구조에 맞게 재작성

---

## 2-2-5. 검수 기능 추가 (중요)

### Raw 검수 (tab_db_create.py 내 ReviewDialog 확장)

* 좌측: PDF Viewer (기존 `tab_review.py`의 `_render_page_to_pixmap` 활용)
* 우측: Raw block 목록
* 클릭 시 bbox 하이라이트 (`tab_review.py`의 `_draw_bbox_on_pixmap` 활용)

### Canonical 검수

* 계층 Tree View
* 선택 시 해당 텍스트 표시

---

# 2-3. 3단계 — Canonical 기반 Chunk 및 FAISS 연동 수정

## 2-3-1. 기존 방식 변경

기존:

```
export_jsonl.py (JSONL) → chunk_builder.py
```

변경:

```
canonical_schema.py (Canonical JSON) → chunk_builder.py
```

---

## 2-3-2. Chunk 구조

```json
{
  "chunk_id": "MOUS_RULE_2024_101_1",
  "doc_id": "MOUS_RULE_2024",

  "text": "...",

  "metadata": {
    "structure_path": "제1장 > 제1절 > 제101조 > 1항",
    "physical_page": 7,
    "file_name": "이동식 해양구조물 규칙_2024.pdf"
  }
}
```

---

## 2-3-3. 수정 대상 모듈

```
src/core/chunk_builder.py      # Canonical 기반 Chunk 생성으로 수정
src/core/chunk_validate.py     # Canonical chunk 검증 추가
src/core/embedding_bge.py      # 인터페이스 유지 (변경 최소)
src/core/faiss_index.py        # 인터페이스 유지 (변경 최소)
src/rag/rag_pipeline.py        # 출처 표기 Canonical 구조 기반으로 개선
```

---

# 3. UI 확장 계획 (V3)

## 현재 탭 구조 (v2 완료 기준)

```
src/ui/tabs/
├── tab_usage.py       # 사용 탭 (모델/질문/검색/답변/PDF뷰어)
├── tab_db_create.py   # DB 생성 탭 (Import→Extract→Parse→Chunk→임베딩 통합)
└── tab_review.py      # 검수 뷰 유틸 (_render_page_to_pixmap, _draw_bbox_on_pixmap)
```

## V3 추가/수정 방향

### DB 생성 탭 확장 (`tab_db_create.py`)

* Raw JSONL 미리보기 단계 추가
* Raw → Canonical 변환 미리보기
* 기존 ReviewDialog에 Raw block bbox 하이라이트 추가

### 검수 기능 확장

* Raw View: block 단위 목록 + bbox 하이라이트
* Canonical Tree View: 계층 구조 탐색

---

# 4. V3 개발 순서

### Step 1

`canonical_schema.py` 작성 → Canonical JSON 구조 확정
→ 기존 문서 1개를 Canonical로 수동 변환하여 검증

### Step 2

`extract_pdf_raw.py` 작성
→ 기존 `extract_pymupdf.py` + `line_rebuild.py` + `normalize.py` 흐름을 Raw JSONL로 통합

### Step 3

`rule_marine_regulation.py` 작성
→ Raw JSONL → Canonical JSON 변환 (기존 `parse_state_machine.py` + `rules.py` 로직 활용)

### Step 4

`chunk_builder.py` Canonical 기반으로 수정
→ `chunk_validate.py` 검증 보완

### Step 5

FAISS 연동 테스트 → `rag_pipeline.py` 출처 표기 개선

---

# 5. 현재 디렉토리 구조 (v2 완료 기준)

```
RAG_app/
├── src/
│   ├── app.py
│   ├── core/
│   │   ├── chunk_builder.py        # Chunk 생성 (v3에서 Canonical 기반으로 수정)
│   │   ├── chunk_validate.py       # Chunk 검증
│   │   ├── embedding_bge.py        # bge-m3 임베딩
│   │   ├── equation_filter.py      # 수식 필터
│   │   ├── export_jsonl.py         # JSONL 저장/로드
│   │   ├── extract_pymupdf.py      # PDF 라인 추출 (v3에서 extract_pdf_raw.py로 대체)
│   │   ├── faiss_index.py          # FAISS 인덱스
│   │   ├── line_rebuild.py         # 라인 재조합
│   │   ├── normalize.py            # 텍스트 정규화
│   │   ├── parse_state_machine.py  # path 태깅 (v3에서 rule_*.py로 대체)
│   │   ├── rules.py                # 정규식 규칙 (chapter/section/article/paragraph)
│   │   ├── table_figure_filter.py  # 표·그림 필터
│   │   ├── table_figure_rules.py   # 표·그림 정규식 패턴
│   │   └── toc_detector.py         # 목차 감지
│   ├── db/
│   │   └── db_manager.py           # FAISS 인덱스 로드/저장/append/rebuild
│   ├── llm/
│   │   └── ollama_client.py        # Ollama API 클라이언트
│   ├── rag/
│   │   ├── chunk_assembler.py      # Chunk 재조합
│   │   ├── prompt_templates.py     # LLM 프롬프트 템플릿
│   │   ├── rag_config.py           # RAG 설정값
│   │   └── rag_pipeline.py         # RAG 파이프라인
│   └── ui/
│       ├── main_window.py          # 메인 윈도우 (탭 2개)
│       └── tabs/
│           ├── tab_usage.py        # 사용 탭 (모델/질문/검색/답변/PDF뷰어)
│           ├── tab_db_create.py    # DB 생성 탭 (통합 파이프라인 + 증분 임베딩)
│           └── tab_review.py       # 검수 뷰 유틸
├── scripts/
│   ├── debug_page7.py
│   ├── download_bge_m3.py
│   ├── test_db_manager.py
│   ├── test_extract_page7.py
│   ├── test_faiss.py
│   └── test_rag.py
├── docs/
│   ├── chunk_diagnosis.md
│   ├── ollama_setup.md
│   ├── phase17_llm_rag.md
│   ├── setup.md
│   └── test_scenarios.md
├── data/               # 원본 PDF
├── output/             # FAISS 인덱스, meta JSONL, 추출 JSONL
├── models/bge-m3/      # bge-m3 로컬 모델
├── readme.md
├── requirements.txt
├── goal_v2.md
├── goal_v3.md          # 이 문서
└── phase_v2.md
```

---

# 6. 향후 확장 전략 (V4 이후)

* 문서 유형 자동 분류
* rule plugin 시스템
* 구조 기반 검색 (예: "제303조만 검색")
* Hybrid 검색 (구조 + 벡터)
* 자동 계층 추론 (font_size, indent 활용)

---

# 7. V3 완료 기준 (Definition of Done)

* PDF → Raw JSONL 정상 생성 (`extract_pdf_raw.py`)
* Raw → Canonical 정상 변환 (`rule_marine_regulation.py`)
* Canonical → Chunk → FAISS 정상 동작
* 기존 RAG 기능 동일 동작
* 출처 표기: 장/절/조/페이지 자동 출력
* Raw/Canonical 검수 기능 동작

---

# 최종 정리

V3의 핵심은:

> 파일 포맷과 문서 의미 구조를 분리하는 아키텍처 전환

이 구조가 완성되면
자동파싱엔진은 "rule 추가" 문제로 단순화된다.

---



---

[V3 개발 핵심 원칙: Universal Structure & User-Centric Interface]
"문서의 형식(Format)으로부터 자유로운 범용 데이터 구조를 구축하고, 사용자에게는 시각적으로 확장된 최적의 분석 환경을 제공한다."

1. 범용성 중심의 아키텍처 (Universal Architecture)
- 고정 파싱 탈피: 특정 문서에 종속된 V2의 고정 구조를 버리고, 모든 문서(PDF, Excel, CSV 등)를 수용할 수 있는 Raw JSONL → Canonical JSON 단계별 정규화 체계를 구축한다.
- 의미 구조 분리: 파일 포맷과 문서의 의미적 구조를 완전히 분리하여, 어떤 데이터가 들어오더라도 동일한 RAG 파이프라인에서 처리될 수 있도록 설계한다.

2. 시각적 확장 및 UI 최적화 (Wide & Clear UI)
- 캔버스 확장: 기본 폼 사이즈를 1920x1080(FHD) 기준으로 확장하고, 모든 UI 요소에 충분한 여백을 확보하여 시각적 답답함을 해소한다.
- 정보 가시성 확보: 2~3줄로 제한되었던 텍스트 영역을 대폭 확장하고, 필요한 경우 탭(Tab) 구조를 적극 활용하여 스크롤을 최소화 하여여 핵심 정보를 한눈에 파악할 수 있게 구성한다. [cite: 0, 2-2-5]
- 검수 기능 강화: Raw 데이터와 Canonical 데이터를 대조하는 검수 뷰는 화면 분할(Split View) 등을 활용하여 데이터 흐름을 직관적으로 확인할 수 있어야 한다. [cite: 0, 2-2-5]

---