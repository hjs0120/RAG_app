# RAG_app — 프로젝트 전체 개요 (V1 ~ V4)

이 문서는 **goal / goal_v2 / goal_v3 / goal_v4**와 **phase / phase_v2 / phase_v3 / phase_v4**를 통합하여, 프로젝트가 어떻게 구성되고 어떤 순서로 개발되었는지, 각 버전별로 어떤 기능이 있는지 한눈에 정리한 문서입니다.

---

## 1. 프로젝트가 하는 일

**RAG_app**은 **PDF 규격문서**에서 텍스트를 추출하고, Chunk 생성·임베딩·FAISS 검색을 거쳐 **Ollama LLM**과 연동하여 **RAG(Retrieval-Augmented Generation) 답변**을 생성하는 워크벤치입니다.

| 구분 | 내용 |
|------|------|
| **입력** | 규격 PDF (예: 이동식 해양구조물 규칙) |
| **중간** | 라인 추출 → 구조 파싱(장/절/조/항) → Chunk JSONL → bge-m3 임베딩 → FAISS 인덱스 |
| **출력** | 사용자 질문에 대한 답변 + 출처(장/절/조/페이지) |
| **UI** | PySide6 데스크톱 앱 (Admin) + V4부터 Web Client(브라우저 채팅) |

---

## 2. 버전별 개발 흐름 요약

| 버전 | 핵심 목표 | 주요 변화 |
|------|-----------|-----------|
| **V1** | 기술 검증(POC) | PDF 추출 → 파싱 → Chunk → 임베딩 → RAG 파이프라인 구축. 8개 탭(Import, Extract, Parse, Export, 검수, Chunk, 임베딩, RAG). |
| **V2** | 실사용 워크벤치 | UX 재설계. 탭 2개(사용 / DB 생성)로 통합. DB Manager(증분 임베딩, Chunk 삭제). 출처 PDF 뷰어. |
| **V3** | 문서 유형 독립 아키텍처 | Raw JSONL → Canonical JSON 단계 분리. 파일 포맷과 의미 구조 분리. 출처 자동 표기(structure_path). Raw/Canonical 검수. |
| **V4** | 서버·웹 확장 | FastAPI REST API 서버. Web Client(채팅 UI). 서버 서비스 탭. PDF 이미지 서빙·출처 팝업 뷰어. |

---

# Part I. V1 — PDF 규격문서 텍스트 추출 및 RAG 파이프라인

## V1 범위

| 항목 | 내용 |
|------|------|
| **입력** | 규격 PDF |
| **출력** | JSONL(라인) → Chunk JSONL → FAISS 인덱스 → RAG 답변 |
| **처리** | 차례 이후 본문부터 추출, Path(장/절/조/항) 태깅 |
| **UI** | PySide6, 다수 탭 + 그룹박스 |

## V1 파이프라인

```
PDF Import
  → 페이지별 텍스트 추출 (PyMuPDF)
  → 라인 재구성 (line rebuild)
  → 차례 구간 스킵
  → Path 태깅 (Chapter/Section/Article/Paragraph)
  → 표/그림/수식 필터
  → JSONL/CSV Export
  → Chunk 생성 (Merge/Split)
  → bge-m3 임베딩 → FAISS IndexFlatIP
  → RAG: 질문 임베딩 → 검색 → Chunk 재조합 → Ollama 답변
```

## V1 UI (탭 구조)

| 탭 | 기능 |
|----|------|
| 1. PDF Import | 파일 선택, doc_id, 출력 경로, "차례 이후부터" 옵션 |
| 2. Extract | PyMuPDF 라인 추출, 진행률, 결과 요약 |
| 3. Parse | Path 태깅(상태 머신), Path 미리보기 |
| 4. Export | JSONL/CSV, 필드 선택 |
| 5. 검수 | PDF·JSONL 좌우 분할, 라인 네비게이션, 수정·저장, bbox 표시 |
| 6. Chunk | Merge/Split 규칙, Chunk JSONL 생성 |
| 7. 임베딩 | bge-m3 임베딩, FAISS 저장, 검색 테스트 |
| 8. RAG | 질문 입력, 검색, 답변 생성, Top-k 결과, 출처 |

## V1 Phase 진도 (Phase 1~19)

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | 프로젝트 구조 및 의존성 설정 | ✅ |
| 2 | 탭 1 — PDF Import | ✅ |
| 3 | 탭 2 — PyMuPDF 라인 추출 | ✅ |
| 4 | 차례 스킵 및 본문 시작점 탐지 | ✅ |
| 5 | 탭 3 — Path 태깅(상태 머신) | ✅ |
| 6 | 탭 4 — JSONL/CSV Export | ✅ |
| 7 | 검수 탭 — PDF·JSONL 로드 및 좌우 분할 뷰 | ✅ |
| 8 | 검수 탭 — 라인 네비게이션 및 진행도 | ✅ |
| 9 | 검수 탭 — 수정 및 저장 | ✅ |
| 10 | 검수 탭 — PDF 뷰어 위 bbox 표시 | ✅ |
| 11 | 표·그림 감지 — 표제목/그림제목만 추출 | ✅ |
| 12 | 수식 제외, paragraph 페이지 단위 구분 | ✅ |
| 13 | Chunk 생성 탭 — RAG용 Chunk JSONL | ✅ |
| 14 | 임베딩 탭 — JSONL 임베딩, FAISS 저장 | ✅ |
| 15 | bge-m3 로컬·GPU 전환 | ✅ |
| 16 | Chunk 품질 개선 (paragraph "0" 분리 등) | ✅ |
| 17 | RAG 파이프라인 — Ollama 연동, Chunk 재조합, 출처 강제 | ✅ |
| 18 | RAG 탭 UI — 질문/검색/답변, 비동기 처리 | ✅ |
| 19 | RAG 문서화 및 테스트 | ✅ |

## V1 달성 기능

- PDF 선택, 차례 이후 추출 옵션
- PyMuPDF 기반 라인 추출 (text, bbox, page, line_no)
- Path 태깅 (장/절/조/항), JSONL/CSV 내보내기
- 검수 탭 (PDF·JSONL 대조, bbox 표시)
- Chunk 생성 (Merge/Split, 600/1000자)
- bge-m3 임베딩, FAISS IndexFlatIP 저장
- RAG: 질문 → FAISS 검색 → Chunk 재조합 → Ollama 답변, 출처 표시

---

# Part II. V2 — 사용성 중심 재설계 (실사용 워크벤치)

## V2 목표

- **V1**: 기술적으로 RAG가 동작함을 증명
- **V2**: "개발자 중심 도구" → "실사용 가능한 RAG 워크벤치" 전환  
  → **UX 재설계 + DB 관리 기능 확장**

## V2 핵심 방향

1. **UI 구조 전면 개편** — 다수 탭 → **2개 탭** (사용 / DB 생성)
2. **DB 관리 고도화** — 증분 임베딩, Chunk 단위 삭제, index/meta 동기화

## V2 탭 구조

```
[ 사용 탭 ]   — 모델 선택, 질문/검색/답변, 검색 결과, 조합 컨텍스트, 출처, PDF 뷰어
[ DB 생성 탭 ] — PDF→텍스트→Chunk→임베딩 통합 파이프라인 + 검수 + 증분 추가
```

## V2 Phase 진도 (Phase 1~10)

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | 프로젝트 구조 리팩토링 (core/rag/db/ui 분리) | ☑ |
| 2 | DB Manager (load/save/append/remove/rebuild) | ☑ |
| 3 | 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개 | ☑ |
| 4 | 사용 탭 — 모델 관리, 질문 & 검색 | ☑ |
| 5 | 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역 | ☑ |
| 6 | 사용 탭 — 출처 영역, PDF 뷰어 연동 | ☑ |
| 7 | DB 생성 탭 — 통합 파이프라인 (PDF→Extract→Parse→Chunk→임베딩) | ☑ |
| 8 | 증분 임베딩 (기존 인덱스에 Chunk 추가) | ☑ |
| 9 | 출처 가독성 개선 (p.XX, 제X조, 절, 항 표시) | ☑ |
| 10 | V2 통합 검증 및 문서화 | ☑ |

## V2 달성 기능

- **사용 탭**: Ollama 모델 목록/선택, 질문 입력, Top-k 검색, 답변 생성, 검색 결과 리스트(점수·section·page·preview), 조합 컨텍스트 표시, 출처 드롭다운, **출처 클릭 시 PDF 뷰어에 해당 페이지 표시**
- **DB 생성 탭**: Import → Extract → Parse → 검수 → Chunk → 임베딩 한 화면에서 순차 실행, **기존 인덱스에 Chunk 추가(증분 임베딩)**
- **DB Manager**: load_index, save_index, append_chunks, remove_chunks, rebuild_index
- **출처 표시**: p.XX, 제X조, 절, 항 형태로 가독성 개선

---

# Part III. V3 — Canonical + Raw 기반 아키텍처 전환

## V3 목표

- **문서 유형에 독립적인** RAG 아키텍처 구축
- **파일 포맷과 문서 의미 구조를 완전히 분리**
- Raw JSONL(공통 추출 포맷) → Canonical JSON(문서 의미 구조) → Chunk → FAISS → RAG
- UI 시각적 확장 (FHD 기준, Raw/Canonical 검수)

## V3 아키텍처

```
파일 (PDF / 향후 Excel, CSV 등)
      ↓
Extractor (파일별)
      ↓
Raw JSONL (공통 추출 포맷: doc_id, block_id, page, text, bbox, style)
      ↓
Structure Mapper (rule_*.py)
      ↓
Canonical JSON (doc_id, doc_type, structure[], location, content)
      ↓
chunk_builder.py (Canonical 기반)
      ↓
embedding_bge + faiss_index → rag_pipeline
```

## V3 Phase 진도 (Phase 1~7)

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | Canonical Schema 확정 — 데이터클래스, 검증, citation_formatter | [x] |
| 2 | PDF → Raw JSONL (`extract_pdf_raw.py`, `raw_validator.py`) | [x] |
| 3 | Raw → Canonical (`rule_marine_regulation.py`) | [x] |
| 4 | Chunk 모듈 Canonical 기반 수정 (`chunk_builder.py`) | [x] |
| 5 | FAISS 연동, RAG 출처 표기 개선 (structure_path 기반) | [x] |
| 6 | DB 생성 탭 — Raw/Canonical 미리보기, bbox 검수, Canonical Tree | [x] |
| 7 | V3 통합 검증 및 문서화 | [x] |

## V3 달성 기능

- **Canonical JSON**: doc_id, doc_type, source, location, structure(장/절/조/항), content
- **Raw JSONL**: block_id, page, block_type, text, bbox, style (파일 포맷 독립)
- **extract_pdf_raw.py**: PDF → Raw 블록 추출 (기존 extract_pymupdf + line_rebuild + normalize 통합)
- **rule_marine_regulation.py**: Raw → Canonical 변환 (기존 parse_state_machine + rules 로직 재구성)
- **출처 표기**: `citation_formatter`로 "p.7, 제 1 장 총칙 > 제 101조" 자동 생성
- **검수**: Raw 탭(bbox 하이라이트), Canonical 탭(계층 Tree + 상세)
- **UI**: FHD(1920×1080) 기준 확장, 텍스트 영역 확대

---

# Part IV. V4 — REST API 기반 서버·웹 확장

## V4 목표

- 로컬 RAG를 **REST API 서버**로 확장
- **브라우저에서 접근 가능한** Web Client(채팅 UI) 제공
- PySide6는 **서버 제어 패널(Admin)**, 실제 질의응답은 **Web Client**

## V4 아키텍처

```
사용자 (Web 브라우저)
  → Web Client (index.html) — fetch API
  → HTTP POST /api/ask
FastAPI 서버 (Uvicorn)
  → core/rag 로드 → FAISS + LLM
PySide6 Admin UI
  → [서버 서비스 탭] 서버 시작/중단, 설정, 로그
  → [사용 탭], [DB 생성 탭] 기존 유지
```

## V4 탭 구조

```
[ 서버 서비스 ] → [ 사용 ] → [ DB 생성 ]
     (메인 탭)      (기존)      (기존)
```

- **서버 서비스 탭**: 호스트/포트, [서버 시작]/[서버 중단], LED 상태, 실시간 로그
- **Web Client**: `http://127.0.0.1:8081/web_client/` — 채팅 UI, 출처 카드, 출처 클릭 시 **팝업으로 PDF 페이지 이미지** 표시

## V4 Phase 진도 (Phase 1~7)

| Phase | 내용 | 완료 |
|-------|------|:----:|
| 1 | FastAPI 앱, POST /api/ask, core/rag 연동 | [x] |
| 2 | Uvicorn 서브프로세스 제어 (server_manager.py) | [x] |
| 3 | 서버 서비스 탭 UI (설정/버튼/LED/로그) | [x] |
| 3-1 | 서버 시작 시 모델 사전 로드 (bge-m3, FAISS, Ollama) | [x] |
| 3-2 | 동시 요청 개수 제한 (큐 대기·순차 처리·거절 안내) | [x] |
| 4 | Web Client (채팅 UI, fetch API, 출처 카드) | [x] |
| 5 | PDF 이미지 서빙, 출처 클릭 시 팝업 뷰어 | [x] |
| 6 | main_window 탭 통합, 통합 테스트 | [x] |
| 7 | V4 통합 검증 및 문서화 | [x] |

## V4 달성 기능

- **API 서버**: FastAPI + Uvicorn, POST /api/ask (query, top_k → answer, sources), GET /health, CORS
- **서버 관리**: Admin UI에서 서버 시작/중단, 로그 파이프, 모델 사전 로드, 동시 요청 제한(거절/대기 안내)
- **Web Client**: HTML/JS 채팅 UI, 출처 카드 뷰, rejected/queued/success 처리
- **PDF 이미지**: `storage/pdf_images/{doc_id}/` 저장, `/view/images` 서빙, sources에 image_url, **출처 클릭 시 팝업으로 해당 페이지 이미지** 표시
- **DB 생성 탭**: 임베딩 완료 시 PDF→이미지 자동 export 연동

---

# Part V. 현재 프로젝트 구성

## 최종 디렉터리 구조

```
003.pdfdb/
├── src/
│   ├── app.py
│   ├── core/                    # 추출, 파싱, Chunk, 임베딩
│   │   ├── canonical_schema.py
│   │   ├── canonical_validator.py
│   │   ├── extract_pdf_raw.py   # PDF → Raw JSONL
│   │   ├── rule_marine_regulation.py  # Raw → Canonical
│   │   ├── raw_validator.py
│   │   ├── chunk_builder.py
│   │   ├── chunk_validate.py
│   │   ├── embedding_bge.py
│   │   ├── faiss_index.py
│   │   ├── pdf_to_images.py     # V4 PDF→이미지
│   │   ├── rules.py, toc_detector.py
│   │   ├── table_figure_*.py, equation_filter.py
│   │   ├── line_rebuild.py, normalize.py
│   │   └── export_jsonl.py
│   ├── db/
│   │   └── db_manager.py        # load/save/append/remove/rebuild
│   ├── llm/
│   │   └── ollama_client.py
│   ├── rag/
│   │   ├── citation_formatter.py
│   │   ├── rag_pipeline.py
│   │   ├── chunk_assembler.py
│   │   ├── prompt_templates.py
│   │   └── rag_config.py
│   ├── server/                 # V4
│   │   ├── api_server.py
│   │   └── server_manager.py
│   └── ui/
│       ├── main_window.py
│       └── tabs/
│           ├── tab_server_service.py  # V4
│           ├── tab_usage.py
│           ├── tab_db_create.py
│           └── tab_review.py
├── web_client/                 # V4
│   ├── index.html
│   ├── style.css
│   └── app.js
├── storage/pdf_images/         # V4 PDF 페이지 이미지
├── data/                       # 원본 PDF
├── output/                     # FAISS 인덱스, meta JSONL
├── models/                     # bge-m3
├── scripts/
├── docs/
│   ├── project_overview.md     # 이 문서
│   ├── goal.md, goal_v2.md, goal_v3.md, goal_v4.md
│   ├── phase.md, phase_v2.md, phase_v3.md, phase_v4.md
│   ├── v4_integrated.md
│   ├── setup.md, ollama_setup.md
│   ├── phase17_llm_rag.md, test_scenarios.md
│   └── chunk_diagnosis.md
├── readme.md
└── requirements.txt
```

## 기술 스택

| 구분 | 기술 |
|------|------|
| UI | PySide6 (Qt 6) |
| API 서버 | FastAPI |
| ASGI | Uvicorn |
| Web Client | HTML5, JavaScript (Vanilla), fetch API |
| PDF | PyMuPDF (fitz) |
| 임베딩 | sentence-transformers, bge-m3 |
| 벡터 DB | FAISS (IndexFlatIP) |
| LLM | Ollama (qwen2.5, llama 등) |

---

# Part VI. 기능 요약표 (버전별)

| 기능 | V1 | V2 | V3 | V4 |
|------|:--:|:--:|:--:|:--:|
| PDF Import, 차례 이후 추출 | ✅ | ✅ | ✅ | ✅ |
| 라인 추출 (PyMuPDF) | ✅ | ✅ | — | — |
| **Raw JSONL 추출** (block 단위) | — | — | ✅ | ✅ |
| Path 태깅 (장/절/조/항) | ✅ | ✅ | — | — |
| **Raw → Canonical 변환** | — | — | ✅ | ✅ |
| JSONL/CSV Export | ✅ | ✅ | ✅ | ✅ |
| 검수 (PDF·라인 대조, bbox) | ✅ | ✅ | — | — |
| **Raw/Canonical 검수** (bbox, Tree) | — | — | ✅ | ✅ |
| Chunk 생성 (Merge/Split) | ✅ | ✅ | ✅(Canonical 기반) | ✅ |
| bge-m3 임베딩, FAISS 저장 | ✅ | ✅ | ✅ | ✅ |
| **증분 임베딩** (기존 인덱스에 추가) | — | ✅ | ✅ | ✅ |
| **Chunk 삭제, index 재구성** | — | ✅ | ✅ | ✅ |
| RAG (질문→검색→Ollama 답변) | ✅ | ✅ | ✅ | ✅ |
| 출처 표시 (기본) | ✅ | ✅ | — | — |
| 출처 표시 **p.XX, 제X조, 절, 항** | — | ✅ | — | — |
| 출처 **structure_path** (장>절>조>항) | — | — | ✅ | ✅ |
| **사용 탭 / DB 생성 탭** 2개 구조 | — | ✅ | ✅ | ✅ |
| **출처 클릭 → PDF 뷰어** (Admin) | — | ✅ | ✅ | ✅ |
| **서버 서비스 탭** (시작/중단/로그) | — | — | — | ✅ |
| **REST API** POST /api/ask | — | — | — | ✅ |
| **Web Client** 채팅 UI | — | — | — | ✅ |
| **출처 클릭 → 팝업 PDF 이미지** (Web) | — | — | — | ✅ |
| **동시 요청 제한** (큐/거절) | — | — | — | ✅ |

---

## 참고 문서

| 문서 | 내용 |
|------|------|
| `readme.md` | 실행 방법, V4/V3 현황, 디렉터리 구조 |
| `docs/goal.md` | V1 설계 (파이프라인, 데이터 스펙, UI) |
| `docs/goal_v2.md` | V2 설계 (UX 재설계, DB 관리) |
| `docs/goal_v3.md` | V3 설계 (Canonical/Raw 아키텍처) |
| `docs/goal_v4.md` | V4 설계 (REST API, Web Client) |
| `docs/phase.md` | V1 Phase 1~19 상세 |
| `docs/phase_v2.md` | V2 Phase 1~10 상세 |
| `docs/phase_v3.md` | V3 Phase 1~7 상세 |
| `docs/phase_v4.md` | V4 Phase 1~7 상세 |
| `docs/v4_integrated.md` | V4 goal+phase 통합 요약 |
| `docs/setup.md` | PyTorch, bge-m3, FAISS 설정 |
| `docs/ollama_setup.md` | Ollama 설치·모델 |
| `docs/phase17_llm_rag.md` | RAG 구현 상세, 출처 규칙 |
| `docs/test_scenarios.md` | RAG 테스트 시나리오 |
