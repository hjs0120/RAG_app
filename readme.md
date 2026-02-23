# RAG_app — PDF 규격문서 RAG 워크벤치

PySide6 기반 데스크톱 앱. PDF 규격문서에서 텍스트를 추출하고, Chunk 생성·임베딩·FAISS 검색을 거쳐 **Ollama LLM**과 연동하여 RAG 답변을 생성한다.

---

## V3 개발 현황 (진행 중)

> V3 핵심 방향: **파일 포맷과 문서 의미 구조를 분리**하는 Canonical 기반 아키텍처 전환

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | Canonical Schema 확정 — 데이터클래스, 검증, 출처 포매터 | [x] |
| 2 | PDF → Raw JSONL 변환 모듈 (`extract_pdf_raw.py`) | [x] |
| 3 | Raw → Canonical 변환 규칙 (`rule_marine_regulation.py`) | [x] |
| 4 | Chunk 모듈 Canonical 기반으로 수정 (`chunk_builder.py`) | [x] |
| 5 | FAISS 연동 및 RAG 파이프라인 출처 표기 개선 | [x] |
| 6 | DB 생성 탭 UI 확장 — Raw/Canonical 미리보기 + 검수 기능 | [ ] |
| 7 | V3 통합 검증 및 문서화 | [ ] |

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

## 주요 기능

| 기능 | 설명 |
|------|------|
| PDF Import | PDF 선택, doc_id 지정, 차례 이후 추출 옵션 |
| Extract | PyMuPDF 라인 추출 (표/그림/수식 제외, 머릿말/꼬리말 필터) |
| Parse | Path 태깅 (chapter/section/article/paragraph), 장·절 제목 병합 |
| 검수 | PDF·JSONL 좌우 분할 뷰, 라인 네비게이션, 수정·저장 |
| Chunk 생성 | RAG용 Chunk JSONL (Merge/Split 규칙, min_chunk_len 필터) |
| 임베딩 | bge-m3 임베딩, FAISS IndexFlatIP 저장 |
| 증분 임베딩 | 기존 인덱스에 새 Chunk JSONL 추가 (AppendWorker 비동기) |
| **RAG** | 질문 → FAISS 검색 → Chunk 재조합 → Ollama 답변 (출처 p.XX, 제X조 형태) |
| PDF 뷰어 | 출처 선택 시 해당 PDF 페이지 표시 (물리 페이지 기준, 뷰포트 너비 맞춤) |

---

## 실행

```bash
pip install -r requirements.txt
python src/app.py
```

**RAG 사용 전 준비**

1. DB 생성 탭에서 PDF → Extract → Parse → Chunk → 임베딩 순서로 실행  
   → `output/rules.index`, `output/rules_meta.jsonl` 생성
2. [Ollama](https://ollama.com) 설치 및 실행
3. 모델 다운로드: `ollama pull qwen2.5:7b-instruct`
4. bge-m3 모델 다운로드: 사용 탭 → [다운로드] 버튼 또는 `python scripts/download_bge_m3.py`

---

## 디렉터리 구조

```
RAG_app/
├── src/
│   ├── app.py
│   ├── core/
│   │   ├── canonical_schema.py       # [V3] Canonical JSON 데이터클래스
│   │   ├── canonical_validator.py    # [V3] Canonical 스키마 검증
│   │   ├── extract_pdf_raw.py        # [V3] PDF → Raw JSONL 변환
│   │   ├── raw_validator.py          # [V3] Raw JSONL 스키마 검증
│   │   ├── rule_marine_regulation.py # [V3] Raw → Canonical 변환 규칙
│   │   ├── chunk_builder.py          # Chunk 생성 (V3에서 Canonical 기반으로 수정)
│   │   ├── chunk_validate.py         # Chunk 검증
│   │   ├── embedding_bge.py          # bge-m3 임베딩
│   │   ├── faiss_index.py            # FAISS 인덱스
│   │   ├── rules.py                  # 정규식 규칙 (chapter/section/article/paragraph)
│   │   ├── table_figure_filter.py    # 표·그림 필터
│   │   ├── table_figure_rules.py     # 표·그림 정규식 패턴
│   │   ├── equation_filter.py        # 수식 필터
│   │   ├── export_jsonl.py           # JSONL 저장/로드
│   │   ├── line_rebuild.py           # 라인 재조합
│   │   ├── normalize.py              # 텍스트 정규화
│   │   └── toc_detector.py           # 목차 감지
│   ├── rag/
│   │   ├── citation_formatter.py     # [V3] 출처 문자열 자동 생성
│   │   ├── rag_pipeline.py           # RAG 파이프라인
│   │   ├── chunk_assembler.py        # Chunk 재조합
│   │   ├── prompt_templates.py       # LLM 프롬프트 템플릿
│   │   └── rag_config.py             # RAG 설정값
│   ├── db/                           # DB Manager (인덱스 로드/저장/append/rebuild)
│   ├── llm/                          # Ollama 클라이언트
│   └── ui/
│       └── tabs/
│           ├── tab_usage.py          # 사용 탭 (모델/질문/검색/답변/PDF뷰어)
│           ├── tab_db_create.py      # DB 생성 탭 (파이프라인 + 증분 임베딩)
│           └── tab_review.py         # 검수 뷰 유틸
├── data/              # 원본 PDF
├── output/            # FAISS 인덱스, meta JSONL
├── models/            # bge-m3 로컬 모델
├── scripts/           # download_bge_m3.py 등
├── docs/              # 설정/설명 문서
├── goal_v2.md
├── goal_v3.md
├── phase_v2.md
└── phase_v3.md
```

> `[V3]` 표시 항목은 V3 신규 개발 모듈 (현재 미생성, Phase 진행에 따라 추가됨)

---

## 출처 표시 형태 (V2)

- 답변 내 출처: `[1] doc_id, p.13, 제301조, 제 3 절 검사, chunk_id=...`
- 드롭다운: `[1] p.13  제301조, 제 3 절 검사  (doc_id)`
- 검색 결과: `[1] score=0.8234 | p.13 | 제301조, 제 3 절 검사 | doc_id`

> 페이지 번호는 PDF 물리 페이지 기준. 표지·목차가 없는 PDF를 사용하면 문서 인쇄 페이지와 일치한다.

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

- **경로**: `data/이동식 해양구조물 규칙_2024.pdf`
- **인덱스**: `output/rules.index`, `output/rules_meta.jsonl`
