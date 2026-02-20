"""RAG 파이프라인 설정 — threshold, top-k 등."""

# FAISS 검색
FAISS_TOP_K = 10

# 근거 부족 시 거절 threshold (FAISS score)
# IndexFlatIP(cosine) 사용 시 0~1 범위, 기준 이하면 LLM 호출 안 함
SCORE_THRESHOLD = 0.3

# Ollama 기본값
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_TEMPERATURE = 0.3
DEFAULT_OLLAMA_NUM_CTX = 4096
