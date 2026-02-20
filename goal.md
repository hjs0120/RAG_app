# 설계문서 — PDF 규격문서 텍스트 추출 및 RAG 파이프라인

---

## 0. 범위 (Scope)

| 항목 | 내용 |
|------|------|
| **입력** | 규격 PDF (예: 이동식 해양구조물 규칙_2024) |
| **출력** | JSONL(라인 단위) → Chunk JSONL → FAISS 인덱스 → RAG 답변 |
| **처리 범위** | 차례 이후 본문부터 추출 |
| **UI** | PySide6 기반 탭 + 그룹박스 |

**처리 범위 세부**

- 차례 표시: `차\s*례`로 식별
- 본문 시작: `제 1 장 총칙` / `제 1 절 일반사항` / `101. 적용` 등

---

## 1. 목표 출력 데이터 스펙

### 1.1 라인 단위 레코드 (JSONL)

| 필드 | 설명 |
|------|------|
| `doc_id` | 문서 식별자 |
| `page` | 페이지 번호 |
| `line_no` | 라인 번호 |
| `path` | chapter / section / article / paragraph |
| `text` | 라인 텍스트 |
| `bbox` | [x0, y0, x1, y1] (PDF 좌표) |
| `source` | 원본 파일 정보 |

### 1.2 Path 매핑 (장/절/조항)

| Path | 예시 |
|------|------|
| part | null (또는 규칙 본문) |
| chapter | 제 1 장 총칙 |
| section | 제 1 절 일반사항 |
| article | 101 (조문 번호) |
| paragraph | 1, (1), (가) 등 항/호/목 |

### 1.3 JSONL 출력 예시

```json
{
  "doc_id": "MOUS_RULE_2024",
  "page": 7,
  "line_no": 14,
  "path": {
    "part": null,
    "chapter": "제 1 장 총칙",
    "section": "제 1 절 일반사항",
    "article": "101",
    "paragraph": "1"
  },
  "text": "1. 이 규칙은 ... 적용한다.",
  "bbox": [x0, y0, x1, y1],
  "source": {"file": "이동식 해양구조물 규칙_2024.pdf"}
}
```

### 1.4 Chunk JSONL (RAG용)

| 필드 | 설명 |
|------|------|
| `chunk_id` | Chunk 식별자 |
| `text` | Chunk 텍스트 (Merge/Split 후) |
| `meta` | doc_id, article, section, pages, chunk_index 등 |

- **Merge**: article + section + paragraph 기준 그룹핑
- **Split**: target 600자 / max 1000자
- 1줄 = 1chunk

---

## 2. 전체 처리 파이프라인

### 2.1 단계 요약

```
PDF Import
    → 페이지별 텍스트 추출 (PyMuPDF 레이아웃)
    → 라인 재구성 (line rebuild)
    → 차례 구간 스킵
    → 정규화 (공백, 헤더/푸터)
    → Path 태깅 (Chapter/Section/Article/Paragraph)
    → 표/그림/수식 필터 (표제목·그림제목만, 수식 제외)
    → JSONL/CSV Export
    → Chunk 생성 (Merge/Split)
    → Chunk JSONL
    → bge-m3 임베딩 (normalize)
    → FAISS IndexFlatIP 저장
    → RAG: 질문 임베딩 → 검색 → Chunk 재조합 → Ollama 답변
```

### 2.2 FAISS 저장 구조

| 파일 | 설명 |
|------|------|
| `rules.index` | FAISS 벡터 인덱스 |
| `rules_meta.jsonl` | 인덱스 i번째 벡터 ↔ chunk 메타 매핑 |

- FAISS는 "0, 1, 2, …" 순서만 유지 → `meta_list[i]`로 chunk 정보 조회

---

## 3. 핵심 알고리즘

### 3.1 차례 이후 시작점 탐지

- `차\s*례` 매칭 → toc_mode = True
- toc_mode 중 `^제\s*\d+\s*장` 매칭 → toc_mode = False, 해당 시점부터 export

### 3.2 라인 추출 (PyMuPDF)

- **레이아웃 좌표 기반**: 같은 y 좌표끼리 묶어 라인 생성
- 산출: `(text, bbox, page, line_no)`

### 3.3 Path 태깅 (상태 머신)

- chapter → section → article → paragraph 순으로 갱신
- 하위 레벨 진입 시 상위 유지, 동급 이하 초기화

**정규식 패턴**

- chapter: `^제\s*(\d+)\s*장`
- section: `^제\s*(\d+)\s*절`
- article: `^(\d+)\.\s*`
- paragraph: `^(\d+)\.\s+` (항), `^\((\d+)\)\s+` (호), `^\((가|나|다|…)\)\s+` (목)

### 3.4 임베딩 및 FAISS (RAG)

| 단계 | 내용 |
|------|------|
| 임베딩 | chunk.jsonl → bge-m3 batch encode → **normalize** (IndexFlatIP = cosine) |
| 저장 | FAISS IndexFlatIP, meta_list 순서 보장 |
| 검색 | query 임베딩 → normalize → faiss.search(top_k) → meta_list로 변환 |

### 3.5 RAG 답변

- 검색 top-k → Chunk 조문/섹션 단위 재조합
- Ollama(qwen2.5:7b-instruct 등)로 근거 기반 답변 생성
- 출처 강제, 근거 부족 시 거절

---

## 4. 권장 파라미터

| 항목 | 값 |
|------|-----|
| embedding model | bge-m3 |
| index type | IndexFlatIP (normalize 시 cosine 유사도) |
| top_k | 5~8 (검색), 10 (UI 기본) |
| chunk target | 600자 / max 1000자 |
| LLM | qwen2.5:7b-instruct, qwen2.5:14b-instruct, llama3.1:8b-instruct |
| temperature | 0.2~0.4 |

---

## 5. UI 설계 (탭)

### 탭 1: PDF Import

- 파일 선택(다중), doc_id, 출력 디렉터리
- "차례 이후부터" 체크박스 (기본 ON)
- 감지된 `차 례` / 첫 `제 n 장` 위치 미리보기

### 탭 2: Extract

- 엔진: PyMuPDF
- 라인화 옵션 (y-merge, 공백 정규화, 하이픈 병합)
- 표제목만/그림제목만 추출, 수식 제외 체크
- 실행 버튼, 진행률, 결과 요약

### 탭 3: Parse (Path 태깅)

- 규칙 세트 선택, 샘플 테스트
- Path 미리보기 (chapter/section/article/paragraph)

### 탭 4: Export

- JSONL/CSV, 필드 선택
- DB Import 친화 검증

### 탭 5: 검수

- PDF·JSONL 로드, 좌우 분할 뷰
- 라인 네비게이션, 수정·저장, bbox 표시

### 탭 6: Chunk 생성

- Merge key (doc_id, article, section, paragraph)
- Split 규칙 (600/1000)
- Chunk JSONL 생성 및 검증

### 탭 7: 임베딩

- Chunk JSONL 선택, 출력 경로
- bge-m3 임베딩 → FAISS 저장
- 검색 테스트 (top-k)

### 탭 8: RAG

- 질문 입력, [검색], [답변 생성]
- Top-k 결과 리스트, 답변·출처 출력
- 비동기 처리

---

## 6. 내부 모듈 구조

```
src/
  app.py
  ui/
    main_window.py
    tabs/
      tab_import.py
      tab_extract.py
      tab_parse.py
      tab_export.py
      tab_review.py
      tab_chunk.py
      tab_embedding.py
      tab_rag.py
  core/
    extract_pymupdf.py
    line_rebuild.py
    normalize.py
    parse_state_machine.py
    rules.py
    table_figure_filter.py
    equation_filter.py
    export_jsonl.py
    export_csv.py
    chunk_builder.py
    chunk_validate.py
    embedding_bge.py
    faiss_index.py
  llm/
    ollama_client.py
  rag/
    rag_pipeline.py
    chunk_assembler.py
    prompt_templates.py
    rag_config.py
```

---

## 7. 품질/검증

- **샘플링 미리보기**: 선택 페이지 라인별 Path 표시
- **목록 스킵 검증**: 차례 이후 첫 "제 n 장"에서 시작 여부
- **DB Import 검증**: JSON 파싱, 필수 필드 누락 여부
- **Chunk 검증**: 길이, chunk_index, 누락 여부
- **RAG 테스트 시나리오**: docs/test_scenarios.md

---

## 8. 참고 문서

| 문서 | 내용 |
|------|------|
| `phase.md` | Phase 1~19 단계별 개발 계획·진도 |
| `docs/setup.md` | PyTorch CUDA, bge-m3, FAISS 설정 |
| `docs/ollama_setup.md` | Ollama 설치·모델·API |
| `docs/phase17_llm_rag.md` | RAG 구현 상세, Chunk 재조합, 출처 규칙 |
