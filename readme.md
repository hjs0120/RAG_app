# RAG_app — PDF 규격문서 RAG 워크벤치

PySide6 기반 데스크톱 앱. PDF 규격문서에서 텍스트를 추출하고, Chunk 생성·임베딩·FAISS 검색을 거쳐 **Ollama LLM**과 연동하여 RAG 답변을 생성한다.

---

## V3 개발 현황 (완료)

> V3 핵심 방향: **파일 포맷과 문서 의미 구조를 분리**하는 Canonical 기반 아키텍처 전환

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | Canonical Schema 확정 — 데이터클래스, 검증, 출처 포매터 | [x] |
| 2 | PDF → Raw JSONL 변환 모듈 (`extract_pdf_raw.py`) | [x] |
| 3 | Raw → Canonical 변환 규칙 (`rule_marine_regulation.py`) | [x] |
| 4 | Chunk 모듈 Canonical 기반으로 수정 (`chunk_builder.py`) | [x] |
| 5 | FAISS 연동 및 RAG 파이프라인 출처 표기 개선 | [x] |
| 6 | DB 생성 탭 UI 확장 — Raw/Canonical 미리보기 + 검수 기능 | [x] |
| 7 | V3 통합 검증 및 문서화 | [x] |

---

## V2 개발 현황 (완료)

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | 프로젝트 구조 리팩토링 (core/rag/db/ui 분리) | ☑ |
| 2 | DB Manager 모듈 (load/save/append/remove/rebuild) | ☑ |
| 3 | 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개 | ☑ |
| 4 | 사용 탭 — 모델 관리, 질문 & 검색 | ☑ |
| 5 | 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역 | ☑ |
| 6 | 사용 탭 — 출처 영역, PDF 뷰어 연동 | ☑ |
| 7 | DB 생성 탭 — 통합 파이프라인 (PDF→Extract→Parse→Chunk→임베딩) | ☑ |
| 8 | 증분 임베딩 (기존 인덱스에 Chunk 추가) + 물리 페이지 단일 체계 정리 | ☑ |
| 9 | 출처 가독성 개선 (p.XX, 제X조, 절, 항 표시) | ☑ |
| 10 | V2 통합 검증 및 문서화 | ☑ |

---

## V3 파이프라인 흐름

```
PDF
  → extract_pdf_raw.py     (Raw JSONL 추출, block 단위)
  → rule_marine_regulation.py  (Raw → Canonical 변환)
  → chunk_builder.py       (Canonical 기반 Chunk 생성)
  → embedding_bge.py + faiss_index.py
  → rag_pipeline.py        (출처: structure_path 기반 "p.7, 제 1 장 총칙 > 제 101조")
```

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| PDF Import | PDF 선택, doc_id 지정, 차례 이후 추출 옵션 |
| Raw 추출 | `extract_pdf_raw` — PDF → Raw JSONL (block_id, page, block_type, text, bbox) |
| Canonical 변환 | `rule_marine_regulation` — Raw → Canonical (structure 계층: chapter/section/article/paragraph) |
| Raw/Canonical 검수 | Raw 탭: bbox 하이라이트. Canonical 탭: 계층 Tree + 상세 |
| Chunk 생성 | Canonical 기반 Chunk (structure_path, physical_page 메타) |
| 임베딩 | bge-m3 임베딩, FAISS IndexFlatIP 저장 |
| 증분 임베딩 | 기존 인덱스에 새 Chunk JSONL 추가 (AppendWorker 비동기) |
| **RAG** | 질문 → FAISS 검색 → Chunk 재조합 → Ollama 답변 (출처: p.XX, 제 X 장 > 제 N조 형태) |
| PDF 뷰어 | 출처 선택 시 해당 PDF 페이지 표시 (물리 페이지 기준, 뷰포트 너비 맞춤) |

---

## 실행

```bash
pip install -r requirements.txt
python src/app.py
```

**RAG 사용 전 준비**

1. DB 생성 탭에서 PDF → Raw 추출 → Canonical 변환 → Canonical JSONL 저장 → Chunk 생성 → 임베딩 순서로 실행  
   → `output/rules.index`, `output/rules_meta.jsonl` 생성
2. [Ollama](https://ollama.com) 설치 및 실행
3. 모델 다운로드: `ollama pull qwen2.5:7b-instruct`
4. bge-m3 모델 다운로드: 사용 탭 → [다운로드] 버튼 또는 `python scripts/download_bge_m3.py`

---

## 디렉터리 구조 (V3)

```
src/core/
├── canonical_schema.py       # Canonical JSON 데이터클래스
├── canonical_validator.py    # Canonical 스키마 검증
├── extract_pdf_raw.py        # PDF → Raw JSONL 변환 (extract_pymupdf 대체)
├── rule_marine_regulation.py # Raw → Canonical 변환 규칙 (parse_state_machine 대체)
├── raw_validator.py          # Raw JSONL 스키마 검증
├── chunk_builder.py          # Chunk 생성 (Canonical 기반)
├── chunk_validate.py         # Chunk 검증
├── embedding_bge.py          # bge-m3 임베딩
├── faiss_index.py            # FAISS 인덱스
├── rules.py                  # 정규식 규칙 (rule_marine_regulation에서 재사용)
├── table_figure_filter.py    # 표·그림 필터
├── table_figure_rules.py     # 표·그림 정규식 패턴
├── equation_filter.py        # 수식 필터
├── line_rebuild.py           # 라인 재조합 (extract_pdf_raw 내부 사용)
├── normalize.py              # 텍스트 정규화 (extract_pdf_raw 내부 사용)
├── toc_detector.py           # 목차 감지
└── export_jsonl.py           # JSONL 저장/로드

src/rag/
├── citation_formatter.py     # 출처 문자열 자동 생성 (structure_path 기반)
├── rag_pipeline.py           # RAG 파이프라인
├── chunk_assembler.py        # Chunk 재조합
├── prompt_templates.py       # LLM 프롬프트 템플릿
└── rag_config.py             # RAG 설정값

src/ui/tabs/
├── tab_usage.py              # 사용 탭 (모델/질문/검색/답변/PDF뷰어)
├── tab_db_create.py          # DB 생성 탭 (Raw→Canonical 파이프라인 + 검수 + Chunk + 임베딩)
└── tab_review.py             # 검수 뷰 유틸 (별도 탭)

data/                         # 원본 PDF
output/                       # FAISS 인덱스, meta JSONL, Canonical JSONL
models/                       # bge-m3 로컬 모델
scripts/                      # download_bge_m3.py, test_*_phase*.py 등
docs/                         # phase_v3.md, setup.md, ollama_setup.md 등
```

---

## 출처 표시 형태 (V3)

- 답변 내 출처: `[1] doc_id, p.7, 제 1 장 총칙 > 제 101조, chunk_id=...`
- 드롭다운: `[1] p.7  제 1 장 총칙 > 제 101조  (doc_id)`
- 검색 결과: `[1] score=0.82 | p.7 | 제 1 장 총칙 > 제 101조 | doc_id`

> V3는 `citation_formatter`로 `structure_path` 기반 출처를 자동 생성. 페이지는 PDF 물리 페이지 기준.

---

## 문서

| 문서 | 내용 |
|------|------|
| `phase_v3.md` | V3 Phase 1~7 단계별 개발 계획 및 진도 |
| `goal_v3.md` | V3 설계 목표 및 핵심 원칙 |
| `phase_v2.md` | V2 Phase 1~10 단계별 개발 계획 및 진도 |
| `goal_v2.md` | V2 설계 목표 |
| `docs/setup.md` | PyTorch CUDA, bge-m3 모델, FAISS 설정 |
| `docs/ollama_setup.md` | Windows Ollama 설치, 모델 다운로드, API 예시 |
| `docs/phase17_llm_rag.md` | RAG 구현 요약, Chunk 재조합/출처 규칙, FAQ |
| `docs/test_scenarios.md` | RAG 테스트 시나리오 5개 |

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024-7-92.pdf` (phase_v3.md 기준)
- **인덱스**: `output/rules.index`, `output/rules_meta.jsonl`
