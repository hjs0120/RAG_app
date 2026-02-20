# Phase 17·18 RAG 파이프라인 구현 요약

Phase 17·18에서 구현한 RAG 파이프라인과 UI의 구조, 규칙, 사용법을 정리합니다.

---

## 1. 아키텍처 개요

```
질문 입력
    ↓
bge-m3 쿼리 임베딩
    ↓
FAISS 검색 (top-k)
    ↓
Chunk 재조합 (조문/섹션 단위)
    ↓
Ollama LLM 답변 생성 (/api/chat)
    ↓
답변 + 출처 출력
```

---

## 2. 주요 모듈

| 모듈 | 역할 |
|------|------|
| `src/llm/ollama_client.py` | Ollama API 클라이언트 (`generate`, `generate_chat`, `health_check`, `load_model`) |
| `src/rag/rag_pipeline.py` | RAG 오케스트레이션 (`run_query` → `RAGResult`) |
| `src/rag/chunk_assembler.py` | FAISS 검색 결과 → 조문/섹션 단위 재조합 |
| `src/rag/prompt_templates.py` | RAG system/user 프롬프트, 출처 포맷 |
| `src/rag/rag_config.py` | top_k, threshold, Ollama 기본값 |
| `src/ui/tabs/tab_rag.py` | RAG 탭 UI — 질문/검색/답변, 비동기 처리 |

---

## 3. Chunk 재조합 규칙

### 그룹핑 키 우선순위

1. **article + section**: `doc_id|article|section` — 같은 조문 내 절 구분 (예: 101.적용 vs 101.하중)
2. **article만**: `doc_id|article|` — 절 정보 없을 때
3. **section만**: `doc_id|_|section`
4. **fallback**: `doc_id|page` — 페이지 단위

### 정책 파라미터

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| FAISS top_k | 10 | 넉넉히 검색 |
| 상위 그룹 수 | 2 | 점수 합산 상위 1~2개 그룹 선택 |
| 그룹당 chunk 수 | 4 | 그룹당 최대 3~6개 chunk |
| 컨텍스트 제한 | 3200자 | 2500~3500 tokens ≈ 3200자 |

### 처리 흐름

1. FAISS top-k 검색 결과를 그룹 키로 묶음
2. 그룹별 점수 합산 (chunk 점수 합)
3. 상위 1~2개 그룹 선택
4. 선택된 그룹에서 점수 높은 chunk 순으로 수집
5. `doc_id, page, chunk_index` 순으로 정렬 후 컨텍스트 조립

---

## 4. 출처 규칙

### 출처 포맷

```
[1] doc_id=MOUS_RULE_2024, page=42, section=제10조 검사 주기, chunk_id=...
[2] doc_id=MOUS_RULE_2024, page=43, section=제11조 ..., chunk_id=...
```

### 생성 규칙

- chunk meta에서 `doc_id`, `page`, `section`, `chunk_id` 추출
- LLM 프롬프트에 출처 목록을 그대로 제공
- 답변 말미에 `[출처]` 섹션 필수, 형식 변경 금지

---

## 5. 근거 부족 시 거절

- FAISS 검색 결과가 **0건**이면 LLM 호출 없이 `"관련 근거를 찾지 못했습니다."` 반환
- 재조합된 컨텍스트가 **비어 있으면** 동일 메시지 반환
- `rag_config.SCORE_THRESHOLD`는 현재 short-circuit에 미사용 (검색 결과 있으면 LLM에 위임)

---

## 6. UI 구성 (RAG 탭)

| 요소 | 설명 |
|------|------|
| 모델 사전 로드 | bge-m3 + Ollama 모델 미리 로드 |
| 인덱스 디렉터리 | FAISS index/meta 경로 (기본: output/) |
| 질문 입력 | `QPlainTextEdit` |
| top_k SpinBox | 1~30, 기본 10 |
| [검색] | FAISS만 실행, Top-k 결과 표시 |
| [답변 생성] | 검색 → 재조합 → Ollama 답변 |
| 검색 결과 리스트 | score, doc_id/page/section/chunk_id, text 미리보기 |
| 답변 영역 | 읽기 전용 |
| 출처 영역 | 답변 아래 별도 표시 |

### 비동기 처리

- `SearchWorker`, `RAGWorker` → `QThread`로 실행
- 상태: "검색중…", "답변 생성중…"

---

## 7. 문제 해결 FAQ

### Q. "Ollama가 실행되지 않았습니다" 오류

**A.** Ollama를 설치·실행한 뒤, `ollama pull qwen2.5:7b-instruct`로 모델을 받으세요. `docs/ollama_setup.md` 참고.

### Q. 검색 결과가 나오는데 답변이 "관련 근거를 찾지 못했습니다"

**A.** Chunk 재조합 결과가 비어 있을 수 있습니다. 검색 결과의 `article`, `section` 메타가 올바른지, `chunk_assembler` 그룹핑 로직을 확인하세요.

### Q. top_k를 늘렸는데 답변 품질이 변하지 않음

**A.** 재조합 단계에서 상위 1~2개 그룹만 사용하므로, top_k를 크게 해도 최종 컨텍스트는 제한됩니다. 관련 chunk가 여러 그룹에 흩어져 있으면 품질이 떨어질 수 있습니다.

### Q. 답변에 출처가 안 붙음

**A.** 프롬프트(`RAG_SYSTEM`)에서 출처 필수 규칙이 있으나, 모델이 무시할 수 있습니다. `temperature`를 낮추거나, 더 지시 따르는 모델을 시도해 보세요.

### Q. 첫 질문이 느림

**A.** bge-m3와 Ollama 모델이 처음 로드되기 때문입니다. RAG 탭의 **"모델 사전 로드"**를 눌러 미리 로드하면 이후 질문이 빨라집니다.

### Q. 인덱스 로드 실패

**A.** 임베딩 탭에서 Chunk JSONL로 FAISS 인덱스를 먼저 생성하세요. `rules.index`, `rules_meta.jsonl`이 같은 폴더에 있어야 합니다.

---

## 8. 설정값 (rag_config.py)

```python
FAISS_TOP_K = 10
SCORE_THRESHOLD = 0.3
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_TEMPERATURE = 0.3
DEFAULT_OLLAMA_NUM_CTX = 4096
```

---

## 9. Phase 17 완료 체크리스트

- [x] ollama_client.py: generate, generate_chat, health_check, load_model
- [x] chunk_assembler.py: 그룹핑·재조합, 상위 그룹/컨텍스트 제한
- [x] prompt_templates.py: RAG system/user, 출처 필수 규칙
- [x] rag_pipeline.py: run_query, RAGResult, 출처 생성
- [x] 근거 부족 시 거절 (0건/빈 컨텍스트)
- [x] RAG 탭 UI: 질문/검색/답변, Top-k 디버깅, 비동기 처리
- [x] 수동 검증 완료
