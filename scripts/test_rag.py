"""RAG 파이프라인 테스트 — Ollama + FAISS 연동 확인."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    from src.core.faiss_index import load_index
    from src.rag.rag_pipeline import RAGPipeline
    from src.llm.ollama_client import OllamaClient

    idx_path = PROJECT_ROOT / "output" / "rules.index"
    meta_path = PROJECT_ROOT / "output" / "rules_meta.jsonl"

    print("=== RAG 파이프라인 테스트 ===\n")
    print(f"인덱스 경로: {idx_path}")
    print(f"메타 경로: {meta_path}\n")

    if not idx_path.exists():
        print("[오류] FAISS 인덱스가 없습니다.")
        print("  → 앱의 '임베딩 탭'에서 Chunk JSONL로 먼저 '임베딩 & FAISS 저장'을 실행하세요.")
        return 1
    if not meta_path.exists():
        print("[오류] 메타 JSONL이 없습니다.")
        return 1

    print("1. Ollama 연결 확인...")
    oc = OllamaClient()
    if not oc.health_check():
        print("   [오류] Ollama가 실행되지 않았습니다.")
        print("   → ollama serve 실행 또는 Ollama 앱을 실행하세요.")
        print("   → ollama pull qwen2.5:7b-instruct 로 모델을 다운로드하세요.")
        return 1
    print("   OK\n")

    print("2. FAISS 인덱스 로드...")
    index, meta_list = load_index(idx_path, meta_path)
    print(f"   OK (총 {len(meta_list)} chunks)\n")

    print("3. RAG 파이프라인 실행...")
    pipeline = RAGPipeline(index, meta_list)
    result = pipeline.run_query("제10조 검사 주기는 어떻게 되나요?")

    print("   --- 질문 ---")
    print(f"   {result.question}\n")
    print("   --- 답변 ---")
    print(result.answer)
    print("\n   --- 출처 ---")
    for s in result.sources:
        print(f"   {s}")
    print("\n=== 테스트 완료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
