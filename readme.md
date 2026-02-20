# RAG_app — PDF 규격문서 텍스트 추출 및 RAG 파이프라인

PySide6 기반 데스크톱 앱. PDF 규격문서에서 텍스트를 추출하고, Chunk 생성·임베딩·FAISS 검색을 거쳐 **Ollama LLM**과 연동하여 RAG 답변을 생성한다.

---

## V2 개발 현황 (phase_v2.md)

- **목표**: 프로토타입(V1) → 실사용 RAG 워크벤치(V2) 전환 (UX 재설계 + DB 관리 확장)
- **기반 문서**: `goal_v2.md`

### V2 개발 예정

| Phase | 내용 |
|-------|------|
| 8 | 증분 임베딩 (기존 인덱스에 Chunk 추가) |
| 9 | Chunk 단위 삭제 기능 |
| 10 | 출처 가독성 개선 (페이지/장/절/항 표시, content_page 매핑) |
| 11 | V2 통합 검증 및 문서화 |

### V2 개발 완료

| Phase | 내용 |
|-------|------|
| 1 | 프로젝트 구조 리팩토링 (core/rag/db_manager/ui 분리) |
| 2 | DB Manager 모듈 (load/save/append/remove/rebuild) |
| 3 | 탭 구조 전면 개편 — 사용 탭 / DB 생성 탭 2개 |
| 4 | 사용 탭 — 모델 관리, 질문 & 검색 |
| 5 | 사용 탭 — 검색 결과, 조합 컨텍스트, 답변 영역 |
| 6 | 사용 탭 — 출처 영역, PDF 뷰어 연동 |
| 7 | DB 생성 탭 — 파이프라인 통합 (Import→Extract→Parse→검수→Chunk→임베딩), 본문 시작 페이지 저장(docs_meta), 장/절 제목 추출 개선, 검수 탭 content_page 표시 |

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| PDF Import | PDF 선택, doc_id, 차례 이후 추출 옵션 |
| Extract | PyMuPDF 라인 추출, 표/그림/수식 제외 |
| Parse | Path 태깅 (chapter/section/article/paragraph) |
| Export | JSONL/CSV 내보내기 |
| 검수 | PDF·JSONL 좌우 분할 뷰, 라인 네비게이션, 수정·저장, bbox 표시, page(문서)/content_page 표시 |
| Chunk 생성 | RAG용 Chunk JSONL (Merge/Split 규칙) |
| 임베딩 | bge-m3 임베딩, FAISS IndexFlatIP 저장 |
| **RAG** | 질문 입력 → FAISS 검색 → Chunk 재조합 → Ollama 답변 생성 (출처 포함) |

---

## 실행

```bash
pip install -r requirements.txt
python src/app.py
```

**RAG 탭 사용 전**

- DB 생성 탭 또는 임베딩 탭에서 Chunk JSONL로 FAISS 인덱스 생성 (`rules.index`, `rules_meta.jsonl`)
- [Ollama](https://ollama.com) 설치 및 실행, 모델 다운로드: `ollama pull qwen2.5:7b-instruct`

---

## 문서

| 문서 | 내용 |
|------|------|
| `phase_v2.md` | V2 Phase 1~11 단계별 개발 계획 및 진도 |
| `goal_v2.md` | V2 설계 목표 |
| `docs/setup.md` | PyTorch CUDA, bge-m3 모델 다운로드, FAISS 설정 |
| `docs/ollama_setup.md` | Windows Ollama 설치, 모델 다운로드, API 예시, 문제 해결 |
| `docs/phase17_llm_rag.md` | RAG 구현 요약, Chunk 재조합/출처 규칙, FAQ |
| `docs/test_scenarios.md` | RAG 테스트 시나리오 5개 (검증 완료) |
| `phase.md` | V1 Phase 1~19 단계별 개발 계획 및 진도 |

---

## V1 개발 완료 내용 (Phase 1 ~ 19)

### Phase 19: RAG 문서화 및 테스트 ✅
- `docs/ollama_setup.md`, `docs/phase17_llm_rag.md`, `docs/test_scenarios.md`
- 테스트 시나리오 5개 검증 완료, Phase 17 완료 체크리스트 반영

### Phase 18: RAG 탭 UI ✅
- 질문 입력, [검색], [답변 생성] 버튼
- Top-k 검색 결과 리스트, 답변·출처 출력
- QThread 비동기 처리, 상태 표시

### Phase 17: RAG 파이프라인 ✅
- Ollama 연동 (`src/llm/ollama_client.py`)
- Chunk 조문/섹션 단위 재조합 (`src/rag/chunk_assembler.py`)
- 프롬프트·출처 강제 (`src/rag/prompt_templates.py`)
- 근거 부족 시 거절, LLM: qwen2.5:7b-instruct 등

### Phase 16: Chunk 품질 개선
- path.section 추출, Merge key에 section 포함
- paragraph "0" 라인별 분리, min_chunk_len

### Phase 15: bge-m3 로컬·GPU 전환
- `models/bge-m3/` 로컬 로딩, `scripts/download_bge_m3.py`

### Phase 14: 임베딩 탭
- Chunk JSONL → bge-m3 → FAISS IndexFlatIP

### Phase 13 ~ 1
- Chunk 생성, 수식 제외, 표/그림 감지, 검수 탭, Export, Parse, Extract, Import, 프로젝트 구조

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024.pdf`
