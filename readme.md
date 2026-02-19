# RAG_app — PDF 규격문서 텍스트 추출 및 RAG 파이프라인

PySide6 기반 데스크톱 앱. PDF 규격문서에서 텍스트를 추출하고, Chunk 생성·임베딩·FAISS 검색을 거쳐 RAG 답변을 생성한다.

---

## 추후 개발 내역 (최신 순)

### Phase 19: RAG 문서화 및 테스트
- `docs/ollama_setup.md` — Windows Ollama 설치, 모델 다운로드, API 예시
- `docs/phase17_llm_rag.md` — Phase 17 구현 요약, chunk 재조합/출처 규칙, UI 구성, FAQ
- 테스트 시나리오 5개: 검색 충분/부족, section 혼합, 출처 확인, Ollama 미실행 시 처리
- Phase 17 완료 체크리스트 docs 반영, 커밋 단위 정리

### Phase 18: RAG 탭 UI
- 질문 입력창, [검색], [답변 생성] 버튼
- Top-k 검색 결과 리스트 (score, doc_id/page/section/chunk_id, chunk preview)
- 답변·출처 출력 영역
- QThread/QRunnable로 비동기 처리, 상태 표시 (검색중, 답변 생성중)

### Phase 17: RAG 파이프라인
- Ollama 연동 (`src/llm/ollama_client.py`)
- Chunk 조문/섹션 단위 재조합 (`src/rag/chunk_assembler.py`)
- 프롬프트 템플릿·출처 강제 (`src/rag/prompt_templates.py`)
- RAG 파이프라인 (`src/rag/rag_pipeline.py`)
- 근거 부족 시 거절(threshold)
- LLM 추천: qwen2.5:7b-instruct, qwen2.5:14b-instruct, llama3.1:8b-instruct

---

## 개발완료 내용 (Phase 1 ~ 16)

### Phase 16: Chunk 품질 개선
- path.section 추출 및 Merge key에 section 포함
- paragraph "0" 그룹 라인별 분리, min_chunk_len 처리
- 101.적용 / 101.하중 등 같은 article 내 절 구분

### Phase 15: bge-m3 로컬·GPU 전환
- `models/bge-m3/` 로컬 로딩, HuggingFace 요청 제거
- `scripts/download_bge_m3.py` 모델 다운로드
- device="cuda" 지정, HF_TOKEN 경고 제거

### Phase 14: 임베딩 탭
- Chunk JSONL → bge-m3 임베딩 → FAISS IndexFlatIP 저장
- `rules.index`, `rules_meta.jsonl` 생성
- 검색 테스트 기능 (top-k 쿼리)

### Phase 13: Chunk 생성 탭
- Merge key: doc_id, article, section, paragraph
- Split: target 600자 / max 1000자
- Chunk JSONL 생성 및 검증

### Phase 12: 수식 제외, paragraph 페이지 단위 구분
- 수식(들여쓰기·변수 정의) 제외 필터
- (path, page) 단위 paragraph 구분, bbox 페이지별 union

### Phase 11: 표·그림 감지
- 표제목/그림제목만 추출, 표·그림 본문 제외
- 패턴 기반 구간 감지

### Phase 10: 검수 탭 — bbox 표시
- PDF 뷰어 위 현재 라인 bbox 빨간색 사각형 표시

### Phase 9: 검수 탭 — 수정 및 저장
- 필드 편집, 라인 넘김 시 수정 유지
- 저장/다른 이름으로 저장

### Phase 8: 검수 탭 — 라인 네비게이션
- 이전/다음 버튼, N/전체 진행도
- PDF 페이지 연동

### Phase 7: 검수 탭 — 좌우 분할 뷰
- PDF + JSONL 로드, 좌측 PDF/우측 JSON 필드 표시

### Phase 6: JSONL/CSV Export
- goal.md 형식 JSONL·CSV 출력
- DB Import 친화 검증

### Phase 5: Path 태깅(상태 머신)
- chapter/section/article/paragraph 규칙
- parse_state_machine path 갱신

### Phase 4: 차례 스킵 및 본문 시작점
- "차 례" 이후 첫 "제 n 장"부터 추출
- TOC 탐지

### Phase 3: PyMuPDF 라인 추출
- 페이지별 라인 추출 (text, bbox, page, line_no)
- line_rebuild, normalize

### Phase 2: PDF Import 탭
- 파일 선택, doc_id, 출력 경로, 차례 이후 체크박스

### Phase 1: 프로젝트 구조
- PySide6, PyMuPDF 의존성
- 4개 탭(Import, Extract, Parse, Export) 스켈레톤

---

## 테스트 데이터

- **경로**: `data/이동식 해양구조물 규칙_2024.pdf`

## 실행

```bash
pip install -r requirements.txt
python src/app.py
```

## 설치 관련련

- **경로**: `docs/setup.md`
- **경로**: `docs/ollama_setup.md` (작성예정정)